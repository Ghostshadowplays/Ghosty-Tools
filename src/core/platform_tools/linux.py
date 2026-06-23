import subprocess
import logging
import sys

logger = logging.getLogger(__name__)

class LinuxTools:
    @staticmethod
    def manage_ufw(enable=True):
        """Enable or disable UFW firewall."""
        if sys.platform != "linux":
            return False, "Not on Linux."
        
        from src.utils.helpers import run_command
        try:
            cmd = ["sudo", "ufw", "enable"] if enable else ["sudo", "ufw", "disable"]
            proc = run_command(cmd)
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            logger.error(f"Error managing UFW: {e}")
            return False, str(e)

    @staticmethod
    def get_universal_packages():
        """Check for Flatpak and Snap packages."""
        from src.utils.helpers import run_command
        results = {"flatpak": [], "snap": []}
        try:
            # Flatpak
            proc = run_command(["flatpak", "list"])
            if proc.returncode == 0:
                results["flatpak"] = proc.stdout.splitlines()
            
            # Snap
            proc = run_command(["snap", "list"])
            if proc.returncode == 0:
                results["snap"] = proc.stdout.splitlines()
        except Exception as e:
            logger.error(f"Error checking universal packages: {e}")
            
        return results

    @staticmethod
    def manage_repositories(action="list", ppa=None):
        """Manage PPAs and repositories."""
        if sys.platform != "linux":
            return False, "Not on Linux."
            
        from src.utils.helpers import run_command
        try:
            if action == "list":
                proc = run_command(["ls", "/etc/apt/sources.list.d/"])
                return True, proc.stdout
            elif action == "add" and ppa:
                proc = run_command(["sudo", "add-apt-repository", "-y", ppa])
                return True, proc.stdout
        except Exception as e:
            logger.error(f"Error managing repositories: {e}")
            return False, str(e)

    @staticmethod
    def get_system_logs(lines=50):
        """Fetch the last N lines of system logs."""
        from src.utils.helpers import run_command
        try:
            proc = run_command(["journalctl", "-n", str(lines), "--no-pager"])
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_disk_usage():
        """Get disk usage summary (df -h)."""
        from src.utils.helpers import run_command
        try:
            proc = run_command(["df", "-h"])
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            return False, str(e)
