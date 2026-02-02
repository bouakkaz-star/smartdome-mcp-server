from pathlib import Path

def get_style_instruction() -> str:
    """Reads the shared style guide to inject into system prompts."""
    try:
        # Assuming run from apps/server/app or similar relative path logic
        # Adjust path to match: apps/server/app/utils/ -> ../../../../directives/shared/style_guide.md
        # BASE_DIR is typically calculated in main, but here we can try absolute or relative check
        
        # Hardcoded relative search for safety in this specific environment
        guide_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "directives" / "shared" / "style_guide.md"
        
        if guide_path.exists():
            content = guide_path.read_text(encoding="utf-8")
            return f"\n\n=== 💎 COMMUNICATION STANDARD (SKILL: CONCISE) ===\n{content}\n================================================="
        else:
            return ""
            
    except Exception:
        return ""
