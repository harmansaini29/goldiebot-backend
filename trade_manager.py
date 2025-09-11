# FILE: trade_manager.py (UPGRADED FOR RESILIENCE)
# =============================================================================
#
#   MANAGES ALL INTERACTIONS WITH THE METATRADER 5 TERMINAL
#   - Establishes and verifies connection.
#   - Fetches market data and account information.
#   - Executes, modifies, and closes trades.
#
# =============================================================================

import MetaTrader5 as mt5
import pandas as pd
import time
from typing import List, Optional, Dict, Any

# --- Core Application Imports ---
from logger import log
import configs as config

class TradeManager:
    """A context manager to handle the MT5 connection lifecycle."""
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        """Initializes the connection to the MetaTrader 5 terminal."""
        try:
            # UPGRADE: Increased timeout to 60 seconds (60000 ms) for stability.
            if not mt5.initialize(path=config.MT5_PATH, timeout=60000):
                log.critical(f"MT5 initialize() failed, error code = {mt5.last_error()}")
                raise ConnectionError("Failed to initialize MT5")

            login_info = mt5.account_info()
            if not login_info:
                raise ConnectionError("Failed to get account info")

            log.info(f"MT5 initialized successfully on account #{login_info.login}")
            self.verify_connection_health()

        except Exception as e:
            log.critical(f"An exception occurred during MT5 initialization: {e}")
            self.connected = False
            # Propagate the error to be handled by the main loop's recovery logic
            raise ConnectionError("Failed to initialize MT5") from e

    def disconnect(self):
        """Shuts down the connection to the MetaTrader 5 terminal."""
        mt5.shutdown()
        log.info("MT5 connection shut down.")

    def is_connected(self) -> bool:
        """Simple check based on terminal info."""
        return mt5.terminal_info() is not None

    def verify_connection_health(self):
        """Performs a quick check to ensure the terminal is responsive."""
        log.info("Verifying connection health...")
        if not mt5.terminal_info():
            raise ConnectionError("Connection health check failed: Terminal info is None.")
        log.info("Connection health verified. Terminal is responsive.")
    
    # =========================================================================
    # UPGRADED FUNCTION WITH RETRY LOGIC
    # =========================================================================
    def get_open_positions(self, symbol: str = None, magic: int = None) -> List[Any]:
        """
        Fetches open positions with a retry mechanism to handle terminal freezes.
        """
        for attempt in range(3): # Try up to 3 times
            positions = mt5.positions_get(symbol=symbol, magic=magic)
            if positions is not None:
                return list(positions)
            
            # If positions is None, the connection dropped.
            log.warning(f"positions_get() returned None (Attempt {attempt + 1}/3). Retrying in 2 seconds...")
            time.sleep(2)

        log.error("Failed to get open positions after 3 attempts. Assuming connection is lost.")
        return None # Return None to trigger self-healing in main.py

    def get_symbol_info(self, symbol: str) -> Optional[Any]:
        """Fetches detailed information for a specific symbol."""
        info = mt5.symbol_info(symbol)
        if not info:
            log.error(f"Failed to get symbol_info for {symbol}")
            return None
        return info

    def fetch_ohlcv(self, timeframe_str: str, limit: int = 100) -> pd.DataFrame:
        """Fetches OHLCV data for the configured trading pair."""
        timeframe_map = {
            '1m': mt5.TIMEFRAME_M1, '5m': mt5.TIMEFRAME_M5, '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1, '4h': mt5.TIMEFRAME_H4,
        }
        timeframe = timeframe_map.get(timeframe_str.lower(), mt5.TIMEFRAME_M30)
        
        try:
            rates = mt5.copy_rates_from_pos(config.TRADING_PAIR, timeframe, 0, limit)
            if rates is None:
                log.warning(f"copy_rates_from_pos failed for {config.TRADING_PAIR}. Error: {mt5.last_error()}")
                return pd.DataFrame()

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            log.error(f"Error fetching OHLCV data: {e}", exc_info=True)
            return pd.DataFrame()

    def execute_trade(self, signal: str, lot_size: float, sl_pips: int, tp_pips: int) -> Optional[Dict[str, Any]]:
        """Places a trade order with specified SL and TP."""
        symbol = config.TRADING_PAIR
        point = self.get_symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask if signal == 'BUY' else mt5.symbol_info_tick(symbol).bid
        
        sl_points = sl_pips * config.POINTS_PER_PIP
        tp_points = tp_pips * config.POINTS_PER_PIP

        if signal == 'BUY':
            order_type = mt5.ORDER_TYPE_BUY
            stop_loss = price - sl_points * point
            take_profit = price + tp_points * point
        else: # SELL
            order_type = mt5.ORDER_TYPE_SELL
            stop_loss = price + sl_points * point
            take_profit = price - tp_points * point
            
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER,
            "comment": "GoldBot vPRO",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order send failed: {result.comment if result else 'None returned'}")
            return None
        
        log.info(f"Trade executed successfully: Ticket #{result.order}")
        return {'ticket': result.order, 'entry_price': result.price}

    def close_trade(self, ticket: int) -> bool:
        """Closes a trade based on its ticket number."""
        positions = self.get_open_positions()
        if positions is None: return False

        for pos in positions:
            if pos.ticket == ticket:
                symbol = pos.symbol
                volume = pos.volume
                order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": order_type,
                    "position": ticket,
                    "price": price,
                    "deviation": config.DEVIATION,
                    "magic": config.MAGIC_NUMBER,
                    "comment": "Closed by GoldBot",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    log.info(f"Successfully sent close order for ticket #{ticket}.")
                    return True
                else:
                    log.error(f"Failed to close ticket #{ticket}. Reason: {result.comment if result else 'None returned'}")
                    return False
        log.warning(f"Could not close trade: Ticket #{ticket} not found in open positions.")
        return False

    def modify_sl_tp(self, ticket: int, new_sl: float = 0.0, new_tp: float = 0.0):
        """Modifies the Stop Loss and/or Take Profit for an open position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp,
        }
        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to modify SL/TP for ticket #{ticket}. Reason: {result.comment if result else 'None returned'}")
        
    def get_trade_history_for_position(self, position_id: int) -> Optional[pd.DataFrame]:
        """Fetches all historical deals associated with a given position ID."""
        try:
            deals = mt5.history_deals_get(position=position_id)
            if deals is None or len(deals) == 0:
                return None
            return pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        except Exception as e:
            log.error(f"Error fetching history for position #{position_id}: {e}")
            return None