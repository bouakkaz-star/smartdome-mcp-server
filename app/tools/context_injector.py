"""
SmartDome OS v6.1 — Context Injector
======================================
Injects contextual information into AI Director prompts:
- User profile & preferences
- Recent conversation summary
- Active tasks & priorities
- System state & anomalies
- Time-aware greetings
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime


def inject_context(
    agent_role: str,
    user_id: str = "kamen",
    thread_id: str = None,
    task_summary: dict = None,
    system_state: dict = None,
) -> str:
    """
    Build a context block to prepend to the AI Director's system prompt.
    Returns a formatted string with relevant contextual information.
    """
    context_parts = []

    # 1. Time awareness
    now = datetime.utcnow()
    hour = now.hour
    if hour < 6:
        greeting = "Late night session"
    elif hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    context_parts.append(f"[CONTEXT] {greeting}. Current time: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    context_parts.append(f"[CONTEXT] Active user: {user_id} | Director: {agent_role.upper()}")

    # 2. Task context (if provided)
    if task_summary:
        pending = task_summary.get("pending", 0)
        in_progress = task_summary.get("in_progress", 0)
        if pending > 0 or in_progress > 0:
            context_parts.append(f"[CONTEXT] Active tasks: {pending} pending, {in_progress} in progress")

    # 3. System state (if provided)
    if system_state:
        anomalies = system_state.get("open_anomalies", 0)
        if anomalies > 0:
            context_parts.append(f"[CONTEXT] System alert: {anomalies} open anomalies")

    # 4. Thread context
    if thread_id:
        context_parts.append(f"[CONTEXT] Thread: {thread_id}")

    return "\n".join(context_parts)
