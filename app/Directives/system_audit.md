# DIRECTIVE: SYSTEM_AUDIT (OMNISCIENCE)
**Trigger:** "Run Master Audit" / "Omniscience Mode"
**Owner:** Virtual CIO (Kamen)

## 🎯 OBJECTIVE
Audit the communication channels of all agents to ensure "Zero Entropy" (System Integrity).

## 🛠️ AUDIT CHECKLIST

### 1. CHANNEL INTEGRITY (Zep V3)
*   **CEO Channel:** `hap_ceo_orchestrator_v3` -> Check for Strategic Alignment.
*   **CTO Channel:** `hap_cto_orchestrator_v3` -> Check for R&D Data consistency.
*   **CMO Channel:** `hap_cmo_orchestrator_v3` -> Check for Brand Voice consistency.
*   **CFO/CLO Channel:** `hap_cfo_orchestrator_v3` -> Check for Compliance flags.

### 2. SYSTEM SILENCE CHECK
*   **Condition:** If `AdminDashboard` returns 404/Empty.
*   **Verdict:** "System Silenced" (Normal for fresh threads).
*   **Action:** No alarm needed.

### 3. MEMORY SYNC STATUS
*   **Protocol:** Zep Cloud <-> LocalStorage.
*   **Verification:** Ensure no "Ghosting" (Leaked messages from other users). 
*   **Status:** CONFIRMED ISOLATION (V3.3 Upgrade).

## 📝 OUTPUT FORMAT
Return the audit result as:
```json
{
  "audit_id": "OMNI-00X",
  "status": "GREEN/RED",
  "channels_active": [List],
  "anomalies": [List]
}
```
