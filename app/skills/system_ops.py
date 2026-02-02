import os
import time
from datetime import datetime

def get_system_time():
    """
    Returns the current system time in ISO format and human-readable Sofia time.
    Useful for coordinating schedules and logs.
    """
    now = datetime.now()
    return {
        "iso": now.isoformat(),
        "human": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Europe/Sofia (Target)"
    }

def list_files(path: str = "."):
    """
    Lists files in a specific directory path.
    Helpful for exploring the codebase or checking for file existence.
    """
    try:
        if not os.path.exists(path):
            return f"Path not found: {path}"
        
        items = os.listdir(path)
        return {
            "directory": os.path.abspath(path),
            "files": items[:50], # Limit to 50 for context safety
            "count": len(items)
        }
    except Exception as e:
        return f"Error listing files: {str(e)}"
