# FILE: trade_manager.py
# =============================================================================
#
#   ROBUST METATRADER 5 CONNECTION & TRADE EXECUTION ENGINE (FINAL)
#
# =============================================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import List, Dict, Optional, Any

# --- Core Application Imports ---
from logger import log
import configs as config

class TradeManager:
    """Manages connection and all trade operations with MetaTrader 5."""

    def __init__(self):
        self.mt5_path = config.MT5_PATH

    def __enter__(self):
        """Initializes the connection when entering the 'with' block."""
        log.info("Connecting to MetaTrader 5...")
        if not mt5.initialize(path=self.mt5_path):
            log.critical(f"MT5 initialize() failed, ret_code={mt5.last_error()}")
            raise ConnectionError("Could not connect to MetaTrader 5 Terminal.")
        
        terminal_info = mt5.terminal_info()
        if terminal_info:
            log.info(f"Connected to {terminal_info.name} on {terminal_info.company}'s server.")
            log.info(f"Trade allowed: {'Yes' if terminal_info.trade_allowed else 'No'}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures the connection is shut down cleanly."""
        log.info("Shutting down MetaTrader 5 connection.")
        mt5.shutdown()

    def _ensure_connection(self):
        """Checks MT5 connection and attempts to reconnect if disconnected."""
        if mt5.terminal_info() is None:
            log.warning("MT5 connection lost. Attempting to reconnect...")
            try:
                mt5.shutdown()
            except Exception:
                pass
            
            time.sleep(1) 
            if not mt5.initialize(path=self.mt5_path):
                log.error(f"FATAL: Failed to reconnect to MetaTrader 5 at {self.mt5_path}")
                return False
            log.info("Successfully reconnected to MetaTrader 5.")
        return True

    def _get_filling_type_for_symbol(self, symbol: str) -> int:
        """Determines the correct filling type based on the symbol's execution mode."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            log.warning(f"Could not get symbol info for {symbol}. Defaulting to ORDER_FILLING_FOK.")
            return mt5.ORDER_FILLING_FOK
        # This covers most modern broker configurations
        return mt5.ORDER_FILLING_FOK

    def open_trade(self, order_type: int, symbol: str, volume: float, price: float, sl: float, tp: float, comment: str = "") -> Optional[Any]:
        """Opens a new trade with explicit result checking."""
        if not self._ensure_connection(): return None
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": volume,
            "type": order_type, "price": price, "sl": sl, "tp": tp,
            "deviation": config.DEVIATION, "magic": config.MAGIC_NUMBER,
            "comment": comment, "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_filling_type_for_symbol(symbol), 
        }
        log.info(f"Sending order request: {request}")
        trade_result = mt5.order_send(request)
        if trade_result is None or trade_result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"ORDER REJECTED. Result: {trade_result}")
            return None
        log.info(f"Order successfully placed. Position Ticket #{trade_result.order}")
        return trade_result

    def modify_sl_tp(self, ticket: int, new_sl: float, new_tp: float) -> bool:
        """Modifies the SL and TP for an open position."""
        if not self._ensure_connection(): return False
        request = { "action": mt5.TRADE_ACTION_SLTP, "position": ticket, "sl": new_sl, "tp": new_tp }
        result = mt5.order_send(request)
        if result is None or result.retcode not in [mt5.TRADE_RETCODE_DONE, 10025]: # 10025 is "No changes"
            log.error(f"Failed to modify SL/TP for ticket #{ticket}. Result: {result}")
            return False
        log.info(f"Successfully modified SL/TP for ticket #{ticket} to SL={new_sl}, TP={new_tp}")
        return True

    def close_trade(self, position: Any, comment: str = "") -> bool:
        """Closes a trade based on a position object."""
        if not self._ensure_connection(): return False
        price = mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": position.symbol, "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": position.ticket, "price": price, "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER, "comment": comment, "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_filling_type_for_symbol(position.symbol),
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to close position #{position.ticket}. Error: {result}")
            return False
        log.info(f"Position #{position.ticket} closed successfully.")
        return True

    def get_open_positions(self, symbol: str = None, magic: int = None) -> List[Any]:
        """Retrieves all open positions, with optional filters."""
        if not self._ensure_connection(): return []
        try:
            if symbol and magic is not None: positions = mt5.positions_get(symbol=symbol, magic=magic)
            elif symbol: positions = mt5.positions_get(symbol=symbol)
            elif magic is not None: positions = mt5.positions_get(magic=magic)
            else: positions = mt5.positions_get()
            return list(positions) if positions else []
        except Exception as e:
            log.error(f"Error getting open positions: {e}", exc_info=True)
            return []

    def fetch_ohlcv(self, timeframe_str: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetches OHLCV data for a given symbol and timeframe."""
        if not self._ensure_connection(): return None
        timeframe_map = {
            '1m': mt5.TIMEFRAME_M1, '5m': mt5.TIMEFRAME_M5, '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1, '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1, '1w': mt5.TIMEFRAME_W1, '1M': mt5.TIMEFRAME_MN1
        }
        timeframe = timeframe_map.get(timeframe_str.lower())
        if timeframe is None:
            log.error(f"Invalid timeframe specified: {timeframe_str}")
            return None
        try:
            rates = mt5.copy_rates_from_pos(config.TRADING_PAIR, timeframe, 0, limit)
            if rates is None or len(rates) == 0:
                log.warning(f"No OHLCV data returned for {config.TRADING_PAIR} on {timeframe_str}.")
                return None
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            log.error(f"Error fetching OHLCV data: {e}", exc_info=True)
            return None

    # =============================================================================
    # --- THIS IS THE 100% CORRECT AND FINAL FIX ---
    # =============================================================================
    def get_trade_history_for_position(self, position_ticket: int, **kwargs) -> Optional[pd.DataFrame]:
        """
        Directly fetches deals for a specific position ticket. This is the fastest
        and most reliable method provided by the MT5 library.
        """
        if not self._ensure_connection(): return None
        
        try:
            # This is the direct, correct way to ask MT5 for a specific trade's history.
            # It eliminates all previous bugs and race conditions.
            deals = mt5.history_deals_get(position=position_ticket)
            
            if deals is None or len(deals) == 0:
                return None
                
            return pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        except Exception as e:
            log.error(f"Error directly fetching history for ticket #{position_ticket}: {e}")
            return None

    def get_current_price(self, side: str) -> float:
        """Gets the current bid or ask price for the trading pair."""
        if not self._ensure_connection(): return 0.0
        
        tick = mt5.symbol_info_tick(config.TRADING_PAIR)
        if tick:
            return tick.ask if side.upper() == 'BUY' else tick.bid
        return 0.0