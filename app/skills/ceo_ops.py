"""
CEO Operations Skill Module
============================
Tools for the Executive Operations Director (CEO Agent).
Vendor tracking, email drafting, and priority management.
"""
import json
import os
from pathlib import Path
from datetime import datetime

# --- Path Resolution ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _SCRIPT_DIR.parent.parent  # apps/server

if "Personal assistant" in str(_SERVER_ROOT):
    _DATA_DIR = _SERVER_ROOT / "data"
else:
    _DATA_DIR = Path("/tmp/data")

VENDOR_FILE = _DATA_DIR / "vendor_tracker.json"


def draft_email(to: str, subject: str, context: str, tone: str = "formal", language: str = "bulgarian") -> dict:
    """
    Generates a professional email draft for the CEO.
    
    Args:
        to: Recipient name or company (e.g., 'Vicat', 'Polycon').
        subject: Email subject line.
        context: Key points to include in the email body.
        tone: Writing tone - 'formal', 'aggressive', or 'friendly'. Default 'formal'.
        language: 'bulgarian' or 'english'. Default 'bulgarian'.
    
    Returns:
        dict: The email draft with subject, to, body fields ready for review.
    """
    # Return the structured request - Gemini will generate the actual draft
    return {
        "action": "draft_generated",
        "to": to,
        "subject": subject,
        "context": context,
        "tone": tone,
        "language": language,
        "instruction": f"Generate a {tone} email in {language} to {to} about: {subject}. Key points: {context}"
    }


def get_vendor_status(vendor_name: str = "all") -> dict:
    """
    Retrieves current vendor status from the vendor tracker.
    Shows relationship status, last contact, and strategy for each vendor.
    
    Args:
        vendor_name: Name of specific vendor or 'all' for full list.
    
    Returns:
        dict: Vendor status information including strategy and contact history.
    """
    # Built-in vendor matrix from CEO directive
    default_vendors = {
        "Ductal": {"status": "BLOCKED", "strategy": "Ignore/Block. Do not engage.", "priority": "low"},
        "Vicat": {"status": "PRIORITY", "strategy": "Aggressive Pursuit. Primary target for UHPC supply.", "priority": "high"},
        "Polycon": {"status": "HOLD", "strategy": "Maintain warm contact but prioritize Vicat.", "priority": "medium"}
    }
    
    # Try loading from file for custom entries
    vendors = default_vendors.copy()
    if VENDOR_FILE.exists():
        try:
            with open(VENDOR_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                vendors.update(saved.get("vendors", {}))
        except Exception:
            pass
    
    if vendor_name.lower() == "all":
        return {"success": True, "vendors": vendors, "count": len(vendors)}
    
    # Search for specific vendor
    for name, data in vendors.items():
        if vendor_name.lower() in name.lower():
            return {"success": True, "vendor": name, **data}
    
    return {"success": False, "error": f"Vendor '{vendor_name}' not found", "available": list(vendors.keys())}


def update_vendor_status(vendor_name: str, status: str, notes: str = "") -> dict:
    """
    Updates the status and strategy notes for a specific vendor.
    
    Args:
        vendor_name: Company name (e.g., 'Vicat', 'Polycon').
        status: New status - 'PRIORITY', 'HOLD', 'BLOCKED', 'ACTIVE', or 'NEGOTIATING'.
        notes: Additional context or strategy update.
    
    Returns:
        dict: Confirmation of the vendor status update.
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        data = {"vendors": {}}
        if VENDOR_FILE.exists():
            with open(VENDOR_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        data["vendors"][vendor_name] = {
            "status": status.upper(),
            "notes": notes,
            "updated_at": datetime.now().isoformat(),
            "priority": "high" if status.upper() in ["PRIORITY", "ACTIVE"] else "medium"
        }
        
        with open(VENDOR_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {"success": True, "message": f"Vendor '{vendor_name}' updated to {status.upper()}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def set_strategic_priority(item: str, level: str, category: str = "general") -> dict:
    """
    Sets a company-wide strategic priority visible to all agents.
    
    Args:
        item: Description of the strategic priority.
        level: Priority level - 'critical', 'high', 'medium', 'low'.
        category: Category - 'general', 'engineering', 'marketing', 'legal', 'finance'.
    
    Returns:
        dict: Confirmation with the priority entry ID.
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        prio_file = _DATA_DIR / "strategic_priorities.json"
        
        data = {"priorities": []}
        if prio_file.exists():
            with open(prio_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        entry = {
            "id": f"sp_{int(datetime.now().timestamp())}",
            "item": item,
            "level": level,
            "category": category,
            "set_by": "CEO",
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        data["priorities"].insert(0, entry)
        
        # Keep only last 20
        data["priorities"] = data["priorities"][:20]
        
        with open(prio_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {"success": True, "message": f"Strategic priority set: [{level.upper()}] {item}", "id": entry["id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}
