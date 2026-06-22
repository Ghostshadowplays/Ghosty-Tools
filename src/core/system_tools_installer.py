import os
import sys
import subprocess
import json
import logging
import re
from enum import Enum
from src.utils.helpers import get_resource_path

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

logger = logging.getLogger(__name__)

class ToolCategory(Enum):
    BROWSERS = "Browsers"
    COMMUNICATIONS = "Communications"
    DEVELOPMENT = "Development"
    GAMES = "Games"
    MS_TOOLS = "Microsoft Tools"
    MULTIMEDIA = "Multimedia Tools"
    PRO_TOOLS = "Pro Tools"
    SELFHOSTED = "Selfhosted Tools"
    UTILITIES = "Utilities"
    GHOSTY_TOOLS = "Ghosty Tools"
    # Legacy categories for compatibility
    DEV_ENV = "Development Environment"
    DEV_TOOLS = "Development Tools"
    TERMINAL = "Terminal & Shell"
    PACKAGE_MGR = "Package Managers"
    ESSENTIAL_UTILS = "Essential Utilities"
    HARDWARE_TOOLS = "Hardware Tools"

class SystemTool:
    def __init__(self, tool_id, name, description, category, install_commands, 
                 check_command, requires_admin=False, requires_restart=False, 
                 post_install_message="", executable_name=None):
        self.id = tool_id
        self.name = name
        self.description = description
        self.category = category
        self.install_commands = install_commands
        self.check_command = check_command
        self.requires_admin = requires_admin
        self.requires_restart = requires_restart
        self.post_install_message = post_install_message
        self.executable_name = executable_name
        self.is_installed = False
        self.winget_id = self._extract_winget_id()

    def _extract_winget_id(self):
        for cmd in self.install_commands:
            if "winget" in cmd.lower() and "--id" in cmd:
                match = re.search(r'--id\s+([^\s]+)', cmd)
                if match:
                    return match.group(1)
        return None

class SystemToolsInstaller:
    def __init__(self, config_path=None):
        self.tools = {}
        if config_path is None:
            config_path = get_resource_path(os.path.join("config", "system_tools.json"))
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        try:
            if not os.path.exists(self.config_path): return
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cat_map = {
                "Browsers": ToolCategory.BROWSERS,
                "Communications": ToolCategory.COMMUNICATIONS,
                "Development": ToolCategory.DEVELOPMENT,
                "Games": ToolCategory.GAMES,
                "Microsoft Tools": ToolCategory.MS_TOOLS,
                "Multimedia Tools": ToolCategory.MULTIMEDIA,
                "Pro Tools": ToolCategory.PRO_TOOLS,
                "Selfhosted Tools": ToolCategory.SELFHOSTED,
                "Utilities": ToolCategory.UTILITIES,
                "Ghosty Tools": ToolCategory.GHOSTY_TOOLS,
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
                    post_install_message=tool_data.get("post_install_message", ""),
                    executable_name=tool_data.get("executable_name")
                )
                self.tools[tool.id] = tool
        except Exception as e:
            logger.error(f"Failed to load system tools config: {e}")

    def check_tool_status(self, tool):
        if sys.platform != 'win32':
            try:
                # On Linux, try 'which' or 'command -v'
                exec_name = tool.executable_name or tool.name.lower().replace(" ", "-")
                if exec_name.endswith(".exe"): exec_name = exec_name[:-4]
                
                res = subprocess.run(["which", exec_name], capture_output=True, text=True)
                if res.returncode == 0:
                    tool.is_installed = True
                    return True
                
                # Check for common linux names
                for alt in [tool.name.lower(), tool.name.lower().replace(" ", "")]:
                    if subprocess.run(["which", alt], capture_output=True).returncode == 0:
                        tool.is_installed = True
                        return True
            except: pass
            
            tool.is_installed = False
            return False
        try:
            # 1. Try defined check_command
            ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", tool.check_command]
            result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=30, shell=False, creationflags=CREATE_NO_WINDOW)
            if result.returncode == 0:
                tool.is_installed = True
                return True

            # 2. Try winget list if ID is available
            if tool.winget_id:
                winget_check = f"winget list --id {tool.winget_id} --exact --source winget"
                ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", winget_check]
                result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=15, shell=False, creationflags=CREATE_NO_WINDOW)
                if result.returncode == 0:
                    tool.is_installed = True
                    return True

            # 3. Try searching common paths if executable name is known
            lookup_names = []
            if tool.executable_name:
                lookup_names.append(tool.executable_name)
            
            # Fallback names based on tool name
            lookup_names.append(f"{tool.name}.exe")
            lookup_names.append(tool.name)

            common_roots = [
                os.environ.get('ProgramFiles', 'C:\\Program Files'),
                os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')
            ]

            for root in common_roots:
                if not os.path.exists(root): continue
                for name in lookup_names:
                    if not name.lower().endswith(".exe") and "." not in name:
                        name = f"{name}.exe"
                    
                    # Search ToolName folder first
                    potential_dir = os.path.join(root, tool.name)
                    if os.path.exists(os.path.join(potential_dir, name)):
                        tool.is_installed = True
                        return True
                    
                    # Then search all folders in root (one level deep)
                    try:
                        for item in os.listdir(root):
                            item_path = os.path.join(root, item)
                            if os.path.isdir(item_path):
                                if os.path.exists(os.path.join(item_path, name)):
                                    tool.is_installed = True
                                    return True
                    except: continue

            tool.is_installed = False
            return False
        except Exception as e:
            logger.error(f"Failed to check status for tool '{getattr(tool, 'name', tool)}': {e}")
            return False
