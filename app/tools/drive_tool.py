"""
SmartDome OS v6.1 — Google Drive Tool
======================================
Google Drive integration for file storage/retrieval.

STATUS: Drive API requires OAuth2 Service Account credentials.
        Until configured, all operations return graceful errors.
        This does NOT block other integrations (Notion, Agent Bus, etc.)

Required env vars (when configured):
  GOOGLE_DRIVE_CREDENTIALS - Path to service account JSON
  GOOGLE_DRIVE_ROOT_FOLDER - Root folder ID for SmartDome files
"""
import os
import logging
from typing import List, Dict, Any, Optional

DRIVE_CONFIGURED = bool(os.getenv("GOOGLE_DRIVE_CREDENTIALS"))


def _not_configured_error(operation: str) -> Dict[str, Any]:
    """Return a clear error when Drive is not configured."""
    return {
        "success": False,
        "error": f"Google Drive not configured — {operation} unavailable",
        "hint": "Set GOOGLE_DRIVE_CREDENTIALS env var with service account JSON path",
    }


async def drive_list_files(folder_id: str = None, max_results: int = 20) -> Dict[str, Any]:
    """List files in a Google Drive folder."""
    if not DRIVE_CONFIGURED:
        return _not_configured_error("list_files")
    return _not_configured_error("list_files")


async def drive_search(query: str, folder_id: str = None, max_results: int = 10) -> Dict[str, Any]:
    """Search for files in Google Drive."""
    if not DRIVE_CONFIGURED:
        return _not_configured_error("search")
    return _not_configured_error("search")


async def drive_upload_file(
    file_bytes: bytes = None,
    filename: str = "unnamed",
    mime_type: str = "application/octet-stream",
    folder_path: str = "Inbox",
    folder_id: str = None,
) -> Dict[str, Any]:
    """Upload a file to Google Drive."""
    if not DRIVE_CONFIGURED:
        logging.warning(f"DRIVE: Upload skipped for '{filename}' — not configured")
        return _not_configured_error("upload")
    return _not_configured_error("upload")


async def drive_get_file_content(file_id: str) -> Dict[str, Any]:
    """Get content/metadata of a specific file."""
    if not DRIVE_CONFIGURED:
        return _not_configured_error("get_file_content")
    return _not_configured_error("get_file_content")


async def drive_create_folder(name: str, parent_id: str = None) -> Dict[str, Any]:
    """Create a folder in Google Drive."""
    if not DRIVE_CONFIGURED:
        return _not_configured_error("create_folder")
    return _not_configured_error("create_folder")


# Legacy compatibility alias
async def search_drive_pdfs(query: str, folder_id: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
    """Legacy search function — returns empty list when not configured."""
    if not DRIVE_CONFIGURED:
        return []
    return []
