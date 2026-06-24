import psutil
import logging
import sys

logger = logging.getLogger(__name__)

class TaskManager:
    PROCESS_DB = {
        "explorer.exe": "Windows Explorer - Desktop and file management.",
        "svchost.exe": "Service Host - A system process that hosts multiple Windows services.",
        "chrome.exe": "Google Chrome - Web browser.",
        "msedge.exe": "Microsoft Edge - Web browser.",
        "taskmgr.exe": "Task Manager - System monitoring utility.",
        "lsass.exe": "Local Security Authority Subsystem Service - Handles security policy.",
        "wininit.exe": "Windows Initialization - Starts services and other processes.",
        "csrss.exe": "Client Server Runtime Process - Handles console windows and process creation.",
        "Ghosty Tools.exe": "Ghosty Tools - Your favorite optimization suite."
    }

    @staticmethod
    def get_process_info(pid):
        """Get detailed info for a process including safety indicator."""
        try:
            proc = psutil.Process(pid)
            info = proc.as_dict(attrs=['pid', 'name', 'username', 'exe', 'cpu_percent', 'memory_percent', 'status'])
            
            # Safety Indicator
            name = info['name'].lower()
            if name in ["svchost.exe", "lsass.exe", "wininit.exe", "csrss.exe", "services.exe"]:
                info['safety'] = "System (Trusted)"
            elif name in TaskManager.PROCESS_DB:
                info['safety'] = "Trusted"
            else:
                info['safety'] = "Unknown"
            
            info['description'] = TaskManager.PROCESS_DB.get(info['name'], "No description available.")
            return info
        except:
            return None

    @staticmethod
    def get_gpu_usage():
        """Get GPU usage (Windows/Linux)."""
        if sys.platform == "win32":
            from src.utils.helpers import run_command
            cmd = ["powershell", "-Command", "Get-WmiObject Win32_VideoController | Select-Object Name, VideoProcessor, AdapterRAM"]
            return run_command(cmd).stdout
        elif sys.platform == "linux":
            from src.utils.helpers import run_command
            return run_command(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv"]).stdout
        return "GPU monitoring not supported."

    @staticmethod
    def get_resource_hogs(count=10):
        """Get top N processes by CPU and Memory usage."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Sort by CPU and then Memory
        cpu_hogs = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:count]
        mem_hogs = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:count]
        
        return {
            "cpu": cpu_hogs,
            "memory": mem_hogs
        }

    @staticmethod
    def kill_process(pid):
        """Kill a process by PID."""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            return True, f"Process {pid} terminated."
        except Exception as e:
            logger.error(f"Failed to kill process {pid}: {e}")
            return False, str(e)
