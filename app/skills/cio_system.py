"""
CIO System Skill Module
========================
Tools for the Chief Information Officer / System Architect.
System configuration, health checks, and directive management.
"""
import json
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _SCRIPT_DIR.parent.parent

if "Personal assistant" in str(_SERVER_ROOT):
    _DATA_DIR = _SERVER_ROOT / "data"
    _CONFIG_PATH = _SERVER_ROOT / "hapm_config.json"
else:
    _DATA_DIR = Path("/tmp/data")
    _CONFIG_PATH = Path("/app/hapm_config.json")


def read_config(key: str = "all") -> dict:
    """
    Reads configuration from hapm_config.json.
    Returns the full config or a specific key.
    
    Args:
        key: Config key to read (e.g., 'directors', 'participants', 'system'). Use 'all' for full config.
    
    Returns:
        dict: The requested configuration data.
    """
    try:
        if not _CONFIG_PATH.exists():
            return {"success": False, "error": "Config file not found"}
        
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        if key == "all":
            # Return sanitized config (exclude sensitive fields)
            safe_config = {k: v for k, v in config.items() if k != "participants"}
            safe_config["participant_count"] = len(config.get("participants", []))
            return {"success": True, "config": safe_config}
        
        if key in config:
            return {"success": True, "key": key, "value": config[key]}
        
        return {"success": False, "error": f"Key '{key}' not found", "available_keys": list(config.keys())}
    except Exception as e:
        return {"success": False, "error": str(e)}


def system_health_check() -> dict:
    """
    Performs a quick health check of all system components.
    Checks data files, config integrity, and storage status.
    
    Returns:
        dict: Health status per component with overall system grade.
    """
    checks = {}
    issues = []
    
    # Core files
    core_files = {
        "hapm_config.json": _CONFIG_PATH,
        "director_tasks.json": _DATA_DIR / "director_tasks.json",
        "chat_history.json": _DATA_DIR / "chat_history.json",
        "audit_log.json": _DATA_DIR / "audit_log.json",
        "system_anomalies.json": _DATA_DIR / "system_anomalies.json"
    }
    
    for name, path in core_files.items():
        if path.exists():
            size = path.stat().st_size
            checks[name] = {"status": "OK", "size_bytes": size}
            if size > 10 * 1024 * 1024:  # 10MB warning
                issues.append(f"{name} exceeds 10MB ({size // 1024 // 1024}MB)")
        else:
            checks[name] = {"status": "MISSING"}
            if name == "hapm_config.json":
                issues.append(f"CRITICAL: {name} missing")
    
    # Data directory summary
    if _DATA_DIR.exists():
        total_files = sum(1 for _ in _DATA_DIR.iterdir() if _.is_file())
        total_size = sum(f.stat().st_size for f in _DATA_DIR.iterdir() if f.is_file())
        checks["data_store"] = {
            "status": "OK",
            "file_count": total_files,
            "total_size_mb": round(total_size / 1024 / 1024, 2)
        }
    
    grade = "A" if not issues else ("B" if len(issues) <= 2 else "C")
    
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "grade": grade,
        "checks": checks,
        "issues": issues
    }


def get_strategic_priorities() -> dict:
    """
    Reads the current strategic priorities set by the board.
    Useful for all agents to align their actions with company direction.
    
    Returns:
        dict: List of active strategic priorities with levels and categories.
    """
    try:
        prio_file = _DATA_DIR / "strategic_priorities.json"
        if not prio_file.exists():
            return {"success": True, "message": "No strategic priorities set.", "priorities": []}
        
        with open(prio_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        active = [p for p in data.get("priorities", []) if p.get("status") == "active"]
        return {"success": True, "active_count": len(active), "priorities": active}
    except Exception as e:
        return {"success": False, "error": str(e)}
