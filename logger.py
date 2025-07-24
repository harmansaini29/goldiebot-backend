# =============================================================================
#
#   LOGGING & NOTIFICATION MODULE
#
# -----------------------------------------------------------------------------
#   This module centralizes all logging functionalities. It sets up a
#   primary application logger for console/file output and a secondary
#   logger for recording trade decisions to a structured CSV file.
#
# =============================================================================

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any

# --- Constants ---
LOGS_DIR = Path("logs")
LOG_FILE = LOGS_DIR / "trading_bot.log"
TRADES_LOG_FILE = LOGS_DIR / "trades_log.csv"

# =============================================================================
# SECTION 1: APPLICATION LOGGER
# =============================================================================
# For general status updates, warnings, and errors.

def setup_logger() -> logging.Logger:
    """
    Configures and returns a professional logger that writes to both the
    console and a log file.
    """
    # Ensure the logs directory exists
    LOGS_DIR.mkdir(exist_ok=True)

    log = logging.getLogger("TradingBot")
    log.setLevel(logging.INFO)

    # Prevent duplicate handlers if this function is called multiple times
    if log.hasHandlers():
        log.handlers.clear()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Create file handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    # Create console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    return log

# --- Global logger instance ---
log = setup_logger()


# =============================================================================
# SECTION 2: CSV TRADE LOGGER
# =============================================================================
# For recording every trade decision for later analysis.

def log_trade(symbol: str, direction: str, price: float, sl: float, tp: float, mode: str, indicators: Dict[str, Any]):
    """
    Logs the details of an executed or attempted trade to a CSV file.
    If the file doesn't exist, it creates it with the correct headers.
    """
    try:
        # Ensure the logs directory exists
        LOGS_DIR.mkdir(exist_ok=True)
        
        file_exists = TRADES_LOG_FILE.exists()
        
        trade_data = {
            "timestamp": pd.Timestamp.now(),
            "symbol": symbol,
            "direction": direction,
            "entry_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "trade_mode": mode,
            "indicators": str(indicators) # Store dict as a string
        }
        
        df = pd.DataFrame([trade_data])
        
        if not file_exists:
            log.info(f"Trade log file not found. Creating {TRADES_LOG_FILE}...")
            df.to_csv(TRADES_LOG_FILE, index=False, header=True)
        else:
            df.to_csv(TRADES_LOG_FILE, mode='a', index=False, header=False)
            
        log.info(f"Successfully logged trade for {symbol} to {TRADES_LOG_FILE}.")

    except Exception as e:
        log.error(f"Failed to log trade to CSV: {e}")

