import os
import subprocess
import logging
import sys
import re

try:
    import winreg
except ImportError:
    winreg = None

from src.core.platform_tools.base import BasePlatformTools

logger = logging.getLogger(__name__)

class WindowsTools(BasePlatformTools):
    @staticmethod
    def manage_context_menu(remove_items=None):
        """Placeholder for context menu management."""
        if winreg is None:
            return False, "Not on Windows or winreg not available."
        
        # Example: removing a specific shell extension or menu item
        # This requires careful registry manipulation.
        return True, "Context menu analysis complete (Feature in development)."

    def toggle_gaming_mode(self, enable=True):
        """Optimize system for gaming."""
        if sys.platform != "win32":
            return False, "Not on Windows."
        
        from src.utils.helpers import run_command
        results = []
        try:
            if enable:
                # Pause Windows Updates (simplified cmd)
                run_command(["powershell", "-Command", "Set-Service -Name wuauserv -StartupType Disabled"])
                results.append("Windows Update service disabled.")
            else:
                run_command(["powershell", "-Command", "Set-Service -Name wuauserv -StartupType Automatic"])
                results.append("Windows Update service restored.")
            
            return True, "\n".join(results)
        except Exception as e:
            logger.error(f"Error toggling gaming mode: {e}")
            return False, str(e)

    def get_hosts_content(self):
        """Read the hosts file content."""
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        try:
            if os.path.exists(hosts_path):
                with open(hosts_path, "r", encoding="utf-8", errors="replace") as f:
                    return True, f.read()
            return False, "Hosts file not found."
        except Exception as e:
            return False, str(e)

    def save_hosts_content(self, content):
        """Save the hosts file content."""
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        try:
            # Backup before saving if not already backed up this session
            backup_path = hosts_path + ".bak"
            if os.path.exists(hosts_path):
                import shutil
                shutil.copy2(hosts_path, backup_path)
            
            with open(hosts_path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            return True, "Hosts file saved successfully (backup created)."
        except Exception as e:
            logger.error(f"Error saving hosts file: {e}")
            return False, str(e)

    @staticmethod
    def edit_hosts_file(entries, action="add"):
        """Manage Windows hosts file entries programmatically."""
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        try:
            if action == "add":
                with open(hosts_path, "a", encoding="utf-8") as f:
                    for entry in entries:
                        f.write(f"\n127.0.0.1 {entry}")
                return True, f"Added {len(entries)} entries to hosts file."
            return False, "Action not implemented."
        except Exception as e:
            logger.error(f"Error editing hosts file: {e}")
            return False, str(e)

    @staticmethod
    def get_winget_apps():
        """List apps available via WinGet."""
        from src.utils.helpers import run_command
        try:
            # Using --source winget might be cleaner, but 'list' is what was requested.
            # We add a timeout and ensure we capture output.
            proc = run_command(["winget", "list"], timeout=15)
            if proc.returncode == 0:
                output = proc.stdout
                # Clean up progress bar/spinner artifacts that winget sometimes leaves in redirected output
                output = re.sub(r'[\-\|\\\/]\s*', '', output)
                # Remove common winget header junk if it exists
                if "Name" in output:
                    lines = output.splitlines()
                    start_idx = 0
                    for i, line in enumerate(lines):
                        if "Name" in line and "Id" in line:
                            start_idx = i
                            break
                    output = "\n".join(lines[start_idx:])
                return True, output
        except Exception as e:
            logger.error(f"Error calling winget: {e}")
        return False, "WinGet not available or failed to list apps."

    def flush_dns(self):
        """Flush the DNS resolver cache."""
        from src.utils.helpers import run_command
        try:
            proc = run_command(["ipconfig", "/flushdns"])
            return proc.returncode == 0, proc.stdout
        except Exception as e:
            return False, str(e)

    def get_system_logs(self, lines=50):
        """Fetch the last N lines of system logs using PowerShell."""
        from src.utils.helpers import run_command
        try:
            cmd = ["powershell", "-Command", f"Get-EventLog -LogName System -Newest {lines} | Select-Object -Property TimeGenerated, EntryType, Source, Message | Format-List"]
            proc = run_command(cmd)
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            logger.error(f"Error fetching system logs: {e}")
            return False, str(e)

    def get_disk_usage(self):
        """Get disk usage summary using wmic or powershell."""
        from src.utils.helpers import run_command
        try:
            cmd = ["powershell", "-Command", "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Used(GB)';E={'{0:N2}' -f ($_.Used/1GB)}}, @{N='Free(GB)';E={'{0:N2}' -f ($_.Free/1GB)}}, @{N='Total(GB)';E={'{0:N2}' -f (($_.Used+$_.Free)/1GB)}} | Format-Table"]
            proc = run_command(cmd)
            if proc.returncode == 0:
                return True, proc.stdout
            return False, proc.stderr
        except Exception as e:
            logger.error(f"Error fetching disk usage: {e}")
            return False, str(e)

    @staticmethod
    def clear_print_spooler():
        """Stop print spooler, clear cache, and restart it."""
        from src.utils.helpers import run_command
        try:
            run_command(["net", "stop", "spooler"])
            spool_path = r"C:\Windows\System32\spool\PRINTERS\*"
            run_command(["powershell", "-Command", f"Remove-Item -Path '{spool_path}' -Force -ErrorAction SilentlyContinue"])
            run_command(["net", "start", "spooler"])
            return True, "Print Spooler reset successfully."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def check_system_files():
        """Run SFC /verifyonly."""
        from src.utils.helpers import run_command
        try:
            # Note: verifyonly doesn't fix things, just checks. Safer for a quick tool.
            proc = run_command(["sfc", "/verifyonly"])
            return proc.returncode == 0, proc.stdout
        except Exception as e:
            return False, str(e)
