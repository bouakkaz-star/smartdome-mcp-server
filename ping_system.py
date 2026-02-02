import os
import asyncio
import httpx
from dotenv import load_dotenv
from zep_cloud.client import Zep
from pathlib import Path

# Load env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

# Config
LOCAL_URL = "http://localhost:8080/debug/zep"
CLOUD_URL = "https://smartdome-engine-435849971140.europe-west1.run.app/debug/zep"

# ... imports ...

async def main():
    output = []
    def log(msg):
        print(msg)
        output.append(str(msg))

    async def ping_backend(name, url):
        log(f"\n📡 PINGING {name} [{url}]...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    log(f"   ✅ ALIVE (200 OK)")
                    log(f"   📝 Response: {resp.json()}")
                    return True
                else:
                    log(f"   ⚠️ RESPONDED with {resp.status_code}")
                    return False
        except Exception as e:
            log(f"   ❌ UNREACHABLE: {e}")
            return False

    async def check_zep_metadata():
        log(f"\n🧠 CHECKING ZEP METADATA...")
        if not ZEP_API_KEY:
            log("   ❌ No ZEP_API_KEY found.")
            return

        try:
            zep = Zep(api_key=ZEP_API_KEY)
            threads_to_check = ["default_thread", "smartdome_cio_thread_v3"]
            
            for tid in threads_to_check:
                try:
                    thread = zep.thread.get(thread_id=tid)
                    log(f"   🧵 Thread '{tid}': FOUND")
                    log(f"      - Created: {getattr(thread, 'created_at', 'Unknown')}")
                    log(f"      - Metadata: {getattr(thread, 'metadata', '{}')}")
                except Exception as e:
                    log(f"   🧵 Thread '{tid}': NOT FOUND/Error ({e})")

        except Exception as e:
            log(f"   ❌ Zep Error: {e}")

    log("=== SYSTEM DIAGNOSTIC ===")
    
    # 1. Ping Local
    local_alive = await ping_backend("LOCALHOST", LOCAL_URL)
    
    # 2. Ping Cloud
    cloud_alive = await ping_backend("CLOUD (SmartDome)", CLOUD_URL)
    
    # 3. Zep Metadata
    await check_zep_metadata()
    
    log("\n=== SUMMARY ===")
    if local_alive:
        log("✅ Local Backend is RUNNING.")
    else:
        log("❌ Local Backend is DOWN.")
        
    if cloud_alive:
        log("✅ Cloud Backend is RUNNING (Active SmartDome Instance).")
    else:
        log("❌ Cloud Backend is DOWN.")
        
    with open("ping_result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
