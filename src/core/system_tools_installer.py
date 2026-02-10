import os
import subprocess
import json
import logging
from enum import Enum

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

logger = logging.getLogger(__name__)

class ToolCategory(Enum):
    DEV_ENV = "Development Environment"
    DEV_TOOLS = "Development Tools"
    TERMINAL = "Terminal & Shell"
    PACKAGE_MGR = "Package Managers"
    ESSENTIAL_UTILS = "Essential Utilities"
    HARDWARE_TOOLS = "Hardware Tools"

class SystemTool:
    def __init__(self, tool_id, name, description, category, install_commands, 
                 check_command, requires_admin=False, requires_restart=False, post_install_message=""):
        self.id = tool_id
        self.name = name
        self.description = description
        self.category = category
        self.install_commands = install_commands
        self.check_command = check_command
        self.requires_admin = requires_admin
        self.requires_restart = requires_restart
        self.post_install_message = post_install_message
        self.is_installed = False

class SystemToolsInstaller:
    def __init__(self, config_path=None):
        self.tools = {}
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "system_tools.json")
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        try:
            if not os.path.exists(self.config_path): return
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cat_map = {
                "Development Environment": ToolCategory.DEV_ENV,
                "Development Tools": ToolCategory.DEV_TOOLS,
                "Terminal & Shell": ToolCategory.TERMINAL,
                "Package Managers": ToolCategory.PACKAGE_MGR,
                "Essential Utilities": ToolCategory.ESSENTIAL_UTILS,
                "Hardware Tools": ToolCategory.HARDWARE_TOOLS
            }
            
            for tool_data in config.get("tools", []):
                tool = SystemTool(
                    tool_id=tool_data["id"],
                    name=tool_data["name"],
                    description=tool_data["description"],
                    category=cat_map.get(tool_data["category"], ToolCategory.DEV_TOOLS),
                    install_commands=tool_data["install_commands"],
                    check_command=tool_data["check_command"],
                    requires_admin=tool_data.get("requires_admin", False),
                    requires_restart=tool_data.get("requires_restart", False),
                    post_install_message=tool_data.get("post_install_message", "")
                )
                self.tools[tool.id] = tool
        except Exception as e:
            logger.error(f"Failed to load system tools config: {e}")

    def check_tool_status(self, tool):
        try:
            ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", tool.check_command]
            result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=30, shell=False, creationflags=CREATE_NO_WINDOW)
            tool.is_installed = (result.returncode == 0)
            return tool.is_installed
        except Exception as e:
            logger.error(f"Failed to check status for tool '{getattr(tool, 'name', tool)}': {e}")
            return False
