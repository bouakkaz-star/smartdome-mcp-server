import os
import asyncio
from dotenv import load_dotenv
from zep_cloud.client import Zep
from zep_cloud.types import Message

from pathlib import Path

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

ZEP_API_KEY = os.getenv("ZEP_API_KEY")

if not ZEP_API_KEY:
    print(f"❌ ERROR: ZEP_API_KEY not found in {env_path.absolute()}")
    # Debug: print all env vars to see if it's loaded
    # print(os.environ)
    exit(1)

zep = Zep(api_key=ZEP_API_KEY)

# ... imports ...

async def check_zep_data():
    output = []
    def log(msg):
        print(msg)
        output.append(str(msg))
    
    log(f"🔍 DEBUG: Zep API Key: {ZEP_API_KEY[:5]}...***")
    
    # 1. Fetch Sessions (Threads in Zep Cloud are roughly equivalent for this context)
    log("\n--- 1. Fetching Recent Sessions/Threads ---")
    try:
        log("Fetching Users...")
        users = zep.user.list()
        
        if users and users.users:
            log(f"✅ Found {len(users.users)} users.")
            for u in users.users:
                log(f"   [User] ID: {u.user_id} | Email: {u.email} | Name: {u.first_name} {u.last_name}")
                log(f"   MetaData: {u.metadata}")
                
                # Check for Valentin/Kamen
                meta_str = str(u.metadata).lower()
                if "valentin" in meta_str or "valentin" in str(u.first_name).lower():
                    log("   ⭐ MATCH: Valentin Found!")
                if "kamen" in meta_str or "kamen" in str(u.first_name).lower():
                    log("   ⭐ MATCH: Kamen Found!")
        else:
            log("⚠️ No users returned by list().")

    except Exception as e:
        log(f"❌ Error fetching users: {e}")

    # 2. Fetch specific threads if known or list usage
    log("\n--- 2. Fetching Recent Messages (from known threads) ---")
    
    # Based on main.py, thread_id defaults to "default_thread" but frontend sends others if configured
    # Let's check a few likely candidates
    candidate_threads = ["default_thread", "smartdome_cio_thread_v3", "session_1", "test_thread"]
    
    for tid in candidate_threads:
        try:
            log(f"\nChecking Thread: {tid}")
            history = zep.thread.get_history(thread_id=tid, limit=5)
            if history and history.messages:
                log(f"   ✅ Found {len(history.messages)} messages.")
                for m in history.messages:
                    content_preview = m.content[:50].replace("\n", " ") + "..."
                    log(f"      - [{m.role}] {content_preview}")
            else:
                log(f"   ℹ️ No history found for {tid}.")
        except Exception as e:
             # Most likely "Not Found" if thread doesn't exist
             # log(f"Error checking {tid}: {e}")
             pass
    
    with open("zep_audit_result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print("✅ Output written to zep_audit_result.txt")

if __name__ == "__main__":
    asyncio.run(check_zep_data())
