# FILE: main.py
# =============================================================================
#
#   MAIN TRADING BOT EXECUTABLE (FINAL & VERIFIED)
#
# =============================================================================

import time
from datetime import datetime
import traceback
import os
import MetaTrader5 as mt5

# --- Core Application Imports ---
from logger import log, EXCEL_REPORTER
import configs as config
from trade_manager import TradeManager
import state_manager as sm
from notifier import send_telegram_alert
import risk_manager as rm
from strategy import TradingStrategy

def initial_cleanup():
    """Cleans up the state file on first run if no trades are open to prevent ghost trades."""
    if os.path.exists(sm.STATE_FILE):
        return
    try:
        with TradeManager() as tm:
            if tm.is_connected() and not tm.get_open_positions():
                log.info("Initial cleanup: No open trades found. Clearing state file.")
                if os.path.exists(sm.STATE_FILE):
                    os.remove(sm.STATE_FILE)
    except Exception as e:
        log.warning(f"Could not perform initial cleanup: {e}")

def is_market_open() -> bool:
    """A simple check to avoid trading on weekends (Friday=4, Saturday=5, Sunday=6)."""
    return datetime.utcnow().weekday() < 5

def sync_positions_with_state(tm: TradeManager):
    """Adopts new manual trades and logs trades that were closed on the terminal."""
    try:
        open_positions = tm.get_open_positions()
        managed_tickets = sm.get_all_managed_trades()
        
        open_tickets = [p.ticket for p in open_positions]
        closed_tickets = [t for t in managed_tickets if t not in open_tickets]
        for ticket in closed_tickets:
            log_closed_trade(tm, ticket)

        for pos in open_positions:
            if pos.ticket not in managed_tickets and pos.magic == 0:
                adopt_manual_trade(tm, pos)
    except Exception as e:
        log.error(f"Error during position sync: {e}", exc_info=True)


def adopt_manual_trade(tm: TradeManager, position):
    """Adds a manually opened trade to the state file and sets a default SL/TP."""
    log.info(f"ADOPTING MANUAL TRADE: Found unmanaged manual trade #{position.ticket}.")
    trade_type = 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'
    
    if position.sl == 0.0 or position.tp == 0.0:
        log.info(f"Manual trade #{position.ticket} is missing SL/TP. Setting defaults.")
        symbol_info = tm.get_symbol_info(config.TRADING_PAIR)
        if not symbol_info:
            log.error(f"Cannot set SL/TP for #{position.ticket}: Could not get symbol info.")
            return

        point, price = symbol_info.point, position.price_open
        sl_distance = config.STOP_LOSS_PIPS * config.POINTS_PER_PIP * point
        tp_distance = config.TAKE_PROFIT_PIPS * config.POINTS_PER_PIP * point
        
        stop_loss = price - sl_distance if trade_type == 'BUY' else price + sl_distance
        take_profit = price + tp_distance if trade_type == 'BUY' else price - tp_distance
        tm.modify_sl_tp(position.ticket, new_sl=stop_loss, new_tp=take_profit)
    
    sm.save_trade_state(position.ticket, {
        'entry_price': position.price_open, 'signal': trade_type, 
        'entry_type': 'Manual/Adopted', 'tp_level': position.tp, 'sl_level': position.sl
    })
    send_telegram_alert(f"🤖 <b>ADOPTED MANUAL TRADE</b> 🤖\n\nNow managing ticket #{position.ticket} with full risk management.")


def log_closed_trade(tm: TradeManager, ticket: int):
    """Fetches history for a closed trade, logs it, and sends alerts."""
    if ticket in EXCEL_REPORTER.get_logged_tickets():
        sm.clear_trade_state(ticket)
        return

    log.info(f"Processing closed trade for ticket #{ticket}. Fetching history...")
    history_df, is_history_complete = None, False
    
    for attempt in range(5):
        history_df = tm.get_trade_history_for_position(ticket)
        if history_df is not None and not history_df.empty:
            if 0 in history_df['entry'].values and 1 in history_df['entry'].values:
                is_history_complete = True
                log.info(f"Attempt {attempt + 1}: Successfully fetched complete history for ticket #{ticket}.")
                break
        log.warning(f"Attempt {attempt + 1}: History for ticket #{ticket} is incomplete. Retrying...")
        time.sleep(2)

    if is_history_complete:
        EXCEL_REPORTER.log_trade_history(history_df)
        profit = history_df['profit'].sum() + history_df['commission'].sum() + history_df['swap'].sum()
        emoji = "✅" if profit >= 0 else "🔻"
        send_telegram_alert(
            f"{emoji} <b>TRADE CLOSED</b> {emoji}\n\n"
            f"<b>Ticket:</b> #{ticket}\n"
            f"<b>Net Profit:</b> ${profit:,.2f}"
        )
        sm.clear_trade_state(ticket)
        log.info(f"Cleared state for closed ticket #{ticket}.")
    else:
        log.error(f"Failed to retrieve complete history for #{ticket}. State not cleared, will retry.")
        
def main_loop(tm: TradeManager):
    """The main execution loop."""
    strategy = TradingStrategy(tm)
    
    while True:
        try:
            if config.CHECK_MARKET_HOURS and not is_market_open():
                log.info("Market is closed. Sleeping.")
                time.sleep(3600)
                continue

            sync_positions_with_state(tm)
            
            # --- FINAL LOGIC: Execute strategy and risk management every cycle ---
            strategy.check_and_execute()
            
            managed_positions = [p for p in tm.get_open_positions() if p.ticket in sm.get_all_managed_trades()]
            if managed_positions:
                rm.manage_trailing_stop_loss(tm, managed_positions)

            time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)

        except Exception as e:
            log.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            error_details = traceback.format_exc()
            send_telegram_alert(f"🚨 <b>BOT LOOP ERROR</b> 🚨\n\n<pre>{error_details[-1000:]}</pre>")
            time.sleep(30)

def main():
    """The main entry point of the trading bot."""
    try:
        initial_cleanup()
        log.info("="*50)
        log.info("STARTING PROFESSIONAL TRADING BOT (vPRO)")
        log.info(f"Strategy: {config.TIMEFRAME} EMA Crossover w/ ATR Filter")
        log.info(f"Trailing SL: {'ENABLED' if config.USE_TRAILING_STOP else 'DISABLED'}")
        log.info("="*50)
        send_telegram_alert("✅ <b>GoldBot vPRO Started Successfully</b> ✅")

        with TradeManager() as tm:
            if tm.is_connected():
                main_loop(tm)
            else:
                log.critical("Could not establish connection to MetaTrader 5. Shutting down.")

    except KeyboardInterrupt:
        log.info("Bot shutdown requested by user.")
        send_telegram_alert("⚪️ <b>Bot Shut Down Manually</b> ⚪️")
    except Exception as e:
        log.critical(f"A fatal error occurred on startup: {e}", exc_info=True)
        error_details = traceback.format_exc()
        send_telegram_alert(f"❌ <b>FATAL STARTUP ERROR</b> ❌\n\n<pre>{error_details[-1000:]}</pre>")

if __name__ == "__main__":
    main()