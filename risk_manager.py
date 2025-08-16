# FILE: risk_manager.py
# =============================================================================
#
#   RISK MANAGEMENT ENGINE (GANN TP TRAILING)
#
# =============================================================================

from typing import Dict, Any, List

# --- Core Application Imports ---
from logger import log
import configs as config
from trade_manager import TradeManager
import indicators
import state_manager as sm

def manage_dynamic_exits(tm: TradeManager, open_positions: List[Any]):
    """
    Main function to manage trailing TP for all open positions based on Gann levels.
    This is called on every new candle.
    """
    if not config.USE_DYNAMIC_EXITS or not open_positions:
        return

    log.info(f"Risk Manager: Checking {len(open_positions)} position(s) for TP updates...")
    
    df_daily = tm.fetch_ohlcv('1d', limit=5)
    if df_daily is None or df_daily.empty or len(df_daily) < 2:
        log.warning("Risk Manager: Could not fetch daily data for Gann TP trailing. Skipping.")
        return

    gann_levels = indicators.calculate_gann_levels(df_daily, config.GANN_CALCULATION_BASIS)
    if not gann_levels:
        log.warning("Risk Manager: Gann levels could not be calculated. Skipping TP trailing.")
        return
    
    for pos in open_positions:
        _trail_take_profit_gann(tm, pos, gann_levels)

def _trail_take_profit_gann(tm: TradeManager, pos: Any, gann: Dict):
    """
    Trails the Take Profit to the next available Gann Angle target once the
    previous target has been surpassed by the current price.
    """
    pos_type_str = 'buy_side' if pos.type == 0 else 'sell_side'
    
    # Get all Gann targets and sort them (ascending for BUY, descending for SELL)
    targets = sorted([v for k, v in gann.get(pos_type_str, {}).items() if 'target' in k])
    if pos.type == 1: # If it's a SELL trade, reverse the sort order
        targets.reverse()

    if not targets:
        return

    # Get the current market price to check against the trigger
    # For a BUY position (type 0), we check the bid price. For SELL, the ask price.
    current_price = tm.get_current_price('sell' if pos.type == 0 else 'buy')
    if current_price == 0.0:
        log.warning(f"Risk Manager: Could not get current price for {pos.symbol}. Skipping trail for #{pos.ticket}.")
        return

    # Find the next logical TP target that is more profitable than the current one
    next_tp = None
    for target in targets:
        is_more_profitable = (pos.type == 0 and target > pos.tp) or \
                             (pos.type == 1 and target < pos.tp)
        if is_more_profitable:
            next_tp = target
            break

    if next_tp is None:
        return # No more profitable targets available

    try:
        # Determine the price level that triggers the TP update.
        # This is the Gann level *before* our 'next_tp'.
        next_tp_index = targets.index(next_tp)
        trigger_target = gann[pos_type_str].get('entry') if next_tp_index == 0 else targets[next_tp_index - 1]
    except (ValueError, KeyError):
        log.warning(f"Risk Manager: Could not determine trigger target for ticket {pos.ticket}. Skipping trail.")
        return

    if trigger_target is None:
        return

    # Check if the current price has crossed the trigger level
    price_crossed_trigger = (pos.type == 0 and current_price > trigger_target) or \
                            (pos.type == 1 and current_price < trigger_target)

    if price_crossed_trigger:
        log.info(f"GANN TRAIL TRIGGER: Price crossed {trigger_target:.5f}. Moving TP for ticket {pos.ticket} to next level: {next_tp:.5f}")
        
        # Modify the TP on the broker side
        success = tm.modify_sl_tp(pos.ticket, new_sl=pos.sl, new_tp=next_tp)

        # If successful, update the bot's internal state to remember the new TP
        if success:
            trade_state = sm.get_trade_state(pos.ticket)
            if trade_state:
                trade_state['tp_level'] = next_tp
                sm.save_trade_state(pos.ticket, trade_state)
