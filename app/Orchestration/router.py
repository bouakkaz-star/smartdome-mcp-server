import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- CONFIG ---
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(env_path)

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = None
if gemini_api_key:
    client = genai.Client(api_key=gemini_api_key)

logger = logging.getLogger("SmartDome-Router")

# --- ROUTER PROMPT ---
ROUTER_SYSTEM_PROMPT = """
ROLE: You are the Central Orchestrator for SmartDome.
Your ONLY job is to route the user's request to the correct Specialist Agent.

AGENTS:
1. **CEO (Valentin):** Strategy, Vision, High-level decisions.
2. **CTO (Biser):** Hardware, 3D Printing, Construction, R&D.
3. **CIO (Kamen):** Software Architecture, Code, AI Systems, Digital Ops.
4. **CFO (Rayna):** Money, Budget, Finance, Accounting.
5. **CMO:** Marketing, Branding, Public Relations.
6. **CLO:** Legal, Compliance, IP, Ethics.
7. **EA (Executive Assistant):** Scheduling, Calendar, Email Drafts, Logistics, or Ambiguous small tasks.

INSTRUCTIONS:
- Analyze the USER INPUT.
- If the user asks about multiple topics, pick the DOMINANT one.
- If the request is "Schedule...", "Remind me...", or "Draft email...", route to **EA**.
- If the request is vague or general chat (e.g. "Hello"), route to **EA**.
- Output JSON ONLY.

FORMAT:
{
  "target_agent": "ceo" | "cto" | "cio" | "cfo" | "cmo" | "clo" | "ea",
  "reasoning": "User asked about..."
}
"""

async def route_request(query: str, user_id: str) -> str:
    """
    Analyzes query and returns the target agent_role string (lowercase).
    """
    if not client:
        return "ea" # Fallback
    
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"{ROUTER_SYSTEM_PROMPT}\n\nUSER ({user_id}): {query}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        data = json.loads(response.text)
        target = data.get("target_agent", "ea").lower()
        logger.info(f"🔀 ROUTING: '{query}' -> {target.upper()} (Reason: {data.get('reasoning')})")
        return target

    except Exception as e:
        logger.error(f"Routing Error: {e}")
        return "ea" # Default safe fallback
