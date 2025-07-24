# =============================================================================
#
#   STRATEGY ENGINE (UPDATED)
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

class TradingStrategy:
    """
    Encapsulates the trading logic, from signal generation to execution.
    """
    def __init__(self, trade_manager: TradeManager):
        self.tm = trade_manager
        log.info("TradingStrategy initialized and ready.")

    def look_for_new_trade(self):
        """
        The main decision-making function. Fetches data, runs indicators,
        and triggers a trade if conditions are met.
        """
        log.info("Looking for a new trade signal...")

        df = self.tm.fetch_ohlcv(config.TIMEFRAME, limit=200)
        if df is None or df.empty:
            log.warning("Could not fetch market data. Skipping this check.")
            return

        # --- Primary Signal Generation ---
        df_with_signals = indicators.calculate_trend_levels(df, length=config.TREND_LEVELS_LENGTH)
        latest_signal = df_with_signals.iloc[-1]['signal']
        log.info(f"Latest Signal from Trend Levels: {latest_signal}")

        if latest_signal in ['BUY', 'SELL']:
            # Pass the DataFrame with all indicator data to the execution function
            self.execute_trade(latest_signal, df_with_signals)
        else:
            # Signal is 'HOLD', do nothing.
            pass


    def execute_trade(self, signal: str, df: pd.DataFrame):
        """
        Handles the process of entering a trade once a signal is confirmed.
        This includes risk calculation, logging, and placing the order.
        """
        # --- Safety Check: Ensure no other trade is already open by this bot ---
        if self.tm.get_open_positions():
            log.info(f"Signal '{signal}' received, but a trade is already open. Skipping.")
            return

        log.info(f"Actionable Signal Found: {signal}! Preparing to enter trade.")

        side = 'buy' if signal == 'BUY' else 'sell'
        
        # CORRECTED: Pass the 'side' to get the correct bid/ask price.
        current_price = self.tm.get_current_price(side)
        if current_price == 0.0:
            log.error("Could not retrieve a valid current price (0.0). Aborting trade.")
            return

        # 1. Calculate SL/TP using the ATR-based risk manager.
        risk_results = calculate_atr_sl_tp(df, current_price, side)

        if not risk_results or risk_results.get('sl') == 0.0:
            log.error("Failed to calculate valid SL/TP from risk manager. Aborting trade.")
            return

        stop_loss = risk_results['sl']
        take_profit = risk_results['tp']

        log.info(f"ATR Zone: {risk_results['zone']}. SL Multiplier: {risk_results['sl_mult']}, TP Multiplier: {risk_results['tp_mult']}.")

        # 2. Log the trade decision to the CSV file if enabled.
        if config.LOG_TRADES_TO_CSV:
            indicators_snapshot = {"atr": risk_results['atr_value']}
            log_trade(
                symbol=config.TRADING_PAIR,
                direction=side.upper(),
                price=current_price,
                sl=stop_loss,
                tp=take_profit,
                mode=f"ATR_{risk_results['zone'].upper()}",
                indicators=indicators_snapshot
            )

        # 3. Execute the trade via the TradeManager.
        # CORRECTED: The parameter name now matches the function definition.
        self.tm.enter_trade(
            side=side,
            lot_size=config.LOT_SIZE,
            stop_loss=stop_loss,
            take_profit=take_profit,
            filling_type_str=config.ORDER_FILLING_TYPE
        )