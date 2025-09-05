# FILE: risk_manager.py (Corrected Version)

import configs as config
from logger import log
from trade_manager import TradeManager
from typing import List, Any

def manage_trailing_stop_loss(tm: TradeManager, open_positions: List[Any]):
    """
    Manages a dynamic trailing stop-loss for all managed positions.
    """
    if not config.USE_TRAILING_STOP or not open_positions:
        return

    symbol_info = tm.get_symbol_info(config.TRADING_PAIR)
    if not symbol_info:
        log.error("Risk Manager: Could not get symbol info for trailing stop.")
        return

    point = symbol_info.point
    current_price_ask = symbol_info.ask
    current_price_bid = symbol_info.bid
    
    if current_price_ask == 0 or current_price_bid == 0:
        log.warning("Risk Manager: Invalid market price (0.0), skipping trailing stop check.")
        return

    for pos in open_positions:
        entry_price = pos.price_open
        current_sl = pos.sl
        trade_type = pos.type  # 0 for BUY, 1 for SELL

        # Determine target take profit in pips
        if trade_type == 0:  # BUY
            potential_profit_pips = (current_price_bid - entry_price) / (config.PIP_TO_POINT_MULTIPLIER * point)
            take_profit_pips = (pos.tp - entry_price) / (config.PIP_TO_POINT_MULTIPLIER * point) if pos.tp > 0 else config.TAKE_PROFIT_PIPS
        else:  # SELL
            potential_profit_pips = (entry_price - current_price_ask) / (config.PIP_TO_POINT_MULTIPLIER * point)
            take_profit_pips = (entry_price - pos.tp) / (config.PIP_TO_POINT_MULTIPLIER * point) if pos.tp > 0 else config.TAKE_PROFIT_PIPS

        if take_profit_pips <= 0:
            continue

        profit_percentage = (potential_profit_pips / take_profit_pips) * 100

        # Activate trailing stop if profit reaches the activation percentage
        if profit_percentage >= config.TRAILING_ACTIVATION_PERCENT:
            trailing_distance = config.TRAILING_STOP_PIPS * config.PIP_TO_POINT_MULTIPLIER * point
            
            if trade_type == 0:  # BUY
                new_sl = current_price_bid - trailing_distance
                if new_sl > current_sl:
                    log.info(f"TRAILING SL (BUY) #{pos.ticket}: Adjusting SL from {current_sl:.5f} to {new_sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)
            else:  # SELL
                new_sl = current_price_ask + trailing_distance
                if new_sl < current_sl or current_sl == 0:
                    log.info(f"TRAILING SL (SELL) #{pos.ticket}: Adjusting SL from {current_sl:.5f} to {new_sl:.5f}")
                    tm.modify_sl_tp(pos.ticket, new_sl=new_sl, new_tp=pos.tp)