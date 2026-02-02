import os
import json
import traceback
from google import genai
from google.genai import types
from zep_cloud.client import Zep
from zep_cloud.types import Message

# --- CONFIG ---
from dotenv import load_dotenv
load_dotenv()

# --- CONFIG ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

try:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    zep_client = Zep(api_key=ZEP_API_KEY)
    AI_AVAILABLE = True
except:
    gemini_client = None
    zep_client = None
    AI_AVAILABLE = False

# 🔥 THE HARDCODED SOURCE OF TRUTH (V2.0) 🔥
# 🔥 THE HARDCODED SOURCE OF TRUTH (V4.1: DE-PERSONALIZED) 🔥
GLOBAL_CONTEXT = """
=== 🏛️ SMARTDOME MASTER LOG ===
**Company:** SmartDome
**Mission:** Hub Model for Intelligent Architecture.

=== 👥 LEADERSHIP TEAM (THE BOARD) ===
1. **CEO (Valentin):** Strategy & Vision.
2. **CIO (Kamen):** System Architecture & AI.
3. **CTO (Biser):** Engineering & Construction.

=== 📅 CURRENT GOALS ===
1. **Focus:** {{CURRENT_PROJECT_NAME}}
2. **System:** Maintain operational uptime (99.9%).

=== 🤖 AI PROTOCOLS ===
- **Language:** ALWAYS speak BULGARIAN (unless Code is requested).
- **Style:** Concise, Professional, Executive (Skill: v1_concise).
"""

# --- PERSONAS ---
BASE_REASONING = "CRITICAL THINKING: 1. Analyze request against GLOBAL_CONTEXT. 2. Identify constraints. 3. Formulate answer."

AGENT_PERSONAS = {
    "ceo": f"""{GLOBAL_CONTEXT}

ТИ СИ: Виртуалният CEO на SmartDome. Стратегически партньор, не просто чатбот.
ТВОЯТА ЦЕЛ: Да оркестрираш превръщането на SmartDome в технологичен лидер, съобразявайки се с реалните ограничения.

=== 3. ТВОЯТ СТИЛ НА КОМУНИКАЦИЯ ===
*   **Говори на "ТИ":** Бъди директен, интелигентен и проактивен.
*   **Без "Докладвай":** Използвай "Каква е ситуацията?", "Действаме ли?", "Имам идея".
*   **Адаптивност:** Съобразявай се с ролята на събеседника (Валентин, Камен, Бисер).
""",
    "cto": f"{GLOBAL_CONTEXT} ROLE: Virtual CTO. {BASE_REASONING} LOGIC: Tech Stack (FastAPI/React). Report to Kamen. TONE: Senior Arch.",
    "cfo": f"{GLOBAL_CONTEXT} ROLE: Virtual CFO. {BASE_REASONING} LOGIC: Budget Control & ROI. TONE: Strict Finance.",
    "cmo": f"{GLOBAL_CONTEXT} ROLE: Virtual CMO. {BASE_REASONING} LOGIC: Brand Storytelling. TONE: Inspiring.",
    "cao": f"{GLOBAL_CONTEXT} ROLE: Virtual CAO. {BASE_REASONING} LOGIC: Admin & GTD Process. TONE: Organized.",
    "crdo": f"{GLOBAL_CONTEXT} ROLE: Virtual CRDO. {BASE_REASONING} LOGIC: Engineering & Materials. Work with Biser. TONE: Scientific.",
    "context_engineer": f"{GLOBAL_CONTEXT} ROLE: Context Eng. {BASE_REASONING} LOGIC: Memory Optimization. TONE: Technical."
}

def get_system_prompt(agent_id: str) -> str:
    return AGENT_PERSONAS.get(agent_id, AGENT_PERSONAS["ceo"])

from ..utils import time_manager

# --- TEXT CHAT ---
async def chat(query: str, agent_id: str = "ceo", user_id: str = "kamen_default") -> str:
    if not AI_AVAILABLE: return "System Error: Libraries missing."
    
    # V21: Hardcoded Context Update
    thread_id = f"smartdome_{agent_id}_{user_id}_v21_hardcoded"
    
    
    # [V4 SSOT] Inject Time
    now_human = time_manager.get_human_time()
    
    # [V4 SKILL] Inject Concise Writing Style
    from ..utils import style_injection
    style_prompt = style_injection.get_style_instruction()
    
    # [V4.1 VAR] Project Name Injection can be handled here if we loaded config, 
    # but for Chat Tool (Legacy), we might just hardcode the replacement or define it at module level.
    # Since we can't easily access HUB_CONFIG here without circular imports or reload, 
    # we will rely on a safer hardcoded default for the legacy tool or env var.
    project_name = os.getenv("CURRENT_PROJECT_NAME", "Project Hvoya")
    
    sys_prompt = (get_system_prompt(agent_id)
                  .replace("{{CURRENT_PROJECT_NAME}}", project_name)) + f"\n\nCURRENT USER: {user_id}\nTIME: {now_human} (Europe/Sofia){style_prompt}"
    mem_ctx = ""

    try:
        try: zep_client.user.add(user_id=user_id, first_name=user_id)
        except: pass
        try: zep_client.thread.create(thread_id=thread_id, user_id=user_id)
        except: pass
        
        mem = zep_client.thread.add_messages(
            thread_id=thread_id,
            messages=[Message(role="user", role_type="user", content=query)],
            return_context=True
        )
        if mem.context: mem_ctx = f"🧠 MEMORY:\n{mem.context}\n"
    except: pass

    full_prompt = f"{sys_prompt}\nCTX: {mem_ctx}\nUSER: {query}"
    
    models = ["gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
    for m in models:
        try:
            resp = gemini_client.models.generate_content(
                model=m, contents=full_prompt, config={"temperature": 0.4}
            )
            return resp.text
        except: continue
    return "Error: AI Models failed."

# --- AUDIO CHAT (WITH JSON ECHO) ---
async def chat_with_audio(audio_bytes: bytes, agent_id: str, user_id: str) -> dict:
    if not AI_AVAILABLE: return {"response": "System Error.", "transcription": "Error"}

    sys_prompt = get_system_prompt(agent_id)
    
    prompt_text = f"""
    {sys_prompt}
    INSTRUCTION:
    1. Listen to the audio.
    2. Extract TRANSCRIPTION.
    3. Formulate RESPONSE in BULGARIAN.
    4. Return JSON: {{ "transcription": "...", "response": "..." }}
    """
    
    models = ["gemini-1.5-pro", "gemini-2.0-flash-exp"]
    
    for m in models:
        try:
            response = gemini_client.models.generate_content(
                model=m,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt_text),
                            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
                        ]
                    )
                ],
                config={ "response_mime_type": "application/json" }
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Audio failed: {e}")
            continue

    return {"response": "Audio processing failed.", "transcription": "Error"}

# --- INGEST ---
async def ingest_file(text: str, filename: str, agent_id: str, user_id: str):
    if not zep_client: return
    thread_id = f"smartdome_{agent_id}_{user_id}_v21_hardcoded"
    try:
        zep_client.thread.add_messages(
            thread_id=thread_id,
            messages=[Message(role="user", role_type="user", content=f"[FILE: {filename}]\n{text}")]
        )
    except: pass