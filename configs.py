# FILE: configs.py
# =============================================================================
#
#   TRADING BOT CONFIGURATION (FINAL & VERIFIED)
#
# =============================================================================

import os

# =============================================================================
# SECTION 1: CORE TRADING PARAMETERS
# =============================================================================
MT5_PATH = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
TRADING_PAIR = "XAUUSD.d"
TIMEFRAME = "30m"
LOT_SIZE = 0.01
MAGIC_NUMBER = 234000
DEVIATION = 20

# =============================================================================
# SECTION 2: STRATEGY & RISK PARAMETERS
# =============================================================================
# --- ENTRY STRATEGY (EMA Crossover) ---
EMA_FAST_PERIOD = 5
EMA_MEDIUM_PERIOD = 8
EMA_SLOW_PERIOD = 13
MIN_SEPARATION_PIPS = 1.5

# --- VOLATILITY FILTER (ATR) ---
USE_ATR_FILTER = True
ATR_PERIOD = 14
ATR_THRESHOLD_PIPS = 3.0 # Min volatility in pips to allow a trade

# --- EXIT STRATEGY (Trend Levels Reversal) ---
TREND_LEVELS_LENGTH = 30

# --- RISK MANAGEMENT ---
TAKE_PROFIT_PIPS = 95
STOP_LOSS_PIPS = 70
POINTS_PER_PIP = 10
USE_TRAILING_STOP = True
TRAILING_ACTIVATION_PERCENT = 40.0 # Activates trailing SL at 40% of the way to TP
TRAILING_STOP_PIPS = 35

# =============================================================================
# SECTION 3: OPERATIONAL SETTINGS
# =============================================================================
CHECK_MARKET_HOURS = True
EXCEL_REPORT_FILENAME = "trading_report.xlsx"
REVERSAL_DELAY_SECONDS = 2
MAIN_LOOP_SLEEP_SECONDS = 3 # Main loop runs every 5 seconds

# =============================================================================
# SECTION 4: NOTIFICATIONS
# =============================================================================
ENABLE_TELEGRAM_ALERTS = True
TELEGRAM_TOKEN = "7478036327:AAGvjxcd-iVKMe-JCQYSIEsDQmATtaGOw18"
TELEGRAM_CHAT_ID = "5502104103"

# --- Sanity Checks ---
if not MT5_PATH:
    print("CRITICAL CONFIG ERROR: MT5_PATH is not set.")
if not TELEGRAM_TOKEN or "YOUR_TOKEN" in TELEGRAM_TOKEN:
    print("WARNING: Telegram token is not configured correctly.")
if not TELEGRAM_CHAT_ID:
    print("WARNING: Telegram chat ID is not configured.")