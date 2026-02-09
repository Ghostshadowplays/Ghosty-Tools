import os
import subprocess
import json
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple, Callable, Any

logger = logging.getLogger(__name__)

class BloatwareCategory(Enum):
    MICROSOFT_STORE_APPS = "Microsoft Store Apps"
    WINDOWS_FEATURES = "Windows Features"
    ONEDRIVE = "OneDrive"
    TELEMETRY = "Telemetry & Privacy"
    OEM_BLOATWARE = "OEM Bloatware"
    WINDOWS_SERVICES = "Windows Services"
    OPTIONAL_COMPONENTS = "Optional Components"

class SafetyLevel(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    RISKY = "risky"

class BloatwareItem:
    def __init__(self, item_id, name, description, category, safety_level, commands, 
                 check_command=None, requires_admin=True, requires_restart=False):
        self.id = item_id
        self.name = name
        self.description = description
        self.category = category
        self.safety_level = safety_level
        self.commands = commands
        self.check_command = check_command
        self.requires_admin = requires_admin
        self.requires_restart = requires_restart
        self.is_installed = False

class BloatRemover:
    def __init__(self, config_path=None):
        self.items = {}
        if config_path is None:
            # Assume it's in the project root/config/
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "bloatware_config.json")
        self.config_path = config_path
        self._load_config()
        
    def _load_config(self):
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"Bloatware config not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            category_mapping = {
                "Microsoft Store Apps": BloatwareCategory.MICROSOFT_STORE_APPS,
                "Windows Features": BloatwareCategory.WINDOWS_FEATURES,
                "OneDrive": BloatwareCategory.ONEDRIVE,
                "Telemetry And Privacy": BloatwareCategory.TELEMETRY,
                "OEM Bloatware": BloatwareCategory.OEM_BLOATWARE,
                "Windows Services": BloatwareCategory.WINDOWS_SERVICES,
                "Optional Components": BloatwareCategory.OPTIONAL_COMPONENTS,
            }
            
            for item_data in config.get("items", []):
                category = category_mapping.get(item_data["category"])
                if not category: continue
                
                item = BloatwareItem(
                    item_id=item_data["id"],
                    name=item_data["name"],
                    description=item_data["description"],
                    category=category,
                    safety_level=SafetyLevel[item_data["safety_level"].upper()],
                    commands=item_data["commands"],
                    check_command=item_data.get("check_command"),
                    requires_admin=item_data.get("requires_admin", True),
                    requires_restart=item_data.get("requires_restart", False)
                )
                self.items[item.id] = item
        except Exception as e:
            logger.error(f"Failed to load bloatware config: {e}")

    def execute_powershell(self, command, timeout=300):
        try:
            ps_command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
            result = subprocess.run(ps_command, capture_output=True, text=True, timeout=timeout, shell=False)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            return False, "", str(e)

    def scan_system(self, progress_callback=None):
        results = {}
        items = list(self.items.values())
        for i, item in enumerate(items):
            if progress_callback: progress_callback(int((i / len(items)) * 100), f"Checking {item.name}...")
            if not item.check_command:
                is_installed = True
            else:
                success, stdout, _ = self.execute_powershell(item.check_command)
                is_installed = success and bool(stdout.strip())
            results[item.id] = is_installed
            item.is_installed = is_installed
        if progress_callback: progress_callback(100, "Scan complete")
        return results

    def remove_items(self, item_ids, output_callback=None):
        """Standard removal method used by Ghosty Tools.py (in _run_bloat_removal)"""
        for item_id in item_ids:
            item = self.items.get(item_id)
            if not item: continue
            
            if output_callback: output_callback(f"Removing {item.name}...", "info")
            for cmd in item.commands:
                success, stdout, stderr = self.execute_powershell(cmd)
                if output_callback:
                    if success:
                        if stdout: output_callback(f"  ✓ {stdout}", "debug")
                    else:
                        output_callback(f"  ✗ {stderr}", "error")
        if output_callback: output_callback("Selected items removal process finished.", "success")
