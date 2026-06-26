import subprocess
import sys
import os

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

class SecurityScanner:
    def get_report(self):
        issues = []
        if sys.platform == 'win32':
            issues.append(self._check_windows_defender())
            issues.append(self._check_firewall())
            issues.append(self._check_uac())
            issues.append(self._check_smbv1())
            issues.append(self._check_shares())
            issues.append(self._check_rdp())
            issues.append(self._check_windows_update_enabled())
            issues.append(self._check_autorun_entries())
            issues.append(self._check_bitlocker())
            issues.append(self._check_guest_account())
            issues.append(self._check_open_ports())
        else:
            issues.append(self._check_linux_firewall())
            issues.append(self._check_ssh_status())
            issues.append(self._check_root_login())
            issues.append(self._check_sudo_nopasswd())
            issues.append(self._check_world_writable())
        return issues

    def _check_linux_firewall(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["ufw", "status"])
            if "inactive" in res.stdout.lower():
                return "UFW Firewall is Inactive", "High"
            return "UFW Firewall is Active", "Low"
        except: return "ufw firewall not found", "Medium"

    def _check_ssh_status(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["systemctl", "is-active", "ssh"])
            if "active" in res.stdout.lower():
                return "SSH Service is Active (Ensure it's needed)", "Medium"
            return "SSH Service is Inactive", "Low"
        except: return "SSH service not found", "Low"

    def _check_root_login(self):
        try:
            if os.path.exists("/etc/ssh/sshd_config"):
                with open("/etc/ssh/sshd_config", "r") as f:
                    content = f.read()
                    if "PermitRootLogin yes" in content:
                        return "SSH Root Login is Enabled", "High"
            return "SSH Root Login is Disabled/Default", "Low"
        except: return "Could not check SSH config", "Low"

    def _check_windows_defender(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = 'Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled'
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            if "False" in res.stdout:
                return "Defender Disabled or Real-time Protection Off", "High"
            return "Defender Enabled", "Low"
        except: return "Error checking Defender", "Medium"

    def _check_firewall(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["netsh", "advfirewall", "show", "allprofiles", "state"])
            if "OFF" in res.stdout.upper():
                return "Firewall Disabled on some profiles", "Critical"
            return "Firewall Enabled", "Low"
        except: return "Error checking Firewall", "Medium"

    def _check_uac(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = "(Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System).EnableLUA"
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            if "0" in res.stdout:
                return "UAC Disabled", "High"
            return "UAC Enabled", "Low"
        except: return "Error checking UAC", "Medium"

    def _check_smbv1(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = "(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State"
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            if "Enabled" in res.stdout:
                return "SMBv1 Enabled (Security Risk)", "High"
            return "SMBv1 Disabled", "Low"
        except: return "Error checking SMBv1", "Low"

    def _check_shares(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["net", "share"])
            shares = [line for line in res.stdout.split('\n') if line and not line.startswith(('Share name', '----------', 'The command completed')) and '$' not in line]
            if shares:
                return f"{len(shares)} Active Network Shares", "Low"
            return "No Active Network Shares", "Low"
        except: return "Error checking Shares", "Low"

    def _check_rdp(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SYSTEM\CurrentControlSet\Control\Terminal Server")
            val, _ = winreg.QueryValueEx(key, "fDenyTSConnections")
            winreg.CloseKey(key)
            if val == 0:
                return "Remote Desktop (RDP) is Enabled", "Medium"
            return "Remote Desktop (RDP) is Disabled", "Low"
        except Exception:
            return "Could not check RDP status", "Low"

    def _check_windows_update_enabled(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU")
            val, _ = winreg.QueryValueEx(key, "NoAutoUpdate")
            winreg.CloseKey(key)
            if val == 1:
                return "Windows Automatic Updates Disabled via Policy", "High"
            return "Windows Automatic Updates Active", "Low"
        except FileNotFoundError:
            return "Windows Automatic Updates Active (default)", "Low"
        except Exception:
            return "Could not check Windows Update policy", "Low"

    def _check_autorun_entries(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = (
                "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run' "
                "| Select-Object * -ExcludeProperty PS* | ConvertTo-Json -Compress"
            )
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            import json
            data = json.loads(res.stdout.strip()) if res.stdout.strip() else {}
            count = len(data)
            if count > 10:
                return f"{count} startup autorun entries detected (review recommended)", "Medium"
            return f"{count} startup autorun entries (normal range)", "Low"
        except Exception:
            return "Could not enumerate autorun entries", "Low"

    def _check_bitlocker(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = "Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProtectionStatus"
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            output = res.stdout.strip()
            if "On" in output or output == "1":
                return "BitLocker Encryption is Active on System Drive", "Low"
            return "BitLocker Not Active on System Drive", "Medium"
        except Exception:
            return "Could not check BitLocker status", "Low"

    def _check_guest_account(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["net", "user", "Guest"])
            if "Account active" in res.stdout and "Yes" in res.stdout:
                return "Guest Account is Enabled", "High"
            return "Guest Account is Disabled", "Low"
        except Exception:
            return "Could not check Guest account", "Low"

    def _check_open_ports(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = (
                "Get-NetTCPConnection -State Listen | "
                "Where-Object { $_.LocalAddress -eq '0.0.0.0' } | "
                "Select-Object -ExpandProperty LocalPort | Sort-Object -Unique"
            )
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            ports = [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]
            risky = [p for p in ports if p in ["23", "21", "3389", "5900", "4444", "1433", "3306"]]
            if risky:
                return f"Risky ports open: {', '.join(risky)}", "High"
            if len(ports) > 15:
                return f"{len(ports)} ports listening (review recommended)", "Medium"
            return f"{len(ports)} ports listening (normal)", "Low"
        except Exception:
            return "Could not enumerate open ports", "Low"

    def _check_sudo_nopasswd(self):
        try:
            sudoers_files = ["/etc/sudoers"]
            sudoers_dir = "/etc/sudoers.d"
            if os.path.isdir(sudoers_dir):
                sudoers_files += [os.path.join(sudoers_dir, f) for f in os.listdir(sudoers_dir)]
            for fpath in sudoers_files:
                try:
                    with open(fpath, "r") as f:
                        content = f.read()
                    if "NOPASSWD" in content:
                        return "sudo NOPASSWD rule detected in sudoers", "High"
                except PermissionError:
                    pass
            return "No sudo NOPASSWD rules found", "Low"
        except Exception:
            return "Could not check sudoers configuration", "Low"

    def _check_world_writable(self):
        try:
            import stat
            sensitive_dirs = ["/etc", "/usr/bin", "/usr/sbin"]
            for d in sensitive_dirs:
                if os.path.isdir(d):
                    mode = os.stat(d).st_mode
                    if mode & stat.S_IWOTH:
                        return f"World-writable sensitive directory: {d}", "Critical"
            return "No world-writable sensitive directories found", "Low"
        except Exception:
            return "Could not check directory permissions", "Low"

