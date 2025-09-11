# FILE: strategy.py
# =============================================================================

import time
import MetaTrader5 as mt5
import configs as config
from logger import log
from trade_manager import TradeManager
import indicators as ind
import state_manager as sm
from notifier import send_telegram_alert

class TradingStrategy:
    def __init__(self, tm: TradeManager):
        self.tm = tm
        self.symbol_info = self.tm.get_symbol_info(config.TRADING_PAIR)
        if not self.symbol_info:
            raise ValueError("Strategy could not initialize: Failed to get symbol info.")

    def _manage_open_trades(self):
        """Checks all open bot positions for an exit signal."""
        open_positions = self.tm.get_open_positions(magic=config.MAGIC_NUMBER)
        if not open_positions:
            return

        # This logic still assumes the bot only manages one trade at a time.
        position = open_positions[0] 
        trade_type = 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'
        log.info(f"Managing open {trade_type} position #{position.ticket}. Checking for exit.")

        df_exit = ind.calculate_trend_levels(
            self.tm.fetch_ohlcv(config.TIMEFRAME, limit=config.TREND_LEVELS_LENGTH + 5),
            length=config.TREND_LEVELS_LENGTH
        )
        if df_exit.empty: return

        exit_signal = df_exit['signal'].iloc[-1]
        if (trade_type == 'BUY' and exit_signal == 'SELL') or \
           (trade_type == 'SELL' and exit_signal == 'BUY'):
            log.warning(f"EXIT SIGNAL DETECTED for {trade_type} #{position.ticket}. Closing.")
            if self.tm.close_trade(position.ticket):
                sm.save_trend_state('NEUTRAL')
                time.sleep(config.REVERSAL_DELAY_SECONDS)

    def _check_for_new_trades(self):
        """Checks for a new entry signal if no bot trades are open."""
        if self.tm.get_open_positions(magic=config.MAGIC_NUMBER):
            return # Don't check for new trades if one is already open

        log.info("No open bot trades. Checking for new entry signal.")
        
        # --- ATR Volatility Filter ---
        if config.USE_ATR_FILTER:
            ohlcv_for_atr = self.tm.fetch_ohlcv(config.TIMEFRAME, limit=config.ATR_PERIOD + 5)
            current_atr = ind.calculate_atr(ohlcv_for_atr, config.ATR_PERIOD, self.symbol_info.point)
            log.info(f"Volatility Check: Current ATR = {current_atr:.2f} pips, Required = {config.ATR_THRESHOLD_PIPS} pips.")
            if current_atr < config.ATR_THRESHOLD_PIPS:
                log.info("Trade filtered: Market volatility is too low.")
                return

        df_entry = ind.calculate_ema_crossover_signal(
            self.tm.fetch_ohlcv(config.TIMEFRAME, limit=100),
            fast=config.EMA_FAST_PERIOD, medium=config.EMA_MEDIUM_PERIOD,
            slow=config.EMA_SLOW_PERIOD, point=self.symbol_info.point
        )
        if df_entry.empty: return

        entry_signal = df_entry['signal'].iloc[-1]
        current_trend = sm.get_trend_state()
        log.info(f"Entry Signal Check: '{entry_signal}' | Trend Memory: '{current_trend}'")

        if entry_signal == 'BUY' and current_trend != 'BULLISH':
            log.info(">>>>>>>>> Valid BUY signal detected. Entering trade. <<<<<<<<<")
            if self.execute_trade('BUY'):
                sm.save_trend_state('BULLISH')
        elif entry_signal == 'SELL' and current_trend != 'BEARISH':
            log.info(">>>>>>>>> Valid SELL signal detected. Entering trade. <<<<<<<<<")
            if self.execute_trade('SELL'):
                sm.save_trend_state('BEARISH')

    def check_and_execute(self):
        """The main strategy function with decoupled professional logic."""
        log.info("Strategy: Running main cycle...")
        self._manage_open_trades()
        self._check_for_new_trades()

    def execute_trade(self, signal: str) -> bool:
        """Calculates SL/TP and sends the trade order."""
        price = self.tm.get_current_price(signal)
        if price is None: return False

        sl_distance = config.STOP_LOSS_PIPS * config.POINTS_PER_PIP * self.symbol_info.point
        tp_distance = config.TAKE_PROFIT_PIPS * config.POINTS_PER_PIP * self.symbol_info.point
        order_type = mt5.ORDER_TYPE_BUY if signal == 'BUY' else mt5.ORDER_TYPE_SELL
        stop_loss = price - sl_distance if signal == 'BUY' else price + sl_distance
        take_profit = price + tp_distance if signal == 'BUY' else price - tp_distance

        result = self.tm.open_trade(
            order_type=order_type, symbol=config.TRADING_PAIR, volume=config.LOT_SIZE,
            price=price, sl=stop_loss, tp=take_profit, comment="GoldBot vPRO"
        )
        if result:
            log.info(f"Trade executed successfully. Ticket: #{result.order}")
            send_telegram_alert(
                f"🚀 <b>NEW TRADE OPENED ({signal})</b> 🚀\n\n"
                f"<b>Symbol:</b> {config.TRADING_PAIR}\n<b>Price:</b> ${price:,.2f}\n"
                f"<b>Ticket:</b> #{result.order}"
            )
            return True
        return False