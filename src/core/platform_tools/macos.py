import subprocess
import logging
import sys
import os

from src.core.platform_tools.base import BasePlatformTools

logger = logging.getLogger(__name__)

class MacOSTools(BasePlatformTools):
    def flush_dns(self):
        """Flush the DNS resolver cache."""
        from src.utils.helpers import run_command
        try:
            # macOS DNS flush command varies by version, but dscacheutil is standard for recent ones
            proc = run_command(["sudo", "dscacheutil", "-flushcache"])
            run_command(["sudo", "killall", "-HUP", "mDNSResponder"])
            return True, "DNS cache flushed."
        except Exception as e:
            return False, str(e)

    def get_hosts_content(self):
        """Read the hosts file content."""
        hosts_path = "/etc/hosts"
        try:
            with open(hosts_path, "r", encoding="utf-8") as f:
                return True, f.read()
        except Exception as e:
            return False, str(e)

    def save_hosts_content(self, content):
        """Save the hosts file content."""
        import tempfile
        import os
        from src.utils.helpers import run_command
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                tf.write(content)
                temp_name = tf.name
            
            proc = run_command(["sudo", "mv", temp_name, "/etc/hosts"])
            if proc.returncode == 0:
                run_command(["sudo", "chmod", "644", "/etc/hosts"])
                return True, "Hosts file saved successfully."
            return False, proc.stderr
        except Exception as e:
            return False, str(e)

    def get_system_logs(self, lines=50):
        """Fetch the last N lines of system logs."""
        from src.utils.helpers import run_command
        try:
            proc = run_command(["log", "show", "--last", "1h", "--limit", str(lines)])
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            return False, str(e)

    def get_disk_usage(self):
        """Get disk usage summary (df -h)."""
        from src.utils.helpers import run_command
        try:
            proc = run_command(["df", "-h"])
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            return False, str(e)

    def toggle_gaming_mode(self, enable=True):
        """Optimize system for gaming (macOS Game Mode is automatic in Sonoma+)."""
        return False, "Game Mode on macOS is managed by the OS (Sonoma and later)."

    def manage_homebrew(self, action="list"):
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

    def run_maintenance_scripts(self):
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

    def scan_app_residue(self):
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

    def get_sip_status(self):
        """Check System Integrity Protection status."""
        if sys.platform != "darwin":
            return False, "Not on macOS."
            
        from src.utils.helpers import run_command
        try:
            proc = run_command(["csrutil", "status"])
            return proc.returncode == 0, proc.stdout
        except Exception as e:
            return False, str(e)
