# =============================================================================
#
#   TRADING BOT CONFIGURATION FILE
#
# =============================================================================

import os

# =============================================================================
# SECTION 1: CORE TRADING PARAMETERS
# =============================================================================
# --- Connection & Symbol Settings ---
# If your MT5 terminal is in a non-standard location, provide the full path to terminal64.exe
# Otherwise, set to None to allow the system to find it automatically.
# Example: MT5_PATH = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
MT5_PATH = None

TRADING_PAIR = "XAUUSD.d"    # Symbol must match your MT5 Market Watch exactly
TIMEFRAME = "5m"            # Timeframe for analysis (e.g., "1m", "5m", "1h", "4h")

# --- Order Execution Settings ---
LOT_SIZE = 0.01             # Trade volume in lots
MAGIC_NUMBER = 234000       # A unique ID to distinguish this bot's trades
ORDER_FILLING_TYPE = "FOK"  # Options: "FOK" (Fill or Kill), "IOC" (Immediate or Cancel)
DEVIATION = 20              # Allowed price slippage in points

# =============================================================================
# SECTION 2: STRATEGY PARAMETERS
# =============================================================================
# --- Main Indicator Settings ---
TREND_LEVELS_LENGTH = 30    # Period for the primary Trend Levels indicator

# =============================================================================
# SECTION 3: RISK MANAGEMENT
# =============================================================================
# --- Initial SL/TP Calculation ---
# Combines SL and TP multipliers for different volatility zones.
# 'sl': Stop Loss multiplier of ATR
# 'tp': Take Profit multiplier of ATR
ATR_MULTIPLIERS = {
    'low':  {'sl': 1.0, 'tp': 2.0},
    'mid':  {'sl': 1.5, 'tp': 2.5},
    'high': {'sl': 2.0, 'tp': 3.5}
}

# --- ATR-Based Trailing Stop ---
USE_TRAILING_STOP = True
TRAILING_STOP_ATR_MULT = 1.5 # Sets the trailing distance as a multiple of the current ATR

# =============================================================================
# SECTION 4: OPERATIONAL SETTINGS
# =============================================================================
CHECK_MARKET_HOURS = True   # Set to False to run the bot 24/7 (e.g., on crypto)
LOG_TRADES_TO_CSV = True    # Set to False to disable writing trades to a CSV file

# =============================================================================
# SECTION 5: NOTIFICATIONS
# =============================================================================
ENABLE_TELEGRAM_ALERTS = True

# --- Securely load credentials from environment variables ---
# IMPORTANT: It is highly recommended to set these as environment variables
# for security, rather than hardcoding them in the file.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7478036327:AAGvjxcd-iVKMe-JCQYSIEsDQmATtaGOw18")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5502104103")

# Check if the fallback token is still being used and print a warning.
if TELEGRAM_TOKEN == "7478036327:AAGvjxcd-iVKMe-JCQYSIEsDQmATtaGOw18":
    print("WARNING: Using a hardcoded fallback Telegram token. Please set the TELEGRAM_TOKEN environment variable for better security.")