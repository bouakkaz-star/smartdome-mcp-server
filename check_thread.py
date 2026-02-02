import os
from zep_cloud.client import Zep
from dotenv import load_dotenv

load_dotenv()
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

def check_thread():
    if not ZEP_API_KEY:
        print("No ZEP_API_KEY found")
        return
    
    zep = Zep(api_key=ZEP_API_KEY)
    thread_id = "smartdome_ceo_orchestrator_v3"
    
    print(f"Checking Zep for thread: {thread_id}")
    
    try:
        res = zep.thread.get(thread_id=thread_id)
        print(f"Thread FOUND! Number of messages: {len(getattr(res, 'messages', []))}")
    except Exception as e:
        print(f"Thread NOT FOUND or Error: {e}")

if __name__ == "__main__":
    check_thread()
