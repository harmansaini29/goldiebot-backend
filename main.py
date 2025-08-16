# FILE: main.py
# =============================================================================
#
#   MAIN TRADING BOT EXECUTABLE (HOSTING-READY) - FINAL PERFECTED VERSION
#
# =============================================================================

import time
import pandas as pd
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
import indicators
import risk_manager as rm

def initial_cleanup():
    """Cleans up the state file on first run if no trades are open to prevent ghost trades."""
    if not os.path.exists(sm.STATE_FILE):
        return
    try:
        with TradeManager() as tm:
            if not tm.get_open_positions():
                log.info("Initial cleanup: No open trades found. Clearing state file to prevent ghosts.")
                if os.path.exists(sm.STATE_FILE):
                    os.remove(sm.STATE_FILE)
    except Exception as e:
        log.warning(f"Could not perform initial cleanup: {e}")

def is_market_open() -> bool:
    """A simple check to avoid trading on weekends (Monday=0, Friday=4)."""
    return datetime.today().weekday() < 5

def sync_positions_with_state(tm: TradeManager):
    """Adopts ONLY manual trades (magic=0) and ensures they are managed."""
    try:
        manual_positions = tm.get_open_positions(magic=0)
        if not manual_positions:
            return

        managed_tickets = sm.get_all_managed_trades()
        unmanaged_manual_positions = [p for p in manual_positions if p.ticket not in managed_tickets]
        
        if not unmanaged_manual_positions:
            return

        log.info(f"Found {len(unmanaged_manual_positions)} unmanaged MANUAL trade(s). Adopting now...")
        df_daily = tm.fetch_ohlcv('1d', limit=5)
        if df_daily is None or df_daily.empty:
            log.warning("Cannot adopt trades: failed to fetch daily data for Gann TP.")
            return
            
        gann_levels = indicators.calculate_gann_levels(df_daily, config.GANN_CALCULATION_BASIS)

        for pos in unmanaged_manual_positions:
            pos_type = 'BUY' if pos.type == 0 else 'SELL'
            side_key = 'buy_side' if pos_type == 'BUY' else 'sell_side'
            take_profit = gann_levels.get(side_key, {}).get('target_1', 0.0)

            if take_profit > 0 and abs(take_profit - pos.tp) > 0.01:
                log.info(f"Setting TP for adopted manual trade #{pos.ticket} to Gann Target 1: {take_profit}")
                tm.modify_sl_tp(pos.ticket, new_sl=pos.sl, new_tp=take_profit)
            
            sm.save_trade_state(pos.ticket, {
                'entry_price': pos.price_open, 'signal': pos_type,
                'entry_type': 'Adopted/Manual', 'tp_level': take_profit, 'sl_level': pos.sl
            })
            send_telegram_alert(
                f"🔵 <b>MANUAL TRADE ADOPTED</b> 🔵\n\n"
                f"<b>Ticket:</b> #{pos.ticket}\n<b>Type:</b> {pos_type}\n"
                f"The bot will now manage this trade's exit."
            )
    except Exception as e:
        log.error(f"Error during position-state sync: {e}", exc_info=True)

def check_for_closed_trades(tm: TradeManager):
    """
    Checks for closed trades, fetches details instantly, logs them, and sends notifications.
    """
    managed_tickets = sm.get_all_managed_trades()
    if not managed_tickets:
        return

    open_positions = tm.get_open_positions()
    open_tickets = {pos.ticket for pos in open_positions}
    closed_tickets = [ticket for ticket in managed_tickets if ticket not in open_tickets]

    if not closed_tickets:
        return

    for ticket in closed_tickets:
        log.info(f"Position with ticket #{ticket} has closed. Fetching details instantly...")
        
        history_deals = None
        for attempt in range(5):
            # --- THE 100% FINAL FIX IS HERE ---
            # Call the function with the correct argument name: 'position_ticket'
            deals = tm.get_trade_history_for_position(position_ticket=ticket)
            # --- END OF FIX ---
            
            if deals is not None and not deals.empty and 0 in deals['entry'].values and 1 in deals['entry'].values:
                history_deals = deals
                log.info(f"Successfully fetched details for ticket #{ticket} on attempt {attempt + 1}.")
                break
            time.sleep(0.2)

        if history_deals is None:
            log.warning(f"Could not find history for closed ticket {ticket} after multiple fast attempts. Will retry next loop.")
            continue

        try:
            trade_state = sm.get_trade_state(ticket) or {}
            entry_deal = history_deals[history_deals['entry'] == 0].iloc[0]
            exit_deal = history_deals[history_deals['entry'] == 1].iloc[0]
            profit = exit_deal['profit']
            
            trade_data = {
                'Ticket #': ticket,
                'Entry Time': pd.to_datetime(entry_deal['time'], unit='s'),
                'Exit Time': pd.to_datetime(exit_deal['time'], unit='s'),
                'Symbol': entry_deal['symbol'], 
                'Timeframe': config.TIMEFRAME,
                'Direction': trade_state.get('signal', 'N/A'),
                'Lot Size': entry_deal['volume'], 
                'Entry Price': entry_deal['price'],
                'Exit Price': exit_deal['price'],
                'Profit/Loss ($)': profit,
                'Entry Type': trade_state.get('entry_type', 'Unknown'),
                'Exit Reason': "TP/SL/Manual/Reversal",
                'Take Profit': trade_state.get('tp_level', 0.0),
                'Stop Loss': trade_state.get('sl_level', 0.0)
            }
            EXCEL_REPORTER.log_trade(trade_data)
            log.info(f"Closed trade #{ticket} successfully logged to Excel.")

            if profit >= 0:
                alert_message = (
                    f"🎉 <b>PROFIT BOOKED!</b> 🎉\n\n"
                    f"<b>congratulations sir/amadam aajcha vadapavv cha jala profit enjoy kara</b>\n\n"
                    f"<b>Ticket:</b> #{ticket}\n"
                    f"<b>Profit:</b> ${profit:.2f}"
                )
            else:
                alert_message = (
                    f"❌ <b>LOSS BOOKED</b> ❌\n\n"
                    f"<b>Ticket:</b> #{ticket}\n"
                    f"<b>Loss:</b> ${profit:.2f}"
                )
            send_telegram_alert(alert_message)

            sm.clear_trade_state(ticket)

        except Exception as e:
            log.error(f"Critical error processing closed trade {ticket}: {e}", exc_info=True)
            send_telegram_alert(
                f"🚨 <b>PROCESSING ERROR</b> 🚨\n\n"
                f"Failed to process closed ticket #{ticket}. It will be retried.\n\n"
                f"<b>Error:</b> <pre>{e}</pre>"
            )
            continue

def main_loop(tm: TradeManager):
    """The core operational loop of the bot."""
    log.info("Starting main operational loop...")
    strategy = TradingStrategy(tm)
    last_candle_timestamp = None
    
    while True:
        try:
            check_for_closed_trades(tm)
            sync_positions_with_state(tm)
            
            if config.CHECK_MARKET_HOURS and not is_market_open():
                log.info("Market is closed. Pausing new trade checks.")
                time.sleep(300)
                continue

            df_latest = tm.fetch_ohlcv(config.TIMEFRAME, limit=100)
            
            if df_latest is not None and not df_latest.empty and len(df_latest) > 1:
                current_candle_timestamp = df_latest.iloc[-1]['time']
                
                if last_candle_timestamp is None or current_candle_timestamp > last_candle_timestamp:
                    log.info(f"New {config.TIMEFRAME} candle detected. Running checks...")
                    bot_positions = tm.get_open_positions(magic=config.MAGIC_NUMBER)
                    if bot_positions:
                        rm.manage_dynamic_exits(tm, bot_positions)
                    strategy.check_and_execute(bot_positions)
                    last_candle_timestamp = current_candle_timestamp
            else:
                log.warning("Could not fetch latest candle data. Retrying...")
            
            time.sleep(1) 

        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.critical(f"A fatal error occurred in the main trading loop: {e}", exc_info=True)
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
        log.info(f"Strategy: {config.TIMEFRAME} Trend Levels Reversal")
        log.info(f"Symbol: {config.TRADING_PAIR} | TP: Gann Target 1")
        log.info(f"Dynamic Exits (Trailing TP): {'ENABLED' if config.USE_DYNAMIC_EXITS else 'DISABLED'}")
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
        send_telegram_alert(f"🚨 <b>CRITICAL BOT FAILURE</b> 🚨\n\n"
                            f"The bot failed to start. Check the logs.\n"
                            f"<pre>{error_details[-1000:]}</pre>")

if __name__ == "__main__":
    main()