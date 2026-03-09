"""
SmartDome OS — Task Engine v6.0
================================
Modular task management system with due dates, categories, reminders,
subtasks, and CEO-grade reporting.

Extracted from main.py and enhanced for the HAP Model architecture.
Backwards-compatible with existing director_tasks.json schema.

Author: Antigravity (CIO Engineering)
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger("smartdome.task_engine")

# ─────────────────────────────────────────────
# AGENT MAP — Full board roster
# ─────────────────────────────────────────────
AGENT_MAP = {
    # Primary directors
    "valentin": "ceo",
    "kamen": "cio",
    "biser": "cto",
    "raina": "cfo",
    # Shared roles (resolve to primary holder)
    "cmo": "cmo",           # Kamen + Valentin shared
    "clo": "clo",           # Valentin + Raina shared
    # Sub-agents & specialists
    "ralf": "ralf",         # CIO sub-agent
    "designer": "designer",
    "antigravity": "antigravity",
    # Direct ID pass-through
    "ceo": "ceo",
    "cio": "cio",
    "cto": "cto",
    "cfo": "cfo",
}

def resolve_agent_id(name: str) -> str:
    """Resolve a friendly name or role to canonical agent ID."""
    return AGENT_MAP.get(name.lower().strip(), name.lower().strip())


# ─────────────────────────────────────────────
# PRIORITY & STATUS DEFINITIONS
# ─────────────────────────────────────────────
VALID_PRIORITIES = {"red", "orange", "green", "blue"}
VALID_STATUSES = {"pending", "in_progress", "completed", "dismissed", "delegated", "overdue"}

PRIORITY_LABELS = {
    "red": "Urgent",
    "orange": "Operational",
    "green": "Standard",
    "blue": "Delegated / Tracking",
}

# ─────────────────────────────────────────────
# TASK CATEGORIES
# ─────────────────────────────────────────────
VALID_CATEGORIES = {
    "finance", "engineering", "legal", "marketing",
    "operations", "hr", "system", "general"
}

VALID_COMPANIES = {
    "smartdome",    # SmartDome EOOD
    "21grama",      # 21 Grama
    "personal",     # Personal expenses/tasks
    "all",          # Cross-company
}


# ═══════════════════════════════════════════════
#  TASK MANAGER — Core CRUD + Enhanced Features
# ═══════════════════════════════════════════════
class TaskEngine:
    """
    Enhanced task manager with due dates, categories, subtasks,
    reminders, and reporting capabilities.

    Backwards-compatible: existing tasks without new fields
    still load and work correctly.
    """

    def __init__(self, filepath: Path, time_manager=None):
        self.filepath = filepath
        self.time_manager = time_manager
        self.ensure_file()

    def _now_iso(self) -> str:
        if self.time_manager:
            return self.time_manager.get_iso_time()
        return datetime.now().isoformat()

    def ensure_file(self):
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"directors": {}}, f, indent=2)

    def load(self) -> dict:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError) as e:
            logger.error(f"TaskEngine failed to load {self.filepath}: {e}")
            return {"directors": {}}

    def save(self, data: dict):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── CREATE ──────────────────────────────────
    def add_task(
        self,
        agent_id: str,
        title: str,
        description: str,
        priority: str = "green",
        source: str = "manual",
        delegated_by: str = None,
        due_date: str = None,
        category: str = "general",
        company: str = "smartdome",
        tags: list = None,
        parent_task_id: str = None,
    ) -> dict:
        """
        Create a new task with full metadata.

        Args:
            agent_id: Target agent canonical ID
            title: Short task title
            description: Detailed description
            priority: red|orange|green|blue
            source: manual|voice|ai_generated|calendar|cio_delegation
            delegated_by: Who delegated (e.g. "CIO")
            due_date: ISO date string (e.g. "2026-02-28")
            category: finance|engineering|legal|marketing|operations|hr|system|general
            company: smartdome|21grama|personal|all
            tags: List of string tags
            parent_task_id: ID of parent task (for subtasks)

        Returns:
            The created task dict
        """
        agent_id = resolve_agent_id(agent_id)
        if priority not in VALID_PRIORITIES:
            priority = "green"
        if category not in VALID_CATEGORIES:
            category = "general"
        if company not in VALID_COMPANIES:
            company = "smartdome"

        data = self.load()
        if agent_id not in data["directors"]:
            data["directors"][agent_id] = {"tasks": []}

        new_task = {
            "id": f"t_{int(time.time() * 1000)}",
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "source": source,
            "delegated_by": delegated_by,
            "created_at": self._now_iso(),
            # ── v6 Enhanced Fields ──
            "due_date": due_date,
            "category": category,
            "company": company,
            "tags": tags or [],
            "parent_task_id": parent_task_id,
            "completed_at": None,
            "reminder_sent": False,
        }

        data["directors"][agent_id]["tasks"].insert(0, new_task)
        self.save(data)
        logger.info(f"Task created: [{agent_id}] {title} (priority={priority}, due={due_date})")
        return new_task

    # ── UPDATE ──────────────────────────────────
    def update_task(
        self,
        agent_id: str,
        task_id: str,
        priority: str = None,
        status: str = None,
        due_date: str = None,
        category: str = None,
        company: str = None,
        tags: list = None,
        description: str = None,
    ) -> bool:
        """Update task fields. Returns True if found and updated."""
        agent_id = resolve_agent_id(agent_id)
        data = self.load()

        if agent_id not in data["directors"]:
            return False

        for task in data["directors"][agent_id]["tasks"]:
            if task["id"] == task_id:
                if priority and priority in VALID_PRIORITIES:
                    task["priority"] = priority
                if status and status in VALID_STATUSES:
                    task["status"] = status
                    if status == "completed":
                        task["completed_at"] = self._now_iso()
                if due_date is not None:
                    task["due_date"] = due_date
                if category and category in VALID_CATEGORIES:
                    task["category"] = category
                if company and company in VALID_COMPANIES:
                    task["company"] = company
                if tags is not None:
                    task["tags"] = tags
                if description is not None:
                    task["description"] = description

                self.save(data)
                return True

        return False

    # ── SOFT DELETE ─────────────────────────────
    def dismiss_task(self, agent_id: str, task_id: str) -> bool:
        """Soft-delete: mark as dismissed."""
        return self.update_task(agent_id, task_id, status="dismissed")

    # ── READ / QUERY ────────────────────────────
    def get_tasks(
        self,
        agent_id: str,
        status_filter: str = None,
        category_filter: str = None,
        company_filter: str = None,
        include_subtasks: bool = True,
    ) -> List[dict]:
        """Get tasks for an agent with optional filters."""
        agent_id = resolve_agent_id(agent_id)
        data = self.load()
        tasks = data.get("directors", {}).get(agent_id, {}).get("tasks", [])

        result = []
        for t in tasks:
            if status_filter and t.get("status") != status_filter:
                continue
            if category_filter and t.get("category", "general") != category_filter:
                continue
            if company_filter and t.get("company", "smartdome") != company_filter:
                continue
            if not include_subtasks and t.get("parent_task_id"):
                continue
            result.append(t)

        return result

    def get_overdue_tasks(self, agent_id: str = None) -> List[dict]:
        """Get all tasks past their due date across all or one agent."""
        data = self.load()
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = []

        agents = [agent_id] if agent_id else list(data.get("directors", {}).keys())

        for aid in agents:
            aid = resolve_agent_id(aid) if agent_id else aid
            for task in data.get("directors", {}).get(aid, {}).get("tasks", []):
                if task.get("status") in ("completed", "dismissed"):
                    continue
                due = task.get("due_date")
                if due and due < today:
                    task["_agent_id"] = aid
                    overdue.append(task)

        return sorted(overdue, key=lambda t: t.get("due_date", "9999"))

    def get_due_soon(self, days: int = 3) -> List[dict]:
        """Get tasks due within the next N days."""
        data = self.load()
        today = datetime.now()
        cutoff = (today + timedelta(days=days)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        due_soon = []

        for aid, agent_data in data.get("directors", {}).items():
            for task in agent_data.get("tasks", []):
                if task.get("status") in ("completed", "dismissed"):
                    continue
                due = task.get("due_date")
                if due and today_str <= due <= cutoff:
                    task["_agent_id"] = aid
                    due_soon.append(task)

        return sorted(due_soon, key=lambda t: t.get("due_date", "9999"))

    # ── DELEGATION ──────────────────────────────
    def delegate_task(
        self,
        from_agent: str,
        to_agent: str,
        title: str,
        description: str,
        priority: str = "green",
        due_date: str = None,
        category: str = "general",
        company: str = "smartdome",
    ) -> dict:
        """
        Create a task for the target agent AND a tracking record
        for the sender. Bidirectional delegation chain.
        """
        from_id = resolve_agent_id(from_agent)
        to_id = resolve_agent_id(to_agent)
        delegator_label = from_id.upper()

        # 1. Task for RECEIVER
        receiver_task = self.add_task(
            agent_id=to_id,
            title=title,
            description=description,
            priority=priority,
            source="ai_generated",
            delegated_by=delegator_label,
            due_date=due_date,
            category=category,
            company=company,
        )

        # 2. Tracking task for SENDER (blue = delegated)
        if from_id != to_id:
            self.add_task(
                agent_id=from_id,
                title=title,
                description=f"Delegated to {to_id.upper()}: {description}",
                priority="blue",
                source="ai_generated",
                due_date=due_date,
                category=category,
                company=company,
            )

        return receiver_task


# ═══════════════════════════════════════════════
#  GEMINI TOOL FUNCTIONS
# ═══════════════════════════════════════════════
# These are registered as function-calling tools for the Gemini model.
# They use a module-level `_engine` reference set during init.

_engine: Optional[TaskEngine] = None

def init_engine(engine: TaskEngine):
    """Called from main.py to inject the TaskEngine instance."""
    global _engine
    _engine = engine


def create_scheduler_task(
    agent_id: str,
    title: str,
    description: str = "Manual entry",
    priority: str = "green",
    from_agent: str = None,
    due_date: str = None,
    category: str = "general",
    company: str = "smartdome",
):
    """
    Creates a new task in the specialized agent scheduler.
    Use this to assign work, set reminders, or delegate between directors.

    Args:
        agent_id: The target agent (ceo, cto, cfo, cio, ralf, designer, cmo, clo, antigravity).
        title: Short title for the task.
        description: Detailed description of what needs to be done.
        priority: 'red' (urgent), 'orange' (operational), 'green' (standard).
        from_agent: The role creating this task for delegation tracking (optional).
        due_date: Deadline in YYYY-MM-DD format (optional but recommended).
        category: Task category — finance, engineering, legal, marketing, operations, hr, system, general.
        company: Which company — smartdome, 21grama, personal, all.
    """
    if _engine is None:
        return "ERROR: Task engine not initialized."

    # ── HALLUCINATION GUARD ──
    forbidden_keywords = [
        "transcription", "audio processing", "transcribe", "listen to audio",
        "explain this", "what is", "tell me about", "describe",
    ]
    title_lower = title.lower()
    desc_lower = description.lower()
    if any(k in title_lower for k in forbidden_keywords) or any(k in desc_lower for k in forbidden_keywords):
        return "ERROR: This should be answered directly, not scheduled as a task. Respond inline."

    try:
        if from_agent:
            task = _engine.delegate_task(
                from_agent=from_agent,
                to_agent=agent_id,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                category=category,
                company=company,
            )
            from_label = resolve_agent_id(from_agent).upper()
            return f"Task '{title}' created for {resolve_agent_id(agent_id).upper()} (delegated by {from_label})."
        else:
            task = _engine.add_task(
                agent_id=agent_id,
                title=title,
                description=description,
                priority=priority,
                source="ai_generated",
                due_date=due_date,
                category=category,
                company=company,
            )
            return f"Task '{title}' created for {resolve_agent_id(agent_id).upper()}."
    except Exception as e:
        return f"Failed to create task: {str(e)}"


def get_task_summary(agent_id: str = None, company: str = None):
    """
    Get a summary of tasks for a specific agent or across all agents.
    Useful for daily briefings and status checks.

    Args:
        agent_id: Target agent ID (optional — omit for all agents).
        company: Filter by company — smartdome, 21grama, personal (optional).
    """
    if _engine is None:
        return "ERROR: Task engine not initialized."

    try:
        data = _engine.load()
        today = datetime.now().strftime("%Y-%m-%d")

        if agent_id:
            agents = {resolve_agent_id(agent_id): data.get("directors", {}).get(resolve_agent_id(agent_id), {"tasks": []})}
        else:
            agents = data.get("directors", {})

        summary_lines = []
        total_pending = 0
        total_overdue = 0
        total_completed = 0

        for aid, agent_data in agents.items():
            tasks = agent_data.get("tasks", [])
            pending = [t for t in tasks if t.get("status") == "pending"
                       and (not company or t.get("company", "smartdome") == company)]
            overdue = [t for t in pending if t.get("due_date") and t["due_date"] < today]
            completed = [t for t in tasks if t.get("status") == "completed"
                         and (not company or t.get("company", "smartdome") == company)]
            in_progress = [t for t in tasks if t.get("status") == "in_progress"
                           and (not company or t.get("company", "smartdome") == company)]

            if pending or completed or in_progress:
                urgent = [t for t in pending if t.get("priority") == "red"]
                line = f"**{aid.upper()}**: {len(pending)} pending"
                if urgent:
                    line += f" ({len(urgent)} urgent)"
                if overdue:
                    line += f", {len(overdue)} OVERDUE"
                if in_progress:
                    line += f", {len(in_progress)} in progress"
                line += f", {len(completed)} completed"
                summary_lines.append(line)

                total_pending += len(pending)
                total_overdue += len(overdue)
                total_completed += len(completed)

        header = f"📊 Task Summary ({datetime.now().strftime('%d %b %Y')})"
        if company:
            header += f" — {company.upper()}"
        totals = f"**Totals:** {total_pending} pending, {total_overdue} overdue, {total_completed} completed"

        return f"{header}\n{totals}\n\n" + "\n".join(summary_lines)
    except Exception as e:
        return f"Failed to generate summary: {e}"


def check_overdue_tasks():
    """
    Check for overdue tasks across all agents.
    Returns a formatted alert for any tasks past their due date.
    Use this proactively in daily briefings.
    """
    if _engine is None:
        return "ERROR: Task engine not initialized."

    try:
        overdue = _engine.get_overdue_tasks()
        if not overdue:
            return "✅ No overdue tasks. All deadlines on track."

        lines = [f"⚠️ **{len(overdue)} OVERDUE TASKS:**\n"]
        for t in overdue:
            agent = t.get("_agent_id", "unknown").upper()
            days_late = (datetime.now() - datetime.strptime(t["due_date"], "%Y-%m-%d")).days
            lines.append(
                f"- [{t.get('priority', 'green').upper()}] **{t['title']}** "
                f"(assigned to {agent}, {days_late}d overdue, "
                f"company: {t.get('company', 'smartdome')})"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to check overdue: {e}"


def check_upcoming_deadlines(days: int = 3):
    """
    Check for tasks due within the next few days.
    Useful for planning and proactive reminders.

    Args:
        days: Number of days to look ahead (default 3).
    """
    if _engine is None:
        return "ERROR: Task engine not initialized."

    try:
        upcoming = _engine.get_due_soon(days=days)
        if not upcoming:
            return f"No tasks due in the next {days} days."

        lines = [f"📅 **{len(upcoming)} tasks due in the next {days} days:**\n"]
        for t in upcoming:
            agent = t.get("_agent_id", "unknown").upper()
            lines.append(
                f"- **{t['title']}** → {agent} "
                f"(due: {t['due_date']}, priority: {t.get('priority', 'green')}, "
                f"company: {t.get('company', 'smartdome')})"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to check deadlines: {e}"


# ═══════════════════════════════════════════════
#  CEO-GRADE WEEKLY REPORT
# ═══════════════════════════════════════════════
def generate_weekly_report(agent_id: str = "ceo"):
    """
    Generates a comprehensive executive summary report.
    Includes per-agent breakdown, overdue alerts, company-level
    financial task tracking, and delegation chain status.
    Triggered by: "Generate summary", "Report status", "Weekly report".

    Args:
        agent_id: The agent requesting the report (for context).
    """
    if _engine is None:
        return "Report generation failed: engine not initialized."

    try:
        data = _engine.load()
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        report_time = today.strftime("%d %B %Y, %H:%M")

        # ── Collect metrics ──
        agent_stats = {}
        company_stats = {c: {"pending": 0, "completed": 0, "overdue": 0} for c in VALID_COMPANIES}
        total_pending = 0
        total_completed = 0
        total_overdue = 0
        total_in_progress = 0
        urgent_items = []
        overdue_items = []
        recent_completions = []

        for aid, agent_data in data.get("directors", {}).items():
            stats = {"pending": 0, "completed": 0, "overdue": 0, "in_progress": 0, "delegated": 0}
            for task in agent_data.get("tasks", []):
                status = task.get("status", "pending")
                company = task.get("company", "smartdome")
                due = task.get("due_date")

                if status == "pending":
                    stats["pending"] += 1
                    total_pending += 1
                    if company in company_stats:
                        company_stats[company]["pending"] += 1
                    if task.get("priority") == "red":
                        urgent_items.append({"agent": aid, "task": task})
                    if due and due < today_str:
                        stats["overdue"] += 1
                        total_overdue += 1
                        if company in company_stats:
                            company_stats[company]["overdue"] += 1
                        overdue_items.append({"agent": aid, "task": task})

                elif status == "completed":
                    stats["completed"] += 1
                    total_completed += 1
                    if company in company_stats:
                        company_stats[company]["completed"] += 1
                    # Recent = completed in last 7 days
                    completed_at = task.get("completed_at", task.get("created_at", ""))
                    if completed_at and completed_at[:10] >= (today - timedelta(days=7)).strftime("%Y-%m-%d"):
                        recent_completions.append({"agent": aid, "task": task})

                elif status == "in_progress":
                    stats["in_progress"] += 1
                    total_in_progress += 1

                elif status == "delegated":
                    stats["delegated"] += 1

            if any(v > 0 for v in stats.values()):
                agent_stats[aid] = stats

        # ── Build Report ──
        report = f"""
# 📊 EXECUTIVE REPORT — SmartDome OS
**Generated:** {report_time}
**Requested by:** {resolve_agent_id(agent_id).upper()}

---

## 🟢 SYSTEM OVERVIEW
| Metric | Count |
|--------|-------|
| Active (Pending) | {total_pending} |
| In Progress | {total_in_progress} |
| Completed (Total) | {total_completed} |
| ⚠️ Overdue | {total_overdue} |

---

## 👥 PER-AGENT BREAKDOWN
"""
        for aid, stats in sorted(agent_stats.items()):
            status_parts = []
            if stats["pending"]: status_parts.append(f"{stats['pending']} pending")
            if stats["in_progress"]: status_parts.append(f"{stats['in_progress']} active")
            if stats["overdue"]: status_parts.append(f"⚠️ {stats['overdue']} overdue")
            if stats["completed"]: status_parts.append(f"{stats['completed']} done")
            if stats["delegated"]: status_parts.append(f"{stats['delegated']} delegated")
            report += f"- **{aid.upper()}**: {', '.join(status_parts)}\n"

        # ── Company breakdown ──
        report += "\n---\n\n## 🏢 BY COMPANY\n"
        for comp, stats in company_stats.items():
            if any(v > 0 for v in stats.values()):
                report += f"- **{comp.upper()}**: {stats['pending']} pending, {stats['completed']} done"
                if stats["overdue"]:
                    report += f", ⚠️ {stats['overdue']} overdue"
                report += "\n"

        # ── Urgent & Overdue ──
        if urgent_items:
            report += "\n---\n\n## 🔴 URGENT ITEMS\n"
            for item in urgent_items:
                t = item["task"]
                due_info = f" (due: {t['due_date']})" if t.get("due_date") else ""
                report += f"- **{t['title']}** → {item['agent'].upper()}{due_info}\n"

        if overdue_items:
            report += "\n---\n\n## ⚠️ OVERDUE ALERTS\n"
            for item in overdue_items:
                t = item["task"]
                days_late = (today - datetime.strptime(t["due_date"], "%Y-%m-%d")).days
                report += f"- **{t['title']}** → {item['agent'].upper()} ({days_late} days late)\n"

        # ── Recent completions ──
        if recent_completions:
            report += "\n---\n\n## ✅ COMPLETED THIS WEEK\n"
            for item in recent_completions[:10]:
                t = item["task"]
                report += f"- {t['title']} ({item['agent'].upper()})\n"

        report += f"\n---\n*Report auto-generated by SmartDome Task Engine v6.0*\n"
        return report.strip()

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return f"Report generation failed: {e}"


# ═══════════════════════════════════════════════
#  ANOMALY LOGGER (moved from main.py)
# ═══════════════════════════════════════════════
_anomaly_path: Optional[Path] = None

def init_anomaly_path(data_dir: Path):
    global _anomaly_path
    _anomaly_path = data_dir / "system_anomalies.json"


def log_anomaly(agent_id: str, description: str, severity: str = "medium"):
    """
    Logs a technical anomaly for the System Engineer (Antigravity).
    Use this when a code-level fix is required (e.g., UI bug, API 500 error).

    Args:
        agent_id: The agent reporting the anomaly.
        description: What went wrong.
        severity: low, medium, high, critical.
    """
    if _anomaly_path is None:
        return "ERROR: Anomaly path not configured."
    try:
        if not _anomaly_path.exists():
            with open(_anomaly_path, "w") as f:
                json.dump({"anomalies": []}, f)

        with open(_anomaly_path, "r") as f:
            data = json.load(f)

        time_mgr = _engine.time_manager if _engine else None
        ts = time_mgr.get_iso_time() if time_mgr else datetime.now().isoformat()

        entry = {
            "id": f"err_{int(time.time() * 1000)}",
            "agent": agent_id,
            "description": description,
            "severity": severity,
            "timestamp": ts,
            "status": "open",
        }
        data["anomalies"].insert(0, entry)

        with open(_anomaly_path, "w") as f:
            json.dump(data, f, indent=2)

        return f"Anomaly logged: [{severity.upper()}] {description}. Engineering notified."
    except Exception as e:
        return f"Failed to log anomaly: {e}"


# ═══════════════════════════════════════════════
#  REMINDER ENGINE
# ═══════════════════════════════════════════════
class ReminderEngine:
    """
    Lightweight reminder system that checks tasks on each poll cycle.
    Designed to work with the existing 5-second frontend polling.

    Backend checks are triggered via a periodic endpoint or
    can be called from the chat loop for proactive reminders.
    """

    def __init__(self, engine: TaskEngine):
        self.engine = engine
        self._last_check: Optional[str] = None

    def check_and_flag_overdue(self) -> List[dict]:
        """
        Scan all tasks, flag overdue ones, return newly-overdue items.
        Call this periodically (e.g., once per hour or on daily briefing).
        """
        data = self.engine.load()
        today = datetime.now().strftime("%Y-%m-%d")
        newly_overdue = []
        modified = False

        for aid, agent_data in data.get("directors", {}).items():
            for task in agent_data.get("tasks", []):
                if task.get("status") in ("completed", "dismissed"):
                    continue
                due = task.get("due_date")
                if due and due < today and task.get("status") != "overdue":
                    # Don't auto-change status — just flag for reporting
                    if not task.get("reminder_sent"):
                        task["reminder_sent"] = True
                        modified = True
                        newly_overdue.append({
                            "agent_id": aid,
                            "task_id": task["id"],
                            "title": task["title"],
                            "due_date": due,
                            "days_late": (datetime.now() - datetime.strptime(due, "%Y-%m-%d")).days,
                        })

        if modified:
            self.engine.save(data)

        self._last_check = today
        return newly_overdue

    def get_daily_briefing(self, agent_id: str) -> str:
        """
        Generate a proactive daily briefing for an agent.
        Includes today's tasks, upcoming deadlines, and overdue alerts.
        """
        agent_id = resolve_agent_id(agent_id)
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        tasks = self.engine.get_tasks(agent_id)
        active = [t for t in tasks if t.get("status") in ("pending", "in_progress")]

        # Today's tasks (due today)
        due_today = [t for t in active if t.get("due_date") == today_str]
        due_tomorrow = [t for t in active if t.get("due_date") == tomorrow_str]
        overdue = [t for t in active if t.get("due_date") and t["due_date"] < today_str]
        no_deadline = [t for t in active if not t.get("due_date")]

        lines = [f"📋 **Daily Briefing for {agent_id.upper()}** — {today.strftime('%A, %d %B %Y')}\n"]

        if overdue:
            lines.append(f"🔴 **{len(overdue)} OVERDUE:**")
            for t in overdue:
                days = (today - datetime.strptime(t["due_date"], "%Y-%m-%d")).days
                lines.append(f"  - {t['title']} ({days}d late, {t.get('priority', 'green')})")

        if due_today:
            lines.append(f"\n📌 **DUE TODAY ({len(due_today)}):**")
            for t in due_today:
                lines.append(f"  - {t['title']} ({t.get('priority', 'green')}, {t.get('company', 'smartdome')})")

        if due_tomorrow:
            lines.append(f"\n📅 **DUE TOMORROW ({len(due_tomorrow)}):**")
            for t in due_tomorrow:
                lines.append(f"  - {t['title']}")

        if no_deadline:
            urgent = [t for t in no_deadline if t.get("priority") == "red"]
            if urgent:
                lines.append(f"\n⚡ **{len(urgent)} URGENT (no deadline set):**")
                for t in urgent:
                    lines.append(f"  - {t['title']}")

        lines.append(f"\n**Total active tasks:** {len(active)}")
        return "\n".join(lines)


# Module-level reminder instance (initialized from main.py)
_reminder: Optional[ReminderEngine] = None

def init_reminder(engine: TaskEngine):
    global _reminder
    _reminder = ReminderEngine(engine)


def get_daily_briefing(agent_id: str = "ceo"):
    """
    Get a proactive daily briefing for an agent.
    Shows today's priorities, upcoming deadlines, and overdue alerts.
    Best used at the start of each working day.

    Args:
        agent_id: The agent to brief (default: ceo).
    """
    if _reminder is None:
        return "Reminder engine not initialized."
    return _reminder.get_daily_briefing(agent_id)
