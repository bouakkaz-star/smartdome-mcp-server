from datetime import datetime
import pytz

# SSOT: Hardcoded Timezone
TZ_SOFIA = pytz.timezone("Europe/Sofia")

def get_now() -> datetime:
    """Returns current time in Europe/Sofia timezone."""
    return datetime.now(TZ_SOFIA)

def get_iso_time() -> str:
    """Returns ISO 8601 formatted string with timezone info."""
    return get_now().isoformat()

def get_human_time() -> str:
    """Returns human readable time (YYYY-MM-DD HH:MM) for Prompts."""
    return get_now().strftime("%Y-%m-%d %H:%M")

def get_log_time() -> str:
    """Returns simple time (HH:MM:SS) for logs."""
    return get_now().strftime("%H:%M:%S")

def get_timestamp_id() -> str:
    """Returns high-precision int timestamp-based ID."""
    return str(int(get_now().timestamp() * 1000))

def parse_iso(iso_str: str) -> datetime:
    """Parses ISO string back to datetime."""
    return datetime.fromisoformat(iso_str)
