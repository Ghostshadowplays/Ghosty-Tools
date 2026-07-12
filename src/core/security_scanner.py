import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)
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
                return "UFW Firewall is Inactive", "High", "enable_ufw"
            return "UFW Firewall is Active", "Low", None
        except Exception as e:
            logger.debug(f"linux_firewall check failed: {e}")
            return "ufw firewall not found", "Medium", None

    def _check_ssh_status(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["systemctl", "is-active", "ssh"])
            if "active" in res.stdout.lower():
                return "SSH Service is Active (Ensure it's needed)", "Medium", None
            return "SSH Service is Inactive", "Low", None
        except Exception as e:
            logger.debug(f"ssh_status check failed: {e}")
            return "SSH service not found", "Low", None

    def _check_root_login(self):
        try:
            if os.path.exists("/etc/ssh/sshd_config"):
                with open("/etc/ssh/sshd_config", "r") as f:
                    content = f.read()
                    if "PermitRootLogin yes" in content:
                        return "SSH Root Login is Enabled", "High", None
            return "SSH Root Login is Disabled/Default", "Low", None
        except Exception as e:
            logger.debug(f"root_login check failed: {e}")
            return "Could not check SSH config", "Low", None

    def _check_windows_defender(self):
        from src.utils.helpers import run_command
        try:
            # AMRunningMode is the most reliable signal on Windows 10/11.
            #   Normal  = Defender is the active AV, fully protecting the system.
            #   Passive = A third-party AV is primary; Defender runs alongside.
            # Individual flags like RealTimeProtectionEnabled can be misleading
            # when Tamper Protection or a management policy is in place.
            ps_cmd = (
                "$mp = Get-MpComputerStatus -ErrorAction SilentlyContinue; "
                "if (-not $mp) { 'ERROR' } "
                "else { "
                "  $mode = $mp.AMRunningMode; "
                "  $tamper = $mp.IsTamperProtected; "
                "  $avList = Get-CimInstance -Namespace root\\SecurityCenter2 "
                "    -ClassName AntiVirusProduct -ErrorAction SilentlyContinue; "
                "  $third = ($avList | Where-Object { $_.displayName -notlike '*Windows Defender*' } "
                "    | Select-Object -First 1 -ExpandProperty displayName); "
                "  if ($mode -eq 'Normal') { 'OK' } "
                "  elseif ($mode -like '*Passive*') { 'PASSIVE:' + $third } "
                "  elseif ($mp.RealTimeProtectionEnabled -eq $true) { 'OK' } "
                "  else { 'DISABLED:' + $tamper } "
                "}"
            )
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            output = res.stdout.strip()
            if output == "OK":
                return "Windows Defender & Real-time Protection Enabled", "Low", None
            elif output.startswith("PASSIVE:"):
                av_name = output.split(":", 1)[1].strip() or "Third-party AV"
                return f"Defender passive — protected by {av_name}", "Low", None
            elif output.startswith("DISABLED:"):
                tamper_on = output.split(":", 1)[1].strip().lower() == "true"
                action = "tamper_protected" if tamper_on else "enable_defender_rt"
                return "Defender Real-time Protection is Off", "High", action
            else:
                return "Could not verify Defender status", "Medium", None
        except Exception as e:
            logger.warning(f"Defender check failed: {e}")
            return "Error checking Defender", "Medium", None

    def _check_firewall(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["netsh", "advfirewall", "show", "allprofiles", "state"])
            if "OFF" in res.stdout.upper():
                return "Firewall Disabled on some profiles", "Critical", "enable_firewall"
            return "Firewall Enabled on all profiles", "Low", None
        except Exception as e:
            logger.warning(f"Firewall check failed: {e}")
            return "Error checking Firewall", "Medium", None

    def _check_uac(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = "(Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System).EnableLUA"
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            if res.stdout.strip() == "0":
                return "UAC Disabled", "High", "enable_uac"
            return "UAC Enabled", "Low", None
        except Exception as e:
            logger.warning(f"UAC check failed: {e}")
            return "Error checking UAC", "Medium", None

    def _check_smbv1(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = "(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State"
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            if "Enabled" in res.stdout:
                return "SMBv1 Enabled (Security Risk)", "High", "disable_smbv1"
            return "SMBv1 Disabled", "Low", None
        except Exception as e:
            logger.debug(f"SMBv1 check failed: {e}")
            return "Error checking SMBv1", "Low", None

    def _check_shares(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["net", "share"])
            shares = [line for line in res.stdout.split('\n') if line and not line.startswith(('Share name', '----------', 'The command completed')) and '$' not in line]
            if shares:
                return f"{len(shares)} Active Network Shares", "Low", None
            return "No Active Network Shares", "Low", None
        except Exception as e:
            logger.debug(f"Shares check failed: {e}")
            return "Error checking Shares", "Low", None

    def _check_rdp(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SYSTEM\CurrentControlSet\Control\Terminal Server")
            val, _ = winreg.QueryValueEx(key, "fDenyTSConnections")
            winreg.CloseKey(key)
            if val == 0:
                return "Remote Desktop (RDP) is Enabled", "Medium", "disable_rdp"
            return "Remote Desktop (RDP) is Disabled", "Low", "enable_rdp"
        except Exception as e:
            logger.debug(f"RDP check failed: {e}")
            return "Could not check RDP status", "Low", None

    def _check_windows_update_enabled(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU")
            val, _ = winreg.QueryValueEx(key, "NoAutoUpdate")
            winreg.CloseKey(key)
            if val == 1:
                return "Windows Automatic Updates Disabled via Policy", "High", "enable_windows_update"
            return "Windows Automatic Updates Active", "Low", None
        except FileNotFoundError:
            return "Windows Automatic Updates Active (default)", "Low", None
        except Exception as e:
            logger.debug(f"WU check failed: {e}")
            return "Could not check Windows Update policy", "Low", None

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
                return f"{count} startup autorun entries detected (review recommended)", "Medium", None
            return f"{count} startup autorun entries (normal range)", "Low", None
        except Exception as e:
            logger.debug(f"Autorun check failed: {e}")
            return "Could not enumerate autorun entries", "Low", None

    def _check_bitlocker(self):
        from src.utils.helpers import run_command
        try:
            ps_cmd = "Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProtectionStatus"
            res = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
            output = res.stdout.strip()
            if "On" in output or output == "1":
                return "BitLocker Encryption is Active on System Drive", "Low", None
            return "BitLocker Not Active on System Drive", "Medium", None
        except Exception as e:
            logger.debug(f"BitLocker check failed: {e}")
            return "Could not check BitLocker status", "Low", None

    def _check_guest_account(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["net", "user", "Guest"])
            if "Account active" in res.stdout and "Yes" in res.stdout:
                return "Guest Account is Enabled", "High", "disable_guest"
            return "Guest Account is Disabled", "Low", None
        except Exception as e:
            logger.debug(f"Guest account check failed: {e}")
            return "Could not check Guest account", "Low", None

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
                return f"Risky ports open: {', '.join(risky)}", "High", None
            if len(ports) > 15:
                return f"{len(ports)} ports listening (review recommended)", "Medium", None
            return f"{len(ports)} ports listening (normal)", "Low", None
        except Exception as e:
            logger.debug(f"Open ports check failed: {e}")
            return "Could not enumerate open ports", "Low", None

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
                        return "sudo NOPASSWD rule detected in sudoers", "High", None
                except PermissionError:
                    pass
            return "No sudo NOPASSWD rules found", "Low", None
        except Exception as e:
            logger.debug(f"sudoers check failed: {e}")
            return "Could not check sudoers configuration", "Low", None

    def _check_world_writable(self):
        try:
            import stat
            sensitive_dirs = ["/etc", "/usr/bin", "/usr/sbin"]
            for d in sensitive_dirs:
                if os.path.isdir(d):
                    mode = os.stat(d).st_mode
                    if mode & stat.S_IWOTH:
                        return f"World-writable sensitive directory: {d}", "Critical", None
            return "No world-writable sensitive directories found", "Low", None
        except Exception as e:
            logger.debug(f"World-writable check failed: {e}")
            return "Could not check directory permissions", "Low", None
