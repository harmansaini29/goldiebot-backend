# FILE: strategy.py
# =============================================================================
#
#   CORE TRADING STRATEGY LOGIC (FINAL)
#
# =============================================================================

import MetaTrader5 as mt5
import time

# --- Core Application Imports ---
from logger import log
import configs as config
from trade_manager import TradeManager
import indicators
import state_manager as sm
from notifier import send_telegram_alert

class TradingStrategy:
    def __init__(self, tm: TradeManager):
        self.tm = tm

    def check_and_execute(self, open_positions):
        """
        The core logic unit. Fetches data, calculates indicators, and decides
        whether to open, close, or reverse a trade.
        """
        log.info("Strategy: Running checks...")
        
        df = self.tm.fetch_ohlcv(config.TIMEFRAME, limit=100)
        if df is None or df.empty:
            log.warning("Strategy: Could not fetch data for analysis. Skipping cycle.")
            return

        df = indicators.calculate_trend_levels(df, config.TREND_LEVELS_LENGTH)
        latest_candle = df.iloc[-2]
        signal = latest_candle['signal']
        
        has_open_position = bool(open_positions)
        current_position = open_positions[0] if has_open_position else None

        log.info(f"Strategy: Has open position: {has_open_position}. Latest Signal: {signal}")

        if not has_open_position and signal in ['BUY', 'SELL']:
            self._execute_new_trade(signal)

        elif has_open_position:
            is_buy_position = current_position.type == mt5.ORDER_TYPE_BUY
            
            if is_buy_position and signal == 'SELL':
                log.info(f"Reversal Signal: Closing BUY position #{current_position.ticket} to open a SELL.")
                self.tm.close_trade(current_position, comment="Reversal to SELL")
                time.sleep(config.REVERSAL_DELAY_SECONDS)
                self._execute_new_trade('SELL')

            elif not is_buy_position and signal == 'BUY':
                log.info(f"Reversal Signal: Closing SELL position #{current_position.ticket} to open a BUY.")
                self.tm.close_trade(current_position, comment="Reversal to BUY")
                time.sleep(config.REVERSAL_DELAY_SECONDS)
                self._execute_new_trade('BUY')

    def _execute_new_trade(self, signal: str):
        """Handles the logic for opening a single new trade."""
        df_daily = self.tm.fetch_ohlcv('1d', limit=5)
        if df_daily is None or df_daily.empty:
            log.error("Strategy: Could not fetch daily data for Gann levels. Aborting trade.")
            return
            
        gann_levels = indicators.calculate_gann_levels(df_daily, config.GANN_CALCULATION_BASIS)
        if not gann_levels:
            log.error("Strategy: Gann levels could not be calculated. Aborting trade.")
            return

        side_key = 'buy_side' if signal == 'BUY' else 'sell_side'
        order_type = mt5.ORDER_TYPE_BUY if signal == 'BUY' else mt5.ORDER_TYPE_SELL
        price = self.tm.get_current_price('buy' if signal == 'BUY' else 'sell')

        if price == 0.0:
            log.error("Strategy: Could not retrieve current price. Aborting trade.")
            return

        try:
            take_profit = gann_levels[side_key]['target_1']
        except KeyError:
            log.error(f"Strategy: Gann levels are missing for '{side_key}'. Cannot place trade.")
            return
        
        comment = f"{signal} by Trend Reversal"
        
        trade_result = self.tm.open_trade(
            order_type=order_type,
            symbol=config.TRADING_PAIR,
            volume=config.LOT_SIZE,
            price=price,
            sl=0.0, # No Stop Loss as per your requirement
            tp=take_profit,
            comment=comment
        )

        if trade_result:
            # --- CORRECTED LOGIC ---
            # The trade's unique Ticket ID is in the .order field of the result.
            ticket_id = trade_result.order 
            
            sm.save_trade_state(ticket_id, {
                'entry_price': price,
                'signal': signal,
                'entry_type': 'Trend Reversal',
                'tp_level': take_profit,
                'sl_level': 0.0
            })
            
            log.info(f"TRADE EXECUTED and state saved for ticket #{ticket_id}.")
            send_telegram_alert(
                f"🚀 <b>NEW TRADE OPENED</b> 🚀\n\n"
                f"<b>Ticket:</b> #{ticket_id}\n"
                f"<b>Type:</b> {signal}\n"
                f"<b>Entry Price:</b> {price:.5f}\n"
                f"<b>Take Profit:</b> {take_profit:.5f}"
            )
        else:
            log.critical(f"STRATEGY ALERT: FAILED to execute {signal} trade. The broker rejected the order.")
            send_telegram_alert(f"🚨 <b>TRADE FAILED</b> 🚨\n\nBroker rejected {signal} order for {config.TRADING_PAIR}. Check logs.")