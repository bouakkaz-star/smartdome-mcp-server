"""
SmartDome DevOps Bridge Agent
Handles server management, config validation, and health monitoring.
Coordinates between Cowork (Claude Desktop) and Antigravity IDE.
"""

import os
import json
import subprocess
import requests
import time
from pathlib import Path
from datetime import datetime

# === PATHS ===
HAPMODEL_ROOT = Path(r"C:\Users\USER\Desktop\HAPModel")
SMARTDOME_SERVER = HAPMODEL_ROOT / "01_Projects" / "SmartDome" / "code" / "apps" / "server"
ANTIGRAVITY_SERVER = Path(r"C:\Users\USER\Desktop\Antigravity\Personal assistant\apps\server")
CONFIG_PATHS = [
    SMARTDOME_SERVER / "hapm_config.json",
    SMARTDOME_SERVER / "app" / "hapm_config.json",
    SMARTDOME_SERVER / "app" / "projects_data" / "smartdome.json",  # CRITICAL OVERRIDE
    ANTIGRAVITY_SERVER / "hapm_config.json",
    ANTIGRAVITY_SERVER / "app" / "hapm_config.json",
]
SERVER_URL = "http://localhost:8080"
TARGET_MODEL = "gemini-2.5-flash"


def health_check():
    """Check if the SmartDome server is running and responsive."""
    try:
        r = requests.get(f"{SERVER_URL}/api/status", timeout=5)
        data = r.json()
        model = data.get("model", "unknown")
        status = data.get("status", "unknown")
        model_ok = model == TARGET_MODEL
        return {
            "server": "online",
            "status": status,
            "model": model,
            "model_correct": model_ok,
            "timestamp": data.get("time"),
            "action_needed": None if model_ok else f"Model mismatch! Expected {TARGET_MODEL}, got {model}"
        }
    except requests.ConnectionError:
        return {"server": "offline", "action_needed": "Server not running. Start with: py -m uvicorn app.main:app --host 0.0.0.0 --port 8080"}
    except Exception as e:
        return {"server": "error", "error": str(e)}


def scan_all_configs():
    """Scan all config files and report model_provider values."""
    results = []
    for path in CONFIG_PATHS:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                model = data.get('system', {}).get('model_provider', 'NOT SET')
                results.append({
                    "path": str(path),
                    "exists": True,
                    "model": model,
                    "correct": model == TARGET_MODEL
                })
            except Exception as e:
                results.append({"path": str(path), "exists": True, "error": str(e)})
        else:
            results.append({"path": str(path), "exists": False})
    return results


def fix_all_configs():
    """Fix model_provider in ALL config files to the target model."""
    fixed = []
    for path in CONFIG_PATHS:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'system' in data and data['system'].get('model_provider') != TARGET_MODEL:
                    old = data['system']['model_provider']
                    data['system']['model_provider'] = TARGET_MODEL
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    fixed.append(f"{path.name}: {old} -> {TARGET_MODEL}")
            except:
                pass

    # Also fix Python files
    py_files = [
        SMARTDOME_SERVER / "app" / "main.py",
        SMARTDOME_SERVER / "app" / "Orchestration" / "router.py",
    ]
    old_models = ["gemini-3-flash-preview", "gemini-3-flash", "gemini-2.0-flash", "gemini-2.5-flash-preview-05-20"]
    for py_path in py_files:
        if py_path.exists():
            content = py_path.read_text(encoding='utf-8')
            original = content
            for old in old_models:
                content = content.replace(old, TARGET_MODEL)
            if content != original:
                py_path.write_text(content, encoding='utf-8')
                fixed.append(f"{py_path.name}: Python references fixed")

    return fixed if fixed else ["All files already correct"]


def test_agent(agent_role: str = "ceo", message: str = "Connectivity test. Confirm online."):
    """Test a specific agent via the chat endpoint."""
    try:
        r = requests.post(
            f"{SERVER_URL}/chat",
            data={
                "text": message,  # Modified from 'message' to 'text' for proper curl parsing in fastAPI
                "agent_role": agent_role, # Modified to use fastAPI parameters
                "user_id": "kamen"
            },
            timeout=30
        )
        return {"agent": agent_role, "status": r.status_code, "response": r.text[:500]}
    except Exception as e:
        return {"agent": agent_role, "error": str(e)}


def test_all_agents():
    """Test all 8 SmartDome agents."""
    agents = ["ceo", "cio", "cto", "cfo", "cmo", "clo", "ralf", "designer"]
    results = []
    for agent in agents:
        result = test_agent(agent, f"System test from DevOps bridge. Report your role, {agent}.")
        results.append(result)
        print(f"  {'✓' if 'response' in result else '✗'} {agent}: {result.get('status', result.get('error', 'unknown'))}")
    return results


def env_check():
    """Verify .env has required API keys."""
    env_path = SMARTDOME_SERVER / ".env"
    if not env_path.exists():
        return {"error": f".env not found at {env_path}"}

    content = env_path.read_text(encoding='utf-8')
    has_gemini = "GEMINI_API_KEY=" in content and not content.split("GEMINI_API_KEY=")[1].split("\n")[0].strip() == ""
    has_zep = "ZEP_API_KEY=" in content and not content.split("ZEP_API_KEY=")[1].split("\n")[0].strip() == ""

    return {
        "env_path": str(env_path),
        "GEMINI_API_KEY": "present" if has_gemini else "MISSING",
        "ZEP_API_KEY": "present" if has_zep else "MISSING"
    }


def full_diagnostic():
    """Run complete system diagnostic."""
    print("=" * 50)
    print(f"SmartDome DevOps Diagnostic - {datetime.now().isoformat()}")
    print("=" * 50)

    print("\n1. SERVER HEALTH:")
    health = health_check()
    for k, v in health.items():
        print(f"   {k}: {v}")

    print("\n2. CONFIG FILES:")
    configs = scan_all_configs()
    for c in configs:
        status = "OK" if c.get("correct") else ("MISSING" if not c.get("exists") else f"WRONG: {c.get('model', c.get('error'))}")
        print(f"   [{status}] {c['path']}")

    print("\n3. ENV KEYS:")
    env = env_check()
    for k, v in env.items():
        print(f"   {k}: {v}")

    print("\n4. ACTION ITEMS:")
    wrong_configs = [c for c in configs if c.get("exists") and not c.get("correct")]
    if wrong_configs:
        print(f"   ! Fix {len(wrong_configs)} config file(s) with wrong model")
    if health.get("server") == "offline":
        print("   ! Start the server")
    elif health.get("action_needed"):
        print(f"   ! {health['action_needed']}")
    if env.get("GEMINI_API_KEY") == "MISSING":
        print("   ! Add GEMINI_API_KEY to .env")
    if not wrong_configs and health.get("model_correct"):
        print("   ✓ All clear! System is healthy.")

    return {"health": health, "configs": configs, "env": env}


# === ENTRY POINT ===
if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diagnostic"

    if cmd == "diagnostic":
        full_diagnostic()
    elif cmd == "fix":
        print("Fixing all configs...")
        results = fix_all_configs()
        for r in results:
            print(f"  {r}")
        print("\nRestart server to apply changes!")
    elif cmd == "test":
        print("Testing all agents...")
        test_all_agents()
    elif cmd == "health":
        result = health_check()
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: py devops_bridge.py [diagnostic|fix|test|health]")
