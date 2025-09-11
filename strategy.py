# FILE: strategy.py
# =============================================================================
#
#   STRATEGY ENGINE (REFINED & VERIFIED)
#   - Generates entry and exit signals based on indicator data.
#   - Decoupled from state management for superior logic.
#
# =============================================================================

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

    def get_entry_signal(self) -> str:
        """
        Checks for a new entry signal (BUY, SELL, or HOLD).
        This is the primary logic for initiating a new trade.
        """
        # --- ATR Volatility Filter ---
        if config.USE_ATR_FILTER:
            ohlcv_for_atr = self.tm.fetch_ohlcv(config.TIMEFRAME, limit=config.ATR_PERIOD + 5)
            if ohlcv_for_atr.empty:
                return 'HOLD' # Not enough data
            
            current_atr = ind.calculate_atr(ohlcv_for_atr, config.ATR_PERIOD, self.symbol_info.point)
            log.info(f"Volatility Check: Current ATR = {current_atr:.2f} pips, Required = {config.ATR_THRESHOLD_PIPS} pips.")
            if current_atr < config.ATR_THRESHOLD_PIPS:
                log.info("Trade filtered: Market volatility is too low.")
                return 'HOLD'

        # --- EMA Crossover Entry Signal ---
        df_entry = ind.calculate_ema_crossover_signal(
            self.tm.fetch_ohlcv(config.TIMEFRAME, limit=100),
            fast=config.EMA_FAST_PERIOD, medium=config.EMA_MEDIUM_PERIOD,
            slow=config.EMA_SLOW_PERIOD, point=self.symbol_info.point
        )
        if df_entry.empty:
            return 'HOLD'

        entry_signal = df_entry['signal'].iloc[-1]
        log.info(f"Entry Signal Check: EMA Crossover signal is '{entry_signal}'.")
        return entry_signal

    def get_exit_signal(self) -> str:
        """
        Checks for an exit signal based on the Trend Levels indicator.
        This is used to close an existing trade.
        """
        df_exit = ind.calculate_trend_levels(
            self.tm.fetch_ohlcv(config.TIMEFRAME, limit=config.TREND_LEVELS_LENGTH + 5),
            length=config.TREND_LEVELS_LENGTH
        )
        if df_exit.empty:
            return 'HOLD'

        exit_signal = df_exit['signal'].iloc[-1]
        log.info(f"Exit Signal Check: Trend Reversal signal is '{exit_signal}'.")
        return exit_signal

    def execute_trade(self, signal: str) -> bool:
        """Calculates SL/TP and sends the trade order to the TradeManager."""
        price = self.tm.get_current_price(signal)
        if price is None:
            return False

        # Calculate SL and TP based on configuration
        sl_distance = config.STOP_LOSS_PIPS * config.POINTS_PER_PIP * self.symbol_info.point
        tp_distance = config.TAKE_PROFIT_PIPS * config.POINTS_PER_PIP * self.symbol_info.point
        
        order_type = mt5.ORDER_TYPE_BUY if signal == 'BUY' else mt5.ORDER_TYPE_SELL
        stop_loss = price - sl_distance if signal == 'BUY' else price + sl_distance
        take_profit = price + tp_distance if signal == 'BUY' else price - tp_distance

        # Open the trade via the trade manager
        result = self.tm.open_trade(
            order_type=order_type, symbol=config.TRADING_PAIR, volume=config.LOT_SIZE,
            price=price, sl=stop_loss, tp=take_profit, comment="GoldBot vPRO"
        )
        
        if result and result.order > 0:
            log.info(f"Trade executed successfully. Ticket: #{result.order}")
            # Save the new trade to our state file immediately
            sm.save_trade_state(result.order, {
                'entry_price': price, 'signal': signal, 'entry_type': 'EMA_Crossover'
            })
            send_telegram_alert(
                f"🚀 <b>NEW TRADE OPENED ({signal})</b> 🚀\n\n"
                f"<b>Symbol:</b> {config.TRADING_PAIR}\n<b>Price:</b> ${price:,.2f}\n"
                f"<b>Ticket:</b> #{result.order}"
            )
            return True
        return False