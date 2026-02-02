from fastapi import HTTPException
import logging

# --- CONFIG ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartDome-Security")

# --- RBAC POLICY DEFINITION ---
# Who can talk to whom?
# Format: 'agent_role': ['authorized_user_1', 'authorized_user_2']
# 'orchestrator' is implicitly allowed everywhere (God Mode).

RBAC_POLICY = {
    'ceo': ['orchestrator'], # Only the Founder talks to the CEO
    'cto': ['orchestrator', 'tech_lead', 'architect'],
    'cio': ['orchestrator', 'architect'],
    'cfo': ['orchestrator', 'finance'],
    'cmo': ['orchestrator', 'architect'],
    'clo': ['orchestrator', 'finance'],
    'ea':  ['orchestrator', 'tech_lead', 'architect', 'finance'] # Everyone can use the EA
}

def verify_access(agent_role: str, user_id: str):
    """
    Verifies if a specific user is allowed to interact with a specific agent.
    Raises HTTPException(403) if access is denied.
    """
    # 1. Normalize inputs
    agent = agent_role.lower().strip()
    user = user_id.lower().strip()

    # 2. God Mode (Orchestrator)
    if user == 'orchestrator':
        return True

    # 3. Check Policy
    allowed_users = RBAC_POLICY.get(agent, [])
    
    # 4. Handle "Unknown Agent" (Default to Safe/Strict or Open?)
    # Strict: If agent not in list, deny.
    if agent not in RBAC_POLICY:
        logger.warning(f"Security Alert: Attempt to access unknown agent '{agent}' by '{user}'")
        raise HTTPException(status_code=403, detail=f"Access Denied: Agent '{agent}' determines strictly controlled access.")

    # 5. Verify User
    if user in allowed_users:
        return True
    
    # 6. DENY
    logger.warning(f"Security Breach: User '{user}' blocked from '{agent}'")
    raise HTTPException(
        status_code=403, 
        detail=f"Access Denied: User '{user}' is not authorized to instruct the {agent.upper()}."
    )
