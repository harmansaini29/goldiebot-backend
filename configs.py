# =============================================================================
#
#   TRADING BOT CONFIGURATION FILE
#
# =============================================================================

import os

# =============================================================================
# SECTION 1: CORE TRADING PARAMETERS
# =============================================================================
MT5_PATH = None
TRADING_PAIR = "XAUUSD.d"
TIMEFRAME = "5m"

# --- Order Execution Settings ---
LOT_SIZE = 0.01
MAGIC_NUMBER = 234000
ORDER_FILLING_TYPE = "FOK"
DEVIATION = 20

# =============================================================================
# SECTION 2: STRATEGY PARAMETERS
# =============================================================================
# --- Entry Signal Indicator ---
TREND_LEVELS_LENGTH = 30

# --- Exit Management Indicators ---
GAUSSIAN_BANDS_LENGTH = 20
GAUSSIAN_BANDS_DISTANCE = 1.0
GANN_CALCULATION_BASIS = "Previous Days Close"

# =============================================================================
# SECTION 3: RISK MANAGEMENT
# =============================================================================
# --- Initial SL/TP Calculation (ATR-based) ---
# This is used only for the initial placement of the trade.
ATR_MULTIPLIERS = {
    'low':  {'sl': 1.5, 'tp': 2.0},
    'mid':  {'sl': 2.0, 'tp': 3.0},
    'high': {'sl': 2.5, 'tp': 4.0}
}

# --- Dynamic Trailing Exit Management ---
USE_DYNAMIC_EXITS = True
# The Gaussian Band will be used as the trailing SL.
# The Gann levels will be used as trailing TP targets.
INITIAL_GANN_TP_TARGET = 'target_2' # e.g., 'target_1', 'target_2'

# =============================================================================
# SECTION 4: OPERATIONAL SETTINGS
# =============================================================================
CHECK_MARKET_HOURS = True
LOG_TRADES_TO_CSV = True

# =============================================================================
# SECTION 5: NOTIFICATIONS
# =============================================================================
ENABLE_TELEGRAM_ALERTS = True
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7478036327:AAGvjxcd-iVKMe-JCQYSIEsDQmATtaGOw18")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5502104103")

if "YOUR_FALLBACK_TOKEN_HERE" in TELEGRAM_TOKEN:
    print("WARNING: Using a fallback Telegram token.")
