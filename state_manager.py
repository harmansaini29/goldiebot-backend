# =============================================================================
#
#   TRADE STATE MANAGER
#
# -----------------------------------------------------------------------------
#   This module manages the persistent state of open trades, saving them
#   to a JSON file. This allows the bot to track its trades and recover
#   its state after a restart. It is thread-safe.
#
# =============================================================================

import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Core Application Imports ---
from logger import log

# --- Constants ---
STATE_FILE = Path("trade_state.json")
STATE_LOCK = threading.Lock() # Ensures thread-safe file access

def _load_state() -> Dict[str, Any]:
    """
    Loads the entire state from the JSON file in a thread-safe manner.
    Returns an empty dictionary if the file doesn't exist or is corrupt.
    """
    with STATE_LOCK:
        if not STATE_FILE.exists():
            return {}
        try:
            with STATE_FILE.open('r') as f:
                # Handle case where file is empty
                content = f.read()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Error loading state file '{STATE_FILE}': {e}. A new one will be created.")
            return {}

def _save_state(state: Dict[str, Any]):
    """Saves the entire state to the JSON file in a thread-safe manner."""
    with STATE_LOCK:
        try:
            with STATE_FILE.open('w') as f:
                json.dump(state, f, indent=4)
        except IOError as e:
            log.error(f"Could not save state to file '{STATE_FILE}': {e}")

def save_trade_state(ticket: int, data: Dict[str, Any]):
    """
    Saves or updates the state for a specific trade ticket.

    Args:
        ticket (int): The trade ticket ID from MT5.
        data (Dict[str, Any]): A dictionary of metadata to save for the trade.
    """
    state = _load_state()
    state[str(ticket)] = data
    _save_state(state)
    log.info(f"State saved for ticket {ticket}.")

def get_trade_state(ticket: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves the state for a specific trade ticket.

    Args:
        ticket (int): The trade ticket ID.

    Returns:
        Optional[Dict[str, Any]]: The stored data for the trade, or None if not found.
    """
    state = _load_state()
    return state.get(str(ticket))

def clear_trade_state(ticket: int):
    """
    Removes a trade from state tracking, typically after it has been closed.

    Args:
        ticket (int): The trade ticket ID to remove.
    """
    state = _load_state()
    if str(ticket) in state:
        del state[str(ticket)]
        _save_state(state)
        log.info(f"State cleared for closed ticket {ticket}.")

def get_all_managed_trades() -> List[int]:
    """
    Returns a list of all trade ticket IDs currently being managed.

    Returns:
        List[int]: A list of integer ticket IDs.
    """
    state = _load_state()
    # Convert string keys back to integers
    return [int(ticket) for ticket in state.keys()]

