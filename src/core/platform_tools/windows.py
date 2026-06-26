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
        """Optimize system for gaming with a comprehensive set of performance tweaks."""
        if sys.platform != "win32":
            return False, "Not on Windows."

        from src.utils.helpers import run_command
        results = []
        errors = []

        def reg_set(hive, key, name, reg_type, value):
            try:
                if winreg is None:
                    return
                k = winreg.CreateKey(hive, key)
                winreg.SetValueEx(k, name, 0, reg_type, value)
                winreg.CloseKey(k)
            except Exception as e:
                errors.append(f"Registry {key}\\{name}: {e}")

        def reg_delete(hive, key, name):
            try:
                if winreg is None:
                    return
                k = winreg.OpenKey(hive, key, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(k, name)
                winreg.CloseKey(k)
            except Exception:
                pass  # Key may not exist — that's fine

        def svc(name, startup):
            r = run_command(["powershell", "-NoProfile", "-Command",
                             f"Set-Service -Name '{name}' -StartupType {startup} -ErrorAction SilentlyContinue"])
            return r.returncode == 0

        HKLM = winreg.HKEY_LOCAL_MACHINE if winreg else None
        HKCU = winreg.HKEY_CURRENT_USER if winreg else None
        DWORD = winreg.REG_DWORD if winreg else None

        if enable:
            # 1. High Performance / Ultimate Performance power plan
            r = run_command(["powercfg", "-duplicatescheme", "e9a42b02-d5df-448d-aa00-03f14749eb61"])
            run_command(["powercfg", "-setactive", "e9a42b02-d5df-448d-aa00-03f14749eb61"])
            results.append("Power plan set to Ultimate Performance.")

            # 2. Disable Xbox Game Bar & Game DVR
            if HKCU and DWORD:
                reg_set(HKCU, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", DWORD, 0)
                reg_set(HKCU, r"System\GameConfigStore", "GameDVR_Enabled", DWORD, 0)
                reg_set(HKLM, r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", DWORD, 0)
            results.append("Xbox Game DVR / capture disabled.")

            # 3. Enable Windows Game Mode
            if HKCU and DWORD:
                reg_set(HKCU, r"Software\Microsoft\GameBar", "AutoGameModeEnabled", DWORD, 1)
                reg_set(HKCU, r"Software\Microsoft\GameBar", "ShowStartupPanel", DWORD, 0)
                reg_set(HKCU, r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", DWORD, 0)
            results.append("Windows Game Mode enabled.")

            # 4. Disable Nagle's algorithm (reduces network latency in games)
            try:
                ps_iface = (
                    "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | "
                    "Select-Object -ExpandProperty InterfaceIndex"
                )
                r2 = run_command(["powershell", "-NoProfile", "-Command", ps_iface])
                for idx in r2.stdout.strip().splitlines():
                    idx = idx.strip()
                    if idx:
                        iface_key = (
                            rf"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{{{idx}}}"
                        )
                        # TcpAckFrequency=1 and TCPNoDelay=1 disable Nagle
                        reg_set(HKLM, iface_key, "TcpAckFrequency", DWORD, 1)
                        reg_set(HKLM, iface_key, "TCPNoDelay", DWORD, 1)
                results.append("Nagle's algorithm disabled (lower network latency).")
            except Exception as e:
                errors.append(f"Nagle tweak: {e}")

            # 5. Set GPU preference to high performance for all apps
            if HKCU and DWORD:
                reg_set(HKCU,
                        r"Software\Microsoft\DirectX\UserGpuPreferences",
                        "DirectXUserGlobalSettings",
                        winreg.REG_SZ,
                        "SwapEffectUpgradeEnable=1;")
            results.append("GPU preference set to high performance.")

            # 6. Disable fullscreen optimizations globally
            if HKCU and DWORD:
                reg_set(HKCU, r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", DWORD, 2)
                reg_set(HKCU, r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", DWORD, 1)
                reg_set(HKCU, r"System\GameConfigStore", "GameDVR_FSEBehavior", DWORD, 2)
            results.append("Fullscreen optimizations disabled.")

            # 7. Disable SysMain (Superfetch) — reduces background I/O during gaming
            if svc("SysMain", "Disabled"):
                results.append("SysMain (Superfetch) disabled.")

            # 8. Pause Windows Update service
            if svc("wuauserv", "Disabled"):
                results.append("Windows Update service paused.")

            # 9. Set MMCSS (Multimedia Class Scheduler) for games
            if HKLM and DWORD:
                reg_set(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
                        "GPU Priority", DWORD, 8)
                reg_set(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
                        "Priority", DWORD, 6)
                reg_set(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
                        "Scheduling Category", winreg.REG_SZ, "High")
            results.append("MMCSS game thread priority raised.")

        else:
            # Restore defaults
            run_command(["powercfg", "-setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"])
            results.append("Power plan restored to Balanced.")

            if HKCU and DWORD:
                reg_delete(HKCU, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled")
                reg_delete(HKCU, r"System\GameConfigStore", "GameDVR_Enabled")
            results.append("Game DVR settings restored.")

            if svc("SysMain", "Automatic"):
                results.append("SysMain (Superfetch) re-enabled.")
            if svc("wuauserv", "Automatic"):
                results.append("Windows Update service restored.")

        summary = "\n".join(results)
        if errors:
            summary += "\n\nWarnings:\n" + "\n".join(errors)
        return True, summary

    @staticmethod
    def get_hosts_content():
        """Read the hosts file content."""
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        try:
            if os.path.exists(hosts_path):
                with open(hosts_path, "r", encoding="utf-8", errors="replace") as f:
                    return True, f.read()
            return False, "Hosts file not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def save_hosts_content(content):
        """Save the hosts file content."""
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        try:
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
