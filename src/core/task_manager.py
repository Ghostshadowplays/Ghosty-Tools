import psutil
import logging

logger = logging.getLogger(__name__)

class TaskManager:
    @staticmethod
    def get_resource_hogs(count=5):
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
