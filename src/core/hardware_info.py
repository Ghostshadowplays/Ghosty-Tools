import sys
import logging
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class HardwareInfo:
    @staticmethod
    def get_disk_health():
        """Get SMART-like data for disks."""
        if sys.platform == "win32":
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, OperationalStatus, HealthStatus, Usage, Size | Format-List"
            ]
            proc = run_command(cmd)
            result = proc.stdout.strip()
            return result if result else "No disk data returned. Administrator privileges may be required."
        elif sys.platform == "linux":
            import shutil
            if not shutil.which("smartctl"):
                return "smartmontools not installed. Run: sudo apt install smartmontools"
            # Try to detect drives dynamically
            import os
            drives = [f"/dev/{d}" for d in os.listdir("/dev") if d.startswith(("sd", "nvme", "hd"))]
            if not drives:
                drives = ["/dev/sda"]
            results = []
            for drive in drives[:3]:
                proc = run_command(["sudo", "smartctl", "-H", drive])
                if proc.stdout.strip():
                    results.append(f"=== {drive} ===\n{proc.stdout.strip()}")
            return "\n\n".join(results) if results else "Could not read SMART data."
        return "Not supported on this platform."

    @staticmethod
    def get_battery_info():
        """Get battery wear, cycle count, etc."""
        if sys.platform == "win32":
            # Get-CimInstance replaces the deprecated Get-WmiObject on modern Windows
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance -ClassName Win32_Battery | "
                "Select-Object Name, DesignCapacity, FullChargeCapacity, EstimatedRunTime, BatteryStatus | "
                "Format-List"
            ]
            proc = run_command(cmd)
            result = proc.stdout.strip()
            if not result:
                return "No battery detected or battery data unavailable."
            return result
        elif sys.platform == "darwin":
            proc = run_command(["system_profiler", "SPPowerDataType"])
            return proc.stdout.strip() or "No battery data available."
        elif sys.platform == "linux":
            import os
            bat_base = "/sys/class/power_supply"
            if not os.path.isdir(bat_base):
                return "No battery information found."
            batteries = [d for d in os.listdir(bat_base) if d.startswith("BAT")]
            if not batteries:
                return "No battery detected."
            lines = []
            for bat in batteries:
                bat_path = os.path.join(bat_base, bat)
                for key in ("capacity", "status", "energy_full", "energy_full_design", "cycle_count"):
                    fpath = os.path.join(bat_path, key)
                    if os.path.exists(fpath):
                        try:
                            with open(fpath) as f:
                                lines.append(f"{bat}/{key}: {f.read().strip()}")
                        except Exception:
                            pass
            return "\n".join(lines) if lines else "No battery data available."
        return "Not supported on this platform."

    @staticmethod
    def get_ram_whea_errors():
        """Check for WHEA (Hardware Error) events related to RAM (Windows only)."""
        if sys.platform == "win32":
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'} "
                "-MaxEvents 20 -ErrorAction SilentlyContinue | "
                "Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-List"
            ]
            proc = run_command(cmd)
            result = proc.stdout.strip()
            if not result:
                return "No WHEA hardware errors found."
            return result
        return "WHEA scan only available on Windows."
