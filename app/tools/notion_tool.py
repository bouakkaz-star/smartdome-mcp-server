"""
SmartDome OS v6.1 — Notion Integration Tool
=============================================
Full CRUD + GTD workflow for Notion task management.
Supports: create, query, update, GTD capture/promote/complete.

Required env vars:
  NOTION_API_KEY       - Notion internal integration token
  NOTION_DATABASE_ID   - Target database ID for tasks
"""
import os
import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv

# ntn_ prefix for Notion Internal Integration Token
NOTION_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def get_notion_config():
    """Dynamically fetch Notion config from environment."""
    return os.getenv("NOTION_API_KEY"), os.getenv("NOTION_DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {os.getenv('NOTION_API_KEY')}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# --- Helpers ---
def _check_config():
    """Validate that Notion API credentials are configured."""
    key, db_id = get_notion_config()
    if not key or not db_id:
        return {"success": False, "error": f"Notion not configured — NOTION_API_KEY or NOTION_DATABASE_ID missing. env_key_exists: {bool(key)}, env_db_exists: {bool(db_id)}"}
    return None


def _extract_task(page: dict) -> dict:
    """Extract a clean task dict from a Notion page object."""
    props = page.get("properties", {})

    # Title
    title = ""
    title_prop = props.get("Task name", props.get("Name", {}))
    if title_prop.get("title"):
        title = "".join(t.get("plain_text", "") for t in title_prop["title"])

    # Status
    status_obj = props.get("Status", {})
    status = status_obj.get("status", {}).get("name", "Unknown") if status_obj.get("status") else "Unknown"

    # Priority
    priority_obj = props.get("Priority", {})
    priority = priority_obj.get("select", {}).get("name", "None") if priority_obj.get("select") else "None"

    # Due date
    due_obj = props.get("Due", props.get("Due Date", {}))
    due_date = None
    if due_obj.get("date") and due_obj["date"].get("start"):
        due_date = due_obj["date"]["start"]

    # Agent
    agent_obj = props.get("Agent", {})
    agent = agent_obj.get("select", {}).get("name", "") if agent_obj.get("select") else ""

    # Project
    project_obj = props.get("Project", {})
    project = project_obj.get("select", {}).get("name", "") if project_obj.get("select") else ""

    # Category
    category_obj = props.get("Category", {})
    category = category_obj.get("select", {}).get("name", "") if category_obj.get("select") else ""

    # GTD Tag
    gtd_obj = props.get("GTD Tag", {})
    gtd_tag = gtd_obj.get("select", {}).get("name", "") if gtd_obj.get("select") else ""

    # Description / Summary (rich_text)
    desc = ""
    desc_prop = props.get("Description", props.get("Summary", {}))
    if desc_prop.get("rich_text"):
        desc = "".join(t.get("plain_text", "") for t in desc_prop["rich_text"])

    return {
        "id": page["id"],
        "title": title,
        "status": status,
        "priority": priority,
        "due_date": due_date,
        "agent": agent,
        "project": project,
        "category": category,
        "gtd_tag": gtd_tag,
        "description": desc,
        "url": page.get("url", ""),
        "created_time": page.get("created_time", ""),
        "last_edited_time": page.get("last_edited_time", ""),
    }


# =====================================================================
# CRUD Operations
# =====================================================================

async def create_notion_task(
    title: str,
    status: str = "Not started",
    priority: str = "Medium",
    description: Optional[str] = None,
    agent_id: Optional[str] = None,
    category: Optional[str] = None,
    due_date: Optional[str] = None,
    project: Optional[str] = None,
    gtd_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a task in the SmartDome Notion database.
    Returns the created page object or error dict.
    """
    err = _check_config()
    if err:
        return err

    properties = {
        "Task name": {
            "title": [{"text": {"content": title}}]
        },
        "Status": {
            "status": {"name": status}
        },
    }

    # Optional fields — only add if value provided and property exists
    if priority:
        properties["Priority"] = {"select": {"name": priority}}
    if agent_id:
        properties["Agent"] = {"select": {"name": agent_id}}
    if category:
        properties["Category"] = {"select": {"name": category}}
    if project:
        properties["Project"] = {"select": {"name": project or "SmartDome"}}
    if gtd_tag:
        properties["GTD Tag"] = {"select": {"name": gtd_tag}}
    if due_date:
        properties["Due"] = {"date": {"start": due_date}}
    if description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": description[:2000]}}]
        }

    async with httpx.AsyncClient(timeout=15) as client:
        key, db_id = get_notion_config()
        headers = {**HEADERS, "Authorization": f"Bearer {key}"}
        try:
            resp = await client.post("https://api.notion.com/v1/pages", json=payload, headers=headers)
            if resp.status_code == 200:
                page = resp.json()
                logging.info(f"NOTION: Created task '{title}' → {page['id']}")
                return {"success": True, "id": page["id"], "url": page.get("url", "")}
            else:
                error_body = resp.json()
                logging.error(f"NOTION: Create failed ({resp.status_code}): {error_body}")
                return {"success": False, "error": resp.status_code, "details": error_body}
        except Exception as e:
            logging.error(f"NOTION: Create exception: {e}")
            return {"success": False, "error": str(e)}


async def query_notion_tasks(
    status: str = None,
    priority: str = None,
    agent_id: str = None,
    project_name: str = None,
    gtd_tag: str = None,
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    Query tasks from the Notion database with optional filters.
    Returns: { success, count, tasks: [...] }
    """
    err = _check_config()
    if err:
        return err

    # Build filter conditions
    filters = []
    if status:
        filters.append({
            "property": "Status",
            "status": {"equals": status}
        })
    if priority:
        filters.append({
            "property": "Priority",
            "select": {"equals": priority}
        })
    if agent_id:
        filters.append({
            "property": "Agent",
            "select": {"equals": agent_id}
        })
    if project_name:
        filters.append({
            "property": "Project",
            "select": {"equals": project_name}
        })
    if gtd_tag:
        filters.append({
            "property": "GTD Tag",
            "select": {"equals": gtd_tag}
        })

    body = {"page_size": min(max_results, 100)}
    if len(filters) == 1:
        body["filter"] = filters[0]
    elif len(filters) > 1:
        body["filter"] = {"and": filters}

    # Sort by last_edited_time desc
    body["sorts"] = [{"timestamp": "last_edited_time", "direction": "descending"}]

    async with httpx.AsyncClient(timeout=15) as client:
        key, db_id = get_notion_config()
        headers = {**HEADERS, "Authorization": f"Bearer {key}"}
        try:
            resp = await client.post(
                f"https://api.notion.com/v1/databases/{db_id}/query",
                json=body,
                headers=headers,
            )
            if resp.status_code != 200:
                error_body = resp.json()
                logging.error(f"NOTION: Query failed ({resp.status_code}): {error_body}")
                return {"success": False, "error": resp.status_code, "details": error_body}

            data = resp.json()
            tasks = [_extract_task(page) for page in data.get("results", [])]
            logging.info(f"NOTION: Queried {len(tasks)} tasks")
            return {"success": True, "count": len(tasks), "tasks": tasks}

        except Exception as e:
            logging.error(f"NOTION: Query exception: {e}")
            return {"success": False, "error": str(e)}


async def update_notion_task(
    task_id: str,
    title: str = None,
    status: str = None,
    priority: str = None,
    agent_id: str = None,
    due_date: str = None,
    description: str = None,
    gtd_tag: str = None,
) -> Dict[str, Any]:
    """
    Update an existing Notion task by page ID.
    Only updates fields that are provided (non-None).
    """
    err = _check_config()
    if err:
        return err

    properties = {}
    if title:
        properties["Task name"] = {"title": [{"text": {"content": title}}]}
    if status:
        properties["Status"] = {"status": {"name": status}}
    if priority:
        properties["Priority"] = {"select": {"name": priority}}
    if agent_id:
        properties["Agent"] = {"select": {"name": agent_id}}
    if due_date:
        properties["Due"] = {"date": {"start": due_date}}
    if description:
        properties["Description"] = {"rich_text": [{"text": {"content": description[:2000]}}]}
    if gtd_tag:
        properties["GTD Tag"] = {"select": {"name": gtd_tag}}

    if not properties:
        return {"success": False, "error": "No fields to update"}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.patch(
                f"https://api.notion.com/v1/pages/{task_id}",
                json={"properties": properties},
                headers=HEADERS,
            )
            if resp.status_code == 200:
                logging.info(f"NOTION: Updated task {task_id}")
                return {"success": True, "id": task_id}
            else:
                error_body = resp.json()
                return {"success": False, "error": resp.status_code, "details": error_body}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =====================================================================
# GTD (Getting Things Done) Workflow
# =====================================================================

async def gtd_capture(
    title: str,
    description: str = None,
    agent_id: str = None,
    project: str = None,
) -> Dict[str, Any]:
    """
    GTD CAPTURE: Add item to inbox. All new items start as GTD Tag = INBOX.
    """
    return await create_notion_task(
        title=title,
        status="Not started",
        priority="Medium",
        description=description,
        agent_id=agent_id,
        project=project,
        gtd_tag="INBOX",
    )


async def gtd_get_next_actions(agent_id: str = None) -> Dict[str, Any]:
    """
    GTD: Get all tasks tagged as NEXT (actionable items).
    Optionally filter by agent.
    """
    return await query_notion_tasks(gtd_tag="NEXT", agent_id=agent_id)


async def gtd_promote_to_next(task_id: str) -> Dict[str, Any]:
    """
    GTD CLARIFY/ORGANIZE: Promote an INBOX item to NEXT (actionable).
    """
    return await update_notion_task(task_id=task_id, gtd_tag="NEXT", status="In progress")


async def gtd_complete_task(task_id: str) -> Dict[str, Any]:
    """
    GTD COMPLETE: Mark a task as done.
    """
    return await update_notion_task(task_id=task_id, status="Done", gtd_tag="DONE")
