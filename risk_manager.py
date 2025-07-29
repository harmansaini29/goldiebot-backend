# =============================================================================
#
#   RISK MANAGEMENT ENGINE (DYNAMIC EXITS)
#
# =============================================================================

import pandas as pd
from ta.volatility import AverageTrueRange
from typing import Dict, Any, Optional, List

# --- Core Application Imports ---
from logger import log
import configs as config
from trade_manager import TradeManager
import indicators

# =============================================================================
# SECTION 1: INITIAL SL/TP CALCULATION
# =============================================================================

def calculate_atr_sl_tp(df: pd.DataFrame, entry_price: float, side: str) -> Optional[Dict[str, Any]]:
    """
    Calculates an initial Stop Loss and Take Profit based on ATR.
    This is used for placing the initial order only.
    """
    try:
        atr_indicator = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr_indicator.average_true_range()
        latest_atr = df['atr'].iloc[-1]

        if pd.isna(latest_atr): return None

        atr_percent = (latest_atr / entry_price) * 100
        if atr_percent < 0.1: zone = 'low'
        elif 0.1 <= atr_percent < 0.25: zone = 'mid'
        else: zone = 'high'

        multipliers = config.ATR_MULTIPLIERS[zone]
        sl_multiplier = multipliers['sl']
        tp_multiplier = multipliers['tp']

        sl_distance = latest_atr * sl_multiplier
        tp_distance = latest_atr * tp_multiplier

        if side == 'buy':
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
        
        return { "sl": stop_loss, "tp": take_profit, "zone": zone, "atr_value": latest_atr }
    except Exception as e:
        log.error(f"Error in initial SL/TP calculation: {e}", exc_info=True)
        return None

# =============================================================================
# SECTION 2: DYNAMIC EXIT MANAGEMENT
# =============================================================================

def manage_dynamic_exits(tm: TradeManager, open_positions: List[Any]):
    """
    Manages Trailing SL and TP for open positions using Gaussian Bands and Gann Angles.
    """
    if not config.USE_DYNAMIC_EXITS or not open_positions:
        return

    # 1. Fetch data and calculate indicators needed for exits
    df_intraday = tm.fetch_ohlcv(config.TIMEFRAME, limit=200)
    df_daily = tm.fetch_ohlcv('1d', limit=5)
    
    if df_intraday is None or df_daily is None:
        log.warning("Dynamic Exits: Could not fetch data.")
        return
        
    df_intraday = indicators.calculate_gaussian_bands(df_intraday, length=config.GAUSSIAN_BANDS_LENGTH, distance=config.GAUSSIAN_BANDS_DISTANCE)
    gann_levels = indicators.calculate_gann_levels(df_daily, config.GANN_CALCULATION_BASIS)
    latest_bands = df_intraday.iloc[-1]

    for pos in open_positions:
        _trail_stop_loss_gaussian(tm, pos, latest_bands)
        if gann_levels:
            _trail_take_profit_gann(tm, pos, gann_levels)

def _trail_stop_loss_gaussian(tm: TradeManager, pos: Any, bands: pd.Series):
    """Trailing SL logic based on Gaussian Bands."""
    new_sl = 0.0
    
    # For a BUY trade, the SL trails along the lower Gaussian band
    if pos.type == 0: # BUY
        new_sl = bands['gauss_lower']
        # Golden Rule: Only move the SL up to lock in profit
        if new_sl > pos.sl:
            log.info(f"Trailing SL for BUY {pos.ticket}: New SL {new_sl:.2f} (Gauss Lower) > Old SL {pos.sl:.2f}")
            tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)
            
    # For a SELL trade, the SL trails along the upper Gaussian band
    elif pos.type == 1: # SELL
        new_sl = bands['gauss_upper']
        # Golden Rule: Only move the SL down to lock in profit
        if new_sl < pos.sl:
            log.info(f"Trailing SL for SELL {pos.ticket}: New SL {new_sl:.2f} (Gauss Upper) < Old SL {pos.sl:.2f}")
            tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)

def _trail_take_profit_gann(tm: TradeManager, pos: Any, gann: Dict):
    """Trailing TP logic based on Gann Angle targets."""
    gann_side = 'buy_side' if pos.type == 0 else 'sell_side'
    current_price = tm.get_current_price('buy' if pos.type == 0 else 'sell')

    # Create a sorted list of Gann targets
    targets = sorted([v for k, v in gann[gann_side].items() if 'target' in k])
    if pos.type == 1: # For sells, targets are descending
        targets.reverse()

    # Find the next Gann target
    next_tp = None
    for target in targets:
        if (pos.type == 0 and target > pos.tp) or \
           (pos.type == 1 and target < pos.tp):
            next_tp = target
            break
            
    if next_tp is None:
        return # No further targets

    # If the price is getting close to the current TP, move to the next target
    is_close_to_tp = abs(current_price - pos.tp) < abs(pos.tp - pos.price_open) * 0.2 # Within 20%
    
    if is_close_to_tp:
        log.info(f"Trailing TP for {gann_side.split('_')[0].upper()} {pos.ticket}: Price near TP. Moving to next Gann Target: {next_tp:.2f}")
        tm.modify_sl_tp(pos.ticket, new_sl=pos.sl, new_tp=next_tp)
