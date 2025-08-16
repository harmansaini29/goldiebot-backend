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
from datetime import datetime  # <-- IMPORT DATETIME INSTEAD OF PANDAS
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
        # --- THIS IS THE CORRECTED LINE ---
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        corrupt_backup_path = STATE_FILE.with_name(f"{STATE_FILE.stem}_corrupt_{timestamp}.json")
        # --- END OF CORRECTION ---
        
        # Check if the file exists before trying to move it
        if STATE_FILE.exists():
            shutil.move(STATE_FILE, corrupt_backup_path)
            log.info(f"Backed up corrupt state file to '{corrupt_backup_path}'")
        return {}
    except Exception as e:
        log.error(f"Failed to read state file: {e}", exc_info=True)
        return {}

def save_trade_state(ticket, data):
    """Atomically saves the state of a single trade to the JSON file."""
    with LOCK:
        current_state = _read_state_file()
        current_state[str(ticket)] = data
        
        temp_filepath = STATE_FILE.with_suffix('.json.tmp')
        try:
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(current_state, f, indent=4)
            shutil.move(temp_filepath, STATE_FILE)
        except Exception as e:
            log.critical(f"Failed to save state to '{STATE_FILE}': {e}", exc_info=True)

def get_trade_state(ticket):
    """Retrieves the state for a single trade ticket."""
    with LOCK:
        state = _read_state_file()
        return state.get(str(ticket))

def get_all_managed_trades():
    """Returns a list of all trade tickets currently being managed."""
    with LOCK:
        state = _read_state_file()
        return [int(ticket) for ticket in state.keys()]

def clear_trade_state(ticket):
    """Atomically removes a trade ticket from the state file."""
    with LOCK:
        current_state = _read_state_file()
        if str(ticket) in current_state:
            del current_state[str(ticket)]
            
            temp_filepath = STATE_FILE.with_suffix('.json.tmp')
            try:
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    json.dump(current_state, f, indent=4)
                shutil.move(temp_filepath, STATE_FILE)
            except Exception as e:
                log.critical(f"Failed to clear state for ticket {ticket}: {e}", exc_info=True)