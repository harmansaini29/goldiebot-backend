# =============================================================================
#
#   MAIN TRADING BOT EXECUTABLE (UPDATED)
#
# =============================================================================

import time
from datetime import datetime, timedelta

# --- Core Application Imports ---
import configs as config
from logger import log
from trade_manager import TradeManager
from strategy import TradingStrategy
from risk_manager import manage_trailing_stop
import state_manager as sm

def is_market_open() -> bool:
    """A simple check to avoid trading on weekends (Monday=0, Friday=4)."""
    return datetime.today().weekday() < 5

def check_for_closed_trades(tm: TradeManager):
    """Checks if any managed trades have been closed and clears their state."""
    managed_tickets = sm.get_all_managed_trades()
    if not managed_tickets:
        return

    # tm.get_open_positions() is already filtered by the bot's magic number
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

                # 1. Manage trailing stops for any open positions, if enabled.
                if config.USE_TRAILING_STOP and open_positions:
                    manage_trailing_stop(tm, open_positions)

                # 2. Check if any previously managed trades have been closed.
                check_for_closed_trades(tm)

                # 3. Check if it's time to look for a new trade entry.
                if datetime.now() >= next_trade_check_time:
                    if config.CHECK_MARKET_HOURS and not is_market_open():
                        log.info("Market is closed. Pausing new trade checks.")
                    else:
                        # IMPROVEMENT: Check the live state from the terminal, not the state manager.
                        if not open_positions:
                            strategy.look_for_new_trade()
                        else:
                            log.info("Already managing an open trade. Skipping new trade check.")
                    
                    # Schedule the next check regardless of the outcome.
                    next_trade_check_time = datetime.now() + timedelta(seconds=check_interval_seconds)

                # The main loop delay. The bot rests here between checks.
                time.sleep(5)

            except KeyboardInterrupt:
                log.info("Bot shutdown requested by user.")
                break
            except Exception as e:
                log.critical(f"A critical error occurred in the main loop: {e}", exc_info=True)
                # Wait before retrying to prevent rapid-fire error loops
                time.sleep(60)

if __name__ == "__main__":
    main()