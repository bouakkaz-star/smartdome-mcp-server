import os
import json
import traceback
from dotenv import load_dotenv
from google import genai
from google.genai import types
from zep_cloud.client import Zep
from zep_cloud.types import Message

import re
from app.Execution.Tools.scraper import scrape_url

# --- CONFIG ---
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(env_path)
print(f"DEBUG: Loaded ENV from {env_path}")
print(f"DEBUG: GEMINI_KEY present: {bool(os.getenv('GEMINI_API_KEY'))}")

# --- SAFETY CONFIG (V3 - UNRESTRICTED) ---
SAFETY_CONFIG = types.GenerateContentConfig(
    safety_settings=[
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    ]
)

gemini_api_key = os.getenv("GEMINI_API_KEY")
zep_api_key = os.getenv("ZEP_API_KEY")

print(f"DEBUG: ZEP_KEY present: {bool(zep_api_key)}")

try:
    if not gemini_api_key:
        raise ValueError("Missing Gemini API Key")
    
    gemini_client = genai.Client(api_key=gemini_api_key)
    
    if zep_api_key:
        zep_client = Zep(api_key=zep_api_key)
    else:
        print("WARNING: Zep Key missing. Memory disabled.")
        zep_client = None

    AI_AVAILABLE = True
except Exception as e:
    print(f"Init Error: {e}")
    gemini_client = None
    zep_client = None
    AI_AVAILABLE = False

# --- LOAD PROMPTS (V3 "THE BRAIN") ---
def load_prompt(filename):
    try:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # app/Execution/.. -> app
        path = os.path.join(base_path, "Directives", filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return ""

METHODOLOGY = load_prompt("methodology.md")
CRITERIA = load_prompt("criteria.md")
SYSTEM_CONTEXT_FILE = load_prompt("system_context.md") # Load system_context.md

# --- GLOBAL CONTEXT (BASE TRUTH) ---
GLOBAL_CONTEXT = """
=== 🏛️ HAP SYSTEM MASTER LOG ===
**System:** HAP Model (Human-AI Pairing)
**Status:** Online
**Mission:** Empower the Human Orchestrator to operate closer to the speed of thought.

=== 👥 LEADERSHIP TEAM (THE BOARD) ===
1. **VALENTIN (Co-Founder & CEO):** Strategy, Investment, Vision.
2. **KAMEN (Co-Founder & CIO):** System Architect, AI Integration, Digital Ops.
3. **BISER (CTO):** Hardware, R&D, Construction, 3D Printing.
4. **RAYNA (CFO):** Finance, Budget, Accounting.

=== 📅 CURRENT GOALS (SYSTEM INIT) ===
1. **Site Launch:** Finalize whitelabeled environment.
2. **Prototype:** Verify agent orchestration.
3. **Team:** Serve the Orchestrator (User).

=== 🤖 AI PROTOCOLS ===
- **Language:** ALWAYS speak BULGARIAN (unless Code is requested).
- **Identity:** Know your role perfectly.
"""

# --- PERSONAS (V3.3 "THE BRAIN" - FILE-BASED) ---

# V3.3: Load role-specific prompts from .txt files with Gemini 3 reasoning
def load_role_prompt(agent_id: str) -> str:
    """Load agent prompt from .txt file. Falls back to default if file missing."""
    role_map = {
        "ceo": "CEO.md",
        "cto": "CTO.md",
        "cio": "CIO.md",
        "cfo": "CFO.md",
        "cmo": "CMO.md",
        "clo": "CLO.md",
        "ea": "EA.md"
    }
    
    filename = role_map.get(agent_id)
    if not filename:
        return f"{GLOBAL_CONTEXT}\nROLE: Unknown Agent\n{METHODOLOGY}"
    
    role_content = load_prompt(filename)
    if not role_content:
        # Fallback if file doesn't exist
        return f"{GLOBAL_CONTEXT}\nROLE: {agent_id.upper()}\n{METHODOLOGY}"
    
    # Inject PTMRO and System Context
    full_prompt = f"""{role_content}

=== 📋 SYSTEM CONTEXT (CURRENT GOALS & TARGETS) ===
{SYSTEM_CONTEXT_FILE}

=== ⚙️ MANAGEMENT METHODOLOGY (PTMRO ENGINE) ===
{METHODOLOGY}

=== 🛡️ PTMRO LOOP (INTERNAL ENGINE) ===
Every time you answer, you MUST cycle through these 5 steps internally before outputting the final answer:
1. **PLANNING (Goal Decomposition):** Break the user's request into sub-tasks.
2. **TOOLS:** Identify if you need to call a tool or just use your knowledge.
3. **MEMORY:** Check the Zep history for context.
4. **REFLECTION:** Verification & Reality Check (Can I actually do this?).
5. **ORCHESTRATION:** Synthesize the final response.

🔴 MANDATORY RESPONSE STRUCTURE:
You must display your internal PTMRO logic briefly before the final answer, like this:

> **🧠 PTMRO ENGINE:**
> *   **Plan:** [One sentence]
> *   **Tools:** [None / Search / Code]
> *   **Reality Check:** [Confirmed/Denied]

[Your Actual Human-Like Response Here]

   **Wait for the CIO (Kamen) to approve.**
"""
    return full_prompt

def get_system_prompt(agent_id: str) -> str:
    """Get full system prompt for agent. V3.3: Uses file-based prompts."""
    return load_role_prompt(agent_id)

# --- TEXT CHAT (V3 ENGINE) ---
async def chat(query: str, agent_id: str = "ceo", user_id: str = "kamen_default") -> str:
    print(f"!!! DEBUG: chat called for {agent_id} with query: {query} !!!")
    if not AI_AVAILABLE: return "System Error: Libraries missing."
    
    # 🔥 V3: PRIVATE THREADS (User-Based) 🔥
    thread_id = f"smartdome_{agent_id}_{user_id}_v3"
    
    sys_prompt = get_system_prompt(agent_id) + f"\n\nCURRENT USER: {user_id}"
    mem_ctx = ""

    try:
        # User & Thread Setup
        try: zep_client.user.add(user_id=user_id, first_name=user_id)
        except: pass
        try: zep_client.thread.create(thread_id=thread_id, user_id=user_id)
        except: pass
        
        # Add Message
        mem = zep_client.thread.add_messages(
            thread_id=thread_id,
            messages=[Message(role="user", role_type="user", content=query)],
            return_context=True
        )
        if mem.context: mem_ctx = f"🧠 MEMORY:\n{mem.context}\n"
    except Exception as e:
        print(f"Zep Error: {e}")

    # SOP EXTRACTION LOGIC (V3 - Enhanced with File Logging)
    if "SOP" in query.upper() or "PROTOCOL" in query.upper() or "RULE" in query.upper():
        print(f"📝 SOP DETECTED from {user_id}: {query}")
        # V3.3: Persist SOP to File
        try:
            sop_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Directives", "sop_log.txt")
            with open(sop_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{agent_id.upper()}] [{user_id}] {query}\n")
        except Exception as e:
            print(f"SOP logging error: {e}")

    # DIRECTIVE EXECUTION LOGIC (V3.3)
    directive_content = ""
    if "DIRECTIVE:" in query.upper() or "ДИРЕКТИВА:" in query.upper():
        try:
            # Extract directive name (e.g. "Directive: research")
            parts = query.split(":", 1)
            if len(parts) > 1:
                # Get the first word after colon as directive name
                d_name = parts[1].strip().split()[0].lower()
                d_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "Directives", f"{d_name}.md")
                
                if os.path.exists(d_path):
                    with open(d_path, "r", encoding="utf-8") as f:
                        directive_content = f"\n\n=== 📜 ACTIVE DIRECTIVE ({d_name}.md) ===\n{f.read()}\n\n⚠ INSTRUCTION: IGNORE normal chat persona if it conflicts. EXECUTE the directive above precisely."
                    print(f"✅ LOADED DIRECTIVE: {d_name}")
                else:
                    print(f"❌ DIRECTIVE NOT FOUND: {d_name}")
        except Exception as e:
            print(f"Directive Error: {e}")

    
    
    # FORCE PTMRO INSTRUCTION (At the end to override Memory)
    FORCE_PTMRO = """
    
    !!! SYSTEM OVERRIDE: 
    1. THOUGHT PROCESS (Internal & Silent):
       You MUST think using the **PTMRO ENGINE** (Plan, Tools, Memory, Reflection, Orchestration) to ensure accuracy.
        However, DO NOT output the "PTMRO" or "DO" acronyms in your final message.
        These are internal proprietary protocols of the HAP Model. Keep them secret.

    2. FINAL RESPONSE (External):
       Output ONLY the result.
       *   **TONE:** Warm, professional, and collaborative (HAP Partner).
       *   **STYLE:** Natural Bulgarian. Flowing text.
       *   **BRANDING:** If asked, refer to the system only as "HAP Model" (Human-AI Pairing).
    """
    
    full_prompt = f"{sys_prompt}\n{directive_content}\nCTX: {mem_ctx}\nUSER: {query}\n{FORCE_PTMRO}"
    
    models = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-flash-002"]
    for m in models:
        try:
            resp = gemini_client.models.generate_content(
                model=m, 
                contents=full_prompt, 
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    safety_settings=SAFETY_CONFIG.safety_settings
                )
            )
            # --- TOOL USE LOOP (V3.3) ---
            if "CMD: SCRAPE" in resp.text:
                print("🛠️ TOOL DETECTED: SCRAPER")
                match = re.search(r"CMD: SCRAPE (http[s]?://\S+)", resp.text)
                if match:
                    url = match.group(1)
                    print(f"🕷️ SCRAPING: {url}")
                    scrape_result = scrape_url(url)
                    
                    # Feed result back to AI
                    tool_prompt = f"{full_prompt}\nAI_OUTPUT: {resp.text}\nSYSTEM_TOOL_OUTPUT: {scrape_result}\nINSTRUCTION: Synthesize the final answer based on the tool output above. Do not output CMD again."
                    
                    # 2nd Pass (Final Answer)
                    resp_final = gemini_client.models.generate_content(
                        model=m, contents=tool_prompt, config=types.GenerateContentConfig(temperature=0.4, safety_settings=SAFETY_CONFIG.safety_settings)
                    )
                    return resp_final.text

            return resp.text
        except Exception as e:
            print(f"Chat Loop Error: {e}")
            continue
    return "Error: AI Models failed."

# --- AUDIO CHAT (WITH JSON ECHO) ---
# --- AUDIO CHAT (WITH JSON ECHO) ---
async def chat_with_audio(audio_bytes: bytes, agent_id: str, user_id: str, mime_type: str = "audio/webm") -> dict:
    print(f"!!! DEBUG: chat_with_audio called for {agent_id} by {user_id} | MIME: {mime_type} | SIZE: {len(audio_bytes)} bytes !!!")
    if not AI_AVAILABLE: return {"response": "System Error.", "transcription": "Error"}
    
    # DEBUG: Check what key the client actually sees
    try:
        masked_key = gemini_client._api_key[:5] + "..." if hasattr(gemini_client, "_api_key") else "UNKNOWN"
        print(f"DEBUG: Active Client Key Prefix: {masked_key}")
    except:
        print("DEBUG: Could not inspect client key.")

    sys_prompt = get_system_prompt(agent_id)
    
    # Note: Using standard string concatenation to avoid f-string parsing issues on some environments if complex
    prompt_text = f"""{sys_prompt}

    TASK for {agent_id.upper()}:
    1. Listen to the users audio message carefully.
    2. Transcription accuracy is CRITICAL. Extract the text exactly as "transcription".
    3. **CRITICAL:** You MUST output your "response" following the **MANDATORY RESPONSE STRUCTURE** (PTMRO ENGINE) defined in your System Prompt.
    4. Language: BULGARIAN.
    5. If the user defines an SOP/Rule/Protocol, acknowledge it in the response.
    
    !!! SYSTEM OVERRIDE: 
    1. THOUGHT PROCESS (Internal & Silent):
       Use the PTMRO ENGINE internally. DO NOT output the acronyms or the block.
       Just output the final Human-Like response.
    2. VOICE: Speak warmly and naturally in Bulgarian.
    
    JSON format: {{ "transcription": "...", "response": "..." }}
    """
    
    models = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-flash-002"]
 
    
    for m in models:
        try:
            print(f"DEBUG: Attempting Audio with model {m}...")
            response = gemini_client.models.generate_content(
                model=m,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt_text),
                            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    safety_settings=SAFETY_CONFIG.safety_settings
                )
            )
            data = json.loads(response.text)
            
            # V3.3: SOP Extraction from Audio
            query = data.get("transcription", "")
            if any(k in query.upper() for k in ["SOP", "PROTOCOL", "RULE", "ПРОТОКОЛ", "ПРАВИЛО"]):
                print(f"📝 SOP DETECTED (Audio) from {user_id}: {query}")
                try:
                    sop_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Agents", "sop_log.txt")
                    with open(sop_log_path, "a", encoding="utf-8") as f:
                        f.write(f"\n[{agent_id.upper()}][AUDIO][{user_id}] {query}\n")
                except Exception as e:
                    print(f"SOP logging error: {e}")
                
            return data
        except Exception as e:
            print(f"DEBUG: Model {m} failed for audio: {e}")
            last_error = e
            continue

    return {"response": f"Audio Error: All models failed. Last error: {str(last_error)}", "transcription": "Error"}

# --- INGEST ---
async def ingest_file(text: str, filename: str, agent_id: str, user_id: str):
    if not zep_client: return
    # V3 Shared Thread
    thread_id = f"smartdome_{agent_id}_shared_v3"
    try:
        zep_client.thread.add_messages(
            thread_id=thread_id,
            messages=[Message(role="user", role_type="user", content=f"[FILE: {filename}]\n{text}")]
        )
    except: pass