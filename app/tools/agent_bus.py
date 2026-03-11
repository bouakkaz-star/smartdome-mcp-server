"""
SmartDome OS v6.1 — Agent Bus
==============================
Inter-agent communication bus for director-to-director messaging.
Enables asynchronous message passing between AI Directors.
"""
import json
import logging
from pathlib import Path
from datetime import datetime

# Agent bus message store (in-memory with file persistence)
AGENT_BUS_FILE = Path(__file__).parent.parent.parent / "data" / "agent_bus.json"

def _ensure_bus_file():
    if not AGENT_BUS_FILE.exists():
        AGENT_BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_BUS_FILE, "w") as f:
            json.dump({"messages": []}, f)

def _load_bus():
    _ensure_bus_file()
    try:
        with open(AGENT_BUS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"messages": []}

def _save_bus(data):
    _ensure_bus_file()
    with open(AGENT_BUS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def send_agent_message(from_agent: str, to_agent: str, content: str, message_type: str = "directive") -> dict:
    """Send a message from one agent to another via the agent bus."""
    data = _load_bus()
    msg = {
        "id": f"bus_{len(data['messages'])+1}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "from": from_agent,
        "to": to_agent,
        "content": content,
        "type": message_type,
        "timestamp": datetime.utcnow().isoformat(),
        "read": False,
    }
    data["messages"].append(msg)
    # Keep last 500 messages
    if len(data["messages"]) > 500:
        data["messages"] = data["messages"][-500:]
    _save_bus(data)
    logging.info(f"AGENT_BUS: {from_agent} → {to_agent}: {content[:50]}...")
    return {"status": "sent", "message_id": msg["id"]}


def get_agent_messages(agent_id: str, unread_only: bool = False, limit: int = 20) -> list:
    """Get messages for a specific agent."""
    data = _load_bus()
    messages = [m for m in data["messages"] if m["to"] == agent_id]
    if unread_only:
        messages = [m for m in messages if not m.get("read")]
    return messages[-limit:]


def get_agent_routing_info(agent_id: str) -> dict:
    """Get routing metadata for an agent (capabilities, status)."""
    ROUTING_TABLE = {
        "ceo": {"name": "CEO", "capabilities": ["strategy", "decisions", "delegation"], "status": "active"},
        "cio": {"name": "CIO", "capabilities": ["software", "systems", "integration", "architecture"], "status": "active"},
        "cto": {"name": "CTO", "capabilities": ["hardware", "infrastructure", "networking"], "status": "active"},
        "cfo": {"name": "CFO", "capabilities": ["finance", "budgets", "accounting", "invoicing"], "status": "active"},
        "cmo": {"name": "CMO", "capabilities": ["marketing", "branding", "content", "social"], "status": "active"},
        "clo": {"name": "CLO", "capabilities": ["legal", "contracts", "compliance", "gdpr"], "status": "active"},
        "designer": {"name": "Designer", "capabilities": ["ui", "ux", "branding", "visual"], "status": "active"},
        "ralf": {"name": "RALF", "capabilities": ["audit", "monitoring", "anomalies", "system_health"], "status": "active"},
    }
    return ROUTING_TABLE.get(agent_id, {"name": agent_id, "capabilities": [], "status": "unknown"})
