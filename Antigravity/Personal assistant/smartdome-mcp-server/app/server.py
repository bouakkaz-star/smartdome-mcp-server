from typing import Dict, Any, List, Callable
from app.tools.notion_tool import create_notion_task
# Ако нямаш drive_tool още, може да махнеш следващия ред, но ако го имаш - остави го
# from app.tools.drive_tool import search_drive_pdfs 
from app.tools.chat_tool import chat  # <--- НОВО 1: Внасяме инструмента

class SmartDomeMCPServer:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self):
        # Тук описваме какво може да прави роботът
        self.register_tool("create_notion_task", create_notion_task)
        # self.register_tool("search_drive_pdfs", search_drive_pdfs)
        self.register_tool("chat", chat)  # <--- НОВО 2: Слагаме го в менюто

    def register_tool(self, name: str, func: Callable):
        self.tools[name] = func

    def get_tools_metadata(self) -> List[Dict[str, Any]]:
        metadata = []
        for name, func in self.tools.items():
            metadata.append({
                "name": name,
                "description": func.__doc__.strip() if func.__doc__ else "No description",
            })
        return metadata

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        tool_func = self.tools[tool_name]
        return await tool_func(**arguments)

server = SmartDomeMCPServer()