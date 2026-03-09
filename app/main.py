import os
import sys
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
import hashlib
import hmac
from datetime import datetime

# --- TASK ENGINE v6 ---
try:
    from task_engine import (
        TaskEngine, init_engine, init_anomaly_path, init_reminder,
        create_scheduler_task, log_anomaly, generate_weekly_report,
        get_task_summary, check_overdue_tasks, check_upcoming_deadlines,
        get_daily_briefing, resolve_agent_id, AGENT_MAP,
    )
except ImportError:
    from app.task_engine import (
        TaskEngine, init_engine, init_anomaly_path, init_reminder,
        create_scheduler_task, log_anomaly, generate_weekly_report,
        get_task_summary, check_overdue_tasks, check_upcoming_deadlines,
        get_daily_briefing, resolve_agent_id, AGENT_MAP,
    )

# --- PLUGIN LOADER (Engineering Team Skills) ---
try:
    from Core.plugin_loader import PluginLoader
except ImportError:
    from app.Core.plugin_loader import PluginLoader

# --- INTEGRATION TOOLS (Drive & Notion) ---
try:
    from tools.drive_tool import drive_list_files, drive_search, drive_upload_file, drive_get_file_content, drive_create_folder
    from tools.notion_tool import (
        create_notion_task, query_notion_tasks, update_notion_task,
        gtd_capture, gtd_get_next_actions, gtd_promote_to_next, gtd_complete_task,
    )
    from tools.agent_bus import send_agent_message, get_agent_messages, get_agent_routing_info
    from tools.output_guard import guard_output
    from tools.context_injector import inject_context
    from tools.inbox_tool import process_inbox_file, classify_file
    INTEGRATION_TOOLS_LOADED = True
except ImportError:
    try:
        from app.tools.drive_tool import drive_list_files, drive_search, drive_upload_file, drive_get_file_content, drive_create_folder
        from app.tools.notion_tool import (
            create_notion_task, query_notion_tasks, update_notion_task,
            gtd_capture, gtd_get_next_actions, gtd_promote_to_next, gtd_complete_task,
        )
        from app.tools.agent_bus import send_agent_message, get_agent_messages, get_agent_routing_info
        from app.tools.output_guard import guard_output
        from app.tools.context_injector import inject_context
        from app.tools.inbox_tool import process_inbox_file, classify_file
        INTEGRATION_TOOLS_LOADED = True
    except ImportError as e:
        logging.warning(f"Integration tools not loaded: {e}")
        INTEGRATION_TOOLS_LOADED = False

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
    sys.path.append(str(Path(__file__).resolve().parent))
try:
    from utils import time_manager
except ImportError:
    from app.utils import time_manager

_SCRIPT_DIR = Path(__file__).resolve().parent  
_SERVER_ROOT = _SCRIPT_DIR.parent  
load_dotenv(_SERVER_ROOT / ".env")
# CRITICAL: Read API key from environment (Cloud Run or .env)
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

# DEBUG: Log startup state
print(f"DEBUG_STARTUP: GEMINI_API_KEY exists: {bool(GOOGLE_API_KEY)}", file=sys.stderr, flush=True)
print(f"DEBUG_STARTUP: ZEP_API_KEY exists: {bool(ZEP_API_KEY)}", file=sys.stderr, flush=True)

_IS_LOCAL = "Personal assistant" in str(_SERVER_ROOT)

# PROJECT SELECTION
PROJECT_ID = os.getenv("HAPM_PROJECT_ID", "smartdome").lower()

if _IS_LOCAL:
    BASE_DIR = _SERVER_ROOT  
    DATA_DIR = BASE_DIR / "data" / PROJECT_ID
    PROJECTS_DIR = BASE_DIR / "projects"
    CONFIG_PATH = PROJECTS_DIR / f"{PROJECT_ID}.json"
    
    # If legacy config exists and projects folder is empty, fallback
    if not CONFIG_PATH.exists():
        CONFIG_PATH = BASE_DIR / "hapm_config.json"
        DIRECTIVES_DIR = BASE_DIR / "directives" / "smartdome"
    else:
        DIRECTIVES_DIR = BASE_DIR / "directives" / PROJECT_ID
else:
    # Cloud container
    BASE_DIR = _SERVER_ROOT
    DATA_DIR = Path(f"/tmp/data/{PROJECT_ID}")
    
    # Direct read from bundled config — no /tmp copy needed
    CONFIG_PATH = _SERVER_ROOT / "hapm_config.json"
    DIRECTIVES_DIR = _SCRIPT_DIR / "directives_data" / PROJECT_ID
    
    # Fallback: check projects_data for multi-project support
    PROJECTS_DIR = _SCRIPT_DIR / "projects_data"
    _PROJECT_CONFIG = PROJECTS_DIR / f"{PROJECT_ID}.json"
    if _PROJECT_CONFIG.exists():
        CONFIG_PATH = _PROJECT_CONFIG
    
    if not DIRECTIVES_DIR.exists():
        DIRECTIVES_DIR = _SERVER_ROOT / "directives" / "smartdome"

DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.info(f"PROJECT_ID: {PROJECT_ID} | DATA_DIR: {DATA_DIR} | CONFIG: {CONFIG_PATH}")

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
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")

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
    except Exception as e:
        logging.error(f"Failed to initialize Zep client: {e}")

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# --- CORS: Locked to SmartDome domains only ---
ALLOWED_ORIGINS = [
    "https://dashboard-chi-ten-42.vercel.app",  # Production frontend
    "http://localhost:5173",                     # Local dev
    "http://localhost:3000",                     # Local dev alt
]
ALLOWED_ORIGIN_REGEX = r"https://.*\.(vercel\.app|smartdome\.pro)"  # Preview deploys + Workspace

# In production, filter out localhost origins
if not _IS_LOCAL:
    ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if "localhost" not in o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=True
)

# --- HELPERS ---
def log_to_file(msg):
    # Print to stderr for server_final.log capture
    print(f"DEBUG_LOG: {msg}", file=sys.stderr, flush=True)
    try:
        import tempfile
        log_path = Path(tempfile.gettempdir()) / "debug_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except IOError:
        pass  # Log file write failure is non-critical

import subprocess

def convert_webm_to_wav(input_path: str) -> str:
    """Convert WebM audio to WAV using ffmpeg. Returns path to WAV file."""
    output_path = input_path.rsplit('.', 1)[0] + ".wav"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path), "-ar", "16000", "-ac", "1", "-f", "wav", str(output_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log_to_file(f"Converted {input_path} → {output_path}")
            return output_path
        else:
            log_to_file(f"ffmpeg conversion failed: {result.stderr}")
            return None
    except Exception as e:
        log_to_file(f"ffmpeg error: {e}")
        return None

def upload_to_gemini(file_obj, mime_type="audio/mp3"):
    """Robust global version using /tmp and correcting MIME types."""
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
        except OSError:
            pass  # Temp file cleanup is non-critical
        
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
# --- TASK ENGINE v6 (modular) ---
task_mgr = TaskEngine(TASKS_FILE, time_manager=time_manager)
init_engine(task_mgr)
init_anomaly_path(DATA_DIR)
init_reminder(task_mgr)
logging.info(f"TaskEngine v6 initialized: {TASKS_FILE}")
# --- CHAT MANAGER (v6.1 — Zep Primary, Local Cache Fallback) ---
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"

class ChatManager:
    """
    Hybrid Chat Storage:
    - PRIMARY: Zep Cloud (persistent, survives Cloud Run restarts)
    - FALLBACK: Local JSON (fast cache, ephemeral)
    Messages are saved to BOTH. History is loaded from Zep first.
    """
    def __init__(self, filepath, zep_client=None):
        self.filepath = filepath
        self.zep_client = zep_client
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
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"ChatManager failed to load {self.filepath}: {e}")
            return {"threads": {}}

    def save(self, data):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_message(self, thread_id, role, content, agent_role=None):
        """Save message to BOTH Zep (primary) and local JSON (cache)."""
        timestamp = time_manager.get_iso_time()

        # 1. Save to Zep Cloud (PRIMARY — persistent)
        if self.zep_client:
            try:
                zep_role = "assistant" if role == "assistant" else "user"
                self.zep_client.memory.add(
                    session_id=thread_id,
                    messages=[Message(role=zep_role, content=content, role_type=zep_role)]
                )
            except Exception as e:
                logging.warning(f"Zep save failed for {thread_id}: {e}")

        # 2. Save to local JSON (CACHE — fast fallback)
        data = self.load()
        if thread_id not in data["threads"]:
            data["threads"][thread_id] = []

        msg = {
            "role": role,
            "content": content,
            "created_at": timestamp,
            "agent_role": agent_role  # BUG #2 FIX: Store which director sent it
        }
        data["threads"][thread_id].append(msg)
        # Keep local cache at 1000 messages (increased from 300)
        if len(data["threads"][thread_id]) > 1000:
            data["threads"][thread_id] = data["threads"][thread_id][-1000:]

        self.save(data)

    def get_history(self, thread_id, limit=100):
        """
        Load history: Try Zep first (persistent), fall back to local JSON.
        Returns list of message dicts with role, content, created_at, agent_role.
        """
        # 1. Try Zep Cloud FIRST (has full history, survives restarts)
        if self.zep_client:
            try:
                memory = self.zep_client.memory.get(session_id=thread_id, memory_type="perpetual")
                if memory and memory.messages:
                    return [
                        {
                            "role": m.role,
                            "content": m.content,
                            "created_at": getattr(m, 'created_at', None),
                            "agent_role": getattr(m, 'metadata', {}).get('agent_role') if hasattr(m, 'metadata') else None
                        }
                        for m in memory.messages[-limit:]
                    ]
            except Exception as e:
                logging.warning(f"Zep history load failed for {thread_id}: {e}, falling back to local")

        # 2. Fallback to local JSON
        data = self.load()
        msgs = data["threads"].get(thread_id, [])
        return msgs[-limit:] if msgs else []

chat_mgr = ChatManager(CHAT_HISTORY_FILE, zep_client=zep)

# --- ENDPOINTS ---
@app.get("/api/config")
async def get_config(): return HUB_CONFIG

@app.get("/api/status")
async def get_status():
    return {
        "status": "Active", 
        "time": time_manager.get_iso_time(),
        "model": HUB_CONFIG.get("system", {}).get("model_provider", "gemini-2.5-flash")
    }

@app.get("/api/history/{thread_id}")
async def get_chat_history(thread_id: str, limit: int = Query(100, ge=1, le=500)):
    """
    v6.1: Zep-primary history with pagination support.
    Zep is checked first (persistent). Local JSON is fallback (cache).
    """
    messages = chat_mgr.get_history(thread_id, limit=limit)
    return {"messages": messages, "count": len(messages), "has_more": len(messages) >= limit}

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

# --- AUTHENTICATION (JWT + bcrypt) ---
import bcrypt
import base64

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY_HOURS = 24

def hash_password(password: str) -> str:
    """Hash password with bcrypt (salted, 12 rounds)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash. Also handles legacy SHA-256 migration."""
    # Legacy SHA-256 check (for existing passwords before this update)
    if len(hashed) == 64 and not hashed.startswith("$2b$"):
        if hashlib.sha256(password.encode()).hexdigest() == hashed:
            return True  # Match — caller should re-hash with bcrypt
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_jwt(user_id: str, slug: str, access: list) -> str:
    """Create a signed JWT token with expiry."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    now = int(time.time())
    payload_data = {
        "sub": user_id,
        "slug": slug,
        "access": access,
        "iat": now,
        "exp": now + (JWT_EXPIRY_HOURS * 3600)
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    signature = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"{header}.{payload}.{signature}"

def verify_jwt(token: str) -> dict:
    """Verify and decode a JWT token. Returns payload or raises HTTPException."""
    try:
        parts = token.replace("Bearer ", "").split(".")
        if len(parts) != 3:
            raise HTTPException(401, "Invalid token format")
        header, payload, signature = parts
        expected_sig = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(401, "Invalid token signature")
        # Decode payload
        padding = 4 - len(payload) % 4
        payload_data = json.loads(base64.urlsafe_b64decode(payload + "=" * padding))
        if payload_data.get("exp", 0) < int(time.time()):
            raise HTTPException(401, "Token expired")
        return payload_data
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise HTTPException(401, f"Token decode error: {e}")

async def get_current_user(request: Request) -> dict:
    """Extract and verify user from Authorization header. Returns user payload."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(401, "Missing Authorization header")
    return verify_jwt(auth_header)

@app.get("/api/auth/status/{slug}")
@limiter.limit("20/minute")
async def check_auth_status(request: Request, slug: str):
    # Reload config to get latest users
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config = json.load(f)
    user = next((p for p in config.get("participants", []) if p["slug"] == slug), None)
    
    if not user: raise HTTPException(404, "User not found")
    
    return {
        "id": user["id"],
        "name": user["name"],
        "has_password": bool(user.get("password_hash"))  # BUG-005 FIX: safe access
    }

# BACKWARD COMPATIBILITY for Stale Vercel Deployments
@app.get("/api/auth/verify-link")
async def legacy_verify_link(slug: str):
    return await check_auth_status(slug)

@app.post("/api/auth/setup")
@limiter.limit("5/minute")
async def setup_password(request: Request, slug: str = Form(...), password: str = Form(...)):
    # 1. Load
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config = json.load(f)
    
    # 2. Find User
    user = next((p for p in config.get("participants", []) if p["slug"] == slug), None)
    if not user: raise HTTPException(404, "User not found")
    
    # 3. Update Password — BUG-005 FIX: use .get() to handle missing key
    if user.get("password_hash"):
        return JSONResponse({"error": "Password already set. Please login."}, status_code=400)
        
    user["password_hash"] = hash_password(password)
    user["is_initialized"] = True

    # 4. Save
    with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(config, f, indent=4)

    token = create_jwt(user["id"], user["slug"], user.get("access", []))
    # Return safe user data (no password_hash)
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"status": "success", "token": token, "user": safe_user}

@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, slug: str = Form(None), user_id: str = Form(None), password: str = Form(...)):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config = json.load(f)
    
    # Find user by slug OR id
    user = None
    if slug:
        user = next((p for p in config["participants"] if p["slug"] == slug), None)
    elif user_id:
        user = next((p for p in config["participants"] if p["id"] == user_id), None)
        
    if not user: raise HTTPException(401, "User not found")

    # Verify — BUG-005 FIX: use .get() to handle missing key
    if not user.get("password_hash"):
        raise HTTPException(403, "Setup required")

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid password")

    # Auto-migrate legacy SHA-256 hashes to bcrypt on successful login
    pw_hash = user.get("password_hash", "")
    if len(pw_hash) == 64 and not pw_hash.startswith("$2b$"):
        user["password_hash"] = hash_password(password)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(config, f, indent=4)
        logging.info(f"Migrated password hash to bcrypt for user {user['id']}")

    token = create_jwt(user["id"], user["slug"], user.get("access", []))
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"token": token, "user": safe_user}

@app.get("/api/tasks/{agent_id}")
async def get_director_tasks(agent_id: str):
    """Get tasks for an agent. Supports full agent map resolution."""
    resolved = resolve_agent_id(agent_id)
    data = task_mgr.load()
    return data.get("directors", {}).get(resolved, {"tasks": []})

@app.post("/api/tasks/create")
async def create_task_api(
    agent_id: str = Form("ralf"),
    title: str = Form(...),
    priority: str = Form("green"),
    due_date: str = Form(None),
    category: str = Form("general"),
    company: str = Form("smartdome"),
):
    """Create a task via the dashboard. Enhanced with v6 fields."""
    task_mgr.add_task(
        agent_id=agent_id, title=title, description="Manual entry",
        priority=priority, source="manual",
        due_date=due_date, category=category, company=company,
    )
    return {"status": "success", "message": "Task created"}

@app.post("/api/tasks/delegate")
@limiter.limit("10/minute")
async def delegate_task_api(
    request: Request,
    from_agent: str = Form(...),
    to_agent: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("green"),
    due_date: str = Form(None),
    category: str = Form("general"),
    company: str = Form("smartdome"),
):
    """
    Delegate a task from one agent to another.
    Creates a task for the receiver AND a tracking task for the sender.
    """
    try:
        task = task_mgr.delegate_task(
            from_agent=from_agent,
            to_agent=to_agent,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            category=category,
            company=company,
        )
        # Log to audit trail
        audit_mgr.log(
            agent=resolve_agent_id(from_agent).upper(),
            request=f"Delegated to {resolve_agent_id(to_agent).upper()}: {title}",
            response=f"Task {task['id']} created with priority {priority}"
        )
        return {
            "status": "delegated",
            "task_id": task["id"],
            "from": resolve_agent_id(from_agent).upper(),
            "to": resolve_agent_id(to_agent).upper(),
        }
    except Exception as e:
        logging.error(f"Delegation failed: {e}")
        raise HTTPException(500, f"Delegation failed: {str(e)}")

@app.post("/api/tasks/update")
async def update_task_api(
    agent_id: str = Form(...),
    task_id: str = Form(...),
    priority: str = Form(None),
    status: str = Form(None),
    due_date: str = Form(None),
    category: str = Form(None),
    company: str = Form(None),
):
    """Update task fields. Uses full agent map resolution."""
    updated = task_mgr.update_task(
        agent_id=agent_id, task_id=task_id,
        priority=priority, status=status,
        due_date=due_date, category=category, company=company,
    )
    if updated:
        return {"status": "updated", "id": resolve_agent_id(agent_id)}
    return {"status": "failed", "reason": "Task or Agent not found"}

@app.delete("/api/tasks/delete")
async def delete_task_api(agent_id: str, task_id: str):
    """Soft-delete (dismiss) a task."""
    if task_mgr.dismiss_task(agent_id, task_id):
        return {"status": "dismissed"}
    return {"status": "failed", "reason": "Task not found"}

@app.get("/api/tasks/overdue")
async def get_overdue_tasks_api(agent_id: str = None):
    """Get overdue tasks, optionally filtered by agent."""
    overdue = task_mgr.get_overdue_tasks(agent_id)
    return {"overdue": overdue, "count": len(overdue)}

@app.get("/api/tasks/upcoming")
async def get_upcoming_tasks_api(days: int = 3):
    """Get tasks due within the next N days."""
    upcoming = task_mgr.get_due_soon(days=days)
    return {"upcoming": upcoming, "count": len(upcoming)}

# =====================================================================
# NOTION TASK BOARD (v7 — Interactive Dashboard)
# =====================================================================

@app.get("/api/notion/tasks")
async def get_notion_tasks(
    status: str = None,
    priority: str = None,
    agent_id: str = None,
    project_name: str = None,
    max_results: int = 50,
):
    """
    Fetch tasks from Notion database for the interactive Task Board.
    Enriches each task with deadline_status (overdue, due_soon, on_track, no_date).
    """
    if not INTEGRATION_TOOLS_LOADED:
        return {"success": False, "error": "Notion integration not loaded"}

    try:
        result = await query_notion_tasks(
            status=status,
            priority=priority,
            agent_id=agent_id,
            project_name=project_name,
            max_results=max_results,
        )

        if not result.get("success"):
            return result

        # Enrich tasks with deadline awareness
        from datetime import datetime as dt
        today = dt.now().date()
        enriched_tasks = []
        for task in result.get("tasks", []):
            due = task.get("due_date")
            if due:
                try:
                    due_date = dt.strptime(due, "%Y-%m-%d").date()
                    days_until = (due_date - today).days
                    if days_until < 0:
                        task["deadline_status"] = "overdue"
                        task["days_remaining"] = days_until
                    elif days_until <= 2:
                        task["deadline_status"] = "due_soon"
                        task["days_remaining"] = days_until
                    else:
                        task["deadline_status"] = "on_track"
                        task["days_remaining"] = days_until
                except (ValueError, TypeError):
                    task["deadline_status"] = "no_date"
                    task["days_remaining"] = None
            else:
                task["deadline_status"] = "no_date"
                task["days_remaining"] = None
            enriched_tasks.append(task)

        # Sort: overdue first, then due_soon, then on_track, then no_date
        status_order = {"overdue": 0, "due_soon": 1, "on_track": 2, "no_date": 3}
        enriched_tasks.sort(key=lambda t: (status_order.get(t["deadline_status"], 3), t.get("days_remaining") or 999))

        return {
            "success": True,
            "count": len(enriched_tasks),
            "tasks": enriched_tasks,
        }
    except Exception as e:
        log_to_file(f"Notion tasks endpoint error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/notion/tasks/{task_id}/voice-context")
async def voice_context_for_task(
    task_id: str,
    text: str = Form(None),
    file: UploadFile = File(None),
    user_id: str = Form("p_valentin"),
):
    """
    Voice-to-task: user speaks to a specific task.
    The audio + task context are sent to the CEO agent for processing.
    The CEO agent can then update the task in Notion based on the voice input.
    """
    if not INTEGRATION_TOOLS_LOADED:
        return {"success": False, "error": "Integration tools not loaded"}

    # 1. Fetch the specific task from Notion for context
    try:
        import httpx
        notion_key = os.getenv("NOTION_API_KEY")
        if not notion_key:
            return {"success": False, "error": "Notion API key not configured"}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.notion.com/v1/pages/{task_id}",
                headers={
                    "Authorization": f"Bearer {notion_key}",
                    "Notion-Version": "2022-06-28",
                },
            )
            if resp.status_code != 200:
                task_context = f"[Task ID: {task_id} — could not fetch details]"
            else:
                page = resp.json()
                props = page.get("properties", {})
                # Extract key fields
                task_title = ""
                title_prop = props.get("Task name", {})
                if title_prop.get("title"):
                    task_title = "".join(t.get("plain_text", "") for t in title_prop["title"])
                task_status = props.get("Status", {}).get("status", {}).get("name", "Unknown")
                task_priority = props.get("Priority", {}).get("select", {}).get("name", "Unknown") if props.get("Priority", {}).get("select") else "None"
                task_due = props.get("Due Date", {}).get("date", {}).get("start", "No date") if props.get("Due Date", {}).get("date") else "No date"

                task_context = f"TASK CONTEXT:\n- Title: {task_title}\n- Status: {task_status}\n- Priority: {task_priority}\n- Due: {task_due}\n- Notion ID: {task_id}"
    except Exception as e:
        task_context = f"[Task ID: {task_id} — error fetching: {e}]"

    # 2. Prepend task context to the user's text and forward to the CEO chat endpoint
    augmented_text = f"{task_context}\n\nUSER VOICE CONTEXT: {text or '[Audio attached — transcribe first]'}\n\nINSTRUCTION: Based on the voice input, decide if you should update the task's priority, deadline, status, or add notes. Use update_notion_task tool if changes are needed. Explain what you changed to the user."

    # Create a new form for the chat endpoint
    from starlette.datastructures import UploadFile as StarletteUpload
    from fastapi import Request as FastRequest

    # Forward to the main chat endpoint logic
    # We'll use an internal redirect approach: call the chat function directly
    log_to_file(f"Voice-to-task: task_id={task_id}, user_id={user_id}, has_audio={file is not None}")

    # Build a synthetic request to the chat endpoint
    form_data = {
        "text": augmented_text,
        "agent_role": "ceo",
        "user_id": user_id,
        "thread_id": f"task_{task_id}",
    }

    # For simplicity, use internal imports and call the same logic
    # But we can't easily forward file uploads internally. Instead, let the frontend
    # call /chat directly with the augmented text + file.
    return {
        "success": True,
        "augmented_text": augmented_text,
        "task_context": task_context,
        "instruction": "Frontend should call /chat with this augmented_text + audio file, agent_role=ceo"
    }


# =====================================================================
# DRIVE INBOX — AI File Classification & Routing
# =====================================================================

@app.post("/api/inbox")
async def inbox_upload(
    file: UploadFile = File(...),
    project_hint: str = Form(None),
    uploader: str = Form("kamen"),
    auto_upload_drive: bool = Form(True),
    auto_create_task: bool = Form(True),
):
    """
    Drive Inbox: Upload → AI Classify → Route to Drive → Create Notion Task.

    Accepts a file upload, classifies it with Gemini Flash, uploads to the
    correct Google Drive project/department folder, and creates a Notion task
    for the responsible agent.
    """
    if not INTEGRATION_TOOLS_LOADED:
        raise HTTPException(status_code=503, detail="Integration tools not loaded — Drive/Notion unavailable")

    try:
        file_bytes = await file.read()
        filename = file.filename or "unnamed_file"
        mime_type = file.content_type or "application/octet-stream"

        log_to_file(f"INBOX: Received '{filename}' ({mime_type}, {len(file_bytes)} bytes) from {uploader}")

        # Run the full pipeline: classify → drive upload → notion task
        result = await process_inbox_file(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            uploader=uploader,
            project_hint=project_hint,
            auto_upload_drive=auto_upload_drive,
            auto_create_task=auto_create_task,
        )

        log_to_file(f"INBOX: Pipeline complete for '{filename}' → {result.get('summary', 'no summary')}")

        return {
            "success": True,
            **result,
        }

    except Exception as e:
        logging.error(f"INBOX ERROR: {e}\n{traceback.format_exc()}")
        log_to_file(f"INBOX ERROR: {filename} → {e}")
        raise HTTPException(status_code=500, detail=f"Inbox processing failed: {str(e)}")


@app.post("/api/inbox/classify-only")
async def inbox_classify_only(
    file: UploadFile = File(...),
    project_hint: str = Form(None),
):
    """
    Classify a file WITHOUT uploading to Drive or creating a task.
    Returns the AI classification for preview/confirmation before routing.
    """
    if not INTEGRATION_TOOLS_LOADED:
        raise HTTPException(status_code=503, detail="Integration tools not loaded")

    try:
        file_bytes = await file.read()
        filename = file.filename or "unnamed_file"
        mime_type = file.content_type or "application/octet-stream"

        classification = await classify_file(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            project_hint=project_hint,
        )

        return {
            "success": True,
            "classification": classification,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": len(file_bytes),
        }

    except Exception as e:
        logging.error(f"INBOX CLASSIFY ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@app.get("/api/calendar")
async def get_calendar_data():
    """
    Calendar endpoint for the MASTER GRID view.
    Generates events from tasks with due dates and system-scheduled items.
    Returns both confirmed events and draft/intent items.
    """
    task_data = task_mgr.load()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    events = []
    drafts = []

    # 1. Build events from tasks with due dates
    for agent_id, agent_data in task_data.get("directors", {}).items():
        for task in agent_data.get("tasks", []):
            due = task.get("due_date")
            status = task.get("status", "pending")

            if not due or status in ("completed", "dismissed"):
                continue

            # Create a calendar event from the task
            priority = task.get("priority", "green")
            events.append({
                "id": task.get("id", ""),
                "summary": task.get("title", "Untitled"),
                "start": f"{due}T09:00:00",
                "end": f"{due}T10:00:00",
                "agent": agent_id.upper(),
                "priority": priority,
                "status": status,
                "source": task.get("source", "manual"),
                "category": task.get("category", "general"),
                "company": task.get("company", "smartdome"),
                "delegated_by": task.get("delegated_by"),
            })

    # 2. Sort events by start date (soonest first)
    events.sort(key=lambda e: e.get("start", "9999"))

    # 3. Overdue items become drafts/alerts
    for event in events:
        if event.get("start", "")[:10] < today_str:
            drafts.append({
                "id": event["id"],
                "raw_text": f"OVERDUE: {event['summary']} (was due {event['start'][:10]}, agent: {event['agent']})",
                "timestamp": event["start"],
                "type": "overdue_alert"
            })

    # 4. Filter events to upcoming only (today and future)
    upcoming_events = [e for e in events if e.get("start", "")[:10] >= today_str]

    return {
        "events": upcoming_events[:20],  # Cap at 20 for performance
        "drafts": drafts[:10],
        "generated_at": time_manager.get_iso_time(),
        "total_scheduled": len(upcoming_events),
        "total_overdue": len(drafts),
    }

AUDIT_FILE = DATA_DIR / "audit_log.json"

# --- TOOLS (imported from task_engine.py) ---
# create_scheduler_task, log_anomaly, generate_weekly_report,
# get_task_summary, check_overdue_tasks, check_upcoming_deadlines,
# get_daily_briefing — all imported at top of file from task_engine

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
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"AuditManager failed to load {self.filepath}: {e}")
            return {"logs": []}

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

@app.get("/api/dashboard/metrics")
async def get_dashboard_metrics():
    """Aggregated metrics endpoint for SmartDome OS dashboard."""
    # 1. Task counts per agent
    task_data = task_mgr.load()
    task_summary = {}
    total_active = 0
    total_completed = 0
    for agent_id, agent_data in task_data.get("directors", {}).items():
        tasks = agent_data.get("tasks", [])
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        task_summary[agent_id] = {"pending": pending, "completed": completed, "in_progress": in_progress, "total": len(tasks)}
        total_active += pending + in_progress
        total_completed += completed

    # 2. Anomalies
    anom_path = DATA_DIR / "system_anomalies.json"
    anomalies = []
    if anom_path.exists():
        try:
            with open(anom_path, "r") as f:
                anomalies = json.load(f).get("anomalies", [])[:10]
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not load anomalies: {e}")

    # 3. Audit log (recent activity)
    audit_data = audit_mgr.load()
    recent_activity = audit_data.get("logs", [])[:10]

    # 4. System info
    version = HUB_CONFIG.get("version", "5.0.0")
    hapm_version = HUB_CONFIG.get("hapm_core_version", "5.0")
    project_name = HUB_CONFIG.get("project_name", "SmartDome")
    directors_config = HUB_CONFIG.get("directors", [])

    # 5. Development pipeline (real tasks formatted for OS view)
    pipeline = []
    for agent_id, agent_data in task_data.get("directors", {}).items():
        for t in agent_data.get("tasks", []):
            if t.get("status") in ["pending", "in_progress"]:
                pipeline.append({
                    "id": t.get("id", ""),
                    "title": t.get("title", "Untitled"),
                    "agent": agent_id.upper(),
                    "status": t.get("status", "pending"),
                    "priority": t.get("priority", "green"),
                    "created_at": t.get("created_at", ""),
                    "source": t.get("source", "manual"),
                    "delegated_by": t.get("delegated_by")
                })

    return {
        "version": version,
        "hapm_version": hapm_version,
        "project_name": project_name,
        "timestamp": time_manager.get_iso_time(),
        "tasks": task_summary,
        "total_active_tasks": total_active,
        "total_completed_tasks": total_completed,
        "anomalies": anomalies,
        "open_anomaly_count": sum(1 for a in anomalies if a.get("status") == "open"),
        "recent_activity": recent_activity,
        "pipeline": pipeline[:10],
        "directors": [{"id": d.get("id"), "name": d.get("name"), "role": d.get("role"), "focus": d.get("focus")} for d in directors_config]
    }

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
    except Exception as e:
        logs.append(f"Could not read debug_log.txt: {str(e)}")

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
    log_to_file(f"--- NEW REQUEST ---")
    log_to_file(f"/chat HIT. Text: '{text}'. File: {file.filename if file else 'None'}")
    
    # Load API Key dynamically inside the endpoint
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"DEBUG: api_key={api_key}", flush=True)
    if not api_key:
        return {"status": "error", "error_code": "GEMINI_AUTH_FAILURE", "response": "No API Key found."}
    
    local_client = genai.Client(api_key=api_key)

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

    # 1.2 DYNAMIC CONTEXT INJECTION (v7)
    # Map user_id to participant_id for context injection
    _participant_map = {
        "kamen_architect": "p_kamen", "kamen": "p_kamen", "p_kamen": "p_kamen",
        "valentin": "p_valentin", "p_valentin": "p_valentin",
        "biser": "p_biser", "p_biser": "p_biser",
        "raina": "p_raina", "p_raina": "p_raina",
    }
    participant_id = _participant_map.get(user_id.lower(), user_id)
    if INTEGRATION_TOOLS_LOADED:
        try:
            base_prompt = inject_context(base_prompt, agent_id, participant_id, HUB_CONFIG)
            log_to_file(f"Context injected for {agent_id} (participant: {participant_id})")
        except Exception as e:
            log_to_file(f"Context injection failed (non-fatal): {e}")

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
        
        # READ FILE BYTES ONCE (avoid double-read drain on Cloud Run)
        file.file.seek(0)
        file_bytes = file.file.read()
        log_to_file(f"Read {len(file_bytes)} bytes from uploaded file.")

        # A) LOCAL ARCHIVE
        try:
            upload_dir = DATA_DIR / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            save_path = upload_dir / f"{timestamp}_{clean_name}"

            with open(save_path, "wb") as buffer:
                buffer.write(file_bytes)
            log_to_file(f"Archived to {save_path}")
        except Exception as e:
            log_to_file(f"Local Archive Failed: {e}")

        # B) GEMINI UPLOAD
        try:
            # Use /tmp for Cloud Run compatibility
            save_path = Path("/tmp") / f"{timestamp}_{clean_name}"

            with open(save_path, "wb") as buffer:
                buffer.write(file_bytes)
            log_to_file(f"Archived to {save_path}")

            log_to_file(f"Uploading as {mime} to Gemini from /tmp: {save_path}")

            upload_path = str(save_path)
            upload_mime = mime

            # --- v6.1 FIX (BUG #12): Send WebM directly to Gemini ---
            # Gemini 2.5 supports WebM/Opus natively. ffmpeg conversion was unreliable
            # and caused silent failures. Removed conversion step entirely.
            if mime == "audio/webm":
                upload_mime = "audio/webm"  # Gemini accepts this directly
                log_to_file(f"Sending WebM audio directly to Gemini (no conversion)")

            f_meta = local_client.files.upload(path=upload_path, config=types.UploadFileConfig(mime_type=upload_mime))
            file_uri = f_meta
            log_to_file(f"Gemini File ID: {f_meta.name}")

            # WAIT FOR FILE PROCESSING (Exponential Backoff — V5.1 Stabilization)
            log_to_file("Waiting for file processing...")
            max_wait_secs = 120
            elapsed_wait = 0
            backoff = 2  # Start at 2s, double each iteration, cap at 10s
            attempt = 0
            while elapsed_wait < max_wait_secs:
                attempt += 1
                try:
                    g_meta = local_client.files.get(name=f_meta.name)
                    state = g_meta.state.name if hasattr(g_meta.state, 'name') else str(g_meta.state)
                    log_to_file(f"Poll {attempt}: State={state} (elapsed={elapsed_wait}s)")
                    if state == "ACTIVE":
                        log_to_file("File is ACTIVE and ready.")
                        break
                    if state == "FAILED":
                        log_to_file(f"File processing FAILED: {getattr(g_meta, 'error', 'Unknown error')}")
                        file_uri = None
                        break
                except Exception as poll_err:
                    log_to_file(f"Polling glitch (attempt {attempt}): {poll_err}")
                time.sleep(backoff)
                elapsed_wait += backoff
                backoff = min(backoff * 2, 10)
            else:
                log_to_file(f"WARNING: File did not become ACTIVE within {max_wait_secs}s.")
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

    # --- HARDCODED CEO PDF INJECTION REMOVED (V5.1 Stabilization) ---
    # Previously injected a stale PDF URI for CEO agents, causing 403/context pollution.
    # CEO agents now operate purely from their directive + user-uploaded files.

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
        model_name = HUB_CONFIG.get("system", {}).get("model_provider", "gemini-2.5-flash")
        core_tools = [
            create_scheduler_task, log_anomaly, generate_weekly_report,
            get_task_summary, check_overdue_tasks, check_upcoming_deadlines,
            get_daily_briefing,
        ]
        # Integration tools (Drive & Notion) — only if loaded
        if INTEGRATION_TOOLS_LOADED:
            integration_tools = [
                drive_list_files, drive_search, drive_get_file_content, drive_create_folder,
                create_notion_task, query_notion_tasks, update_notion_task,
                gtd_capture, gtd_get_next_actions, gtd_promote_to_next, gtd_complete_task,
                send_agent_message, get_agent_messages, get_agent_routing_info,
            ]
            core_tools = core_tools + integration_tools
        try:
            skill_tools = plugin_loader.get_tool_list()
            if not isinstance(skill_tools, list):
                skill_tools = []
        except Exception as e:
            skill_tools = []
            log_to_file(f"Plugin loader failed: {e}")
        all_tools = core_tools + skill_tools
        
        messages = [types.Content(role="user", parts=parts)]
        gen_config = types.GenerateContentConfig(
            system_instruction=base_prompt,
            tools=all_tools, 
            automatic_function_calling={"disable": True},
            temperature=0.7
        )

        resp = local_client.models.generate_content(model=model_name, contents=messages, config=gen_config)
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
                
                # Map core tool names to their functions (from task_engine)
                CORE_TOOL_MAP = {
                    "create_scheduler_task": create_scheduler_task,
                    "log_anomaly": log_anomaly,
                    "generate_weekly_report": generate_weekly_report,
                    "get_task_summary": get_task_summary,
                    "check_overdue_tasks": check_overdue_tasks,
                    "check_upcoming_deadlines": check_upcoming_deadlines,
                    "get_daily_briefing": get_daily_briefing,
                }
                # Agent Bus tools (sync)
                if INTEGRATION_TOOLS_LOADED:
                    CORE_TOOL_MAP.update({
                        "send_agent_message": send_agent_message,
                        "get_agent_messages": get_agent_messages,
                        "get_agent_routing_info": get_agent_routing_info,
                    })
                # Integration tools (async — Drive & Notion)
                ASYNC_TOOL_MAP = {}
                if INTEGRATION_TOOLS_LOADED:
                    ASYNC_TOOL_MAP = {
                        "drive_list_files": drive_list_files,
                        "drive_search": drive_search,
                        "drive_get_file_content": drive_get_file_content,
                        "drive_create_folder": drive_create_folder,
                        "create_notion_task": create_notion_task,
                        "query_notion_tasks": query_notion_tasks,
                        "update_notion_task": update_notion_task,
                        "gtd_capture": gtd_capture,
                        "gtd_get_next_actions": gtd_get_next_actions,
                        "gtd_promote_to_next": gtd_promote_to_next,
                        "gtd_complete_task": gtd_complete_task,
                    }

                for call in resp.function_calls:
                    log_to_file(f"Executing tool: {call.name}")
                    try:
                        if call.name == "create_scheduler_task":
                            args = dict(call.args or {})
                            args.pop('from_agent', None)
                            res = create_scheduler_task(**args, from_agent=agent_id)
                            final_text += f"\n[SYSTEM]: {res}\n"
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": res}))
                        elif call.name in CORE_TOOL_MAP:
                            res = CORE_TOOL_MAP[call.name](**(call.args or {}))
                            tag = "[SYSTEM]" if "report" in call.name or "briefing" in call.name else "[SYSTEM_LOG]"
                            final_text += f"\n{tag}: {res}\n"
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": res}))
                        elif call.name in ASYNC_TOOL_MAP:
                            import asyncio
                            args = dict(call.args or {})
                            # Inject agent_id for scoped access
                            if "agent_id" in args or "agent_id" in ASYNC_TOOL_MAP[call.name].__code__.co_varnames:
                                args.setdefault("agent_id", agent_id)
                            res = await ASYNC_TOOL_MAP[call.name](**args)
                            tag = "[DRIVE]" if "drive" in call.name else "[NOTION]"
                            final_text += f"\n{tag}: {json.dumps(res, ensure_ascii=False, default=str)[:500]}\n"
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": json.dumps(res, ensure_ascii=False, default=str)}))
                        elif call.name in plugin_loader.tools:
                            res = plugin_loader.execute(call.name, **(call.args or {}))
                            # Auto-upload generated documents to Google Drive
                            if isinstance(res, dict) and res.get("ready_for_upload") and res.get("filepath"):
                                try:
                                    from tools.drive_tool import drive_upload_file
                                    import asyncio
                                    with open(res["filepath"], "rb") as df:
                                        doc_bytes = df.read()
                                    mime_map = {".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
                                    ext = Path(res["filepath"]).suffix
                                    upload_result = asyncio.get_event_loop().run_until_complete(
                                        drive_upload_file(doc_bytes, res["filename"], res.get("drive_folder", "Shared"),
                                                         agent_id=agent_id, mime_type=mime_map.get(ext, "application/octet-stream")))
                                    if upload_result.get("success"):
                                        res["drive_link"] = upload_result.get("link", "")
                                        res["drive_status"] = "uploaded"
                                        log_to_file(f"Auto-uploaded {res['filename']} to Drive/{res.get('drive_folder')}")
                                except Exception as drive_err:
                                    res["drive_status"] = f"upload_failed: {drive_err}"
                                    log_to_file(f"Drive upload failed for {res.get('filename')}: {drive_err}")
                            res_str = json.dumps(res) if isinstance(res, dict) else str(res)
                            final_text += f"\n[TOOL]: {res_str}\n"
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": res}))
                        else:
                            response_parts.append(types.Part.from_function_response(name=call.name, response={"error": "Tool not found"}))
                    except Exception as e:
                        log_to_file(f"Tool Error ({call.name}): {e}")
                        response_parts.append(types.Part.from_function_response(name=call.name, response={"error": str(e)}))

                messages.append(types.Content(role="user", parts=response_parts))
                resp = local_client.models.generate_content(model=model_name, contents=messages, config=gen_config)
            else:
                final_text += (resp.text if resp.text else "")
                break

        if not final_text:
            log_to_file("Warning: final_text is empty. Forcing fallback.")
            final_text = "Командата е изпълнена успешно, но не беше генериран текст. Моля, проверете таблото за управление."

        # 5.5 OUTPUT GUARD — enforce style, banned words, constraints
        if INTEGRATION_TOOLS_LOADED:
            guard_result = guard_output(final_text, agent_id=agent_id)
            if guard_result["cleaned"]:
                log_to_file(f"Guard: {len(guard_result['violations'])} violations cleaned for {agent_id}: {guard_result['violations'][:3]}")
            final_text = guard_result["text"]

        # --- Extract transcript from audio responses ---
        transcript = None
        if file_received and mime.startswith("audio") and "[TRANSCRIPT]:" in final_text:
            import re as _re
            transcript_match = _re.search(r'\[TRANSCRIPT\]:\s*(.+?)(?:\n|$)', final_text, _re.DOTALL)
            if transcript_match:
                transcript = transcript_match.group(1).strip()

        # 6. LOG & PERSIST (v6.1: include agent_role for cross-director labeling fix)
        chat_mgr.add_message(thread_id, "user", original_user_text, agent_role=agent_role)
        chat_mgr.add_message(thread_id, "assistant", final_text, agent_role=agent_role)
        audit_mgr.log(agent_role, original_user_text, final_text)

        response_payload = {"status": "success", "response": final_text}
        if transcript:
            response_payload["transcript"] = transcript
        return response_payload

    except Exception as e:
        traceback.print_exc()
        log_to_file(f"CRITICAL ERROR: {e}")
        # V5.1: Specific error codes for frontend-actionable feedback
        err_str = str(e).lower()
        error_code = "UNKNOWN_ERROR"
        if "api key" in err_str or "403" in err_str:
            error_code = "GEMINI_AUTH_FAILURE"
        elif "timeout" in err_str or "deadline" in err_str:
            error_code = "REQUEST_TIMEOUT"
        elif "file" in err_str and ("upload" in err_str or "process" in err_str):
            error_code = "FILE_UPLOAD_FAILURE"
        elif "rate" in err_str or "429" in err_str:
            error_code = "RATE_LIMIT_EXCEEDED"
        return {"status": "error", "error_code": error_code, "response": f"System Error: {str(e)}"}



#Helper


# --- TTS ---
@app.post("/api/tts")
async def text_to_speech(text: str = Form(...)):
    if not GOOGLE_API_KEY: return JSONResponse({"error": "No API Key"}, status_code=500)
    # Use Authorization header instead of URL parameter to avoid key leakage in logs
    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    headers = {"Authorization": f"Bearer {GOOGLE_API_KEY}", "Content-Type": "application/json"}
    payload = {"input": {"text": text}, "voice": {"languageCode": "bg-BG", "name": "bg-BG-Standard-A"}, "audioConfig": {"audioEncoding": "MP3"}}

    import httpx
    async with httpx.AsyncClient() as tts_client:
        resp = await tts_client.post(url, json=payload, headers=headers, timeout=10.0)

    if resp.status_code == 200: return {"audioContent": resp.json().get("audioContent")}
    return JSONResponse({"error": "TTS Error"}, status_code=resp.status_code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
