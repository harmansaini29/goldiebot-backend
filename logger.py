# FILE: logger.py

import logging
from pathlib import Path

# --- Core Application Imports ---
import configs as config
from excel_reporter import ExcelReporter, ExcelHandler

# --- Constants ---
LOGS_DIR = Path("logs")
APP_LOG_FILE = LOGS_DIR / "trading_bot.log"
EXCEL_REPORT_FILE = LOGS_DIR / config.EXCEL_REPORT_FILENAME

# --- Global instance of the Excel Reporter ---
EXCEL_REPORTER = ExcelReporter(filepath=EXCEL_REPORT_FILE)

def setup_logger() -> logging.Logger:
    """Configures a logger that writes to console, a text file, and selectively to Excel."""
    LOGS_DIR.mkdir(exist_ok=True)

    log = logging.getLogger("TradingBot")
    log.setLevel(logging.INFO)

    if log.hasHandlers():
        log.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler (shows all messages)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # Main Application Log File Handler (for debugging, shows all messages)
    fh = logging.FileHandler(APP_LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    log.addHandler(fh)

    # --- Excel Handler for Activity Log ---
    excel_handler = ExcelHandler(reporter=EXCEL_REPORTER)
    # CHANGED: Raise the level to WARNING. This will stop INFO messages like
    # "Scheduled check running..." from being logged to the Excel ActivityLog.
    # It will still log important warnings and errors.
    excel_handler.setLevel(logging.WARNING)
    excel_formatter = logging.Formatter('%(message)s') # Keep messages clean for Excel
    excel_handler.setFormatter(excel_formatter)
    log.addHandler(excel_handler)

    return log

# Initialize the logger globally
log = setup_logger()