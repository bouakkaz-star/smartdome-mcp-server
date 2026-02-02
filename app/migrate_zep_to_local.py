import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from zep_cloud.client import Zep

# Setup
logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv()
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

if not ZEP_API_KEY:
    logging.error("No ZEP_API_KEY found.")
    exit(1)

zep = Zep(api_key=ZEP_API_KEY)
HISTORY_FILE = BASE_DIR / "apps" / "server" / "data" / "chat_history.json"

LEGACY_THREADS = [
    "smartdome_clean_ceo_thread_v3",
    "smartdome_clean_ceo_thread",
    "smartdome_ceo_thread_v3",
    "smartdome_ceo_thread"
]
TARGET_THREAD = "smartdome_ceo_thread_v4"

def load_local_history():
    if not HISTORY_FILE.exists():
        return {"threads": {}}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"threads": {}}

def save_local_history(data):
    # Backup first
    if HISTORY_FILE.exists():
        backup_path = HISTORY_FILE.with_suffix(".json.bak")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(load_local_history(), f, indent=2)
            
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def migrate():
    data = load_local_history()
    if TARGET_THREAD not in data["threads"]:
        data["threads"][TARGET_THREAD] = []
    
    current_msgs = data["threads"][TARGET_THREAD]
    # Create simple hash set for dedup (content + role)
    seen_hashes = set()
    for m in current_msgs:
        h = f"{m.get('role')}_{m.get('content')}"
        seen_hashes.add(h)
    
    logging.info(f"Current V4 messages: {len(current_msgs)}")
    
    total_imported = 0
    
    for thread_id in LEGACY_THREADS:
        try:
            logging.info(f"Fetching Zep Thread: {thread_id} ...")
            z_thread = zep.thread.get(thread_id)
            if not z_thread or not z_thread.messages:
                logging.info(f"  -> Empty or Not Found.")
                continue
                
            msgs = z_thread.messages
            logging.info(f"  -> Found {len(msgs)} messages.")
            
            for m in msgs:
                # Normalize
                role = m.role
                content = m.content
                created_at = getattr(m, 'created_at', None)
                
                h = f"{role}_{content}"
                if h not in seen_hashes:
                    new_msg = {
                        "role": role,
                        "content": content,
                        "created_at": created_at,
                        "metadata": {"source": "zep_migration", "original_thread": thread_id}
                    }
                    current_msgs.append(new_msg)
                    seen_hashes.add(h)
                    total_imported += 1
                    
        except Exception as e:
            logging.error(f"  -> Error fetching {thread_id}: {e}")

    # Sort chronological
    # Zep usually returns chronological, but let's be safe if we merge multiple threads
    # Use a safe sort key
    def sort_key(msg):
        t = msg.get("created_at")
        if t: return str(t)
        return "9999" # Push undetermined to end? Or beginning? Zep usually has dates.
        
    current_msgs.sort(key=sort_key)
    
    data["threads"][TARGET_THREAD] = current_msgs
    save_local_history(data)
    
    logging.info(f"Migration Complete. Imported {total_imported} new messages.")
    logging.info(f"Total V4 Messages: {len(data['threads'][TARGET_THREAD])}")

if __name__ == "__main__":
    migrate()
