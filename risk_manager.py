# FILE: risk_manager.py
# =============================================================================

import configs as config
from logger import log
from trade_manager import TradeManager
from typing import List, Any
import MetaTrader5 as mt5

def manage_trailing_stop_loss(tm: TradeManager, open_positions: List[Any]):
    """Manages a dynamic trailing stop-loss for all managed positions."""
    if not config.USE_TRAILING_STOP or not open_positions:
        return

    symbol_info = tm.get_symbol_info(config.TRADING_PAIR)
    if not symbol_info:
        log.error("Risk Manager: Could not get symbol info for trailing stop.")
        return

    point = symbol_info.point
    
    for pos in open_positions:
        current_sl = pos.sl
        entry_price = pos.price_open
        trade_type = pos.type

        # Use the most up-to-date market price for calculations
        current_price_ask = tm.get_current_price('SELL')
        current_price_bid = tm.get_current_price('BUY')
        if not current_price_ask or not current_price_bid:
            log.warning("Risk Manager: Could not get current price, skipping trailing stop.")
            continue

        # Determine the target TP in pips to calculate profit percentage
        if pos.tp > 0:
            if trade_type == mt5.ORDER_TYPE_BUY:
                take_profit_pips = (pos.tp - entry_price) / (config.POINTS_PER_PIP * point)
            else: # SELL
                take_profit_pips = (entry_price - pos.tp) / (config.POINTS_PER_PIP * point)
        else:
            take_profit_pips = config.TAKE_PROFIT_PIPS
        
        if take_profit_pips <= 0: continue

        # Calculate current unrealized profit in pips
        if trade_type == mt5.ORDER_TYPE_BUY:
            potential_profit_pips = (current_price_bid - entry_price) / (config.POINTS_PER_PIP * point)
        else: # SELL
            potential_profit_pips = (entry_price - current_price_ask) / (config.POINTS_PER_PIP * point)
        
        profit_percentage = (potential_profit_pips / take_profit_pips) * 100

        # Activate trailing stop if profit reaches the activation percentage
        if profit_percentage >= config.TRAILING_ACTIVATION_PERCENT:
            trailing_distance = config.TRAILING_STOP_PIPS * config.POINTS_PER_PIP * point
            
            if trade_type == mt5.ORDER_TYPE_BUY:
                new_sl = current_price_bid - trailing_distance
                if new_sl > current_sl:
                    log.info(f"TRAILING SL (BUY) #{pos.ticket}: Adjusting SL from {current_sl:.5f} to {new_sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)
            else: # SELL
                new_sl = current_price_ask + trailing_distance
                if new_sl < current_sl or current_sl == 0:
                    log.info(f"TRAILING SL (SELL) #{pos.ticket}: Adjusting SL from {current_sl:.5f} to {new_sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)