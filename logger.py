# FILE: logger.py (Updated with Log Rotation)
# =============================================================================
#
#   LOGGING ENGINE WITH AUTOMATIC LOG ROTATION
#   - Prevents log files from growing indefinitely.
#   - Automatically manages backups and deletes old logs.
#
# =============================================================================

import logging
from logging.handlers import RotatingFileHandler  # <-- IMPORT THE NEW HANDLER
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
    """Configures a logger that writes to console, a rotating text file, and Excel."""
    LOGS_DIR.mkdir(exist_ok=True)

    log = logging.getLogger("TradingBot")
    log.setLevel(logging.INFO)

    if log.hasHandlers():
        log.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 1. Console Handler (shows all messages)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # =========================================================================
    # --- 2. IMPROVEMENT: Use RotatingFileHandler instead of FileHandler ---
    # This is the part that solves the problem.
    # =========================================================================
    fh = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=1 * 1024 * 1024,  # Limit each log file to 1 MB
        backupCount=5,             # Keep up to 5 old log files
        encoding='utf-8'
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    log.addHandler(fh)

    # 3. Excel Handler for Activity Log
    excel_handler = ExcelHandler(reporter=EXCEL_REPORTER)
    excel_handler.setLevel(logging.WARNING)
    excel_formatter = logging.Formatter('%(message)s')
    excel_handler.setFormatter(excel_formatter)
    log.addHandler(excel_handler)

    return log

# Initialize the logger globally
log = setup_logger()