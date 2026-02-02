import os
from zep_cloud.client import Zep
from zep_cloud.types import Message
from dotenv import load_dotenv

load_dotenv()
ZEP_API_KEY = os.getenv("ZEP_API_KEY")

def test_zep():
    if not ZEP_API_KEY:
        print("No ZEP_API_KEY found")
        return
    
    zep = Zep(api_key=ZEP_API_KEY)
    thread_id = "smartdome_cio_thread_v3"
    user_id = "kamen_architect_v3"
    
    print(f"Testing Zep for thread: {thread_id}")
    
    try:
        # 1. Add messages
        print("Adding test messages...")
        zep.thread.add_messages(thread_id=thread_id, messages=[
            Message(role="user", content="Diagnostic test message - Human"),
            Message(role="assistant", content="Diagnostic test message - AI")
        ])
        print("Messages added potentially.")
        
        # 2. Retrieve
        print("Retrieving history...")
        res = zep.thread.get(thread_id=thread_id, lastn=5)
        msgs = getattr(res, 'messages', [])
        print(f"Retrieved {len(msgs)} messages.")
        for m in msgs:
            print(f" - {getattr(m, 'role', '?')}: {getattr(m, 'content', '?')[:30]}... ({getattr(m, 'created_at', '?')})")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_zep()
