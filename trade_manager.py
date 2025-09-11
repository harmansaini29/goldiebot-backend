# FILE: trade_manager.py (Corrected & Professional)
# =============================================================================
#
#   METATRADER 5 CONNECTION & EXECUTION ENGINE
#
# =============================================================================

import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd
import pytz
import time

# --- Core Application Imports ---
import configs as config
from logger import log
from typing import List, Optional

class TradeManager:
    """Handles all interactions with the MetaTrader 5 terminal."""
    def __init__(self):
        self._is_connected = False

    def __enter__(self):
        """Context manager for establishing and VERIFYING the MT5 connection."""
        try:
            if not mt5.initialize(path=config.MT5_PATH, timeout=30):
                log.critical(f"MT5 initialize() failed, error code = {mt5.last_error()}")
                raise ConnectionError("Failed to initialize MT5")
            
            account_info = mt5.account_info()
            if not account_info:
                log.critical("Failed to get account info from MT5.")
                mt5.shutdown()
                raise ConnectionError("Failed to connect to trading account")

            log.info(f"MT5 initialized successfully on account #{account_info.login}")
            
            log.info("Verifying connection health...")
            max_retries = 5
            for i in range(max_retries):
                terminal_info = mt5.terminal_info()
                if terminal_info:
                    log.info("Connection health verified. Terminal is responsive.")
                    self._is_connected = True
                    break
                else:
                    log.warning(f"Connection not fully established. Retrying in 3 seconds... ({i+1}/{max_retries})")
                    time.sleep(3)
            
            if not self._is_connected:
                raise ConnectionError(f"Failed to verify terminal connection after {max_retries} retries.")
            
        except Exception as e:
            log.critical(f"An exception occurred during MT5 initialization: {e}", exc_info=False)
            self._is_connected = False
            if mt5.terminal_info():
                 mt5.shutdown()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager for shutting down the MT5 connection."""
        if self._is_connected:
            mt5.shutdown()
            log.info("MT5 connection shut down.")
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def get_symbol_info(self, symbol: str):
        if not self._is_connected: return None
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                log.error(f"Failed to get info for symbol {symbol}, it may not be visible in Market Watch.")
                return None
            return info
        except Exception as e:
            log.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def fetch_ohlcv(self, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetches OHLCV data and returns a pandas DataFrame."""
        if not self._is_connected: return pd.DataFrame()
        try:
            tf_map = {
                "1m": mt5.TIMEFRAME_M1, "5m": mt5.TIMEFRAME_M5, "15m": mt5.TIMEFRAME_M15,
                "30m": mt5.TIMEFRAME_M30, "1h": mt5.TIMEFRAME_H1, "4h": mt5.TIMEFRAME_H4,
            }
            mt5_timeframe = tf_map.get(timeframe)
            if mt5_timeframe is None:
                log.error(f"Unsupported timeframe: {timeframe}")
                return pd.DataFrame()

            rates = mt5.copy_rates_from_pos(config.TRADING_PAIR, mt5_timeframe, 0, limit)
            if rates is None or len(rates) == 0:
                log.warning("Could not fetch OHLCV data from MT5.")
                return pd.DataFrame()
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            log.error(f"Error fetching OHLCV data: {e}")
            return pd.DataFrame()

    def get_open_positions(self, symbol: str = None, magic: int = None) -> Optional[List]:
        """
        Retrieves all open positions, with optional filters.
        Returns a list of positions on success, or None on connection failure.
        """
        if not self._is_connected: return None
        try:
            positions = mt5.positions_get(symbol=symbol)
            if positions is None:
                # A None result from positions_get indicates a connection issue.
                log.warning("positions_get() returned None. The connection has been lost.")
                return None # <<< THE CRITICAL FIX: Propagate the failure signal.
            
            if magic is not None:
                return [p for p in positions if p.magic == magic]
            return list(positions)
        except Exception as e:
            log.error(f"Error getting open positions: {e}")
            return None

    def get_current_price(self, signal: str) -> Optional[float]:
        if not self._is_connected: return None
        try:
            tick = mt5.symbol_info_tick(config.TRADING_PAIR)
            if tick:
                return tick.ask if signal == 'BUY' else tick.bid
            log.error("Could not get current tick price.")
            return None
        except Exception as e:
            log.error(f"Error getting current price: {e}")
            return None

    def open_trade(self, order_type, symbol, volume, price, sl, tp, comment):
        if not self._is_connected: return None
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        try:
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"Order #{result.order} sent successfully.")
                return result
            else:
                error_code = mt5.last_error()
                log.error(f"Order send failed. Result: {result}. Error code: {error_code}")
                return None
        except Exception as e:
            log.error(f"Exception during order_send: {e}")
            return None

    def close_trade(self, ticket: int) -> bool:
        if not self._is_connected: return False
        try:
            positions = self.get_open_positions()
            # Handle potential connection loss during the operation
            if positions is None:
                log.error(f"Cannot close ticket #{ticket}, connection lost.")
                return False

            position_to_close = next((p for p in positions if p.ticket == ticket), None)
            if not position_to_close:
                log.warning(f"Attempted to close ticket #{ticket}, but it was not found.")
                return True

            order_type = mt5.ORDER_TYPE_SELL if position_to_close.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = self.get_current_price('SELL' if order_type == mt5.ORDER_TYPE_SELL else 'BUY')
            if price is None: return False

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": position_to_close.ticket,
                "symbol": position_to_close.symbol,
                "volume": position_to_close.volume,
                "type": order_type,
                "price": price,
                "deviation": config.DEVIATION,
                "magic": config.MAGIC_NUMBER,
                "comment": "Closed by Bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"Close order for ticket #{ticket} sent successfully.")
                return True
            else:
                log.error(f"Failed to close ticket #{ticket}. Result: {result}. Error: {mt5.last_error()}")
                return False
        except Exception as e:
            log.error(f"Exception while closing trade #{ticket}: {e}")
            return False

    def modify_sl_tp(self, ticket: int, new_sl: float, new_tp: float) -> bool:
        if not self._is_connected: return False
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": float(new_sl),
            "tp": float(new_tp),
        }
        try:
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"Successfully modified SL/TP for ticket #{ticket}.")
                return True
            else:
                log.error(f"Failed to modify SL/TP for #{ticket}. Error: {mt5.last_error()}")
                return False
        except Exception as e:
            log.error(f"Exception during SL/TP modification for #{ticket}: {e}")
            return False
            
    def get_trade_history_for_position(self, position_id: int) -> Optional[pd.DataFrame]:
        if not self._is_connected: return None
        try:
            from_date = datetime.now(tz=pytz.timezone("Etc/UTC")) - pd.Timedelta(days=90)
            history_deals = mt5.history_deals_get(from_date, datetime.now(tz=pytz.timezone("Etc/UTC")))
            
            if history_deals is None:
                log.warning("Could not get trade history from MT5.")
                return None
            
            if len(history_deals) == 0:
                return pd.DataFrame()
            
            deals_df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
            position_deals = deals_df[deals_df['position_id'] == position_id]
            return position_deals if not position_deals.empty else None
        except Exception as e:
            log.error(f"Error fetching trade history for position #{position_id}: {e}")
            return None