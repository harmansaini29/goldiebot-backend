
# =============================================================================
# SECTION 1: CORE TRADING PARAMETERS
# =============================================================================
# --- Connection Settings ---
# FIX: THE PATH WAS POINTING TO THE WRONG FOLDER. THIS IS NOW CORRECTED.
# This path points to the standard MetaTrader 5 installation folder.
# Remember to use double backslashes (\\).
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
MT5_PATH = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"

# --- Symbol & Timeframe ---
TRADING_PAIR = "XAUUSD.d"
TIMEFRAME = "30m"

# --- Order Execution Settings ---
LOT_SIZE = 1.00
MAGIC_NUMBER = 234000
DEVIATION = 20

# =============================================================================
# SECTION 2: STRATEGY & RISK PARAMETERS
# =============================================================================
# --- ENTRY STRATEGY (EMA Crossover) ---
EMA_FAST_PERIOD = 5
EMA_MEDIUM_PERIOD = 8
EMA_SLOW_PERIOD = 13

# --- EXIT STRATEGY (Trend Levels Reversal) ---
TREND_LEVELS_LENGTH = 30

# --- Fixed Stop-Loss and Take-Profit Settings ---
TAKE_PROFIT_PIPS = 90
STOP_LOSS_PIPS = 80
PIP_TO_POINT_MULTIPLIER = 10

# --- Advanced Trailing Stop-Loss Settings ---
USE_TRAILING_STOP = True
TRAILING_ACTIVATION_PERCENT = 40.0
TRAILING_STOP_PIPS = 40

# =============================================================================
# SECTION 3: OPERATIONAL SETTINGS
# =============================================================================
CHECK_MARKET_HOURS = True
EXCEL_REPORT_FILENAME = "trading_report.xlsx"
REVERSAL_DELAY_SECONDS = 2

# =============================================================================
# SECTION 4: NOTIFICATIONS
# =============================================================================
ENABLE_TELEGRAM_ALERTS = True
TELEGRAM_TOKEN = "7478036327:AAGvjxcd-iVKMe-JCQYSIEsDQmATtaGOw18"
TELEGRAM_CHAT_ID = "5502104103"

# --- Sanity Checks ---
if not MT5_PATH:
    print("CRITICAL CONFIG ERROR: MT5_PATH is not set in your .env file.")
if not TELEGRAM_TOKEN or "YOUR_TOKEN" in TELEGRAM_TOKEN:
    print("WARNING: Telegram token is not configured correctly in your .env file.")
if not TELEGRAM_CHAT_ID:
    print("WARNING: Telegram chat ID is not configured in your .env file.")
