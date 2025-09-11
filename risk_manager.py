# FILE: risk_manager.py (Corrected & Verified)
# =============================================================================

import configs as config
from logger import log
from trade_manager import TradeManager
from typing import List, Any
import MetaTrader5 as mt5

def manage_trailing_stop_loss(tm: TradeManager, open_positions: List[Any]):
    """
    Manages a dynamic trailing stop-loss for all managed positions.
    --- REWRITTEN FOR ACCURACY ---
    """
    if not config.USE_TRAILING_STOP or not open_positions:
        return

    symbol_info = tm.get_symbol_info(config.TRADING_PAIR)
    if not symbol_info:
        log.error("Risk Manager: Could not get symbol info for trailing stop.")
        return

    # Fetch the latest market prices once to ensure consistency for this cycle
    tick = mt5.symbol_info_tick(config.TRADING_PAIR)
    if not tick:
        log.warning("Risk Manager: Could not get current tick, skipping trailing stop.")
        return
        
    current_price_ask = tick.ask
    current_price_bid = tick.bid
    point = symbol_info.point
    
    for pos in open_positions:
        entry_price = pos.price_open
        current_sl = pos.sl
        trade_type = pos.type

        # --- Determine the total TP distance in pips ---
        if pos.tp > 0:
            if trade_type == mt5.ORDER_TYPE_BUY:
                total_tp_pips = (pos.tp - entry_price) / (config.POINTS_PER_PIP * point)
            else: # SELL
                total_tp_pips = (entry_price - pos.tp) / (config.POINTS_PER_PIP * point)
        else:
            # Fallback to config if TP is not set on the trade for some reason
            total_tp_pips = config.TAKE_PROFIT_PIPS
        
        if total_tp_pips <= 0: continue

        # --- CORRECTLY calculate current unrealized profit in pips ---
        if trade_type == mt5.ORDER_TYPE_BUY:
            # Profit for a BUY is based on the BID price (the price you can sell at)
            profit_pips = (current_price_bid - entry_price) / (config.POINTS_PER_PIP * point)
        else: # SELL
            # Profit for a SELL is based on the ASK price (the price you can buy back at)
            profit_pips = (entry_price - current_price_ask) / (config.POINTS_PER_PIP * point)
        
        profit_percentage = (profit_pips / total_tp_pips) * 100

        # Activate trailing stop if profit reaches the activation percentage
        if profit_percentage >= config.TRAILING_ACTIVATION_PERCENT:
            trailing_distance_points = config.TRAILING_STOP_PIPS * config.POINTS_PER_PIP * point
            
            if trade_type == mt5.ORDER_TYPE_BUY:
                # The new SL must be higher than the old one to be valid
                new_sl = current_price_bid - trailing_distance_points
                if new_sl > current_sl:
                    log.info(f"TRAILING SL (BUY) #{pos.ticket}: Adjusting SL from {current_sl:.5f} to {new_sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)
            else: # SELL
                # The new SL must be lower than the old one to be valid
                new_sl = current_price_ask + trailing_distance_points
                if new_sl < current_sl or current_sl == 0:
                    log.info(f"TRAILING SL (SELL) #{pos.ticket}: Adjusting SL from {current_sl:.5f} to {new_sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)