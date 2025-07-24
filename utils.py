import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from ta.volatility import BollingerBands
import logging

# -----------------------------------------------------------------------------
# Utility Module
# -----------------------------------------------------------------------------
# This file contains helper functions used across the trading bot to make
# decisions smarter and the code cleaner.
# -----------------------------------------------------------------------------

# --- Set up a professional logger ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/bot_activity.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger()


def is_market_open() -> bool:
    """
    Checks if it's a weekday. A simple check to avoid running on weekends.
    Note: This doesn't account for market holidays.
    """
    return datetime.today().weekday() < 5 # Monday=0, Sunday=6


def get_trade_mode(symbol: str, timeframe: int) -> str:
    """
    Determines the trade mode ('scalp' or 'swing') based on market volatility.
    Uses Bollinger Band width as a proxy for volatility.

    Args:
        symbol (str): The trading symbol.
        timeframe (int): The MT5 timeframe constant.

    Returns:
        str: 'scalp' for low volatility, 'swing' for high volatility.
    """
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
        if rates is None:
            log.warning("Could not fetch rates for volatility check.")
            return "scalp" # Default to safer mode on error

        df = pd.DataFrame(rates)
        indicator = BollingerBands(close=df['close'], window=20, window_dev=2)
        
        # Calculate the width of the Bollinger Bands
        bb_width = indicator.bollinger_hband() - indicator.bollinger_lband()
        
        # Check the average width over the last 20 periods
        avg_width = bb_width.iloc[-20:].mean()
        
        # Get the symbol's point size for a normalized threshold
        point = mt5.symbol_info(symbol).point
        volatility_threshold = 150 * point # e.g., 15 pips for forex

        if avg_width > volatility_threshold:
            log.info(f"High volatility detected (BB Width: {avg_width:.5f}). Mode: SWING")
            return "swing"
        else:
            log.info(f"Low volatility detected (BB Width: {avg_width:.5f}). Mode: SCALP")
            return "scalp"

    except Exception as e:
        log.error(f"Volatility check failed: {e}")
        return "scalp" # Default to safer mode
