# FILE: main.py
# =============================================================================
#
#   MAIN TRADING BOT EXECUTABLE (PROFESSIONAL & FINAL VERSION)
#   - Isolates management logic for Manual vs. Automated trades.
#   - Automatically sets default SL/TP on newly adopted manual trades.
#   - Includes robust state synchronization and error handling.
#   - Optimized loop timing for balance of speed and efficiency.
#
# =============================================================================

import time
from datetime import datetime
import traceback
import os

# --- Core Application Imports ---
import configs as config
from logger import log, EXCEL_REPORTER
from trade_manager import TradeManager
from strategy import TradingStrategy
import state_manager as sm
from notifier import send_telegram_alert
import risk_manager as rm

def initial_cleanup():
    """Cleans up the state file on first run if no trades are open to prevent ghost trades."""
    if not os.path.exists(sm.STATE_FILE):
        return
    try:
        with TradeManager() as tm:
            if tm.is_connected() and not tm.get_open_positions():
                log.info("Initial cleanup: No open trades found. Clearing state file to prevent ghosts.")
                if os.path.exists(sm.STATE_FILE):
                    os.remove(sm.STATE_FILE)
    except Exception as e:
        log.warning(f"Could not perform initial cleanup: {e}")

def is_market_open() -> bool:
    """A simple check to avoid trading on weekends (Monday=0, Friday=4)."""
    return datetime.today().weekday() < 5

def sync_positions_with_state(tm: TradeManager):
    """Adopts new manual trades and logs trades that were closed on the terminal."""
    open_positions = tm.get_open_positions()
    managed_tickets = sm.get_all_managed_trades()
    
    # Find tickets in our state that are no longer open on the terminal
    closed_tickets = [t for t in managed_tickets if t not in [p.ticket for p in open_positions]]
    for ticket in closed_tickets:
        log_closed_trade(tm, ticket)

    # Find open trades on the terminal that are not in our state (i.e., new manual trades)
    for pos in open_positions:
        if pos.ticket not in managed_tickets and pos.magic == 0:
            adopt_manual_trade(tm, pos)

def adopt_manual_trade(tm: TradeManager, position):
    """
    Adds a manually opened trade to the state file and sets a default SL/TP if they are missing.
    This enables the trailing stop loss for manual trades.
    """
    log.info(f"ADOPTING MANUAL TRADE: Found unmanaged manual trade #{position.ticket}.")
    trade_type = 'BUY' if position.type == 0 else 'SELL'
    
    current_sl = position.sl
    current_tp = position.tp
    
    # Set default SL/TP on manual trades if they don't have them
    if current_sl == 0.0 or current_tp == 0.0:
        log.info(f"Manual trade #{position.ticket} is missing SL/TP. Setting default values from config.")
        
        symbol_info = tm.get_symbol_info(config.TRADING_PAIR)
        if not symbol_info:
            log.error(f"Cannot set SL/TP for #{position.ticket}: Could not get symbol info.")
            return

        point = symbol_info.point
        price = position.price_open
        
        sl_distance = config.STOP_LOSS_PIPS * config.PIP_TO_POINT_MULTIPLIER * point
        tp_distance = config.TAKE_PROFIT_PIPS * config.PIP_TO_POINT_MULTIPLIER * point
        
        if trade_type == 'BUY':
            stop_loss = price - sl_distance
            take_profit = price + tp_distance
        else: # SELL
            stop_loss = price + sl_distance
            take_profit = price - tp_distance
            
        if tm.modify_sl_tp(position.ticket, new_sl=stop_loss, new_tp=take_profit):
            current_sl = stop_loss
            current_tp = take_profit
    
    # Save the trade to the state file so it can be managed by the risk manager
    sm.save_trade_state(position.ticket, {
        'entry_price': position.price_open,
        'signal': trade_type,
        'entry_type': 'Manual/Adopted',
        'tp_level': current_tp,
        'sl_level': current_sl
    })
    send_telegram_alert(f"🤖 <b>ADOPTED MANUAL TRADE</b> 🤖\n\nNow managing ticket #{position.ticket} with full risk management.")

def log_closed_trade(tm: TradeManager, ticket: int):
    """Fetches history for a closed trade, logs it to Excel, and clears its state."""
    if ticket in EXCEL_REPORTER.get_logged_tickets():
        sm.clear_trade_state(ticket)
        return

    log.info(f"Detected closed trade for ticket #{ticket}. Fetching history...")
    history_df = tm.get_trade_history_for_position(ticket)
    
    if history_df is not None and not history_df.empty:
        EXCEL_REPORTER.log_trade_history(history_df)
        log.info(f"Successfully logged trade history for ticket #{ticket} to Excel.")
        
        profit = history_df['profit'].sum()
        emoji = "✅" if profit >= 0 else "🔻"
        send_telegram_alert(
            f"{emoji} <b>TRADE CLOSED</b> {emoji}\n\n"
            f"<b>Ticket:</b> #{ticket}\n"
            f"<b>Profit:</b> ${profit:,.2f}"
        )
    else:
        log.warning(f"Could not retrieve history for closed ticket #{ticket}. It may have been closed long ago.")
        
    sm.clear_trade_state(ticket)
    log.info(f"Cleared state for closed ticket #{ticket}.")

def main_loop(tm: TradeManager):
    """The main execution loop with separated logic for bot vs. manual trades."""
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
            
            # 1. STRATEGY LOGIC (Entry/Exit) is applied ONLY to bot-opened trades.
            log.info(f"Applying core strategy logic to {len(bot_trades)} bot trade(s).")
            strategy.check_and_execute(bot_trades)
            
            # 2. RISK MANAGEMENT (Trailing SL) is applied to ALL managed trades.
            if all_open_positions:
                log.info(f"Applying risk management to {len(all_open_positions)} total trade(s).")
                rm.manage_trailing_stop_loss(tm, all_open_positions)

            # --- OPTIMIZED LOOP DELAY ---
            # A 1-second delay is highly responsive for trailing stops
            # without wasting significant CPU resources.
            time.sleep(1)

        except Exception as e:
            log.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            error_details = traceback.format_exc()
            send_telegram_alert(
                f"🚨 <b>BOT LOOP ERROR</b> 🚨\n\n"
                f"An unexpected error occurred. The bot will retry in 30 seconds.\n\n"
                f"<pre>{error_details[-1000:]}</pre>"
            )
            time.sleep(30)

def main():
    """The main entry point of the trading bot."""
    try:
        initial_cleanup()
        log.info("="*50)
        log.info("STARTING PROFESSIONAL TRADING BOT")
        log.info(f"Strategy: {config.TIMEFRAME} Stacked EMA ({config.EMA_FAST_PERIOD}/{config.EMA_MEDIUM_PERIOD}/{config.EMA_SLOW_PERIOD})")
        log.info(f"Symbol: {config.TRADING_PAIR} | TP: {config.TAKE_PROFIT_PIPS} pips | SL: {config.STOP_LOSS_PIPS} pips")
        log.info(f"Trailing SL: {'ENABLED' if config.USE_TRAILING_STOP else 'DISABLED'} | Activation: {config.TRAILING_ACTIVATION_PERCENT}% | Trail: {config.TRAILING_STOP_PIPS} pips")
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
        send_telegram_alert(
            f"❌ <b>FATAL STARTUP ERROR</b> ❌\n\n"
            f"The bot could not start. Please check the logs.\n\n"
            f"<pre>{error_details[-1000:]}</pre>"
        )

if __name__ == "__main__":
    main()