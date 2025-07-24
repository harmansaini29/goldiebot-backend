# =============================================================================
#
#   METATRADER 5 TRADE MANAGER (UPDATED)
#
# =============================================================================

import MetaTrader5 as mt5
import pandas as pd
from typing import Dict, Optional, List, Any

# --- Core Application Imports ---
from logger import log
from notifier import send_telegram_alert
import configs as config

class TradeManager:
    """
    A context manager to handle the MT5 connection and trading operations.
    """
    def __init__(self):
        """Initializes the TradeManager with settings from the config file."""
        self.trade_pair = config.TRADING_PAIR
        self.magic_number = config.MAGIC_NUMBER
        self.deviation = config.DEVIATION
        self.is_initialized = False

    def __enter__(self):
        """Initializes the MT5 connection when entering the 'with' block."""
        # CORRECTED: Handle both automatic (None) and specified MT5 paths
        initialized = mt5.initialize(path=config.MT5_PATH) if config.MT5_PATH else mt5.initialize()
        
        if not initialized:
            log.critical(f"MT5 initialize() failed, error code = {mt5.last_error()}")
            send_telegram_alert("<b>CRITICAL ERROR</b>: Bot failed to connect to MT5 terminal.")
            raise SystemExit("Could not initialize MT5 connection. Exiting.")

        log.info(f"MT5 initialized successfully. Version: {mt5.version()}")
        self._verify_symbol()
        self.is_initialized = True
        log.info(f"TradeManager ready for symbol: {self.trade_pair}")
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Shuts down the MT5 connection when exiting the 'with' block."""
        if self.is_initialized:
            mt5.shutdown()
            log.info("MT5 connection shut down successfully.")

    def _verify_symbol(self):
        """Checks if the trading symbol is available and visible in Market Watch."""
        symbol_info = mt5.symbol_info(self.trade_pair)
        if not symbol_info:
            log.critical(f"Symbol {self.trade_pair} not found. Ensure it's in Market Watch.")
            raise SystemExit(f"Symbol {self.trade_pair} not found. Exiting.")

        if not symbol_info.visible:
            log.warning(f"Symbol {self.trade_pair} not visible, attempting to enable...")
            if not mt5.symbol_select(self.trade_pair, True):
                log.critical(f"Failed to enable symbol {self.trade_pair}. Exiting.")
                raise SystemExit(f"Could not enable symbol {self.trade_pair}. Exiting.")
            log.info(f"Symbol {self.trade_pair} enabled successfully.")

    def fetch_ohlcv(self, timeframe_str: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """Fetches OHLCV data for the specified timeframe."""
        timeframe_map = {
            '1m': mt5.TIMEFRAME_M1, '5m': mt5.TIMEFRAME_M5, '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1, '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1
        }
        mt5_timeframe = timeframe_map.get(timeframe_str)
        if mt5_timeframe is None:
            log.error(f"Unsupported timeframe provided: '{timeframe_str}'")
            return None

        rates = mt5.copy_rates_from_pos(self.trade_pair, mt5_timeframe, 0, limit)
        if rates is None:
            log.error(f"Failed to get rates for {self.trade_pair}. Error: {mt5.last_error()}")
            return None
            
        df = pd.DataFrame(rates)
        df['timestamp'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    def get_current_price(self, side: str) -> float:
        """Fetches the correct price based on trade direction (ask for buy, bid for sell)."""
        tick = mt5.symbol_info_tick(self.trade_pair)
        if tick is None: return 0.0
        return tick.ask if side == 'buy' else tick.bid

    def enter_trade(self, side: str, lot_size: float, stop_loss: float, take_profit: float, filling_type_str: str) -> Optional[Dict[str, Any]]:
        """Constructs and sends a trade order to MT5."""
        order_type = mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL
        price = self.get_current_price(side)

        filling_type_map = {
            "FOK": mt5.ORDER_FILLING_FOK,
            "IOC": mt5.ORDER_FILLING_IOC,
            "RETURN": mt5.ORDER_FILLING_RETURN
        }
        filling_type = filling_type_map.get(filling_type_str.upper())
        if filling_type is None:
            log.error(f"Invalid ORDER_FILLING_TYPE in config: '{filling_type_str}'. Aborting trade.")
            return None

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.trade_pair,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": round(stop_loss, 5),
            "tp": round(take_profit, 5),
            "deviation": self.deviation,      # IMPROVEMENT: Using value from config
            "magic": self.magic_number,       # IMPROVEMENT: Using value from config
            "comment": "Python Bot Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        log.info(f"Sending trade to MT5: {side.upper()} {lot_size} lots of {self.trade_pair} at {price:.5f}")
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order failed! Code: {result.retcode}, Comment: {result.comment}, Request: {result.request._asdict()}")
            send_telegram_alert(f"🚨 <b>TRADE FAILED</b> 🚨\n\n<b>Symbol:</b> {self.trade_pair}\n<b>Reason:</b> {result.comment}")
            return None
        
        log.info(f"Order successful! Ticket: {result.order}, Price: {result.price}, Volume: {result.volume}")
        alert_msg = f"✅ <b>TRADE EXECUTED</b> ✅\n\n<b>Symbol:</b> {self.trade_pair}\n<b>Type:</b> {side.upper()}\n<b>Lots:</b> {lot_size}\n<b>Price:</b> {result.price:.5f}\n<b>SL:</b> {stop_loss:.5f}\n<b>TP:</b> {take_profit:.5f}"
        send_telegram_alert(alert_msg)
        return result._asdict()

    def get_open_positions(self) -> List[mt5.TradePosition]:
        """ CRITICAL FIX: Fetches only open positions matching the bot's magic number. """
        positions = mt5.positions_get(symbol=self.trade_pair)
        if positions is None:
            log.error(f"Failed to get positions for {self.trade_pair}. Error: {mt5.last_error()}")
            return []
            
        # Filter positions to only those opened by this bot instance
        return [p for p in positions if p.magic == self.magic_number]

    def modify_sl_tp(self, ticket: int, new_sl: float, new_tp: float):
        """Updates the Stop Loss and Take Profit for an existing position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": round(new_sl, 5),
            "tp": round(new_tp, 5),
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"Successfully modified Ticket {ticket}: New SL={new_sl:.5f}")
            send_telegram_alert(f"⚙️ <b>TRAILING STOP UPDATE</b> ⚙️\n\n<b>Ticket:</b> {ticket}\n<b>New SL:</b> {new_sl:.5f}")
        else:
            log.warning(f"Could not modify Ticket {ticket}: {result.comment} | Code: {result.retcode}")