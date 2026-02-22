"""
Orchestrator Skill: Queue Reporting for SmartDome Command Bridge.

This skill provides tools for the engineering agent (Antigravity)
to inspect and report on the state of all director task queues.
"""
import json
from pathlib import Path

# --- Path Resolution ---
# In Cloud Run: /tmp/data/director_tasks.json
# Local Dev: Relative to script location
_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _SCRIPT_DIR.parent  # apps/server/app -> apps/server

if "Personal assistant" in str(_SERVER_ROOT):
    # Local Dev
    _DATA_DIR = _SERVER_ROOT.parent.parent / "apps" / "server" / "data"
else:
    # Cloud Run
    _DATA_DIR = Path("/tmp/data")

TASKS_FILE = _DATA_DIR / "director_tasks.json"


def get_queue_summary() -> dict:
    """
    Returns a summary of all pending tasks across all directors.
    Useful for the engineering agent to see what's in the pipe.
    """
    try:
        if not TASKS_FILE.exists():
            return {"error": "Tasks file not found", "path": str(TASKS_FILE)}

        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = {}
        for director_id, director_data in data.get("directors", {}).items():
            tasks = director_data.get("tasks", [])
            pending = [t for t in tasks if t.get("status") == "pending"]
            in_progress = [t for t in tasks if t.get("status") == "in_progress"]
            completed = [t for t in tasks if t.get("status") == "completed"]

            summary[director_id] = {
                "pending_count": len(pending),
                "in_progress_count": len(in_progress),
                "completed_count": len(completed),
                "pending_titles": [t.get("title", "Untitled") for t in pending[:5]]  # Top 5
            }

        return {"success": True, "summary": summary}
    except Exception as e:
        return {"error": str(e)}


def get_my_queue(agent_id: str = "antigravity") -> dict:
    """
    Returns the full list of pending tasks for a specific agent.
    Default is 'antigravity' (the engineering queue).
    """
    try:
        if not TASKS_FILE.exists():
            return {"error": "Tasks file not found"}

        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        agent_data = data.get("directors", {}).get(agent_id.lower(), {})
        tasks = agent_data.get("tasks", [])
        pending = [t for t in tasks if t.get("status") == "pending"]

        return {"success": True, "agent": agent_id, "pending_tasks": pending}
    except Exception as e:
        return {"error": str(e)}
