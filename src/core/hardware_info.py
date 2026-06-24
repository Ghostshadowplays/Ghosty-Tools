import sys
import logging
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class HardwareInfo:
    @staticmethod
    def get_disk_health():
        """Get SMART-like data for disks."""
        if sys.platform == "win32":
            # Using wmic or powershell for basic disk health
            cmd = ["powershell", "-Command", "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, OperationalStatus, HealthStatus, Usage, Size"]
            proc = run_command(cmd)
            return proc.stdout
        elif sys.platform == "linux":
            # Requires smartmontools
            proc = run_command(["sudo", "smartctl", "--all", "/dev/sda"])
            return proc.stdout
        return "Not supported on this platform."

    @staticmethod
    def get_battery_info():
        """Get battery wear, cycle count, etc."""
        if sys.platform == "win32":
            # powercfg /batteryreport is good but it generates a file.
            # We can use WMIC for some info.
            cmd = ["powershell", "-Command", "Get-WmiObject -Class Win32_Battery | Select-Object DesignCapacity, FullChargeCapacity, EstimatedRunTime"]
            proc = run_command(cmd)
            return proc.stdout
        elif sys.platform == "darwin":
            proc = run_command(["system_profiler", "SPPowerDataType"])
            return proc.stdout
        return "Not supported on this platform."

    @staticmethod
    def get_ram_whea_errors():
        """Check for WHEA (Hardware Error) events related to RAM (Windows only)."""
        if sys.platform == "win32":
            cmd = ["powershell", "-Command", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'} -ErrorAction SilentlyContinue"]
            proc = run_command(cmd)
            if not proc.stdout:
                return "No WHEA errors found."
            return proc.stdout
        return "WHEA scan only available on Windows."
