# =============================================================================
#
#   TELEGRAM NOTIFIER
#
# -----------------------------------------------------------------------------
#   This module handles sending alerts and notifications via Telegram.
#
# =============================================================================

import requests
from requests.exceptions import RequestException

# --- Core Application Imports ---
from logger import log
import configs as config

def send_telegram_alert(message: str):
    """
    Sends a message to the configured Telegram chat.

    Args:
        message (str): The message to send. Supports basic HTML formatting.
    """
    if not config.ENABLE_TELEGRAM_ALERTS:
        return

    token = config.TELEGRAM_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID

    if not token or "FALLBACK" in token or not chat_id:
        log.warning("Telegram token or chat ID is not configured. Skipping alert.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes
        log.info("Telegram alert sent successfully.")
    except RequestException as e:
        log.error(f"Failed to send Telegram alert: {e}")

