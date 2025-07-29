# =============================================================================
#
#   MAIN TRADING BOT EXECUTABLE (CORRECTED)
#
# =============================================================================

import time
from datetime import datetime, timedelta

# --- Core Application Imports ---
import configs as config
from logger import log
from trade_manager import TradeManager
from strategy import TradingStrategy
# --- FIX APPLIED HERE ---
# The function was renamed to reflect the new dynamic exit logic.
from risk_manager import manage_dynamic_exits
import state_manager as sm

def is_market_open() -> bool:
    """A simple check to avoid trading on weekends (Monday=0, Friday=4)."""
    return datetime.today().weekday() < 5

def check_for_closed_trades(tm: TradeManager):
    """Checks if any managed trades have been closed and clears their state."""
    managed_tickets = sm.get_all_managed_trades()
    if not managed_tickets:
        return

    open_tickets = [pos.ticket for pos in tm.get_open_positions()]

    for ticket in managed_tickets:
        if ticket not in open_tickets:
            log.info(f"Position with ticket {ticket} is no longer open. Clearing state.")
            sm.clear_trade_state(ticket)

def main():
    """The main function that sets up and runs the bot in a continuous loop."""
    log.info("--- Starting Professional Trading Bot for MT5 ---")
    log.info(f"Pair: {config.TRADING_PAIR}, Timeframe: {config.TIMEFRAME}, MagicNum: {config.MAGIC_NUMBER}")

    with TradeManager() as tm:
        strategy = TradingStrategy(tm)
        
        check_interval_seconds = 60
        next_trade_check_time = datetime.now()

        log.info(f"Bot is running. New trade check interval: {check_interval_seconds} seconds.")
        
        while True:
            try:
                open_positions = tm.get_open_positions()

                # 1. Manage dynamic exits for any open positions.
                # --- FIX APPLIED HERE ---
                if open_positions:
                    manage_dynamic_exits(tm, open_positions)

                # 2. Check if any previously managed trades have been closed.
                check_for_closed_trades(tm)

                # 3. Check if it's time to look for a new trade entry.
                if datetime.now() >= next_trade_check_time:
                
                    if config.CHECK_MARKET_HOURS and not is_market_open():
                        log.info("Market is closed. Pausing new trade checks.")
                    else:
                        if not open_positions:
                            strategy.look_for_new_trade()
                        else:
                            log.info("Already managing an open trade. Skipping new trade check.")
                    
                    next_trade_check_time = datetime.now() + timedelta(seconds=check_interval_seconds)

                time.sleep(5)

            except KeyboardInterrupt:
                log.info("Bot shutdown requested by user.")
                break
            except Exception as e:
                log.critical(f"A critical error occurred in the main loop: {e}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    main()
