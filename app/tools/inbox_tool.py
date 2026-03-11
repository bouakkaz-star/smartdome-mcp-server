"""
SmartDome OS v6.1 — Drive Inbox Tool
=====================================
AI-powered file classification and routing using Gemini Flash.
Classifies uploaded files, routes them to Google Drive, and creates Notion tasks.

Dependencies: Google Gemini, Google Drive API, Notion API
"""
import os
import json
import logging
from pathlib import Path

# --- Lazy import to avoid circular deps ---
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# --- Classification Schema ---
CLASSIFICATION_SCHEMA = {
    "categories": [
        "contract", "invoice", "receipt", "report", "presentation",
        "design_asset", "legal_document", "correspondence", "marketing_material",
        "technical_spec", "meeting_notes", "financial_statement", "other"
    ],
    "departments": ["ceo", "cio", "cto", "cfo", "cmo", "clo", "designer", "ralf"],
    "priorities": ["P0", "P1", "P2", "P3", "P4"],
}


async def classify_file(file_bytes: bytes, filename: str, mime_type: str, project_hint: str = None) -> dict:
    """
    Classify a file using Gemini Flash.
    Returns: { category, department, priority, summary, suggested_folder, project }
    """
    if not GEMINI_AVAILABLE:
        raise RuntimeError("Gemini SDK not available — cannot classify files")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    client = genai.Client(api_key=api_key)

    # Build classification prompt
    prompt = f"""You are a document classifier for SmartDome estate management system.
Analyze this file and return a JSON classification.

Filename: {filename}
MIME Type: {mime_type}
File Size: {len(file_bytes)} bytes
{f'Project Hint: {project_hint}' if project_hint else ''}

Return ONLY valid JSON with these fields:
{{
    "category": one of {json.dumps(CLASSIFICATION_SCHEMA["categories"])},
    "department": one of {json.dumps(CLASSIFICATION_SCHEMA["departments"])},
    "priority": one of {json.dumps(CLASSIFICATION_SCHEMA["priorities"])},
    "summary": "1-2 sentence description of the document",
    "suggested_folder": "recommended Drive folder path",
    "project": "smartdome or other project name",
    "tags": ["tag1", "tag2"]
}}"""

    try:
        # Upload file to Gemini for analysis
        uploaded = client.files.upload(
            file=file_bytes,
            config=types.UploadFileConfig(
                display_name=filename,
                mime_type=mime_type,
            ),
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded, prompt],
        )

        # Parse JSON from response
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        classification = json.loads(text)
        logging.info(f"INBOX: Classified '{filename}' → {classification.get('category')} / {classification.get('department')}")
        return classification

    except json.JSONDecodeError as e:
        logging.warning(f"INBOX: Gemini returned non-JSON for '{filename}': {e}")
        return {
            "category": "other",
            "department": "cio",
            "priority": "P2",
            "summary": f"Unclassified file: {filename}",
            "suggested_folder": "Inbox/Unclassified",
            "project": project_hint or "smartdome",
            "tags": ["needs-review"],
        }
    except Exception as e:
        logging.error(f"INBOX: Classification failed for '{filename}': {e}")
        raise


async def process_inbox_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    uploader: str = "kamen",
    project_hint: str = None,
    auto_upload_drive: bool = True,
    auto_create_task: bool = True,
) -> dict:
    """
    Full inbox pipeline: Classify → Drive Upload → Notion Task.
    Returns result dict with classification, drive_url, task_id.
    """
    # Step 1: Classify
    classification = await classify_file(file_bytes, filename, mime_type, project_hint)

    result = {
        "classification": classification,
        "filename": filename,
        "size_bytes": len(file_bytes),
        "uploader": uploader,
        "drive_uploaded": False,
        "task_created": False,
    }

    # Step 2: Upload to Google Drive (if configured and requested)
    if auto_upload_drive:
        try:
            from tools.drive_tool import drive_upload_file
            folder = classification.get("suggested_folder", "Inbox")
            drive_result = await drive_upload_file(
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type,
                folder_path=folder,
            )
            result["drive_uploaded"] = True
            result["drive_url"] = drive_result.get("url", "")
            result["drive_folder"] = folder
        except Exception as e:
            logging.warning(f"INBOX: Drive upload skipped for '{filename}': {e}")
            result["drive_error"] = str(e)

    # Step 3: Create Notion task (if configured and requested)
    if auto_create_task:
        try:
            from tools.notion_tool import create_notion_task
            task_result = create_notion_task(
                title=f"[INBOX] {classification.get('summary', filename)[:80]}",
                agent_id=classification.get("department", "cio"),
                priority=classification.get("priority", "P2"),
                category=classification.get("category", "other"),
            )
            result["task_created"] = True
            result["task_id"] = task_result.get("id", "")
        except Exception as e:
            logging.warning(f"INBOX: Notion task skipped for '{filename}': {e}")
            result["task_error"] = str(e)

    result["summary"] = f"{classification.get('category', 'file')} → {classification.get('department', 'cio').upper()} (P{classification.get('priority', '2')[-1]})"

    return result
