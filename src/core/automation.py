import os
import sys
import logging
import time
import psutil
import threading
from datetime import datetime
from src.utils.helpers import run_command, get_config_dir

logger = logging.getLogger(__name__)

class Automation:
    def __init__(self):
        self.running = False

    def start_health_agent(self, callback):
        """Monitor system health in background."""
        self.running = True
        threading.Thread(target=self._health_loop, args=(callback,), daemon=True).start()

    def _health_loop(self, callback):
        while self.running:
            # 1. Check RAM
            ram = psutil.virtual_memory()
            if ram.percent > 90:
                callback("RAM Usage Alert", f"RAM usage is critical: {ram.percent}%")
            
            # 2. Check Uptime
            uptime_seconds = time.time() - psutil.boot_time()
            if uptime_seconds > 14 * 24 * 3600:
                callback("Uptime Alert", "System has been running for over 14 days. Consider a restart.")
            
            time.sleep(300) # Check every 5 minutes

    @staticmethod
    def generate_system_report():
        """Generate a comprehensive system report."""
        report = []
        report.append(f"GhostyTools System Report - {datetime.now()}")
        report.append("="*40)
        
        # OS Info
        import platform
        report.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
        report.append(f"Machine: {platform.machine()}")
        
        # Hardware
        report.append("\nHardware Summary:")
        report.append(f"CPU Cores: {psutil.cpu_count(logical=True)}")
        report.append(f"Total RAM: {psutil.virtual_memory().total / (1024**3):.2f} GB")
        
        # Drivers (Windows only)
        if sys.platform == "win32":
            report.append("\nDriver List (Top 10):")
            proc = run_command([
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "Get-CimInstance Win32_PnPSignedDriver | "
                "Where-Object { $_.DeviceName } | "
                "Sort-Object DeviceName | "
                "Select-Object -First 10 DeviceName,DriverVersion,Manufacturer | "
                "Format-Table -AutoSize | Out-String | Write-Host"
            ])
            driver_lines = [l for l in proc.stdout.splitlines() if l.strip()]
            report.append("\n".join(driver_lines) if driver_lines else "  (No driver data available)")
            
        return "\n".join(report)

    @staticmethod
    def schedule_maintenance():
        """Perform weekly maintenance tasks."""
        from src.core.cleanup_engine import CleanupEngine
        from src.core.dns_manager import DNSManager
        
        engine = CleanupEngine()
        engine.clean_shader_cache()
        engine.clean_launcher_caches()
        DNSManager.flush_dns()
        
        logger.info("Auto-maintenance task completed.")
