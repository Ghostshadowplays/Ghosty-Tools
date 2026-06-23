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
        else:
            issues.append(self._check_linux_firewall())
            issues.append(self._check_ssh_status())
            issues.append(self._check_root_login())
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

