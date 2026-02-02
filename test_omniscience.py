import requests
import json

API_URL = "http://localhost:8080/admin/history"

# These must match AdminDashboard.jsx exactly
DASHBOARD_TARGETS = [
    {"role": "CEO", "thread": "smartdome_ceo_valentin_v3", "owner": "Valentin"},
    {"role": "CIO", "thread": "smartdome_cio_kamen_v3", "owner": "Kamen"},
    {"role": "CTO", "thread": "smartdome_cto_biser_v3", "owner": "Biser"},
    {"role": "CMO", "thread": "smartdome_cmo_kamen_v3", "owner": "Kamen (Marketing Lead)"},
    {"role": "CFO", "thread": "smartdome_cfo_rayna_v3", "owner": "Rayna"},
    {"role": "CLO", "thread": "smartdome_clo_rayna_v3", "owner": "Rayna"}
]

def audit_omniscience():
    print("👁️ STARTING OMNISCIENCE AUDIT (MASTER VIEW CHECK)\n" + "="*60)
    
    success_count = 0
    
    for target in DASHBOARD_TARGETS:
        print(f"\n[AUDITING] {target['role']} Channel...")
        print(f"   🎯 Target Thread: {target['thread']}")
        
        try:
            resp = requests.get(f"{API_URL}?thread_id={target['thread']}")
            
            if resp.status_code == 200:
                data = resp.json()
                msg_count = len(data.get("messages", []))
                
                if msg_count > 0:
                    last_msg = data["messages"][0]["content"][:100].replace("\n", " ")
                    print(f"   ✅ STATUS: ONLINE | Messages: {msg_count}")
                    print(f"   📝 LATEST LOG: \"{last_msg}...\"")
                    success_count += 1
                else:
                    print(f"   ⚠️ STATUS: EMPTY (No history found).")
            elif resp.status_code == 404:
                 print(f"   ❌ STATUS: 404 NOT FOUND (Dashboard will show 'Silenced')")
                 print(f"      -> Reason: Agent hasn't been messaged yet by {target['owner']}.")
            else:
                print(f"   🔥 STATUS: ERROR {resp.status_code}")
                
        except Exception as e:
            print(f"   ☠️ NETWORK ERROR: {e}")

    print("\n" + "="*60)
    print(f"📊 AUDIT RESULT: {success_count}/{len(DASHBOARD_TARGETS)} Channels Active.")
    
    if success_count < 3:
        print("\n❌ CRITICAL: Omniscience is blind. Check thread_id mismatches between App.jsx and AdminDashboard.jsx.")
    else:
        print("\n✅ OMNISCIENCE CONFIRMED. The Dashboard is seeing the live matrix.")

if __name__ == "__main__":
    audit_omniscience()
