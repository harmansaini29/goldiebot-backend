# FILE: main.py (Fully Updated & Corrected Version)
# =============================================================================
#
#   MAIN TRADING BOT EXECUTABLE
#   - Solves circular import error with a local import.
#   - Fixes missed trade logs with a robust retry mechanism.
#   - Corrects SL/TP calculation for adopted trades.
#
# =============================================================================

import time
from datetime import datetime
import traceback
import os

# --- Core Application Imports ---
from logger import log, EXCEL_REPORTER
import configs as config
from trade_manager import TradeManager
import state_manager as sm
from notifier import send_telegram_alert
import risk_manager as rm

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
    open_positions = tm.get_open_positions()
    managed_tickets = sm.get_all_managed_trades()
    
    # Log trades that were managed but are now closed
    open_tickets = [p.ticket for p in open_positions]
    closed_tickets = [t for t in managed_tickets if t not in open_tickets]
    for ticket in closed_tickets:
        log_closed_trade(tm, ticket)

    # Adopt trades that are open but not managed (i.e., manual trades)
    for pos in open_positions:
        if pos.ticket not in managed_tickets and pos.magic == 0:
            adopt_manual_trade(tm, pos)

def adopt_manual_trade(tm: TradeManager, position):
    """Adds a manually opened trade to the state file and sets a default SL/TP."""
    log.info(f"ADOPTING MANUAL TRADE: Found unmanaged manual trade #{position.ticket}.")
    trade_type = 'BUY' if position.type == 0 else 'SELL'
    
    current_sl, current_tp = position.sl, position.tp
    
    # If SL or TP is not set, apply default values from config
    if current_sl == 0.0 or current_tp == 0.0:
        log.info(f"Manual trade #{position.ticket} is missing SL/TP. Setting default values.")
        symbol_info = tm.get_symbol_info(config.TRADING_PAIR)
        if not symbol_info:
            log.error(f"Cannot set SL/TP for #{position.ticket}: Could not get symbol info.")
            return

        point, price = symbol_info.point, position.price_open
        sl_distance = config.STOP_LOSS_PIPS * config.POINTS_PER_PIP * point
        tp_distance = config.TAKE_PROFIT_PIPS * config.POINTS_PER_PIP * point
        
        # --- BUG FIX: Correct take_profit calculation for SELL trades ---
        stop_loss = price - sl_distance if trade_type == 'BUY' else price + sl_distance
        take_profit = price + tp_distance if trade_type == 'BUY' else price - tp_distance
        
        if tm.modify_sl_tp(position.ticket, new_sl=stop_loss, new_tp=take_profit):
            current_sl, current_tp = stop_loss, take_profit
    
    sm.save_trade_state(position.ticket, {
        'entry_price': position.price_open, 'signal': trade_type, 'entry_type': 'Manual/Adopted',
        'tp_level': current_tp, 'sl_level': current_sl
    })
    send_telegram_alert(f"🤖 <b>ADOPTED MANUAL TRADE</b> 🤖\n\nNow managing ticket #{position.ticket} with full risk management.")

def log_closed_trade(tm: TradeManager, ticket: int):
    """
    Fetches history for a closed trade, logs it, and sends alerts.
    Includes a retry loop to prevent missing logs due to server-side delays.
    """
    if ticket in EXCEL_REPORTER.get_logged_tickets():
        sm.clear_trade_state(ticket)
        return

    log.info(f"Processing closed trade for ticket #{ticket}. Fetching history...")
    
    history_df = None
    is_history_complete = False
    
    for attempt in range(5):
        history_df = tm.get_trade_history_for_position(ticket)
        
        if history_df is not None and not history_df.empty:
            has_entry = 0 in history_df['entry'].values
            has_exit = 1 in history_df['entry'].values
            if has_entry and has_exit:
                is_history_complete = True
                log.info(f"Attempt {attempt + 1}: Successfully fetched complete history for ticket #{ticket}.")
                break
        
        log.warning(f"Attempt {attempt + 1}: History for ticket #{ticket} is incomplete. Retrying in 2s...")
        time.sleep(2)

    if is_history_complete:
        EXCEL_REPORTER.log_trade_history(history_df)
        log.info(f"Successfully logged trade history for ticket #{ticket} to Excel.")
        
        profit = history_df['profit'].sum()
        emoji = "✅" if profit >= 0 else "🔻"
        send_telegram_alert(
            f"{emoji} <b>TRADE CLOSED</b> {emoji}\n\n"
            f"<b>Ticket:</b> #{ticket}\n"
            f"<b>Profit:</b> ${profit:,.2f}"
        )
        sm.clear_trade_state(ticket)
        log.info(f"Cleared state for closed ticket #{ticket}.")
    else:
        log.error(f"Failed to retrieve complete history for closed ticket #{ticket}. State will not be cleared, will retry next cycle.")
        
def main_loop(tm: TradeManager):
    """The main execution loop."""
    from strategy import TradingStrategy # Local import to prevent circular dependency
    strategy = TradingStrategy(tm)
    
    while True:
        try:
            if config.CHECK_MARKET_HOURS and not is_market_open():
                log.info("Market is closed. Sleeping until next session.")
                time.sleep(3600)
                continue

            sync_positions_with_state(tm)
            
            all_open_positions = tm.get_open_positions()
            bot_trades = [p for p in all_open_positions if p.magic == config.MAGIC_NUMBER]
            
            # Run strategy only if no bot trades are currently open
            if not bot_trades:
                strategy.check_and_execute()
            
            # Apply risk management to all managed trades (bot + adopted)
            managed_positions = [p for p in all_open_positions if p.ticket in sm.get_all_managed_trades()]
            if managed_positions:
                rm.manage_trailing_stop_loss(tm, managed_positions)

            time.sleep(5) # Check every 5 seconds

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
        log.info("STARTING PROFESSIONAL TRADING BOT (Corrected Version)")
        log.info(f"Strategy: {config.TIMEFRAME} EMA Crossover | Exit: Trend Levels Reversal")
        log.info(f"Trailing SL: {'ENABLED' if config.USE_TRAILING_STOP else 'DISABLED'}")
        log.info("="*50)
        send_telegram_alert("✅ <b>BOT STARTED SUCCESSFULLY</b> ✅")

        with TradeManager() as tm:
            main_loop(tm)

    except KeyboardInterrupt:
        log.info("Bot shutdown requested by user.")
        send_telegram_alert("⚪️ <b>Bot Shut Down Manually</b> ⚪️")
    except Exception as e:
        log.critical(f"A fatal error occurred on startup: {e}", exc_info=True)
        error_details = traceback.format_exc()
        send_telegram_alert(f"❌ <b>FATAL STARTUP ERROR</b> ❌\n\n<pre>{error_details[-1000:]}</pre>")

if __name__ == "__main__":
    main()