import sys
import logging
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class ServicesManager:
    SERVICE_INFO = {
        "SysMain": {"desc": "Superfetch - Prefetches apps into RAM. Safe to disable for SSDs.", "safe": True},
        "wuauserv": {"desc": "Windows Update - Handles system updates.", "safe": False},
        "PrintSpooler": {"desc": "Handles print jobs. Safe to disable if not printing.", "safe": True},
        "DiagTrack": {"desc": "Telemetry - Sends usage data to Microsoft. Safe to disable.", "safe": True},
        "XblAuthManager": {"desc": "Xbox Live Auth - Required for Xbox apps.", "safe": True}
    }

    @staticmethod
    def get_services():
        """List all services and their status."""
        if sys.platform == "win32":
            cmd = ["powershell", "-Command", "Get-Service | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json"]
            proc = run_command(cmd)
            import json
            try:
                services = json.loads(proc.stdout)
                for s in services:
                    s['info'] = ServicesManager.SERVICE_INFO.get(s['Name'], {"desc": "No info available.", "safe": False})
                return services
            except:
                return []
        elif sys.platform == "linux":
            # systemctl
            proc = run_command(["systemctl", "list-units", "--type=service", "--all"])
            return proc.stdout
        return []

    @staticmethod
    def manage_service(name, action):
        """Action: start, stop, enable, disable."""
        if sys.platform == "win32":
            cmd_map = {
                "start": ["powershell", "-Command", f"Start-Service -Name {name}"],
                "stop": ["powershell", "-Command", f"Stop-Service -Name {name}"],
                "enable": ["powershell", "-Command", f"Set-Service -Name {name} -StartupType Automatic"],
                "disable": ["powershell", "-Command", f"Set-Service -Name {name} -StartupType Disabled"]
            }
            if action in cmd_map:
                proc = run_command(cmd_map[action])
                return proc.returncode == 0, proc.stdout if proc.returncode == 0 else proc.stderr
        elif sys.platform == "linux":
            proc = run_command(["sudo", "systemctl", action, name])
            return proc.returncode == 0, proc.stdout
        return False, "Not supported."
