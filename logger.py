# FILE: logger.py (Updated with Log Rotation)
# =============================================================================
#
#   LOGGING ENGINE WITH AUTOMATIC LOG ROTATION
#   - Prevents log files from growing indefinitely.
#   - Automatically manages backups and deletes old logs.
#
# =============================================================================

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# --- Constants ---
LOGS_DIR = Path("logs")
APP_LOG_FILE = LOGS_DIR / "trading_bot.log"

def setup_logger() -> logging.Logger:
    """Configures a logger that writes to console and a rotating text file."""
    LOGS_DIR.mkdir(exist_ok=True)
    
    log = logging.getLogger("TradingBot")
    log.setLevel(logging.INFO)

    if log.hasHandlers():
        log.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 1. Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # 2. Rotating File Handler
    fh = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=2 * 1024 * 1024,  # Limit each log file to 2 MB
        backupCount=5,            # Keep up to 5 old log files
        encoding='utf-8'
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    log.addHandler(fh)
    
    return log

# Initialize the logger globally so it's available for other modules
log = setup_logger()

# Import other modules after logger is set up
import configs as config
from excel_reporter import ExcelReporter, ExcelHandler

# --- Setup Excel Logging ---
EXCEL_REPORT_FILE = LOGS_DIR / config.EXCEL_REPORT_FILENAME
EXCEL_REPORTER = ExcelReporter(filepath=EXCEL_REPORT_FILE)

# Create and add the Excel handler to the existing logger
excel_handler = ExcelHandler(reporter=EXCEL_REPORTER)
excel_handler.setLevel(logging.WARNING)
excel_formatter = logging.Formatter('%(message)s')
excel_handler.setFormatter(excel_formatter)

# --- BUG FIX: Add the 'excel_handler' object, not the 'excel_formatter' ---
log.addHandler(excel_handler)