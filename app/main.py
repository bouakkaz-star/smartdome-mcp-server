import os
import json
import uvicorn
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from zep_cloud.client import Zep
from zep_cloud.types import Message
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import traceback
import re
import secrets
import time

# --- PLUGIN LOADER (Engineering Team Skills) ---
try:
    from Core.plugin_loader import PluginLoader
except ImportError:
    from app.Core.plugin_loader import PluginLoader

# --- UTILS ---
def wait_for_files_active(files):
    """Waits for the given files to be active.
    Some files uploaded to the Gemini API need to be processed before they can
    be used as prompt inputs. The status can be seen by querying the file's
    "state" field.
    This implementation checks for a file's state and waits if the state is
    "PROCESSING". If the state is "FAILED", it raises an exception.
    """
    print("DEBUG: Waiting for file processing...", file=sys.stderr, flush=True)
    for name in (file.name for file in files):
        file = client.files.get(name=name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(2)
            file = client.files.get(name=name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
    print("...all files ready", file=sys.stderr, flush=True)

if __name__ == "__main__":
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
try:
    from utils import time_manager
except ImportError:
    from app.utils import time_manager

load_dotenv()

# CRITICAL: Read API key from environment (Cloud Run or .env)
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

# DEBUG: Log startup state
import sys
print(f"DEBUG_STARTUP: GEMINI_API_KEY exists: {bool(GOOGLE_API_KEY)}", file=sys.stderr, flush=True)
print(f"DEBUG_STARTUP: Key prefix: {GOOGLE_API_KEY[:10] if GOOGLE_API_KEY else 'NONE'}...", file=sys.stderr, flush=True)

# Environment-aware path resolution
# In cloud container: /app is the root, files are at /app/app/main.py
# In local dev: files are at .../Personal assistant/apps/server/app/main.py
_SCRIPT_DIR = Path(__file__).resolve().parent  # /app/app or .../apps/server/app
_SERVER_ROOT = _SCRIPT_DIR.parent  # /app or .../apps/server

# Check if we're in LOCAL dev (path contains 'Personal assistant')
_IS_LOCAL = "Personal assistant" in str(_SERVER_ROOT)

if _IS_LOCAL:
    BASE_DIR = _SERVER_ROOT.parent.parent  # Up to 'Personal assistant'
    DATA_DIR = BASE_DIR / "apps" / "server" / "data"
    CONFIG_PATH = BASE_DIR / "hapm_config.json"
    DIRECTIVES_DIR = BASE_DIR / "directives" / "smartdome"
else:
    # Cloud container - Read-Only Source at /workspace (or wherever)
    BASE_DIR = _SERVER_ROOT
    DATA_DIR = Path("/tmp/data")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy config to /tmp to allow writing
    import shutil
    # Config is now DEPLOYED with the app in the same folder
    SOURCE_CONFIG = _SCRIPT_DIR / "hapm_config.json"
    CONFIG_PATH = Path("/tmp/hapm_config.json")
    
    # ALWAYS mirror source to /tmp to ensure latest build config is used
    if SOURCE_CONFIG.exists():
        try:
            shutil.copy(SOURCE_CONFIG, CONFIG_PATH)
            logging.info(f"Mirrored config to {CONFIG_PATH}")
        except Exception as e:
            logging.error(f"Failed to copy config: {e}")
            if not CONFIG_PATH.exists(): CONFIG_PATH = SOURCE_CONFIG 

    # Deployment Source has 'directives_data' (force copied)
    DIRECTIVES_DIR = _SCRIPT_DIR / "directives_data" / "smartdome"

    # BOOTSTRAP DATA (Copy from build source to /tmp/data on first run)
    import shutil
    BOOTSTRAP_HISTORY = _SCRIPT_DIR / "chat_history_bootstrap.json"
    CLOUD_HISTORY = DATA_DIR / "chat_history.json"
    
    if BOOTSTRAP_HISTORY.exists() and not CLOUD_HISTORY.exists():
        try:
            shutil.copy(BOOTSTRAP_HISTORY, CLOUD_HISTORY)
            logging.info(f"Bootstrapped chat history to {CLOUD_HISTORY}")
        except Exception as e:
            logging.error(f"Bootstrap history failed: {e}")

TASKS_FILE = DATA_DIR / "director_tasks.json"

logging.basicConfig(level=logging.INFO)

HUB_CONFIG = {}
if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f: HUB_CONFIG = json.load(f)
    except: pass

client = None
if GOOGLE_API_KEY: client = genai.Client(api_key=GOOGLE_API_KEY)

# --- INITIALIZE PLUGIN LOADER (DevOps Agent Skills) ---
SKILLS_DIR = _SCRIPT_DIR / "skills"
plugin_loader = PluginLoader(str(SKILLS_DIR))
plugin_loader.load_all()
logging.info(f"Loaded {len(plugin_loader.tools)} skills: {list(plugin_loader.tools.keys())}")

zep = None
if ZEP_API_KEY: 
    try: zep = Zep(api_key=ZEP_API_KEY)
    except: pass

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"],
    allow_methods=["*"], 
    allow_headers=["*"],
    allow_credentials=True
)

# --- HELPERS ---
def log_to_file(msg):
    import sys
    # Print to stderr for server_final.log capture
    print(f"DEBUG_LOG: {msg}", file=sys.stderr, flush=True)
    try:
        import tempfile
        log_path = Path(tempfile.gettempdir()) / "debug_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except: pass

def upload_to_gemini(file_obj, mime_type="audio/mp3"):
    """Robust global version using /tmp and correcting MIME types."""
    import sys
    import tempfile
    try:
        log_to_file(f"Starting upload_to_gemini (mime: {mime_type})...")
        
        # We need a physical path for most SDKs
        file_obj.file.seek(0)
        content = file_obj.file.read()
        
        if not client: 
            log_to_file("ERROR: Gemini Client not initialized.")
            return None
        
        # --- MIME TYPE CORRECTION ---
        final_mime = mime_type
        if mime_type == "audio/webm":
            final_mime = "video/webm"
        
        upload_params = {"mime_type": final_mime}
        if "audio" in mime_type or "video" in mime_type:
            upload_params["display_name"] = "User Recording"
            
        # Create temp file in /tmp
        temp_dir = Path(tempfile.gettempdir())
        temp_path = temp_dir / f"gemini_upload_{int(time.time())}.tmp"
        with open(temp_path, "wb") as f:
            f.write(content)
            
        log_to_file(f"Temp file saved to {temp_path} ({len(content)} bytes). Uploading...")
        
        # SDK Call
        try:
            uploaded_file = client.files.upload(
                file=temp_path,
                config=types.UploadFileConfig(**upload_params)
            )
        except Exception as e:
            log_to_file(f"Upload failed: {e}")
            return None

        # Cleanup
        try: os.remove(temp_path)
        except: pass
        
        log_to_file(f"Upload Success: {uploaded_file.uri}. Waiting for ACTIVE state...")
        
        # --- WAIT FOR ACTIVE STATE (Fix Race Condition) ---
        max_wait = 60  # Increased for Gemini 3
        wait_interval = 5 # Higher interval to avoid 500 polling glitch
        elapsed = 0
        while elapsed < max_wait:
            try:
                # Use name directly from uploaded_file
                file_check = client.files.get(name=uploaded_file.name)
                state = file_check.state.name if hasattr(file_check.state, 'name') else str(file_check.state)
                log_to_file(f"File state: {state} (elapsed: {elapsed}s)")
                
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    log_to_file("ERROR: File entered FAILED state. Aborting.")
                    return None
            except Exception as e:
                # Catch transient 500 errors or JSON parsing issues from SDK
                log_to_file(f"DEBUG: Handling polling glitch: {e}")
                # Don't return None here, just wait and retry
            
            time.sleep(wait_interval)
            elapsed += wait_interval
        
        if elapsed >= max_wait:
            log_to_file(f"WARNING: File did not become ACTIVE within {max_wait}s")
            return None 

        return uploaded_file.uri

    except Exception as e:
        log_to_file(f"Upload Error: {e}")
        return None

# --- ENDPOINTS ---
# --- TASK MANAGER ---
class TaskManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.ensure_file()

    def ensure_file(self):
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"directors": {}}, f, indent=2)

    def load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f: # Force UTF-8
                return json.load(f)
        except: return {"directors": {}}

    def save(self, data):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


    def add_task(self, agent_id, title, description, priority, source="manual", delegated_by=None):
        data = self.load()
        if agent_id not in data["directors"]:
            data["directors"][agent_id] = {"tasks": []}
            
        new_task = {
            "id": f"t_{int(time.time()*1000)}",
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "source": source,
            "delegated_by": delegated_by,
            "created_at": time_manager.get_iso_time()
        }
        data["directors"][agent_id]["tasks"].insert(0, new_task)
        self.save(data)

    # --- HELPER: Logic removed (using global helper) ---
    def dummy_upload_placeholder():
         pass

    # ... (skipping TaskManager/ChatManager) ...

    # In chat_endpoint:
    # ...
    # if file and file.filename:
    #     mime = ... 
    #     uri = upload_to_gemini(file, mime)
    #     if uri:
    #         parts.append(...)
    #     else:
    #         # ERROR INJECTION
    #         print("[DEBUG] Upload returned None. Injecting Error Message.", file=sys.stderr)
    #         base_prompt += "\n\n[SYSTEM ERROR]: user attached a file but the system failed to upload it to your context. Inform the user: 'I received your file signal, but the upload pipeline failed. Please check backend logs.'"

task_mgr = TaskManager(TASKS_FILE)
# --- CHAT MANAGER ---
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"

class ChatManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.ensure_file()

    def ensure_file(self):
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"threads": {}}, f, indent=2)

    def load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {"threads": {}}

    def save(self, data):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_message(self, thread_id, role, content):
        data = self.load()
        if thread_id not in data["threads"]:
            data["threads"][thread_id] = []
        
        msg = {
            "role": role,
            "content": content,
            "created_at": time_manager.get_iso_time()
        }
        data["threads"][thread_id].append(msg)
        if len(data["threads"][thread_id]) > 300:
            data["threads"][thread_id] = data["threads"][thread_id][-300:]
            
        self.save(data)
    
    def get_history(self, thread_id):
        data = self.load()
        return data["threads"].get(thread_id, [])

chat_mgr = ChatManager(CHAT_HISTORY_FILE)

# --- ENDPOINTS ---
@app.get("/api/config")
async def get_config(): return HUB_CONFIG

@app.get("/api/status")
async def get_status():
    return {
        "status": "Active", 
        "time": time_manager.get_iso_time(),
        "model": HUB_CONFIG.get("system", {}).get("model_provider", "gemini-3-flash-preview")
    }

@app.get("/api/history/{thread_id}")
async def get_chat_history(thread_id: str):
    # Hybrid: Try Local first (faster/reliable)
    local_msgs = chat_mgr.get_history(thread_id)
    if local_msgs:
        return {"messages": local_msgs}
    
    # Fallback to Zep (Legacy)
    if zep:
        try:
             z_msgs = zep.thread.get(thread_id).messages
             return {"messages": [{"role": m.role, "content": m.content, "created_at": getattr(m, 'created_at', None)} for m in z_msgs]}
        except: pass
        
    return {"messages": []}

@app.get("/api/debug/system")
async def debug_system():
    import os
    listing = []
    for root, dirs, files in os.walk("."):
        for name in files:
            listing.append(os.path.join(root, name))
    
    cio_path = DIRECTIVES_DIR / "cio.md"
    cio_content = "NOT FOUND"
    if cio_path.exists():
        with open(cio_path, "r", encoding="utf-8") as f: cio_content = f.read()[:200] + "..."

    return {
        "cwd": os.getcwd(),
        "listing_limit_50": listing[:50],
        "directives_dir": str(DIRECTIVES_DIR),
        "directives_exists": DIRECTIVES_DIR.exists(),
        "cio_md_exists": cio_path.exists(),
        "cio_snippet": cio_content,
        "config_path": str(CONFIG_PATH),
        "config_exists": CONFIG_PATH.exists()
    }

# --- AUTHENTICATION ---
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.get("/api/auth/status/{slug}")
async def check_auth_status(slug: str):
    # Reload config to get latest users
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config = json.load(f)
    user = next((p for p in config.get("participants", []) if p["slug"] == slug), None)
    
    if not user: raise HTTPException(404, "User not found")
    
    return {
        "id": user["id"],
        "name": user["name"],
        "has_password": user["password_hash"] is not None
    }

# BACKWARD COMPATIBILITY for Stale Vercel Deployments
@app.get("/api/auth/verify-link")
async def legacy_verify_link(slug: str):
    return await check_auth_status(slug)

@app.post("/api/auth/setup")
async def setup_password(slug: str = Form(...), password: str = Form(...)):
    # 1. Load
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config = json.load(f)
    
    # 2. Find User
    user = next((p for p in config.get("participants", []) if p["slug"] == slug), None)
    if not user: raise HTTPException(404, "User not found")
    
    # 3. Update Password
    if user["password_hash"] is not None:
        return JSONResponse({"error": "Password already set. Please login."}, status_code=400)
        
    user["password_hash"] = hash_password(password)
    user["is_initialized"] = True
    
    # 4. Save
    with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(config, f, indent=4)
    
    return {"status": "success", "token": f"sd_{secrets.token_hex(8)}", "user": user}

@app.post("/api/auth/login")
async def login(slug: str = Form(None), user_id: str = Form(None), password: str = Form(...)):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config = json.load(f)
    
    # Find user by slug OR id
    user = None
    if slug:
        user = next((p for p in config["participants"] if p["slug"] == slug), None)
    elif user_id:
        user = next((p for p in config["participants"] if p["id"] == user_id), None)
        
    if not user: raise HTTPException(401, "User not found")
    
    # Verify
    if not user["password_hash"]:
         # Allow login if no password set? No, force setup via UI logic. 
         # But for legacy dev, we might allow it. 
         # User requested mandatory password.
         raise HTTPException(403, "Setup required")
         
    if hash_password(password) != user["password_hash"]:
        raise HTTPException(401, "Invalid password")
        
    return {"token": f"sd_{secrets.token_hex(8)}", "user": user}

@app.get("/api/tasks/{agent_id}")
async def get_director_tasks(agent_id: str):
    data = task_mgr.load()
    return data.get("directors", {}).get(agent_id, {"tasks": []})

@app.post("/api/tasks/create")
async def create_task_api(agent_id: str = Form("ralf"), title: str = Form(...), priority: str = Form("green")):
    task_mgr.add_task(agent_id, title, "Manual entry", priority, "manual")
    return {"status": "success", "message": "Task created"}

@app.post("/api/tasks/update")
async def update_task_api(
    agent_id: str = Form(...), 
    task_id: str = Form(...), 
    priority: str = Form(None),
    status: str = Form(None)
):
    data = task_mgr.load()
    updated = False
    
    # Map friendly names if needed
    agent_map = {"valentin": "ceo", "kamen": "cio", "biser": "cto", "designer": "designer", "ralf": "ralf"}
    target_id = agent_map.get(agent_id.lower(), agent_id.lower())

    if target_id in data["directors"]:
        for t in data["directors"][target_id]["tasks"]:
            if t["id"] == task_id:
                if priority: t["priority"] = priority
                if status: t["status"] = status
                updated = True
                break
    
    if updated:
        task_mgr.save(data)
        return {"status": "updated", "id": target_id}
    return {"status": "failed", "reason": "Task or Agent not found"}

@app.delete("/api/tasks/delete")
async def delete_task_api(agent_id: str, task_id: str):
    data = task_mgr.load()
    
    # Map friendly names
    agent_map = {"valentin": "ceo", "kamen": "cio", "biser": "cto", "designer": "designer", "ralf": "ralf"}
    target_id = agent_map.get(agent_id.lower(), agent_id.lower())

    if target_id in data["directors"]:
        # SOFT DELETE: Mark as dismissed instead of removing
        for t in data["directors"][target_id]["tasks"]:
            if t["id"] == task_id:
                t["status"] = "dismissed"
                task_mgr.save(data)
                return {"status": "dismissed"}
            
    return {"status": "failed", "reason": "Task not found"}

AUDIT_FILE = DATA_DIR / "audit_log.json"

# --- TOOLS ---
def create_scheduler_task(agent_id: str, title: str, description: str = "Manual entry", priority: str = "green", from_agent: str = None):
    """
    Creates a new task in the specialized agent scheduler.
    
    Args:
        agent_id: The target agent (cio, cto, ralf, etc).
        title: Short title.
        description: Details.
        priority: 'red', 'orange', 'green'.
        from_agent: The role creating this task (optional).
    """
    try:
        # Validate Priority
        if priority not in ["red", "orange", "green"]: priority = "green"
        
        # --- HALLUCINATION GUARD ---
        # Block tasks that are just "Transcription" or "Audio" - the AI should DO IT, not schedule it.
        forbidden_keywords = ["transcription", "audio processing", "transcribe", "listen to audio"]
        if any(k in title.lower() for k in forbidden_keywords) or any(k in description.lower() for k in forbidden_keywords):
            return "ERROR: DO NOT SCHEDULE TRANSCRIPTION. Just transcribe the audio directly in your response."

        # Map friendly names
        agent_map = {"valentin": "ceo", "kamen": "cio", "biser": "cto", "designer": "designer", "ralf": "ralf"}
        target_id = agent_map.get(agent_id.lower(), agent_id.lower())
        
        # Determine source parameters
        delegator = None
        delegator_id = None
        
        if from_agent:
             delegator = agent_map.get(from_agent.lower(), from_agent.lower()).upper()
             delegator_id = agent_map.get(from_agent.lower(), from_agent.lower())

        # 1. Create Task for TARGET (Receiver)
        task_mgr.add_task(target_id, title, description, priority, "ai_generated", delegated_by=delegator)
        
        # 2. Create Tracking Task for SENDER (Start)
        # If we have a known delegator ID (sender), add a record there too.
        if delegator_id and delegator_id != target_id:
             sender_desc = f"Delegated to {target_id.upper()}: {description}"
             task_mgr.add_task(delegator_id, title, sender_desc, "blue", "ai_generated") # Blue = Delegated Status in UI logic

        src_msg = f" (Delegated by {delegator})" if delegator else ""
        return f"Task '{title}' created successfully for {target_id.upper()}{src_msg}."
    except Exception as e:
        return f"Failed to create task: {str(e)}"

def log_anomaly(agent_id: str, description: str, severity: str = "medium"):
    """
    Logs a technical anomaly for the System Engineer (Antigravity).
    Use this when a code-level fix is required (e.g., UI bug, API 500 error).
    """
    try:
        path = DATA_DIR / "system_anomalies.json"
        if not path.exists():
            with open(path, "w") as f: json.dump({"anomalies": []}, f)
            
        with open(path, "r") as f: data = json.load(f)
        
        entry = {
            "id": f"err_{int(time.time()*1000)}",
            "agent": agent_id,
            "description": description,
            "severity": severity,
            "timestamp": time_manager.get_iso_time(),
            "status": "open"
        }
        data["anomalies"].insert(0, entry) # Newest first
        
        with open(path, "w") as f: json.dump(data, f, indent=2)
        return f"Anomaly logged: [{severity.upper()}] {description}. Engineering notified."
    except Exception as e:
        return f"Failed to log anomaly: {e}"

def generate_weekly_report(agent_id: str):
    """
    Generates an immediate system summary report (Tasks & Anomalies).
    Triggered by user command "Generate summary", "Report status", etc.
    """
    try:
        # 1. Load Tasks
        task_data = task_mgr.load()
        active_tasks = 0
        completed_tasks = 0
        
        for d_id, data in task_data.get("directors", {}).items():
            for t in data.get("tasks", []):
                if t["status"] == "completed": completed_tasks += 1
                elif t["status"] == "pending": active_tasks += 1

        # 2. Load Anomalies
        anom_path = DATA_DIR / "system_anomalies.json"
        anom_count = 0
        latest_anom = "None"
        if anom_path.exists():
            with open(anom_path, "r") as f: 
                anoms = json.load(f).get("anomalies", [])
                anom_count = len(anoms)
                if anoms: latest_anom = f"[{anoms[0]['severity']}] {anoms[0]['description']}"

        report = f"""
# 📊 SYSTEM REPORT (Generated by {agent_id})
**Time:** {time_manager.get_iso_time()}

## 🟢 Operational Status
- **Active Tasks:** {active_tasks}
- **Completed:** {completed_tasks}

## 🔴 System Health
- **Open Anomalies:** {anom_count}
- **Latest Alert:** {latest_anom}

## 📋 Next Steps
Review 'director_tasks.json' for full details.
"""
        return report
    except Exception as e:
        return f"Report generation failed: {e}"

class AuditManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.ensure_file()

    def ensure_file(self):
        if not self.filepath.exists():
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"logs": []}, f, indent=2)

    def load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {"logs": []}

    def save(self, data):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def log(self, agent, request, response):
        data = self.load()
        entry = {
            "timestamp": time_manager.get_iso_time(),
            "agent": agent,
            "request": request[:100] + "..." if len(request) > 100 else request,
            "response": response[:100] + "..." if len(response) > 100 else response
        }
        data["logs"].insert(0, entry) # Newest first
        if len(data["logs"]) > 50: data["logs"] = data["logs"][:50]
        self.save(data)

audit_mgr = AuditManager(AUDIT_FILE)

@app.get("/api/audit")
async def get_system_audit():
    return audit_mgr.load() 

@app.get("/api/system_logs")
async def get_system_logs():
    logs = []
    # Attempt 1: Read STDOUT capture (server_final.log)
    try:
        log_path = Path("server_final.log")
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                # Read all, take last 100
                lines = f.readlines()
                logs = lines[-100:][::-1]
    except Exception as e:
        logs.append(f"Could not read server_final.log: {str(e)}")

    
    # Attempt 2: ALWAYS Read debug_log.txt (Internal App Logs)
    try:
        import tempfile
        log_path = Path(tempfile.gettempdir()) / "debug_log.txt"
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs.extend(["--- DEBUG LOGS ---"] + lines[-100:][::-1])
    except Exception: pass
    
    if not logs: logs = ["System init... waiting for logs."]
    
    return {"logs": logs} 

# --- HELPERS (Standardized) ---
# log_to_file is already defined at line 122

def wait_for_files_active(files):
    # ... existing ...
    pass

# ... inside chat_endpoint ...
@app.post("/chat")
async def chat_endpoint(
    request: Request,
    text: str = Form(None),
    file: UploadFile = File(None),
    agent_role: str = Form("ceo"), 
    user_id: str = Form("kamen_architect"),
    thread_id: str = Form("default_smartdome_thread")
):
    import sys
    log_to_file(f"--- NEW REQUEST ---")
    log_to_file(f"/chat HIT. Text: '{text}'. File: {file.filename if file else 'None'}")
    
    if not client: return {"response": "No API Key"}

    # 1. SETUP & INITIALIZATION
    agent_id = agent_role.lower()
    file_received = False
    file_uri = None
    timestamp = int(time.time())
    clean_name = "unknown_file"
    mime = "application/octet-stream"

    # 1.1 LOAD DIRECTIVE
    directive_path = DIRECTIVES_DIR / f"{agent_id}.md"
    base_prompt = directive_path.read_text(encoding="utf-8") if directive_path.exists() else f"You are {agent_role}."
    
    # Inject Tools
    base_prompt += "\n- Use 'git_status' for any code questions."

    # 2. FILE HANDLING (Archive + Gemini Upload)
    if file and file.filename:
        file_received = True
        log_to_file(f"File Params: {file.filename} | Type: {file.content_type}")
        
        filename = file.filename.lower()
        mime = file.content_type if file.content_type else "application/octet-stream"
        
        # Explicit overrides
        if filename.endswith(".mp3"): mime = "audio/mp3"
        elif filename.endswith(".wav"): mime = "audio/wav"
        # REVERT: User confirms "Video" logic breaks recognition. 
        # Force AUDIO/WEBM to trigger Gemini's Audio model, not Video model.
        elif filename.endswith((".webm", ".weba")): 
             mime = "audio/webm"
        
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', file.filename)
        
        # A) LOCAL ARCHIVE
        try:
            upload_dir = DATA_DIR / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            save_path = upload_dir / f"{timestamp}_{clean_name}"
            
            file.file.seek(0)
            with open(save_path, "wb") as buffer:
                buffer.write(file.file.read())
            log_to_file(f"Archived to {save_path}")
        except Exception as e:
            log_to_file(f"Local Archive Failed: {e}")

        # B) GEMINI UPLOAD
        try:
            # Use /tmp for Cloud Run compatibility
            save_path = Path("/tmp") / f"{timestamp}_{clean_name}"
            
            file.file.seek(0)
            with open(save_path, "wb") as buffer:
                buffer.write(file.file.read())
            log_to_file(f"Archived to {save_path}")

            log_to_file(f"Uploading as {mime} to Gemini from /tmp: {save_path}")
            f_meta = client.files.upload(path=str(save_path), config=types.UploadFileConfig(mime_type=mime))
            file_uri = f_meta
            log_to_file(f"Gemini File ID: {f_meta.name}")

            # WAIT FOR FILE PROCESSING (Improved loop)
            log_to_file("Waiting for file processing...")
            for i in range(20):
                g_meta = client.files.get(name=f_meta.name)
                log_to_file(f"Try {i+1}: State = {g_meta.state.name}")
                if g_meta.state.name == "ACTIVE":
                    log_to_file("File is ACTIVE and ready.")
                    break
                if g_meta.state.name == "FAILED":
                    log_to_file(f"File processing FAILED: {g_meta.error.message if hasattr(g_meta, 'error') else 'Unknown error'}")
                    file_uri = None # INVALIDATE FILE
                    break
                time.sleep(1.5)
            else:
                 # Loop finished without ACTIVE
                 log_to_file("WARNING: File did not become ACTIVE within timeout.")
                 file_uri = None
            
            # Cleanup /tmp
            if save_path.exists(): save_path.unlink()

            # C) SINGLE-PASS ARCHITECTURE (Restored V5 Baseline)
            # We simply keep file_uri active. The Agent will process it directly.
            # No dedicated transcription pass.
            log_to_file("--> SINGLE PASS: Audio will be processed by Agent directly.")

            if mime == "application/pdf":
                base_prompt += "\n[SYSTEM]: PDF attached. Analyze carefully."

        except Exception as e:
            log_to_file(f"Gemini Upload Error: {e}")

    # 3. BUILD CONVERSATION PARTS
    parts = []
    
    # MULTIMODAL STABILITY: Audio/Files MUST be first in the parts list for prompt visibility
    if file_uri:
        log_to_file(f"Attaching Gemini File to prompt: {file_uri.name}")
        # CORRECT SDK SYNTAX for v1.x:
        parts.append(types.Part(file_data=types.FileData(file_uri=file_uri.uri, mime_type=file_uri.mime_type)))

    # --- HARDCODED CEO CONTEXT INJECTION (Temporary Fix for Large File Upload) ---
    ceo_aliases = ["ceo", "valentin", "executive"]
    if agent_id.lower() in ceo_aliases and not file_uri:
        log_to_file("CEO Agent Detected: Injecting pre-uploaded PDF report context.")
        CEO_PDF_URI = "https://generativelanguage.googleapis.com/v1beta/files/0x1fgexz3lrv"
        parts.insert(0, types.Part(file_data=types.FileData(file_uri=CEO_PDF_URI, mime_type="application/pdf")))
        base_prompt = "[СИСТЕМНА ИНСТРУКЦИЯ]: ГОВОРИ САМО НА БЪЛГАРСКИ. Прикачен е структурен доклад за анализ.\n" + base_prompt
    # --- END HARDCODED ---

    original_user_text = text if text else ""
    # Filter out fallback tags for cleaner prompt
    clean_text = original_user_text.replace("[AUDIO_COMMUNICATION]", "").replace("Audio message...", "").strip()
    
    if not clean_text and file_received:
        user_msg_final = f"I am providing {mime} file(s). Please analyze them according to your directive: {base_prompt[:100]}..."
    else:
        user_msg_final = clean_text or "..."
    
    if file_received and not file_uri:
        user_msg_final = "[SYSTEM ERROR]: Audio file received but failed to upload/process in Gemini. Do not hallucinate. State that an error occurred."
    elif file_received and mime.startswith("audio/") and file_uri:
        user_msg_final = f"TRANSCRIBE THE ATTACHED AUDIO IN BULGARIAN. START WITH '[TRANSCRIPT]:'. (Context: {clean_text or 'Audio-only input'})"
    
    parts.append(types.Part.from_text(text=f"USER INPUT: {user_msg_final}"))

    # 4. MEMORY
    local_hist = chat_mgr.get_history(thread_id)
    if local_hist:
         hist_txt = "\n".join([f"{m['role']}: {m['content']}" for m in local_hist[-10:]])
         base_prompt += f"\nRECENT HISTORY:\n{hist_txt}\n"
    
    # 5. GENERATE WITH TOOLS
    try:
        model_name = HUB_CONFIG.get("system", {}).get("model_provider", "gemini-3-flash-preview")
        core_tools = [create_scheduler_task, log_anomaly, generate_weekly_report]
        skill_tools = plugin_loader.get_tool_list()
        all_tools = core_tools + skill_tools
        
        messages = [types.Content(role="user", parts=parts)]
        gen_config = types.GenerateContentConfig(
            system_instruction=base_prompt,
            tools=all_tools, 
            automatic_function_calling={"disable": True},
            temperature=0.7
        )

        resp = client.models.generate_content(model=model_name, contents=messages, config=gen_config)
        final_text = ""

        # 5.2 RECURSIVE TOOL HANDLING
        turn_count = 0
        max_turns = 5
        final_text = ""
        
        while turn_count < max_turns:
            turn_count += 1
            if resp.function_calls:
                log_to_file(f"Turn {turn_count}: Tools detected: {len(resp.function_calls)}")
                messages.append(resp.candidates[0].content)
                response_parts = []
                
                for call in resp.function_calls:
                    log_to_file(f"Executing tool: {call.name}")
                    try:
                        if call.name == "create_scheduler_task":
                            # Fix duplicate key conflict: pop from_agent if already present in call.args
                            args = dict(call.args or {})
                            args.pop('from_agent', None)
                            res = create_scheduler_task(**args, from_agent=agent_id)
                            final_text += f"\n[SYSTEM]: {res}\n"
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": res}))
                        elif call.name == "log_anomaly":
                            res = log_anomaly(**call.args)
                            final_text += f"\n[SYSTEM_LOG]: {res}\n"
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": res}))
                        elif call.name in plugin_loader.tools:
                            res = plugin_loader.execute(call.name, **(call.args or {}))
                            res_str = json.dumps(res) if isinstance(res, dict) else str(res)
                            final_text += f"\n[TOOL]: {res_str}\n" # Optional: Keep for internal trace
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": res}))
                        else:
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"error": "Tool not found"}))
                    except Exception as e:
                        log_to_file(f"Tool Error ({call.name}): {e}")
                        response_parts.append(types.Part.from_function_response(name=call.name, response={"error": str(e)}))

                messages.append(types.Content(role="user", parts=response_parts))
                resp = client.models.generate_content(model=model_name, contents=messages, config=gen_config)
            else:
                final_text += (resp.text if resp.text else "")
                break

        if not final_text:
            log_to_file("Warning: final_text is empty. Forcing fallback.")
            final_text = "Командата е изпълнена успешно, но не беше генериран текст. Моля, проверете таблото за управление."

        # 6. LOG & PERSIST
        chat_mgr.add_message(thread_id, "user", original_user_text)
        chat_mgr.add_message(thread_id, "assistant", final_text)
        audit_mgr.log(agent_role, original_user_text, final_text)

        return {"status": "success", "response": final_text}

    except Exception as e:
        traceback.print_exc()
        log_to_file(f"CRITICAL ERROR: {e}")
        return {"status": "error", "response": f"System Error: {str(e)}"}



#Helper


# --- TTS ---
@app.post("/api/tts")
async def text_to_speech(text: str = Form(...)):
    if not GOOGLE_API_KEY: return JSONResponse({"error": "No API Key"}, status_code=500)
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_API_KEY}"
    payload = {"input": {"text": text}, "voice": {"languageCode": "bg-BG", "name": "bg-BG-Standard-A"}, "audioConfig": {"audioEncoding": "MP3"}}
    
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=10.0)
    
    if resp.status_code == 200: return {"audioContent": resp.json().get("audioContent")}
    return JSONResponse({"error": "TTS Error"}, status_code=resp.status_code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
