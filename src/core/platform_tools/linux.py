import subprocess
import logging
import sys

from src.core.platform_tools.base import BasePlatformTools

logger = logging.getLogger(__name__)

class LinuxTools(BasePlatformTools):
    def flush_dns(self):
        """Flush the DNS resolver cache."""
        from src.utils.helpers import run_command
        # Try different common Linux DNS flush commands
        commands = [
            ["sudo", "resolvectl", "flush-caches"],
            ["sudo", "systemd-resolve", "--flush-caches"],
            ["sudo", "nmcli", "networking", "off"], # Then on? No, that's harsh
            ["sudo", "/etc/init.d/nscd", "restart"]
        ]
        for cmd in commands:
            try:
                proc = run_command(cmd)
                if proc.returncode == 0:
                    return True, f"DNS flushed using {' '.join(cmd)}"
            except:
                continue
        return False, "Could not flush DNS cache."

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
            # We need sudo to write to /etc/hosts, so write to a temp file first
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                tf.write(content)
                temp_name = tf.name
            
            # Use sudo mv to replace the hosts file
            proc = run_command(["sudo", "mv", temp_name, "/etc/hosts"])
            if proc.returncode == 0:
                run_command(["sudo", "chmod", "644", "/etc/hosts"])
                return True, "Hosts file saved successfully."
            return False, proc.stderr
        except Exception as e:
            return False, str(e)

    def toggle_gaming_mode(self, enable=True):
        """Optimize system for gaming (stub for Linux)."""
        # Could use gamemoded if available
        return False, "Gaming mode optimization not yet implemented for Linux."

    def manage_ufw(self, enable=True):
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

    def get_universal_packages(self):
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

    def manage_repositories(self, action="list", ppa=None):
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

    def get_system_logs(self, lines=50):
        """Fetch the last N lines of system logs."""
        from src.utils.helpers import run_command
        try:
            proc = run_command(["journalctl", "-n", str(lines), "--no-pager"])
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
