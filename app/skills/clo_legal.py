"""
CLO Legal Skill Module
=======================
Tools for the Chief Legal Officer.
Contract analysis, NDA generation, and IP registry.
"""
import json
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _SCRIPT_DIR.parent.parent

if "Personal assistant" in str(_SERVER_ROOT):
    _DATA_DIR = _SERVER_ROOT / "data"
else:
    _DATA_DIR = Path("/tmp/data")

IP_REGISTRY_FILE = _DATA_DIR / "ip_registry.json"


def generate_nda(party_name: str, jurisdiction: str = "Bulgaria", scope: str = "mutual", duration_months: int = 24) -> dict:
    """
    Generates a structured NDA (Non-Disclosure Agreement) template.
    Outputs the key sections that the CLO should review and finalize.
    
    Args:
        party_name: Name of the other party (company or individual).
        jurisdiction: Legal jurisdiction. Default 'Bulgaria'.
        scope: 'mutual' (both parties) or 'unilateral' (one-way). Default 'mutual'.
        duration_months: Confidentiality period in months. Default 24.
    
    Returns:
        dict: NDA structure with key clauses for review.
    """
    nda_type = "Mutual" if scope == "mutual" else "Unilateral"
    
    return {
        "success": True,
        "type": f"{nda_type} NDA",
        "parties": {
            "party_a": "SmartDome EOOD",
            "party_b": party_name
        },
        "jurisdiction": jurisdiction,
        "duration_months": duration_months,
        "key_clauses": {
            "confidential_info": "All technical specifications, business strategies, financial data, and proprietary methodologies (including HAPM).",
            "exclusions": "Public domain information, independently developed knowledge, prior knowledge.",
            "obligations": f"{'Both parties' if scope == 'mutual' else party_name} must maintain strict confidentiality.",
            "remedies": "Injunctive relief + damages per Bulgarian Commercial Code.",
            "return_of_materials": "All confidential materials must be returned/destroyed within 30 days of termination.",
            "governing_law": f"Laws of {jurisdiction}"
        },
        "instruction": f"Review this {nda_type} NDA structure for {party_name}. Finalize the exact legal language before signing."
    }


def ip_registry(action: str, asset_name: str = "", asset_type: str = "software", description: str = "") -> dict:
    """
    Manages the SmartDome IP (Intellectual Property) asset register.
    
    Args:
        action: 'list' to view all, 'add' to register new IP, 'search' to find specific.
        asset_name: Name of the IP asset (required for 'add' and 'search').
        asset_type: Type - 'software', 'methodology', 'design', 'patent', 'trademark'. Default 'software'.
        description: Description of the IP asset (for 'add' action).
    
    Returns:
        dict: IP registry entries or confirmation of new registration.
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        data = {"assets": []}
        if IP_REGISTRY_FILE.exists():
            with open(IP_REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        if action == "list":
            return {"success": True, "count": len(data["assets"]), "assets": data["assets"]}
        
        elif action == "add":
            if not asset_name:
                return {"success": False, "error": "asset_name is required for 'add' action."}
            
            entry = {
                "id": f"ip_{int(datetime.now().timestamp())}",
                "name": asset_name,
                "type": asset_type,
                "description": description,
                "owner": "SmartDome EOOD",
                "registered_at": datetime.now().isoformat(),
                "status": "active",
                "protection": "trade_secret"
            }
            data["assets"].append(entry)
            
            with open(IP_REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return {"success": True, "message": f"IP asset '{asset_name}' registered.", "entry": entry}
        
        elif action == "search":
            matches = [a for a in data["assets"] if asset_name.lower() in a.get("name", "").lower()]
            return {"success": True, "query": asset_name, "results": matches}
        
        return {"success": False, "error": f"Unknown action '{action}'. Use 'list', 'add', or 'search'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def contract_risk_scan(contract_text: str) -> dict:
    """
    Flags potential risk areas in a contract text for CLO review.
    Checks for common high-risk clauses and missing protections.
    
    Args:
        contract_text: The contract text to analyze.
    
    Returns:
        dict: Risk flags and recommendations for each identified issue.
    """
    risk_keywords = {
        "unlimited liability": "HIGH",
        "indemnify": "MEDIUM",
        "non-compete": "HIGH",
        "perpetual": "MEDIUM",
        "exclusive rights": "HIGH",
        "penalty": "MEDIUM",
        "automatic renewal": "MEDIUM",
        "intellectual property transfer": "HIGH",
        "all rights": "HIGH",
        "waive": "HIGH",
        "irrevocable": "HIGH"
    }
    
    text_lower = contract_text.lower()
    flags = []
    
    for keyword, severity in risk_keywords.items():
        if keyword in text_lower:
            flags.append({
                "clause": keyword,
                "severity": severity,
                "recommendation": f"Review '{keyword}' clause carefully — potential risk."
            })
    
    # Check for missing protections
    missing = []
    protections = ["governing law", "dispute resolution", "termination", "confidentiality", "limitation of liability"]
    for p in protections:
        if p not in text_lower:
            missing.append(p)
    
    risk_level = "HIGH" if any(f["severity"] == "HIGH" for f in flags) else "MEDIUM" if flags else "LOW"
    
    return {
        "success": True,
        "risk_level": risk_level,
        "flags": flags,
        "missing_clauses": missing,
        "total_flags": len(flags),
        "recommendation": "Seek legal counsel before signing." if risk_level == "HIGH" else "Review flagged items."
    }
