# =============================================================================
#
#   STRATEGY ENGINE (TREND LEVELS ENTRY)
#
# =============================================================================

import pandas as pd
from typing import Dict, Any

# --- Core Application Imports ---
from trade_manager import TradeManager
import indicators
import configs as config
from logger import log, log_trade
from risk_manager import calculate_atr_sl_tp
import state_manager as sm

class TradingStrategy:
    """
    This strategy uses the 'Trend Levels' indicator for trade entries.
    Exit logic is handled separately by the risk manager.
    """
    def __init__(self, trade_manager: TradeManager):
        self.tm = trade_manager
        log.info("TradingStrategy (Trend Levels Entry) initialized.")

    def look_for_new_trade(self):
        """
        Fetches data, calculates the Trend Levels indicator, and executes
        a trade immediately if a BUY or SELL signal is found.
        """
        log.info("Looking for a new trade signal...")

        df = self.tm.fetch_ohlcv(config.TIMEFRAME, limit=200)
        if df is None or df.empty:
            log.warning("Could not fetch market data. Skipping this check.")
            return

        # --- Primary Signal Generation ---
        df_with_signals = indicators.calculate_trend_levels(df, length=config.TREND_LEVELS_LENGTH)
        latest_signal = df_with_signals.iloc[-1]['signal']
        log.info(f"Signal from Trend Levels: {latest_signal}")

        if latest_signal in ['BUY', 'SELL']:
            self.execute_trade(latest_signal, df)

    def execute_trade(self, signal: str, df: pd.DataFrame):
        """
        Calculates an initial SL/TP and executes the trade.
        """
        log.info(f"Actionable Signal Found: {signal}! Executing trade.")
        
        side = 'buy' if signal == 'BUY' else 'sell'
        current_price = self.tm.get_current_price(side)
        if current_price == 0.0:
            log.error("Could not retrieve a valid current price. Aborting trade.")
            return

        # 1. Calculate an initial SL/TP using ATR for order placement
        risk_results = calculate_atr_sl_tp(df, current_price, side)
        if not risk_results:
            log.error("Failed to calculate initial SL/TP. Aborting trade.")
            return
            
        stop_loss = risk_results['sl']
        # Set initial TP based on Gann if available, otherwise use ATR
        df_daily = self.tm.fetch_ohlcv('1d', limit=5)
        gann_levels = indicators.calculate_gann_levels(df_daily, config.GANN_CALCULATION_BASIS)
        
        take_profit = risk_results['tp'] # Default to ATR TP
        if gann_levels:
            gann_side = 'buy_side' if side == 'buy' else 'sell_side'
            initial_tp_key = config.INITIAL_GANN_TP_TARGET
            if initial_tp_key in gann_levels[gann_side]:
                 take_profit = gann_levels[gann_side][initial_tp_key]
                 log.info(f"Setting initial TP to Gann Target '{initial_tp_key}': {take_profit:.2f}")

        log.info(f"Initial Risk - ATR Zone: {risk_results['zone']}. SL: {stop_loss:.2f}, TP: {take_profit:.2f}")

        if config.LOG_TRADES_TO_CSV:
            log_trade(
                symbol=config.TRADING_PAIR, direction=side.upper(), price=current_price,
                sl=stop_loss, tp=take_profit, mode="TREND_LEVELS_ENTRY",
                indicators={"atr": risk_results['atr_value']}
            )

        # 2. Execute the trade
        trade_result = self.tm.enter_trade(
            side=side, lot_size=config.LOT_SIZE, stop_loss=stop_loss,
            take_profit=take_profit, filling_type_str=config.ORDER_FILLING_TYPE
        )

        # 3. Save the trade to the state manager if successful
        if trade_result and trade_result.get('order'):
            sm.save_trade_state(trade_result['order'], {'entry_price': current_price})
