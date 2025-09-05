# FILE: strategy.py (Definitive Final Version)
# =============================================================================
#
#   CORE TRADING STRATEGY & EXECUTION LOGIC
#
# =============================================================================
import time
import MetaTrader5 as mt5

# --- Core Application Imports ---
import configs as config
from logger import log
from trade_manager import TradeManager
import indicators as ind
import state_manager as sm
from notifier import send_telegram_alert

class TradingStrategy:
    def __init__(self, tm: TradeManager):
        self.tm = tm

    def check_and_execute(self, bot_trades: list):
        """
        The main strategy function. Checks for entry and exit signals and executes trades.
        """
        log.info("Strategy: Running checks...")
        
        # --- 1. MANAGE EXISTING BOT TRADES (EXIT LOGIC) ---
        if bot_trades:
            # We assume only one bot trade can be open at a time
            position = bot_trades[0]
            trade_type = 'BUY' if position.type == 0 else 'SELL'
            log.info(f"Managing open {trade_type} position #{position.ticket}. Checking for exit signal.")
            
            # Use the Trend Levels indicator for exit signals
            df_exit = ind.calculate_trend_levels(
                self.tm.fetch_ohlcv(config.TIMEFRAME, limit=config.TREND_LEVELS_LENGTH + 5),
                length=config.TREND_LEVELS_LENGTH
            )
            
            if df_exit.empty:
                log.warning("Could not calculate exit signal, skipping check.")
                return

            exit_signal = df_exit['signal'].iloc[-1]
            log.info(f"Exit Signal Check (Trend Levels): {exit_signal}")

            if (trade_type == 'BUY' and exit_signal == 'SELL') or \
               (trade_type == 'SELL' and exit_signal == 'BUY'):
                log.warning(f"EXIT SIGNAL DETECTED for {trade_type} #{position.ticket}. Closing trade.")
                if self.tm.close_trade(position.ticket):
                    # Reset trend memory to neutral to allow re-entry after exit
                    sm.save_trend_state('NEUTRAL')
                    time.sleep(config.REVERSAL_DELAY_SECONDS) # Pause briefly after closing
                return # Stop further checks this cycle

        # --- 2. CHECK FOR NEW TRADES (ENTRY LOGIC) ---
        else:
            log.info("No open bot trades. Checking for new entry signal.")
            
            df_entry = ind.calculate_ema_crossover_signal(
                self.tm.fetch_ohlcv(config.TIMEFRAME, limit=100),
                fast=config.EMA_FAST_PERIOD,
                medium=config.EMA_MEDIUM_PERIOD,
                slow=config.EMA_SLOW_PERIOD
            )
            
            if df_entry.empty:
                log.warning("Could not calculate entry signal, skipping check.")
                return

            entry_signal = df_entry['signal'].iloc[-1]
            current_trend = sm.get_trend_state()
            log.info(f"Entry Signal Check (EMA Crossover): {entry_signal} | Current Trend Memory: {current_trend}")
            
            # --- THE "10/10 PERFECT" ENTRY LOGIC ---
            # Condition 1: There is a BUY signal
            # Condition 2: The bot's memory is NOT already 'BULLISH'
            if entry_signal == 'BUY' and current_trend != 'BULLISH':
                log.info(">>>>>>>>> Valid BUY signal detected. Entering trade. <<<<<<<<<")
                self.execute_trade('BUY')
                sm.save_trend_state('BULLISH') # Set memory to BULLISH
            
            # Condition 1: There is a SELL signal
            # Condition 2: The bot's memory is NOT already 'BEARISH'
            elif entry_signal == 'SELL' and current_trend != 'BEARISH':
                log.info(">>>>>>>>> Valid SELL signal detected. Entering trade. <<<<<<<<<")
                self.execute_trade('SELL')
                sm.save_trend_state('BEARISH') # Set memory to BEARISH

    def execute_trade(self, signal: str):
        """Calculates SL/TP and sends the trade order to the TradeManager."""
        symbol_info = self.tm.get_symbol_info(config.TRADING_PAIR)
        if not symbol_info:
            log.error("Could not execute trade: Symbol info not found.")
            return

        point = symbol_info.point
        price = self.tm.get_current_price(signal)
        if price is None:
            log.error("Could not execute trade: Failed to get current price.")
            return

        sl_distance = config.STOP_LOSS_PIPS * config.PIP_TO_POINT_MULTIPLIER * point
        tp_distance = config.TAKE_PROFIT_PIPS * config.PIP_TO_POINT_MULTIPLIER * point

        if signal == 'BUY':
            order_type = mt5.ORDER_TYPE_BUY
            stop_loss = price - sl_distance
            take_profit = price + tp_distance
        else: # SELL
            order_type = mt5.ORDER_TYPE_SELL
            stop_loss = price + sl_distance
            take_profit = price - tp_distance

        result = self.tm.open_trade(
            order_type=order_type,
            symbol=config.TRADING_PAIR,
            volume=config.LOT_SIZE,
            price=price,
            sl=stop_loss,
            tp=take_profit,
            comment=f"{signal} Signal by GoldBot"
        )
        
        if result:
            log.info(f"Trade executed successfully. Ticket: #{result.order}")
            send_telegram_alert(
                f"🚀 <b>NEW TRADE OPENED</b> 🚀\n\n"
                f"<b>Type:</b> {signal}\n"
                f"<b>Symbol:</b> {config.TRADING_PAIR}\n"
                f"<b>Price:</b> ${price:,.2f}\n"
                f"<b>Ticket:</b> #{result.order}"
            )