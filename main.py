# FILE: main.py (Final Corrected Version)
# =============================================================================
import time
from datetime import datetime
import traceback
import MetaTrader5 as mt5
from typing import Optional

from logger import log, EXCEL_REPORTER
import configs as config
from trade_manager import TradeManager
import state_manager as sm
from notifier import send_telegram_alert
from strategy import TradingStrategy
from risk_manager import manage_trailing_stop_loss

def is_market_open() -> bool:
    return datetime.utcnow().weekday() < 5

def sync_positions_with_state(tm: TradeManager) -> Optional[bool]:
    try:
        open_positions = tm.get_open_positions()
        if open_positions is None: return None

        managed_tickets = sm.get_all_managed_trades()
        open_tickets = {p.ticket for p in open_positions}
        closed_on_terminal = [t for t in managed_tickets if t not in open_tickets]
        for ticket in closed_on_terminal:
            log.warning(f"Managed trade #{ticket} was closed outside the bot. Processing closure.")
            log_closed_trade(tm, ticket)

        for pos in open_positions:
            if pos.ticket not in managed_tickets:
                adopt_manual_trade(tm, pos)
        return True
    except Exception as e:
        log.error(f"Error during position sync: {e}", exc_info=True)
        return False

def adopt_manual_trade(tm: TradeManager, position):
    log.info(f"ADOPTING MANUAL TRADE: Found unmanaged trade #{position.ticket}.")
    trade_type = 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'

    if position.sl == 0.0 or position.tp == 0.0:
        log.info(f"Manual trade #{position.ticket} is missing SL/TP. Setting defaults.")
        
        # --- THIS IS THE FIX ---
        # Access the property from the TradeManager instead of calling the old method
        symbol_info = tm.symbol_info
        # ---------------------

        if not symbol_info:
            log.error(f"Cannot set SL/TP for #{position.ticket}: Could not get symbol info.")
            return
        point, price = symbol_info.point, position.price_open
        sl_distance = config.STOP_LOSS_PIPS * config.POINTS_PER_PIP * point
        tp_distance = config.TAKE_PROFIT_PIPS * config.POINTS_PER_PIP * point
        stop_loss = price - sl_distance if trade_type == 'BUY' else price + sl_distance
        take_profit = price + tp_distance if trade_type == 'BUY' else price - sl_distance
        tm.modify_sl_tp(position.ticket, new_sl=stop_loss, new_tp=take_profit)

    sm.save_trade_state(position.ticket, {'entry_price': position.price_open, 'signal': trade_type, 'entry_type': 'Manual/Adopted'})
    send_telegram_alert(f"🤖 <b>ADOPTED MANUAL TRADE</b> 🤖\n\nNow managing ticket #{position.ticket}.")

def log_closed_trade(tm: TradeManager, ticket: int):
    if ticket in EXCEL_REPORTER.get_logged_tickets():
        sm.clear_trade_state(ticket)
        return

    log.info(f"Processing closed trade for ticket #{ticket}. Fetching history...")
    history_df, is_history_complete = None, False
    for attempt in range(5):
        history_df = tm.get_trade_history_for_position(ticket)
        if history_df is not None and not history_df.empty and 0 in history_df['entry'].values and 1 in history_df['entry'].values:
            is_history_complete = True
            log.info(f"Attempt {attempt + 1}: Successfully fetched complete history for #{ticket}.")
            break
        log.warning(f"Attempt {attempt + 1}: History for #{ticket} is incomplete. Retrying...")
        time.sleep(2)

    if is_history_complete:
        EXCEL_REPORTER.log_trade_history(history_df)
        profit = history_df['profit'].sum() + history_df['commission'].sum() + history_df['swap'].sum()
        emoji = "✅" if profit >= 0 else "🔻"
        send_telegram_alert(f"{emoji} <b>TRADE CLOSED</b> {emoji}\n\n<b>Ticket:</b> #{ticket}\n<b>Net Profit:</b> ${profit:,.2f}")
        sm.clear_trade_state(ticket)
        log.info(f"Cleared state for closed ticket #{ticket}.")
    else:
        log.error(f"Failed to retrieve complete history for #{ticket}. State not cleared.")

def main_loop(tm: TradeManager):
    strategy = TradingStrategy(tm)
    last_candle_time = None
    connection_lost_counter = 0

    while True:
        try:
            if config.CHECK_MARKET_HOURS and not is_market_open():
                log.info("Market is closed. Sleeping.")
                time.sleep(3600)
                continue

            sync_result = sync_positions_with_state(tm)
            if sync_result is None:
                connection_lost_counter += 1
                log.warning(f"Connection to MT5 lost. Retrying... (Attempt {connection_lost_counter})")
                if connection_lost_counter > 5:
                    log.critical("Connection lost for over threshold. Forcing reconnect.")
                    return
                time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)
                continue
            connection_lost_counter = 0

            open_positions = tm.get_open_positions()
            if open_positions is None:
                time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)
                continue

            managed_positions = [p for p in open_positions if p.ticket in sm.get_all_managed_trades()]
            
            if managed_positions:
                manage_trailing_stop_loss(tm, managed_positions)

            latest_candle = tm.fetch_ohlcv(config.TIMEFRAME, limit=1)
            if latest_candle.empty:
                time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)
                continue

            current_candle_time = latest_candle['time'].iloc[0]
            if current_candle_time != last_candle_time:
                log.info(f"New {config.TIMEFRAME} candle detected at {current_candle_time}. Running strategy checks.")
                last_candle_time = current_candle_time

                if managed_positions:
                    exit_signal = strategy.get_exit_signal()
                    for pos in managed_positions:
                        trade_type = 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL'
                        if (trade_type == 'BUY' and exit_signal == 'SELL') or (trade_type == 'SELL' and exit_signal == 'BUY'):
                            log.warning(f"EXIT SIGNAL DETECTED for {trade_type} #{pos.ticket}. Closing trade.")
                            tm.close_trade(pos.ticket)

                open_positions = tm.get_open_positions()
                if open_positions is None: continue
                
                bot_positions = [p for p in open_positions if p.magic == config.MAGIC_NUMBER and p.ticket in sm.get_all_managed_trades()]
                if not bot_positions:
                    entry_signal = strategy.get_entry_signal()
                    if entry_signal in ['BUY', 'SELL']:
                        log.info(f">>>>>>> Valid {entry_signal} signal detected. Executing trade. <<<<<<<")
                        strategy.execute_trade(entry_signal)
                else:
                    log.info("A bot-managed trade is already open. Skipping new entry check.")

            time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)

        except Exception as e:
            log.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            error_details = traceback.format_exc()
            send_telegram_alert(f"🚨 <b>BOT CRITICAL ERROR</b> 🚨\n\n<pre>{error_details[-1000:]}</pre>")
            time.sleep(30)

def main():
    while True:
        try:
            log.info("="*50)
            log.info("STARTING PROFESSIONAL TRADING BOT (vPRO - Self-Healing)")
            log.info(f"Strategy: {config.TIMEFRAME} EMA Crossover w/ ATR Filter & Trend Reversal Exit")
            log.info(f"Trailing SL: {'ENABLED' if config.USE_TRAILING_STOP else 'DISABLED'}")
            log.info("="*50)
            send_telegram_alert("✅ <b>GoldBot vPRO (Self-Healing) Started Successfully</b> ✅")

            with TradeManager() as tm:
                if tm.is_connected():
                    main_loop(tm)
                else:
                    log.critical("Could not establish connection to MetaTrader 5 on startup.")

            log.warning("Main loop exited. Attempting to reconnect in 15 seconds...")
            send_telegram_alert("⚠️ <b>Connection Lost.</b> Attempting to reconnect... ⚠️")
            time.sleep(15)

        except KeyboardInterrupt:
            log.info("Bot shutdown requested by user.")
            send_telegram_alert("⚪️ <b>Bot Shut Down Manually</b> ⚪️")
            break
        except Exception as e:
            log.critical(f"A fatal error occurred: {e}", exc_info=True)
            error_details = traceback.format_exc()
            send_telegram_alert(f"❌ <b>FATAL ERROR</b> ❌\n\n<pre>{error_details[-1000:]}</pre>")
            log.info("Restarting after fatal error in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    main()