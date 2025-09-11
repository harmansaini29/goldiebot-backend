# FILE: state_manager.py (Corrected & Simplified)
# =============================================================================
#
#   ROBUST & ATOMIC STATE MANAGEMENT FOR MANAGED TRADES
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
LOCK = threading.Lock()

def _read_state_file() -> dict:
    """Safely reads the entire state file."""
    if not STATE_FILE.exists() or STATE_FILE.stat().st_size == 0:
        return {'managed_trades': {}} # Return a valid empty structure
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure the core key exists for robustness
            if 'managed_trades' not in data:
                return {'managed_trades': {}}
            return data
    except json.JSONDecodeError:
        log.critical(f"STATE CORRUPTION: '{STATE_FILE}' is corrupt. A backup will be attempted.")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        corrupt_backup_path = STATE_FILE.with_name(f"{STATE_FILE.stem}_corrupt_{timestamp}.json")
        
        try:
            if STATE_FILE.exists():
                shutil.move(STATE_FILE, corrupt_backup_path)
                log.info(f"Backed up corrupt state file to '{corrupt_backup_path}'. A new state file will be created.")
        except Exception as move_err:
            log.error(f"Could not back up corrupt state file: {move_err}")
        return {'managed_trades': {}}
    except Exception as e:
        log.error(f"Failed to read state file '{STATE_FILE}': {e}", exc_info=True)
        return {'managed_trades': {}}
        
def _write_state_file(state_data: dict):
    """Atomically writes the entire state file."""
    temp_filepath = STATE_FILE.with_suffix('.json.tmp')
    try:
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4)
        shutil.move(temp_filepath, STATE_FILE)
    except Exception as e:
        log.critical(f"Failed to save state to '{STATE_FILE}': {e}", exc_info=True)

def save_trade_state(ticket: int, data: dict):
    """Atomically saves the state of a single managed trade."""
    with LOCK:
        current_state = _read_state_file()
        current_state['managed_trades'][str(ticket)] = data
        _write_state_file(current_state)

def get_trade_state(ticket: int) -> dict:
    """Retrieves the state for a single trade ticket."""
    with LOCK:
        state = _read_state_file()
        return state.get('managed_trades', {}).get(str(ticket), {})

def get_all_managed_trades() -> list[int]:
    """Returns a list of all trade tickets currently being managed by the bot."""
    with LOCK:
        state = _read_state_file()
        return [int(ticket) for ticket in state.get('managed_trades', {}).keys()]

def clear_trade_state(ticket: int):
    """Atomically removes a trade ticket from the state file after it's closed."""
    with LOCK:
        current_state = _read_state_file()
        if str(ticket) in current_state.get('managed_trades', {}):
            del current_state['managed_trades'][str(ticket)]
            _write_state_file(current_state)