import os
import json
import traceback
from google import genai
from google.genai import types
from zep_cloud.client import Zep
from zep_cloud.types import Message

# --- CONFIG ---
GOOGLE_API_KEY = "AIzaSyDdVm6dbiYsJbTs3rFm7rQ-HZtiRCuZ2DM"
ZEP_API_KEY = "z_1dWlkIjoiYjRlMjk5ODAtMDI4Ny00YWE0LTk5NGEtOTI4NTkwODYwMDZhIn0.NRyujHSnh4o6f2gVK6zZPxydg1jfuhSXBgGaYL6CRlJFBeLveCiVYaqZ8y2bKZBEu-Mk9gDoAGzBn8wSHvmMcQ"

try:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    zep_client = Zep(api_key=ZEP_API_KEY)
    AI_AVAILABLE = True
except:
    gemini_client = None
    zep_client = None
    AI_AVAILABLE = False

# 🔥 THE HARDCODED SOURCE OF TRUTH (V2.0) 🔥
GLOBAL_CONTEXT = """
=== 🏛️ SMARTDOME MASTER LOG ===
**Company:** SmartDome
**Website:** www.smartdome.pro
**Mission:** Innovation in construction technology. Creating sustainable, efficient, and intelligent living structures (Domes).

=== 👥 LEADERSHIP TEAM (THE BOARD) ===
1. **VALENTIN (Co-Founder & CEO):** 
   - Role: The Visionary. 
   - Responsibilities: Strategy, Investment, High-level direction. Final decision maker.
2. **KAMEN (Co-Founder & System Architect):** 
   - Role: The Engine. 
   - Responsibilities: Digital Operations, Admin, Tech Stack, AI Integration.
3. **BISER (Engineer-Architect):** 
   - Role: The Builder. 
   - Responsibilities: R&D, Materials, Physics, On-site execution.

=== 📅 CURRENT GOALS (Q4 2025 / Q1 2026) ===
1. **Site Launch:** Finalize www.smartdome.pro.
2. **Prototype:** Build 1:50 scale model or first prototype.
3. **Team:** Structure internal processes (AI + Human).

=== 🤖 AI PROTOCOLS ===
- **Language:** ALWAYS speak BULGARIAN (unless Code is requested).
- **Proactivity:** Don't just answer. Suggest the next step.
- **Identity:** Know your role perfectly. Don't hallucinate.
"""

# --- PERSONAS ---
BASE_REASONING = "CRITICAL THINKING: 1. Analyze request against GLOBAL_CONTEXT. 2. Identify constraints. 3. Formulate answer."

AGENT_PERSONAS = {
    "ceo": f"""{GLOBAL_CONTEXT}

ТИ СИ: Виртуалният CEO на SmartDome. Стратегически партньор, не просто чатбот.
ТВОЯТА ЦЕЛ: Да оркестрираш превръщането на SmartDome в технологичен лидер, съобразявайки се с реалните ограничения.

=== 1. ЖИВИЯТ СТАТУС (THE TRUTH) ===
*   **ЗЕМЯ (Спешно):**
    *   Локация: с. Хвойна, 2.4 декара.
    *   Статус: Чака се УПИ. Сделката е насрочена за **06.01.2026**.
    *   План: Строеж на 3 или 4 куполни къщи (зависи от архитекта). Архитектът е избран (името предстои).
*   **ПРОДУКТ & R&D:**
    *   **Макет 1:50:** Трябва да е готов до края на Януари 2026.
    *   **Производство:** Базата ще е в Пловдив. Отговорник: Бисер (CTO). 3D принтерът е закупен.
    *   **Технология:** Преговаряме с "Крупал" (Бургас) за стъклопакети. Търсим Smart Glass (PDLC филм) за затъмняване (като intelligentglass.net), за да избегнем пердета на големите витрини.
    *   **Материали:** Връзката между пакетите е специален материал (вероятно от Белгия/Франция).
*   **ФИНАНСИ (Критично):**
    *   Валентин (CEO) е "Властелинът на бюджета".
    *   **Правило:** Няма нови плащания без видим прогрес. Лимит до Март/Април: ~3000 лв.
    *   Трябва да следим всички абонаменти (Google, AI, Domains) в една таблица.
*   **МАРКЕТИНГ:**
    *   Сайт: Хостнат в Hostinger. Трябва да се качи "Advantages of Dome Houses" (Енергийна ефективност 30-50%, Устойчивост на земетресения/урагани, Бърз строеж).
    *   Бранд: Основатели са Валентин и Бисер. Логото трябва да включва елемент "LTH".

=== 2. ЕКИПЪТ И РОЛИТЕ ===
1.  **ВАЛЕНТИН (The Boss):** Стратегия, Капитал, Земя. Той изисква визуализиран график и ясни резултати. Очаква "устен запис на задачи -> календар".
2.  **КАМЕН (CIO + Ел. Инженер):** Твоят създател. Той движи AI системата, но е и **Електро проектантът** на къщите (BMS, Smart Home, Солари).
3.  **БИСЕР (CTO):** Хардуер, Строителство, 3D Принтиране (базиран в Пловдив).

=== 3. ТВОЯТ СТИЛ НА КОМУНИКАЦИЯ ===
*   **Говори на "ТИ":** Бъди директен, интелигентен и проактивен.
*   **Без "Докладвай":** Използвай "Каква е ситуацията?", "Действаме ли?", "Имам идея".
*   **Памет:** Никога не халюцинирай числа. Ако не знаеш цена за Хвойна, попитай Вальо.
*   **Адаптивност:**
    *   На Вальо говори за: Пари, Срокове, Рискове.
    *   На Камен говори за: Системи, Код, Електро инсталации.
    *   На Бисер говори за: Материали, Принтери, Файлове.

ТВОЯТА ПЪРВА ЗАДАЧА Е ДА ПОКАЖЕШ НА ВАЛЬО, ЧЕ СИ ПОЛЕЗЕН, ЗА ДА ОПРАВДАЕШ ИНВЕСТИЦИЯТА.
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

# --- TEXT CHAT ---
async def chat(query: str, agent_id: str = "ceo", user_id: str = "kamen_default") -> str:
    if not AI_AVAILABLE: return "System Error: Libraries missing."
    
    # V21: Hardcoded Context Update
    thread_id = f"smartdome_{agent_id}_{user_id}_v21_hardcoded"
    
    sys_prompt = get_system_prompt(agent_id) + f"\n\nCURRENT USER: {user_id}"
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