# FILE: trade_manager.py (Professionally Corrected)
# =============================================================================

from __future__ import annotations
import time
import MetaTrader5 as mt5
import pandas as pd
from typing import List, Optional, Any

from logger import log
import configs as config

class TradeManager:
    """
    A context manager to handle the MT5 connection, symbol resolution,
    and all trade execution and history-related tasks.
    """
    def __init__(self):
        self.trading_pair: str = config.TRADING_PAIR
        self.symbol_info: mt5.SymbolInfo | None = None

    def __enter__(self) -> TradeManager:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        try:
            if not mt5.initialize(path=config.MT5_PATH, timeout=60000):
                raise ConnectionError(f"MT5 initialize() failed: {mt5.last_error()}")

            account_info = mt5.account_info()
            if not account_info:
                raise ConnectionError(f"MT5 account_info() failed: {mt5.last_error()}")

            log.info(f"MT5 initialized successfully on account #{account_info.login}")
            self._resolve_and_prepare_symbol()
            self.verify_connection_health()

        except Exception as e:
            log.critical(f"MT5 connect error: {e}")
            raise

    def _resolve_and_prepare_symbol(self):
        info = mt5.symbol_info(self.trading_pair)
        if info is None:
            log.warning(f"Symbol '{self.trading_pair}' not found. Attempting auto-resolve...")
            resolved_symbol = self._auto_resolve_symbol(self.trading_pair)
            if not resolved_symbol:
                raise ValueError(f"Could not resolve TRADING_PAIR '{self.trading_pair}'")
            self.trading_pair = resolved_symbol
            log.info(f"Auto-resolved trading pair to '{self.trading_pair}'")
            info = mt5.symbol_info(self.trading_pair)

        if not info.visible:
            log.info(f"Symbol '{self.trading_pair}' not visible. Enabling in Market Watch...")
            if not mt5.symbol_select(self.trading_pair, True):
                raise ConnectionError(f"Failed to enable symbol '{self.trading_pair}'")
            time.sleep(1) 
            info = mt5.symbol_info(self.trading_pair)
        
        self.symbol_info = info
        log.info(f"Successfully prepared symbol '{self.trading_pair}'.")

    def _auto_resolve_symbol(self, base: str) -> str | None:
        all_symbols = mt5.symbols_get()
        if not all_symbols: return None
        base_low = base.lower()
        matches = [s.name for s in all_symbols if s.name.lower().startswith(base_low)]
        return matches[0] if matches else None

    def disconnect(self):
        mt5.shutdown()
        log.info("MT5 connection shut down.")

    def is_connected(self) -> bool:
        return mt5.terminal_info() is not None

    def verify_connection_health(self):
        if not self.is_connected():
            raise ConnectionError("Terminal connection is unhealthy or disconnected.")
        log.info("Connection health verified. Terminal is responsive.")

    def get_current_price(self, signal: str) -> float:
        tick = mt5.symbol_info_tick(self.trading_pair)
        if not tick:
            raise RuntimeError(f"Failed to fetch tick data for {self.trading_pair}")
        return tick.ask if signal.upper() == "BUY" else tick.bid

    def get_open_positions(self) -> List[Any] | None:
        for attempt in range(3):
            try:
                positions = mt5.positions_get(symbol=self.trading_pair)
                if positions is not None:
                    return list(positions)
                log.warning(f"positions_get() returned None (Attempt {attempt+1}/3). MT5 error={mt5.last_error()}")
                time.sleep(1.5)
            except Exception as e:
                log.error(f"positions_get() raised an exception: {e}", exc_info=True)
        log.error("get_open_positions failed after all attempts.")
        return None

    def fetch_ohlcv(self, timeframe_str: str, limit: int = 100) -> pd.DataFrame:
        timeframe_map = {
            '1m': mt5.TIMEFRAME_M1, '5m': mt5.TIMEFRAME_M5, '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1, '4h': mt5.TIMEFRAME_H4,
        }
        timeframe = timeframe_map.get(timeframe_str.lower(), mt5.TIMEFRAME_M30)
        rates = mt5.copy_rates_from_pos(self.trading_pair, timeframe, 0, limit)
        if rates is None:
            log.warning(f"copy_rates_from_pos failed for '{self.trading_pair}'.")
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def open_trade(self, order_type, symbol, volume, price, sl, tp, comment) -> mt5.TradeResult | None:
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": volume,
            "type": order_type, "price": price, "sl": sl, "tp": tp,
            "deviation": config.DEVIATION, "magic": config.MAGIC_NUMBER,
            "comment": comment, "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order failed: {result.comment if result else mt5.last_error()}")
            return None
        
        log.info(f"Trade executed successfully: ticket=#{result.order}, price={result.price}")
        return result

    def close_trade(self, ticket: int) -> bool:
        positions = self.get_open_positions()
        if not positions:
            log.error(f"close_trade failed: Cannot find ticket #{ticket} or fetch positions.")
            return False

        position_to_close = next((p for p in positions if p.ticket == ticket), None)
        if not position_to_close:
            log.warning(f"close_trade: ticket #{ticket} not found among open positions.")
            return False
        
        order_type = mt5.ORDER_TYPE_SELL if position_to_close.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = self.get_current_price('SELL' if order_type == mt5.ORDER_TYPE_SELL else 'BUY')

        request = {
            "action": mt5.TRADE_ACTION_DEAL, "position": ticket,
            "symbol": position_to_close.symbol, "volume": position_to_close.volume,
            "type": order_type, "price": price, "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER, "comment": "Closed by Bot",
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"Successfully closed ticket #{ticket}")
            return True
        log.error(f"Failed to close ticket #{ticket}: {result.comment if result else mt5.last_error()}")
        return False

    # --- THIS FUNCTION HAS BEEN FIXED ---
    def modify_sl_tp(self, ticket: int, new_sl: float = 0.0, new_tp: float = 0.0) -> bool:
        """
        Modifies the Stop Loss and/or Take Profit for an open position.
        Returns True on success, False on failure.
        """
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp
        }
        result = mt5.order_send(request)
        
        # Check if the result is valid and the return code indicates success
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return True
        
        # Log the error if the modification failed
        log.error(f"modify_sl_tp failed for #{ticket}: {result.comment if result else mt5.last_error()}")
        return False
    # ------------------------------------

    def get_trade_history_for_position(self, position_id: int) -> pd.DataFrame | None:
        deals = mt5.history_deals_get(position=position_id)
        return pd.DataFrame(list(deals), columns=deals[0]._asdict().keys()) if deals else None