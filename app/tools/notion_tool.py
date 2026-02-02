import os
import httpx
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Зареждаме ключовете
load_dotenv()

NOTION_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

async def create_notion_task(
    title: str, 
    status: str = "Not started", 
    priority: str = "Medium",
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a REAL task in the SmartDome Notion workspace via API.
    """
    
    if not NOTION_KEY or not DATABASE_ID:
        return {"error": "Missing API Keys in .env file"}

    url = "https://api.notion.com/v1/pages"

    # Структурата на данните за Notion
    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Task name": {
                "title": [
                    {"text": {"content": title}}
                ]
            },
            "Status": {
                "status": {
                    "name": status
                }
            },
            "Priority": {
                "select": {
                    "name": priority
                }
            }
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            # Ако Notion върне грешка, искаме да я видим
            return {"error": response.status_code, "details": response.json()}
            
        return response.json()