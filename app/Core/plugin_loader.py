import os
import importlib
import inspect
import logging
from typing import List, Callable, Dict, Any

logger = logging.getLogger("SmartDome-PluginLoader")

class PluginLoader:
    """
    Dynamically loads Python modules from a directory and extracts functions
    that can be used as tools (functions with docstrings).
    """
    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.tools: Dict[str, Callable] = {}

    def load_all(self):
        """Scans the skills directory and loads all .py files."""
        if not os.path.exists(self.skills_dir):
            logger.error(f"Skills directory not found: {self.skills_dir}")
            return

        # Get all .py files except __init__.py
        modules = [
            f[:-3] for f in os.listdir(self.skills_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]

        for module_name in modules:
            try:
                # Import path relative to the app root (e.g., app.skills.module)
                # Assuming this is called from within the server environment where skills is a package
                import_path = f"skills.{module_name}"
                module = importlib.import_module(import_path)
                # Refresh module to handle hot-reloading if needed (optional)
                importlib.reload(module)
                
                self._extract_tools(module)
                logger.info(f"Loaded skill module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load module {module_name}: {e}")

    def _extract_tools(self, module):
        """Extracts functions from a module that have docstrings."""
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                # We consider any function with a docstring a potential tool
                if obj.__doc__:
                    self.tools[name] = obj

    def get_tool_list(self) -> List[Callable]:
        """Returns the list of extracted functions for Gemini's tools parameter."""
        return list(self.tools.values())

    def execute(self, function_name: str, **kwargs) -> Any:
        """Executes a loaded tool by name."""
        if function_name in self.tools:
            return self.tools[function_name](**kwargs)
        raise ValueError(f"Tool {function_name} not found.")
