# FILE: state_manager.py (Improved & Efficient)
# =============================================================================
#
#   ROBUST & ATOMIC STATE MANAGEMENT ENGINE
#
# =============================================================================

import json
import shutil
import threading
from pathlib import Path
from datetime import datetime
from logger import log

# --- Constants ---
STATE_FILE = Path("trade_state.json")
# Use a threading lock to prevent race conditions during file access
LOCK = threading.Lock()

def _read_state_file():
    """Safely reads the entire state file."""
    if not STATE_FILE.exists() or STATE_FILE.stat().st_size == 0:
        return {}
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        log.critical(f"STATE CORRUPTION: '{STATE_FILE}' is corrupt. A backup will be attempted, and a new state file will be created.")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        corrupt_backup_path = STATE_FILE.with_name(f"{STATE_FILE.stem}_corrupt_{timestamp}.json")
        
        if STATE_FILE.exists():
            shutil.move(STATE_FILE, corrupt_backup_path)
            log.info(f"Backed up corrupt state file to '{corrupt_backup_path}'")
        return {}
    except Exception as e:
        log.error(f"Failed to read state file: {e}", exc_info=True)
        return {}
        
def _write_state_file(state_data):
    """Atomically writes the entire state file."""
    temp_filepath = STATE_FILE.with_suffix('.json.tmp')
    try:
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4)
        shutil.move(temp_filepath, STATE_FILE)
    except Exception as e:
        log.critical(f"Failed to save state to '{STATE_FILE}': {e}", exc_info=True)

def save_trade_state(ticket, data):
    """Atomically saves the state of a single trade to the JSON file."""
    with LOCK:
        current_state = _read_state_file()
        if 'managed_trades' not in current_state:
            current_state['managed_trades'] = {}
        current_state['managed_trades'][str(ticket)] = data
        _write_state_file(current_state)

def get_trade_state(ticket):
    """Retrieves the state for a single trade ticket."""
    with LOCK:
        state = _read_state_file()
        return state.get('managed_trades', {}).get(str(ticket))

def get_all_managed_trades():
    """Returns a list of all trade tickets currently being managed."""
    with LOCK:
        state = _read_state_file()
        return [int(ticket) for ticket in state.get('managed_trades', {}).keys()]

def clear_trade_state(ticket):
    """Atomically removes a trade ticket from the state file."""
    with LOCK:
        current_state = _read_state_file()
        if 'managed_trades' in current_state and str(ticket) in current_state['managed_trades']:
            del current_state['managed_trades'][str(ticket)]
            _write_state_file(current_state)

# --- NEW FUNCTIONS FOR TREND MEMORY ---
def save_trend_state(trend: str):
    """Saves the current overall trend state ('BULLISH' or 'BEARISH')."""
    with LOCK:
        current_state = _read_state_file()
        current_state['trend_state'] = trend
        _write_state_file(current_state)
        
def get_trend_state():
    """Retrieves the current overall trend state."""
    with LOCK:
        state = _read_state_file()
        return state.get('trend_state', 'NEUTRAL') # Default to NEUTRAL