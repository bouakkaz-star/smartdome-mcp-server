"""
RALF System Audit Skill Module
================================
Advanced monitoring and audit tools for the System Auditor.
System health checks, anomaly history, and compliance verification.
"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _SCRIPT_DIR.parent.parent

if "Personal assistant" in str(_SERVER_ROOT):
    _DATA_DIR = _SERVER_ROOT / "data"
    _DIRECTIVES_DIR = _SERVER_ROOT / "directives" if (_SERVER_ROOT / "directives").exists() else _SERVER_ROOT.parent.parent / "directives" / "smartdome"
else:
    _DATA_DIR = Path("/tmp/data")
    _DIRECTIVES_DIR = Path("/app/app/Directives")


def run_system_audit() -> dict:
    """
    Performs a comprehensive system audit checking all core data files,
    task queues, anomaly counts, and configuration integrity.
    
    Returns:
        dict: Full audit report with health status per subsystem.
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "HEALTHY",
        "subsystems": {},
        "warnings": [],
        "errors": []
    }
    
    # 1. Check data directory
    if _DATA_DIR.exists():
        report["subsystems"]["data_directory"] = {"status": "OK", "path": str(_DATA_DIR)}
    else:
        report["subsystems"]["data_directory"] = {"status": "MISSING", "path": str(_DATA_DIR)}
        report["errors"].append("Data directory not found")
        report["overall_status"] = "CRITICAL"
    
    # 2. Check director_tasks.json
    tasks_file = _DATA_DIR / "director_tasks.json"
    if tasks_file.exists():
        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)
            directors = task_data.get("directors", {})
            total_tasks = sum(len(d.get("tasks", [])) for d in directors.values())
            pending = sum(sum(1 for t in d.get("tasks", []) if t.get("status") == "pending") for d in directors.values())
            report["subsystems"]["task_system"] = {
                "status": "OK",
                "total_tasks": total_tasks,
                "pending": pending,
                "directors_count": len(directors)
            }
            if pending > 20:
                report["warnings"].append(f"High task backlog: {pending} pending tasks")
        except Exception as e:
            report["subsystems"]["task_system"] = {"status": "ERROR", "error": str(e)}
            report["errors"].append(f"Task system error: {e}")
    else:
        report["subsystems"]["task_system"] = {"status": "EMPTY", "message": "No tasks file found"}
    
    # 3. Check anomalies
    anom_file = _DATA_DIR / "system_anomalies.json"
    if anom_file.exists():
        try:
            with open(anom_file, "r", encoding="utf-8") as f:
                anom_data = json.load(f)
            anomalies = anom_data.get("anomalies", [])
            open_count = sum(1 for a in anomalies if a.get("status") == "open")
            high_count = sum(1 for a in anomalies if a.get("severity") == "high" and a.get("status") == "open")
            report["subsystems"]["anomaly_tracker"] = {
                "status": "WARNING" if high_count > 0 else "OK",
                "total": len(anomalies),
                "open": open_count,
                "high_severity_open": high_count
            }
            if high_count > 0:
                report["warnings"].append(f"{high_count} high-severity anomalies remain open")
                report["overall_status"] = "DEGRADED"
        except Exception as e:
            report["subsystems"]["anomaly_tracker"] = {"status": "ERROR", "error": str(e)}
    else:
        report["subsystems"]["anomaly_tracker"] = {"status": "OK", "message": "No anomalies file (clean state)"}
    
    # 4. Check audit log
    audit_file = _DATA_DIR / "audit_log.json"
    if audit_file.exists():
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                audit_data = json.load(f)
            log_count = len(audit_data.get("logs", []))
            report["subsystems"]["audit_log"] = {"status": "OK", "entries": log_count}
        except Exception as e:
            report["subsystems"]["audit_log"] = {"status": "ERROR", "error": str(e)}
    else:
        report["subsystems"]["audit_log"] = {"status": "EMPTY"}
    
    # 5. Check chat history
    chat_file = _DATA_DIR / "chat_history.json"
    if chat_file.exists():
        try:
            size_kb = chat_file.stat().st_size / 1024
            report["subsystems"]["chat_history"] = {"status": "OK", "size_kb": round(size_kb, 1)}
            if size_kb > 5000:
                report["warnings"].append(f"Chat history large: {round(size_kb/1024,1)} MB")
        except Exception:
            report["subsystems"]["chat_history"] = {"status": "UNKNOWN"}
    
    # 6. Check config
    config_files = ["hapm_config.json"]
    for cf in config_files:
        cf_path = _DATA_DIR.parent / cf
        if cf_path.exists():
            report["subsystems"][f"config_{cf}"] = {"status": "OK"}
        else:
            report["subsystems"][f"config_{cf}"] = {"status": "MISSING"}
            report["warnings"].append(f"Config file missing: {cf}")
    
    if report["errors"]:
        report["overall_status"] = "CRITICAL"
    elif report["warnings"] and report["overall_status"] == "HEALTHY":
        report["overall_status"] = "DEGRADED"
    
    return report


def get_anomaly_history(days: int = 7) -> dict:
    """
    Retrieves anomaly history for the specified number of past days.
    Shows open, resolved, and severity breakdown.
    
    Args:
        days: Number of past days to include. Default 7.
    
    Returns:
        dict: Anomaly history with timeline and resolution status.
    """
    try:
        anom_file = _DATA_DIR / "system_anomalies.json"
        if not anom_file.exists():
            return {"success": True, "message": "No anomalies recorded.", "anomalies": []}
        
        with open(anom_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        anomalies = data.get("anomalies", [])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        recent = [a for a in anomalies if a.get("timestamp", "") >= cutoff]
        
        return {
            "success": True,
            "period_days": days,
            "total": len(recent),
            "open": sum(1 for a in recent if a.get("status") == "open"),
            "resolved": sum(1 for a in recent if a.get("status") == "resolved"),
            "by_severity": {
                "high": sum(1 for a in recent if a.get("severity") == "high"),
                "medium": sum(1 for a in recent if a.get("severity") == "medium"),
                "low": sum(1 for a in recent if a.get("severity") == "low")
            },
            "anomalies": recent[:15]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def resolve_anomaly(anomaly_id: str, resolution_note: str = "Resolved by RALF") -> dict:
    """
    Marks a specific anomaly as resolved in the system.
    
    Args:
        anomaly_id: The anomaly ID to resolve (e.g., 'err_1234567890').
        resolution_note: Description of how the issue was resolved.
    
    Returns:
        dict: Confirmation of resolution with updated anomaly details.
    """
    try:
        anom_file = _DATA_DIR / "system_anomalies.json"
        if not anom_file.exists():
            return {"success": False, "error": "No anomalies file found."}
        
        with open(anom_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for anomaly in data.get("anomalies", []):
            if anomaly.get("id") == anomaly_id:
                anomaly["status"] = "resolved"
                anomaly["resolved_at"] = datetime.now().isoformat()
                anomaly["resolution_note"] = resolution_note
                
                with open(anom_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return {
                    "success": True,
                    "message": f"Anomaly {anomaly_id} marked as resolved.",
                    "anomaly": anomaly
                }
        
        return {"success": False, "error": f"Anomaly ID '{anomaly_id}' not found."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_system_uptime() -> dict:
    """
    Returns system uptime information and basic resource metrics.
    
    Returns:
        dict: Uptime data, Python version, and data store sizes.
    """
    import platform
    import sys
    
    data_sizes = {}
    if _DATA_DIR.exists():
        for f in _DATA_DIR.iterdir():
            if f.is_file() and f.suffix == ".json":
                data_sizes[f.name] = round(f.stat().st_size / 1024, 1)
    
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "data_store_sizes_kb": data_sizes,
        "total_data_kb": round(sum(data_sizes.values()), 1),
        "timestamp": datetime.now().isoformat()
    }
