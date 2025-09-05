# FILE: trade_manager.py
# =============================================================================
#
#   ROBUST METATRADER 5 CONNECTION & TRADE EXECUTION ENGINE (PROFESSIONAL & FINAL)
#
# =============================================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Any

# --- Core Application Imports ---
from logger import log
import configs as config

class TradeManager:
    """
    Manages the connection and all trade operations with MetaTrader 5
    using a robust context manager pattern.
    """
    def __init__(self):
        """Initializes the TradeManager."""
        self.mt5_path = config.MT5_PATH
        self._connected = False

    def __enter__(self):
        """Initializes the connection when entering the 'with' block."""
        log.info("Connecting to MetaTrader 5...")
        if not mt5.initialize(path=self.mt5_path):
            log.critical(f"MT5 initialize() failed, error code={mt5.last_error()}")
            raise ConnectionError("Could not connect to MetaTrader 5 Terminal.")
        
        terminal_info = mt5.terminal_info()
        if terminal_info:
            log.info(f"Connected to {terminal_info.name} on {terminal_info.company}'s server.")
            log.info(f"Trade allowed: {'Yes' if terminal_info.trade_allowed else 'No'}")
            self._connected = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Shuts down the connection when exiting the 'with' block."""
        log.info("Shutting down MetaTrader 5 connection.")
        mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        """
        Public method to check the connection status.
        Crucial for the initial cleanup process in main.py.
        """
        return self._connected and mt5.terminal_info() is not None

    def _ensure_connection(self) -> bool:
        """Checks if the MT5 terminal is still connected and attempts to reconnect if not."""
        if self.is_connected():
            return True
            
        log.warning("MT5 connection lost. Attempting to reconnect...")
        if mt5.initialize(path=self.mt5_path):
            log.info("Reconnected to MT5 successfully.")
            self._connected = True
            return True
        else:
            log.critical(f"Failed to reconnect to MT5. Error code={mt5.last_error()}")
            self._connected = False
            return False

    def get_symbol_info(self, symbol: str) -> Optional[Any]:
        """Fetches information for a specific trading symbol."""
        if not self._ensure_connection(): return None
        
        info = mt5.symbol_info(symbol)
        if not info:
            log.error(f"Failed to find symbol {symbol}")
            return None
        return info

    def fetch_ohlcv(self, timeframe_str: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """Fetches OHLCV data for the configured trading pair."""
        if not self._ensure_connection(): return None
        
        timeframe_map = {
            '1m': mt5.TIMEFRAME_M1, '5m': mt5.TIMEFRAME_M5, '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1, '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1
        }
        timeframe = timeframe_map.get(timeframe_str.lower())
        if timeframe is None:
            log.error(f"Unsupported timeframe: {timeframe_str}")
            return None
            
        try:
            rates = mt5.copy_rates_from_pos(config.TRADING_PAIR, timeframe, 0, limit)
            if rates is None: return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            log.error(f"Error fetching OHLCV data: {e}")
            return None

    # --- UPDATED & REFACTORED METHOD ---
    def get_open_positions(self, magic: Optional[int] = None) -> List[Any]:
        """
        Retrieves open positions. If magic is None, returns all positions for the symbol.
        If magic is specified, it filters by that magic number.
        """
        if not self._ensure_connection(): 
            return []
        
        try:
            positions = mt5.positions_get(symbol=config.TRADING_PAIR)
            
            if positions is None:
                log.error(f"Failed to get positions for {config.TRADING_PAIR}, error code={mt5.last_error()}")
                return []

            # If a magic number is specified, filter the results in Python
            if magic is not None:
                return [p for p in positions if p.magic == magic]
            
            # Otherwise, return all positions for the symbol
            return list(positions)

        except Exception as e:
            log.error(f"An exception occurred while getting open positions: {e}", exc_info=True)
            return []

    def open_trade(self, order_type, symbol, volume, price, sl, tp, comment):
        """Places a new market order."""
        if not self._ensure_connection(): return None
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order send failed, retcode={result.retcode}, comment={result.comment}")
            return None
        return result

    # --- UPDATED METHOD TO BE SAFER ---
    def close_trade(self, ticket: int) -> bool:
        """Closes an open position by its ticket number."""
        if not self._ensure_connection(): return False
        
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            log.warning(f"Attempted to close ticket #{ticket}, but it was not found (already closed).")
            return True 
            
        position = positions[0]
        order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        # Explicitly check for price retrieval failure
        price = self.get_current_price('SELL' if order_type == mt5.ORDER_TYPE_SELL else 'BUY')
        if price is None:
            log.error(f"Cannot close ticket #{ticket} because the current price could not be fetched.")
            return False
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": order_type,
            "price": price,
            "deviation": config.DEVIATION,
            "magic": position.magic, # Use the original magic number for closure
            "comment": "Close Position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to close ticket #{ticket}, retcode={result.retcode}, comment={result.comment}")
            return False
        return True

    def modify_sl_tp(self, ticket: int, new_sl: float, new_tp: float) -> bool:
        """Modifies the Stop Loss and/or Take Profit of an open position."""
        if not self._ensure_connection(): return False
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to modify SL/TP for ticket #{ticket}, retcode={result.retcode}, comment={result.comment}")
            return False
        return True

    def get_trade_history_for_position(self, position_ticket: int) -> Optional[pd.DataFrame]:
        """Directly fetches all deals related to a specific position ticket."""
        if not self._ensure_connection(): return None
        
        try:
            deals = mt5.history_deals_get(position=position_ticket)
            if deals is None or len(deals) == 0:
                return None
            return pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        except Exception as e:
            log.error(f"Error fetching history for ticket #{position_ticket}: {e}")
            return None

    # --- UPDATED METHOD TO RETURN NONE ON FAILURE ---
    def get_current_price(self, side: str) -> Optional[float]:
        """Gets the current bid or ask price for the trading pair. Returns None on failure."""
        if not self._ensure_connection(): return None
        
        tick = mt5.symbol_info_tick(config.TRADING_PAIR)
        if tick:
            return tick.ask if side.upper() == 'BUY' else tick.bid
            
        log.warning(f"Could not retrieve latest tick data for {config.TRADING_PAIR}.")
        return None