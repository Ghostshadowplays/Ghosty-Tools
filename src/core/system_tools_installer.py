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
        self.detected_winget_id = None

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
        self._winget_installed_cache = {}
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
        tool.detected_winget_id = None
        if sys.platform != 'win32':
            try:
                # On Linux, try 'which' or 'command -v'
                exec_name = tool.executable_name or tool.name.lower().replace(" ", "-")
                if exec_name.endswith(".exe"): exec_name = exec_name[:-4]
                
                from src.utils.helpers import run_command
                res = run_command(["which", exec_name])
                if res.returncode == 0:
                    tool.is_installed = True
                    return True
                
                # Check for common linux names
                for alt in [tool.name.lower(), tool.name.lower().replace(" ", "")]:
                    if run_command(["which", alt]).returncode == 0:
                        tool.is_installed = True
                        return True
            except: pass
            
            tool.is_installed = False
            return False
        from src.utils.helpers import run_command
        try:
            # 1. Try defined check_command
            # Optimization: If it's a winget check, use the cache
            if "winget" in tool.check_command.lower() and tool.winget_id:
                # Try finding by ID first
                if tool.winget_id.lower() in self._winget_installed_cache:
                    tool.detected_winget_id = self._winget_installed_cache[tool.winget_id.lower()]
                    tool.is_installed = True
                    return True
                # Fallback to finding by tool name in cache
                if tool.name.lower() in self._winget_installed_cache:
                    tool.detected_winget_id = self._winget_installed_cache[tool.name.lower()]
                    tool.is_installed = True
                    return True
                
                # If it's explicitly a winget check and NOT in cache, we can skip the slow process call
                if "winget list --id" in tool.check_command:
                    # Fall through to step 3 (file check) as winget might not have it but it might still be there
                    pass
                else:
                    ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", tool.check_command]
                    result = run_command(ps_cmd, timeout=30)
                    if result.returncode == 0:
                        tool.is_installed = True
                        return True
            else:
                ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", tool.check_command]
                result = run_command(ps_cmd, timeout=30)
                if result.returncode == 0:
                    tool.is_installed = True
                    return True

            # 2. Try winget list if ID is available (use cache)
            if tool.winget_id:
                low_id = tool.winget_id.lower()
                low_name = tool.name.lower()
                
                # Check ID directly
                if low_id in self._winget_installed_cache:
                    tool.detected_winget_id = self._winget_installed_cache[low_id]
                    tool.is_installed = True
                    return True
                
                # Check Name directly
                if low_name in self._winget_installed_cache:
                    tool.detected_winget_id = self._winget_installed_cache[low_name]
                    tool.is_installed = True
                    return True
                
                # Try common variations (e.g. "Teams" -> "Microsoft Teams")
                variations = [
                    f"microsoft {low_name}",
                    f"google {low_name}",
                    f"mozilla {low_name}",
                    f"{low_name} desktop",
                    f"{low_name} client"
                ]
                for var in variations:
                    if var in self._winget_installed_cache:
                        tool.detected_winget_id = self._winget_installed_cache[var]
                        tool.is_installed = True
                        return True
                
                # Last resort: substring match if tool.name is long enough
                if len(low_name) >= 4:
                    for cache_key, actual_id in self._winget_installed_cache.items():
                        if low_name in cache_key:
                            # Verify it's not a different tool (e.g. "Teams" matching "TeamSpeak")
                            # We check if it's a word boundary or a common prefix
                            if f" {low_name}" in f" {cache_key}":
                                tool.detected_winget_id = actual_id
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

    def refresh_installed_cache(self):
        """Pre-fetch all installed winget app IDs to avoid repeated slow calls."""
        if sys.platform != 'win32': return
        
        from src.utils.helpers import run_command
        try:
            # We use a longer timeout for the initial bulk list
            proc = run_command(["winget", "list"], timeout=60)
            if proc.returncode == 0:
                self._winget_installed_cache = self._parse_winget_ids(proc.stdout)
                logger.info(f"Refreshed winget cache: {len(self._winget_installed_cache)} entries mapped.")
            else:
                self._winget_installed_cache = {}
        except Exception as e:
            logger.error(f"Error refreshing winget cache: {e}")
            self._winget_installed_cache = {}

    def _parse_winget_ids(self, output):
        """Extract mapping of Name/ID -> Actual ID from winget list output."""
        mapping = {}
        if not output: return mapping
        
        lines = output.splitlines()
        header_line = ""
        for line in lines:
            if "Name" in line and "Id" in line:
                header_line = line
                break
        
        if not header_line: return mapping

        name_pos = header_line.find("Name")
        id_pos = header_line.find("Id")
        version_pos = header_line.find("Version")
        
        for line in lines:
            if line == header_line or line.startswith("---") or not line.strip():
                continue
            
            if len(line) > id_pos:
                # Extract ID
                if version_pos > id_pos:
                    id_val = line[id_pos:version_pos].strip()
                else:
                    id_val = line[id_pos:].strip().split()[0]
                
                if not id_val or id_val.startswith("[") or id_val == "Id":
                    continue
                
                # Extract Name
                name_val = line[name_pos:id_pos].strip()
                
                # Store in mapping
                mapping[id_val.lower()] = id_val
                if name_val:
                    mapping[name_val.lower()] = id_val
        return mapping
