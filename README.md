# 🤖 GoldieBot vPRO - Professional Trading Bot Backend

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![MetaTrader5](https://img.shields.io/badge/MetaTrader5-Latest-green.svg)](https://www.metatrader5.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

A professional-grade, self-healing automated trading bot backend designed for MetaTrader 5 (MT5). GoldieBot vPRO combines advanced technical analysis, intelligent risk management, and robust state persistence to execute reliable forex trading strategies with real-time Telegram notifications.

---

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Core Components](#core-components)
- [Trading Strategy](#trading-strategy)
- [Risk Management](#risk-management)
- [Monitoring & Logging](#monitoring--logging)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## ✨ Features

### 🎯 Trading Capabilities
- **Multi-Signal Strategy**: EMA (5/8/13) Crossover with ATR volatility filtering
- **Trend-Based Exit Logic**: Intelligent reversal detection using trend levels
- **Trailing Stop Loss**: Dynamic SL management that activates at 40% profit progression
- **One-Trade Limit**: Ensures single open position at any time for risk control
- **Manual Trade Adoption**: Automatic recognition and adoption of manually opened positions

### 🛡️ Risk Management
- **Configurable Stop Loss & Take Profit**: Customizable in pips with Point conversion
- **ATR Volatility Filter**: Prevents trading during low volatility periods
- **Trailing Stop Activation**: Smart SL trailing when profit reaches threshold
- **Position Synchronization**: Reconciles bot-managed positions with MT5 terminal
- **Commission & Swap Tracking**: Accurate P&L calculation including all costs

### 💾 State Persistence
- **Atomic JSON State Storage**: Thread-safe trade state management with corruption recovery
- **Excel Reporting Engine**: Robust multi-sheet trade history and performance analysis
- **Automatic Backup**: Corrupt file detection with timestamped backups
- **Connection Recovery**: Self-healing reconnection logic with exponential backoff

### 📱 Real-Time Notifications
- **Telegram Integration**: Instant alerts for trade entry, exit, and critical errors
- **HTML-Formatted Messages**: Professional emoji-enhanced notifications
- **Error Logging**: Complete error traceback delivery via Telegram
- **Status Updates**: Connection status and bot health monitoring

### 🔄 Operational Resilience
- **Auto-Reconnection**: Automatic MT5 reconnection on connection loss (5+ attempts trigger restart)
- **Symbol Auto-Resolution**: Handles symbol naming variations automatically
- **Market Hours Check**: Optional market closure detection (weekends)
- **Graceful Degradation**: Non-fatal errors logged without halting bot operation

---

## 🏗️ System Architecture

### High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (Orchestrator)                   │
│  - Connection Management | Position Sync | Main Loop Control    │
└──────────────┬────────────────────────────┬─────────────────────┘
               │                            │
       ┌───────▼──────────┐        ┌────────▼─────────┐
       │  TradeManager    │        │  TradingStrategy │
       │  (MT5 Abstraction)│      │  (Signal Logic)  │
       │ - Connection     │        │ - Entry Signals  │
       │ - Order Mgmt     │        │ - Exit Signals   │
       │ - OHLCV Data     │        │ - Trade Execution│
       └─────────────────┘        └──────┬───────────┘
               │                         │
       ┌───────┴────────┐        ┌──────▼──────────┐
       │  Indicators    │        │  RiskManager    │
       │  - ATR         │        │  - Trailing SL  │
       │  - EMA Stack   │        │  - Position SL/TP
       │  - Trend Levels│        │  - Risk Limits  │
       └────────────────┘        └────────────────┘
               │
       ┌───────┴──────────────────────────────────────┐
       │         State & Reporting Layer              │
       ├──────────────┬──────────────┬────────────────┤
       │ StateManager │ ExcelReporter│ Logger         │
       │ (JSON State) │ (Excel Logs) │ (File/Console) │
       └──────────────┴──────────────┴────────────────┘
               │
       ┌───────▼──────────────────────┐
       │  Notifier (Telegram)         │
       │  - Trade Alerts              │
       │  - Error Notifications       │
       │  - Status Updates            │
       └──────────────────────────────┘
```

---

## 📦 Prerequisites

### System Requirements
- **OS**: Windows 10/11 (MetaTrader 5 requirement)
- **Python**: 3.8 or higher
- **RAM**: Minimum 2 GB
- **Disk Space**: 500 MB free space

### Software Requirements
- **MetaTrader 5**: Installed and configured with trading account
- **Terminal Access**: MT5 terminal must be running or auto-launch via `MT5_PATH`
- **Internet Connection**: Required for MT5 data feeds and Telegram

### Account Requirements
- Active forex trading account with MT5 broker
- Sufficient account balance for configured lot size
- Telegram account and bot token

---

## 📥 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/harmansaini29/goldiebot-backend.git
cd goldiebot-backend
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
python -c "import MetaTrader5 as mt5; print('MT5 ready:', mt5.version())"
```

---

## ⚙️ Configuration

### 1. Environment Variables (`.env`)

Create or update `.env` file in project root:

```env
# --- MetaTrader 5 Configuration ---
TELEGRAM_TOKEN = "your_bot_token_here"
TELEGRAM_CHAT_ID = "your_chat_id_here"
```

**Obtaining Telegram Credentials:**
1. Create a bot via [@BotFather](https://t.me/botfather) on Telegram
2. Copy the bot token
3. Get your chat ID by messaging your bot and checking `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 2. Core Configuration (`configs.py`)

#### Section 1: Trading Parameters

```python
MT5_PATH = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
TRADING_PAIR = "XAUUSD.d"          # Gold/USD or your preferred instrument
TIMEFRAME = "30m"                   # Candle timeframe: 1m, 5m, 15m, 30m, 1h, 4h
LOT_SIZE = 0.01                     # Trading volume in standard lots
MAGIC_NUMBER = 234000               # Unique bot identifier
DEVIATION = 20                      # Slippage tolerance in points
```

#### Section 2: Strategy Parameters

```python
# --- EMA Crossover Entry Strategy ---
EMA_FAST_PERIOD = 5
EMA_MEDIUM_PERIOD = 8
EMA_SLOW_PERIOD = 13
MIN_SEPARATION_PIPS = 1.5          # Minimum EMA stack separation for valid signal

# --- ATR Volatility Filter ---
USE_ATR_FILTER = True
ATR_PERIOD = 14
ATR_THRESHOLD_PIPS = 3.0           # Minimum volatility to allow trade

# --- Trend Levels Exit Strategy ---
TREND_LEVELS_LENGTH = 30           # Lookback period for trend reversal detection

# --- Risk Management ---
TAKE_PROFIT_PIPS = 95              # Target profit in pips
STOP_LOSS_PIPS = 70                # Stop loss in pips
POINTS_PER_PIP = 10                # Platform point conversion (standard = 10)
USE_TRAILING_STOP = True           # Enable dynamic trailing stop
TRAILING_ACTIVATION_PERCENT = 40.0 # Activate trailing SL at 40% of TP
TRAILING_STOP_PIPS = 35            # Trailing distance in pips
```

#### Section 3: Operational Settings

```python
CHECK_MARKET_HOURS = True           # Skip trading on weekends
EXCEL_REPORT_FILENAME = "trading_report.xlsx"
REVERSAL_DELAY_SECONDS = 2         # Delay before processing reversals
MAIN_LOOP_SLEEP_SECONDS = 3        # Bot cycle frequency
```

---

## 🚀 Usage

### Starting the Bot

#### Method 1: Direct Python Execution

```bash
python main.py
```

#### Method 2: Using PM2 (Production Deployment)

```bash
# Start bot as daemon
pm2 start ecosystem.config.js

# Monitor bot in real-time
pm2 monit

# View logs
pm2 logs goldiebot

# Stop bot
pm2 stop goldiebot

# Restart bot
pm2 restart goldiebot
```

#### Method 3: Windows Batch Script

```bash
start_bot.bat
```

### Bot Lifecycle

1. **Initialization**: Bot connects to MT5, resolves trading symbol, verifies connection health
2. **Startup Notification**: Telegram alert with strategy configuration
3. **Main Loop**: Executes every `MAIN_LOOP_SLEEP_SECONDS` with:
   - Position synchronization
   - New candle detection
   - Entry signal generation
   - Exit signal processing
   - Trailing stop management
4. **Position Management**: Tracks all open positions with state persistence
5. **Auto-Reconnection**: On connection loss, retries up to 5 times
6. **Graceful Shutdown**: `Ctrl+C` triggers clean exit with notification

### Monitoring

**Real-Time Monitoring:**
```bash
# View application logs
tail -f logs/trading_bot.log

# View Excel reports
# Open logs/trading_report.xlsx in Excel for trade history and performance
```

**Telegram Notifications:**
- ✅ **Entry**: `🚀 NEW TRADE OPENED (BUY/SELL) 🚀`
- 🔻 **Exit**: `✅ TRADE CLOSED` or `❌ TRADE CLOSED` (profit/loss)
- ⚠️ **Events**: Manual trade adoption, position synchronization
- 🚨 **Errors**: Critical errors with stack traces

---

## 🔧 Core Components

### 1. **main.py** - Bot Orchestrator
**Responsibility**: Core bot logic and lifecycle management

**Key Functions:**
- `main()`: Entry point with error recovery
- `main_loop(tm)`: Core trading loop with candle detection
- `sync_positions_with_state(tm)`: Reconciles MT5 positions with bot state
- `adopt_manual_trade(tm, position)`: Adopts manually opened positions
- `log_closed_trade(tm, ticket)`: Processes trade closure and Excel logging
- `is_market_open()`: Market hours detection

**Flow:**
```
main() → initialization → main_loop() → [every candle]:
  ├─ Sync positions
  ├─ Get entry signal
  ├─ Get exit signal
  ├─ Manage trailing stops
  └─ Process trades
```

---

### 2. **trade_manager.py** - MT5 Abstraction Layer
**Responsibility**: All MetaTrader 5 communication and trade execution

**Key Classes:**
```python
class TradeManager:
    # Connection Management
    - connect(): Initialize MT5 connection
    - disconnect(): Safely close MT5 connection
    - is_connected(): Check connection health
    - verify_connection_health(): Validate terminal responsiveness
    
    # Symbol Management
    - _resolve_and_prepare_symbol(): Auto-resolve symbol name
    - _auto_resolve_symbol(base): Handle symbol variants
    
    # Data Retrieval
    - get_current_price(signal): Fetch bid/ask price
    - fetch_ohlcv(timeframe, limit): Retrieve candle data
    - get_open_positions(): Get all open positions
    
    # Trade Execution
    - open_trade(...): Execute buy/sell order
    - close_trade(ticket): Close position by ticket
    - modify_sl_tp(ticket, new_sl, new_tp): Update SL/TP
    
    # History
    - get_trade_history_for_position(ticket): Retrieve deal history
```

**Context Manager Usage:**
```python
with TradeManager() as tm:
    if tm.is_connected():
        positions = tm.get_open_positions()
        tm.open_trade(...)  # Trade execution
    tm.disconnect()  # Automatic on exit
```

---

### 3. **strategy.py** - Trading Signal Generation
**Responsibility**: Generate entry/exit signals based on technical analysis

**Key Methods:**
```python
class TradingStrategy:
    - __init__(tm): Initialize with TradeManager
    - get_entry_signal(): Generate BUY/SELL/HOLD entry signal
    - get_exit_signal(): Generate BUY/SELL/HOLD exit signal
    - execute_trade(signal): Execute trade with SL/TP calculation
```

**Signal Logic:**
1. **Entry Signal**:
   - ATR volatility check (if enabled)
   - EMA crossover detection
   - Minimum EMA separation validation
   - Returns: BUY / SELL / HOLD

2. **Exit Signal**:
   - Trend levels reversal detection
   - Returns: BUY / SELL / HOLD

---

### 4. **indicators.py** - Technical Analysis Engine
**Responsibility**: Calculate technical indicators using pandas

**Key Indicators:**

#### ATR (Average True Range)
```python
calculate_atr(df, period, point) -> float
# Calculates volatility in pips
# Uses exponential moving average (EMA) method
```

#### EMA Crossover
```python
calculate_ema_crossover_signal(df, fast, medium, slow, point) -> DataFrame
# Fast/Medium/SLOW EMA stack detection
# Green candle requirement for BUY
# Red candle requirement for SELL
# Minimum separation check
```

#### Trend Levels
```python
calculate_trend_levels(df, length) -> DataFrame
# 20/30-period high/low tracking
# Trend reversal detection
```

---

### 5. **risk_manager.py** - Risk & Position Management
**Responsibility**: Dynamic trailing stop loss and position safety

**Key Function:**
```python
manage_trailing_stop_loss(tm, open_positions)
# Activates when profit reaches TRAILING_ACTIVATION_PERCENT
# Trails SL by TRAILING_STOP_PIPS below current price
# Separate logic for BUY and SELL positions
# Confirmation checks ensure SL was modified
```

**Trailing Stop Logic:**
- For BUY: `new_SL = current_ask - (trailing_pips * point)`
- For SELL: `new_SL = current_bid + (trailing_pips * point)`

---

### 6. **state_manager.py** - Atomic State Persistence
**Responsibility**: Thread-safe trade state management using JSON

**Key Functions:**
```python
save_trade_state(ticket, data)          # Save/update trade state
get_trade_state(ticket) -> dict         # Retrieve single trade state
get_all_managed_trades() -> List[int]   # List all managed trade tickets
clear_trade_state(ticket)               # Remove trade from state
```

**State File Structure:**
```json
{
  "managed_trades": {
    "1234567": {
      "entry_price": 2000.50,
      "signal": "BUY",
      "entry_type": "EMA_Crossover"
    }
  }
}
```

**Features:**
- Atomic writes with `.json.tmp` temporary files
- Automatic corruption detection and recovery
- Timestamped backup creation on corruption

---

### 7. **excel_reporter.py** - Trade Reporting Engine
**Responsibility**: Robust Excel workbook management with atomic writes

**Key Class:**
```python
class ExcelReporter:
    - log_trade_history(deals_df): Format and log closed trades
    - log_activity(level, message): Log events to ActivityLog sheet
    - get_logged_tickets(): Retrieve all logged trade tickets
```

**Excel Sheets:**
1. **TradeHistory**: Individual trade records
   - Ticket #, Symbol, Type, Open/Close Time/Price, P&L, Commission, Swap, Comment
2. **ActivityLog**: Event log with timestamps
3. **MonthlySummary**: Aggregated monthly performance

**Corruption Recovery:**
- Bad zip file detection
- Automatic backup to `trading_report.<timestamp>.bak`
- Workbook recreation on corruption

---

### 8. **logger.py** - Logging & Monitoring
**Responsibility**: Multi-channel logging with rotation

**Output Channels:**
1. **Console**: Real-time INFO+ level logs
2. **File**: Rotating handler (2MB files, 5 backups)
3. **Excel**: Warning+ level events to Excel ActivityLog

**Log Rotation:**
```python
RotatingFileHandler(
    maxBytes=2 * 1024 * 1024,  # 2 MB per file
    backupCount=5              # Keep 5 old files
)
```

---

### 9. **notifier.py** - Telegram Alerts
**Responsibility**: Send real-time notifications

**Function:**
```python
send_telegram_alert(message: str)
# Sends HTML-formatted message to Telegram
# Timeout: 10 seconds
# Supports emoji and basic HTML formatting
```

---

## 📊 Trading Strategy Details

### Strategy: EMA Crossover with Volatility Filter & Trend Reversal Exit

#### Entry Conditions (ALL must be met):
1. **Volatility Check**: `ATR > ATR_THRESHOLD_PIPS`
2. **EMA Alignment**:
   - BUY: `EMA_5 > EMA_8 > EMA_13` (bullish stack)
   - SELL: `EMA_5 < EMA_8 < EMA_13` (bearish stack)
3. **Minimum Separation**: `|EMA_5 - EMA_13| > MIN_SEPARATION_PIPS`
4. **Candle Color**:
   - BUY: Green candle (close > open)
   - SELL: Red candle (close < open)
5. **Single Position**: No existing bot-managed position

#### Exit Conditions:
- Trend reversal detected by Trend Levels indicator
- Trailing stop loss hit (when activated)
- Take profit hit
- Manual intervention via terminal

#### Position Limits:
- **Maximum Open Positions**: 1
- **Maximum Lot Size**: Configurable (default: 0.01)
- **Risk-Reward Ratio**: Typically 1:1.35 (70 pips SL, 95 pips TP)

---

## 🛡️ Risk Management Features

### 1. Volatility Filtering
- **Purpose**: Avoid trading during ranging/choppy markets
- **Implementation**: ATR > threshold validation
- **Benefit**: Reduces false signals and whipsaw losses

### 2. Trailing Stop Loss
- **Activation**: At 40% of target profit progress
- **Movement**: Every 3 seconds (main loop frequency)
- **Benefit**: Locks in profits while allowing growth

### 3. Position Synchronization
- **Frequency**: Every main loop cycle (3 seconds)
- **Function**: Reconciles terminal positions with bot state
- **Benefit**: Detects external closes and manual trades

### 4. Single Trade Limit
- **Policy**: Only 1 bot-managed position at a time
- **Enforcement**: Entry signal check validates no open positions
- **Benefit**: Prevents over-leverage and margin issues

### 5. Automatic Adoption
- **Detection**: Unmanaged positions matching trading pair
- **Action**: Adopt position and apply default SL/TP if missing
- **Benefit**: Seamless manual+automatic trading integration

---

## 📋 Monitoring & Logging

### Log Levels

| Level | Use Case | Output |
|-------|----------|--------|
| **INFO** | Normal operations, signal detection, trades | Console + File |
| **WARNING** | Connection issues, missed signals, adoption | Console + File |
| **ERROR** | Order failures, sync issues | Console + File + Telegram |
| **CRITICAL** | Connection loss, fatal errors | Console + File + Telegram |

### Log File Rotation

- **Location**: `logs/trading_bot.log`
- **Max Size**: 2 MB per file
- **Backup Files**: 5 old files retained
- **Format**: `YYYY-MM-DD HH:MM:SS - Logger - Level - Message`

### Excel Reports

- **Location**: `logs/trading_report.xlsx`
- **Auto-Created**: On first run or if missing
- **Atomic Writes**: Temporary file strategy prevents corruption
- **Update Frequency**: After each trade closure

---

## 🔥 Advanced Features

### 1. Connection Recovery with Exponential Backoff
```python
# Automatic reconnection logic
- Attempt 1: Immediate reconnect
- Attempt 2-5: Retry with warnings
- After 5 failures: Force restart (exit main loop)
```

### 2. Symbol Auto-Resolution
```python
# Handles symbol variants automatically
Examples: "XAUUSD" → "XAUUSD.d", "EURUSD" → "EURUSD.a"
```

### 3. Market Hours Detection
```python
# Optional weekend/market closure bypass
if CHECK_MARKET_HOURS and not is_market_open():
    sleep(1 hour)  # Skip trading on weekends
```

### 4. Atomic State & Excel Operations
```python
# Prevents corruption from crashes/unexpected termination
1. Write to temporary file (.tmp)
2. Flush to disk
3. Atomic rename to final path
4. On corruption: Timestamped backup + recovery
```

### 5. Manual Trade Integration
- Automatically detects manually opened positions
- Applies bot SL/TP if missing
- Tracks alongside bot-opened positions
- Maintains separate state for transparency

---

## 🐛 Troubleshooting

### Common Issues & Solutions

#### Issue: "MT5 initialize() failed"
```
Error: Connection to MetaTrader 5 failed
Solution:
1. Verify MT5_PATH in configs.py points to terminal64.exe
2. Ensure MetaTrader 5 is installed and accessible
3. Check account is active and logged in
4. Restart MetaTrader 5 terminal
```

#### Issue: "Symbol 'XAUUSD.d' not found"
```
Error: Trading pair not recognized
Solution:
1. Check trading pair exists in your MT5 Market Watch
2. Use auto-resolution: Bot attempts variants automatically
3. Add symbol manually to Market Watch in MT5
4. Verify symbol name exact spelling (case-sensitive)
```

#### Issue: "positions_get() returned None"
```
Error: Cannot fetch open positions
Solution:
1. Check MT5 connection is stable
2. Verify account has access to trading pair
3. Bot retries up to 3 times automatically
4. If persistent, check MT5 terminal logs
```

#### Issue: "Telegram alert failed"
```
Error: Notification not received
Solution:
1. Verify TELEGRAM_TOKEN is correct
2. Verify TELEGRAM_CHAT_ID is correct
3. Check internet connectivity
4. Ensure Telegram bot is active (@BotFather)
```

#### Issue: "Excel file is corrupt"
```
Error: trading_report.xlsx cannot open
Solution:
1. Bot automatically backs up corrupt file
2. Check logs/ directory for `.bak` files
3. Bot creates new working file automatically
4. Restore from backup if needed
```

#### Issue: "State corruption detected"
```
Error: JSON file is invalid
Solution:
1. Bot creates `trade_state_corrupt_<timestamp>.json.bak`
2. All trades reset to fresh state
3. Manual verification recommended in MT5 terminal
4. Excel history preserved (backup created)
```

### Performance Tuning

#### Reduce CPU Usage
```python
# Increase main loop sleep
MAIN_LOOP_SLEEP_SECONDS = 5  # From default 3
```

#### Reduce False Signals
```python
# Increase minimum EMA separation
MIN_SEPARATION_PIPS = 2.5  # From default 1.5

# Increase ATR threshold
ATR_THRESHOLD_PIPS = 4.0  # From default 3.0
```

#### More Aggressive Trading
```python
# Reduce ATR threshold
ATR_THRESHOLD_PIPS = 2.0  # More trades allowed

# Use faster EMAs
EMA_FAST_PERIOD = 3  # From default 5
```

---

## 📁 Project Structure

```
goldiebot-backend/
├── main.py                 # Entry point & core bot logic
├── configs.py              # Configuration parameters
├── trade_manager.py        # MT5 connection & trading
├── strategy.py             # Signal generation
├── indicators.py           # Technical analysis
├── risk_manager.py         # Position management
├── state_manager.py        # JSON state persistence
├── excel_reporter.py       # Excel reporting engine
├── logger.py               # Logging configuration
├── notifier.py             # Telegram notifications
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
├── ecosystem.config.js     # PM2 configuration
├── start_bot.bat          # Windows batch script
├── logs/                  # Log files directory
│   ├── trading_bot.log
│   ├── trading_bot.log.1
│   └── trading_report.xlsx
├── trade_state.json       # Current trade state
└── README.md              # This file
```

---

## 📦 Dependencies

```txt
MetaTrader5>=5.0.0          # MT5 API
pandas>=1.3.0               # Data manipulation
numpy>=1.21.0               # Numerical computing
openpyxl>=3.6.0            # Excel file handling
python-dotenv>=0.19.0      # Environment variables
requests>=2.26.0           # HTTP client
pytz>=2021.3               # Timezone handling
pywin32                    # Windows process management
```

See `requirements.txt` for specific versions.

---

## 🤝 Contributing

### Code Standards
- Follow PEP 8 style guide
- Add docstrings to all functions and classes
- Include type hints where possible
- Add inline comments for complex logic

### Reporting Issues
1. Check existing issues first
2. Include:
   - Python version and OS
   - MT5 version
   - Complete error message and stack trace
   - Reproduction steps
   - Relevant log excerpts

### Pull Requests
1. Fork repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes with tests
4. Submit PR with detailed description

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## ⚠️ Disclaimer

**TRADING RISK NOTICE:**
- This bot is for educational purposes. Automated trading involves substantial risk of loss.
- Past performance is not indicative of future results.
- Test extensively on demo accounts before live trading.
- Only trade what you can afford to lose.
- The developers assume no responsibility for trading losses.
- Always maintain sufficient account balance for your configured lot size.

---

## 📞 Support

For issues, questions, or feature requests:
1. Check this README thoroughly
2. Review logs in `logs/trading_bot.log`
3. Check closed/open GitHub issues
4. Create a new GitHub issue with details

---

## 🚀 Roadmap

Planned features for future releases:
- [ ] Multi-pair support
- [ ] Multiple strategy switching
- [ ] Advanced portfolio analytics
- [ ] Machine learning signal optimization
- [ ] Web dashboard for monitoring
- [ ] REST API for external integration
- [ ] Backtesting engine
- [ ] Risk allocation by portfolio
- [ ] Advanced filter conditions
- [ ] Performance statistics dashboards

---

## 📜 Version History

### v1.0.0 (Current)
- Initial release
- EMA Crossover strategy
- ATR volatility filtering
- Trailing stop loss
- Excel reporting
- Telegram notifications
- State persistence with recovery

---

**Last Updated**: 2025-09-18  
**Maintained by**: Harman Saini  
**Repository**: [harmansaini29/goldiebot-backend](https://github.com/harmansaini29/goldiebot-backend)

---

<div align="center">

### Made with ❤️ for professional traders

[⭐ Star this repo if you find it helpful!](https://github.com/harmansaini29/goldiebot-backend)

</div>
