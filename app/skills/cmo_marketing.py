"""
CMO Marketing Skill Module
============================
Tools for the Chief Marketing Officer.
Social media content, brand voice, and campaign management.
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

CAMPAIGNS_FILE = _DATA_DIR / "campaigns.json"


def generate_social_post(platform: str, topic: str, tone: str = "professional", language: str = "bulgarian") -> dict:
    """
    Creates a structured social media post draft with platform-specific formatting.
    
    Args:
        platform: Target platform - 'linkedin', 'instagram', 'twitter', 'facebook'.
        topic: Subject matter for the post.
        tone: Writing tone - 'professional', 'casual', 'inspirational', 'technical'. Default 'professional'.
        language: 'bulgarian' or 'english'. Default 'bulgarian'.
    
    Returns:
        dict: Post structure with character limits, hashtag suggestions, and draft outline.
    """
    limits = {
        "linkedin": {"chars": 3000, "hashtags": 5, "format": "Long-form with paragraphs"},
        "instagram": {"chars": 2200, "hashtags": 30, "format": "Visual-first with caption"},
        "twitter": {"chars": 280, "hashtags": 3, "format": "Concise with impact"},
        "facebook": {"chars": 63206, "hashtags": 5, "format": "Conversational with media"}
    }
    
    platform_info = limits.get(platform.lower(), limits["linkedin"])
    
    return {
        "success": True,
        "platform": platform,
        "char_limit": platform_info["chars"],
        "max_hashtags": platform_info["hashtags"],
        "format_guide": platform_info["format"],
        "topic": topic,
        "tone": tone,
        "language": language,
        "brand_tags": ["#SmartDome", "#HAPM", "#PropTech", "#3DPrinting", "#Innovation"],
        "instruction": f"Draft a {tone} {platform} post about '{topic}' in {language}. Follow {platform_info['format']} format. Max {platform_info['chars']} chars."
    }


def campaign_tracker(action: str, campaign_name: str = "", channel: str = "", budget: float = 0, notes: str = "") -> dict:
    """
    Tracks marketing campaign status and performance.
    
    Args:
        action: 'list' to view all, 'create' to start new campaign, 'update' to modify.
        campaign_name: Name of the campaign.
        channel: Distribution channel (e.g., 'LinkedIn', 'Email', 'Event').
        budget: Campaign budget in BGN.
        notes: Additional context or performance notes.
    
    Returns:
        dict: Campaign data or confirmation of action.
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        data = {"campaigns": []}
        if CAMPAIGNS_FILE.exists():
            with open(CAMPAIGNS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        if action == "list":
            return {"success": True, "count": len(data["campaigns"]), "campaigns": data["campaigns"]}
        
        elif action == "create":
            entry = {
                "id": f"camp_{int(datetime.now().timestamp())}",
                "name": campaign_name,
                "channel": channel,
                "budget": budget,
                "status": "planned",
                "created_at": datetime.now().isoformat(),
                "notes": notes,
                "metrics": {"reach": 0, "engagement": 0, "conversions": 0}
            }
            data["campaigns"].insert(0, entry)
            
            with open(CAMPAIGNS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return {"success": True, "message": f"Campaign '{campaign_name}' created.", "campaign": entry}
        
        elif action == "update":
            for camp in data["campaigns"]:
                if campaign_name.lower() in camp.get("name", "").lower():
                    if notes:
                        camp["notes"] = notes
                    camp["updated_at"] = datetime.now().isoformat()
                    
                    with open(CAMPAIGNS_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    
                    return {"success": True, "message": f"Campaign '{camp['name']}' updated.", "campaign": camp}
            
            return {"success": False, "error": f"Campaign '{campaign_name}' not found."}
        
        return {"success": False, "error": f"Unknown action '{action}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def brand_voice_check(text: str) -> dict:
    """
    Validates text against SmartDome brand guidelines.
    Checks for tone consistency and brand alignment.
    
    Args:
        text: The text content to validate.
    
    Returns:
        dict: Compliance score and specific feedback.
    """
    issues = []
    score = 100
    
    text_lower = text.lower()
    
    # Check for banned/off-brand phrases
    off_brand = ["cheap", "basic", "simple solution", "just a house", "ordinary"]
    for phrase in off_brand:
        if phrase in text_lower:
            issues.append(f"Off-brand language: '{phrase}' — use premium alternatives")
            score -= 15
    
    # Check for required brand values
    brand_values = ["innovation", "sustainable", "smart", "precision", "future"]
    values_present = sum(1 for v in brand_values if v in text_lower)
    if values_present == 0 and len(text) > 100:
        issues.append("No brand value keywords detected. Consider incorporating innovation/sustainability themes.")
        score -= 10
    
    # Check for technical accuracy
    if "3d print" in text_lower and "uhpc" not in text_lower and "concrete" not in text_lower:
        issues.append("Mention of 3D printing should reference UHPC/concrete material for accuracy.")
        score -= 5
    
    score = max(0, score)
    grade = "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "D"
    
    return {
        "success": True,
        "score": score,
        "grade": grade,
        "issues": issues,
        "verdict": "On-brand" if score >= 70 else "Needs revision"
    }
