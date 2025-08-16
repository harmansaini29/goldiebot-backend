# FILE: configs.py
# =============================================================================
#
#   TRADING BOT CONFIGURATION (HOSTING-READY)
#
# =============================================================================

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# SECTION 1: CORE TRADING PARAMETERS
# =============================================================================
# --- Connection Settings ---
# Full path to the MT5 terminal.exe (e.g., C:/Program Files/MetaTrader 5/terminal64.exe)
MT5_PATH = os.getenv("MT5_PATH")

# --- Symbol & Timeframe ---
TRADING_PAIR = "XAUUSD.d"
TIMEFRAME = "1m"

# --- Order Execution Settings ---
LOT_SIZE = 0.01
MAGIC_NUMBER = 234000
DEVIATION = 20 # Slippage deviation in points

# =============================================================================
# SECTION 2: STRATEGY & RISK PARAMETERS
# =============================================================================
# --- Trend Levels Reversal Strategy ---
TREND_LEVELS_LENGTH = 30
# Basis for the daily Gann level calculation. Options: 'Previous Days Close', 'Todays Open', etc.
GANN_CALCULATION_BASIS = "Previous Days Close" 

## NEW: Risk Management Flag
# Set to True to enable the Gann-based trailing Take Profit.
# Set to False to use a fixed TP (Gann Target 1) for the entire trade duration.
USE_DYNAMIC_EXITS = True

# =============================================================================
# SECTION 3: OPERATIONAL SETTINGS
# =============================================================================
# If True, the bot will not check for trades outside of market hours (Mon-Fri).
CHECK_MARKET_HOURS = True
EXCEL_REPORT_FILENAME = "trading_report.xlsx"
# Safety delay (in seconds) between closing a trade and opening a reverse trade.
REVERSAL_DELAY_SECONDS = 2 

# =============================================================================
# SECTION 4: NOTIFICATIONS
# =============================================================================
ENABLE_TELEGRAM_ALERTS = True
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Sanity Checks ---
if not MT5_PATH:
    print("CRITICAL CONFIG ERROR: MT5_PATH is not set in your .env file.")
if not TELEGRAM_TOKEN or "YOUR_TOKEN" in TELEGRAM_TOKEN:
    print("WARNING: Telegram token is not set correctly. Notifications disabled.")
    ENABLE_TELEGRAM_ALERTS = False
