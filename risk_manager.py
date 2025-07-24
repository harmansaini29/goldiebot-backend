# =============================================================================
#
#   RISK MANAGEMENT ENGINE
#
# -----------------------------------------------------------------------------
#   This module centralizes all risk management logic, including the
#   initial calculation of Stop Loss and Take Profit, and the ongoing
#   management of trailing stops for open positions.
#
# =============================================================================

import pandas as pd
from ta.volatility import AverageTrueRange
from typing import Dict, Any, Optional

# --- Core Application Imports ---
from logger import log
import configs as config
from trade_manager import TradeManager # Used for type hinting

# =============================================================================
# SECTION 1: INITIAL SL/TP CALCULATION
# =============================================================================

def calculate_atr_sl_tp(df: pd.DataFrame, entry_price: float, side: str) -> Optional[Dict[str, Any]]:
    """
    Calculates Stop Loss and Take Profit levels based on the Average True Range (ATR).

    This function determines the market's volatility zone (low, mid, high)
    and applies the corresponding multipliers from the config file.

    Args:
        df (pd.DataFrame): DataFrame containing OHLC data.
        entry_price (float): The price at which the trade will be entered.
        side (str): The direction of the trade ('buy' or 'sell').

    Returns:
        Dict[str, Any]: A dictionary containing the calculated 'sl', 'tp',
                        and other metadata, or None if calculation fails.
    """
    try:
        # 1. Calculate ATR
        atr_indicator = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr_indicator.average_true_range()
        latest_atr = df['atr'].iloc[-1]

        # 2. Determine Volatility Zone
        atr_percent = (latest_atr / entry_price) * 100
        if atr_percent < 0.1:
            zone = 'low'
        elif 0.1 <= atr_percent < 0.25:
            zone = 'mid'
        else:
            zone = 'high'

        # 3. Get SL/TP Multipliers from Config
        sl_multiplier = config.ATR_SL_MULTIPLIERS[zone]
        tp_multiplier = config.ATR_TP_MULTIPLIERS[zone]

        # 4. Calculate Final SL and TP Levels
        sl_distance = latest_atr * sl_multiplier
        tp_distance = latest_atr * tp_multiplier

        if side == 'buy':
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else: # 'sell'
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
        
        results = {
            "sl": round(stop_loss, 5),
            "tp": round(take_profit, 5),
            "atr_value": round(latest_atr, 5),
            "zone": zone,
            "sl_mult": sl_multiplier,
            "tp_mult": tp_multiplier
        }
        return results

    except Exception as e:
        log.error(f"An error occurred during SL/TP calculation: {e}")
        return None

# =============================================================================
# SECTION 2: TRAILING STOP MANAGEMENT
# =============================================================================

def manage_trailing_stop(tm: TradeManager):
    """
    Manages the trailing stop for all open positions based on ATR.

    This function checks each open position managed by this bot. If a position
    is in profit, it calculates a new Stop Loss based on the current price and
    the configured ATR multiplier, and updates it if the new SL is better.

    Args:
        tm (TradeManager): The active TradeManager instance.
    """
    if not config.USE_TRAILING_STOP:
        return # Exit if trailing stop is disabled in configs

    open_positions = tm.get_open_positions()
    if not open_positions:
        return

    # Fetch data once for all positions to calculate current ATR
    df = tm.fetch_ohlcv(config.TIMEFRAME, limit=100)
    if df is None or df.empty:
        log.warning("Trailing Stop: Could not fetch data to calculate ATR.")
        return
        
    atr_indicator = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
    current_atr = atr_indicator.average_true_range().iloc[-1]
    
    trailing_distance = current_atr * config.TRAILING_STOP_ATR_MULT

    for pos in open_positions:
        # Ensure we only manage trades opened by this bot (if magic number is used)
        # Note: The magic number is set in the TradeManager, so we don't need to check it here
        # unless multiple bots with different magic numbers are running.

        new_sl = 0.0
        
        # For a BUY position, the new SL is the current price minus the distance
        if pos.type == 0: # POSITION_TYPE_BUY
            current_price = tm.get_current_price('buy') # Check against bid price
            if current_price > pos.price_open: # Only trail if in profit
                new_sl = current_price - trailing_distance
                # We only move the stop up
                if new_sl > pos.sl:
                    log.info(f"Trailing BUY position {pos.ticket}: New SL {new_sl:.5f} is better than old SL {pos.sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)

        # For a SELL position, the new SL is the current price plus the distance
        elif pos.type == 1: # POSITION_TYPE_SELL
            current_price = tm.get_current_price('sell') # Check against ask price
            if current_price < pos.price_open: # Only trail if in profit
                new_sl = current_price + trailing_distance
                # We only move the stop down
                if new_sl < pos.sl:
                    log.info(f"Trailing SELL position {pos.ticket}: New SL {new_sl:.5f} is better than old SL {pos.sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)

