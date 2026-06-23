import subprocess
import logging
import sys
import os

logger = logging.getLogger(__name__)

class MacOSTools:
    @staticmethod
    def manage_homebrew(action="list"):
        """Manage Homebrew casks and formulae."""
        if sys.platform != "darwin":
            return False, "Not on macOS."
            
        from src.utils.helpers import run_command
        try:
            if action == "list":
                proc = run_command(["brew", "list"])
                return True, proc.stdout
            elif action == "update":
                proc = run_command(["brew", "update"])
                return True, proc.stdout
        except Exception as e:
            logger.error(f"Error managing Homebrew: {e}")
            return False, str(e)

    @staticmethod
    def run_maintenance_scripts():
        """Trigger macOS periodic maintenance scripts."""
        if sys.platform != "darwin":
            return False, "Not on macOS."
            
        from src.utils.helpers import run_command
        try:
            proc = run_command(["sudo", "periodic", "daily", "weekly", "monthly"])
            if proc.returncode == 0:
                return True, "Maintenance scripts triggered successfully."
            return False, proc.stderr
        except Exception as e:
            logger.error(f"Error running maintenance scripts: {e}")
            return False, str(e)

    @staticmethod
    def scan_app_residue():
        """Scan for leftover files in Library folders."""
        if sys.platform != "darwin":
            return []
            
        home = os.path.expanduser("~")
        search_paths = [
            os.path.join(home, "Library", "Application Support"),
            os.path.join(home, "Library", "Caches"),
            os.path.join(home, "Library", "Preferences"),
            os.path.join(home, "Library", "Logs")
        ]
        
        # Simplified placeholder for residue scanning logic
        # In a real app, this would match against uninstalled app names
        return [p for p in search_paths if os.path.exists(p)]

    @staticmethod
    def get_sip_status():
        """Check System Integrity Protection status."""
        if sys.platform != "darwin":
            return False, "Not on macOS."
            
        from src.utils.helpers import run_command
        try:
            proc = run_command(["csrutil", "status"])
            return proc.returncode == 0, proc.stdout
        except Exception as e:
            return False, str(e)
