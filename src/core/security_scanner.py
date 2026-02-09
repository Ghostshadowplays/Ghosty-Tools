import subprocess

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

class SecurityScanner:
    def _check_windows_defender(self):
        try:
            ps_cmd = 'Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled'
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            if "False" in res.stdout:
                return "Defender Disabled or Real-time Protection Off", "High"
            return "Defender Enabled", "Low"
        except: return "Error checking Defender", "Medium"

    def _check_firewall(self):
        try:
            res = subprocess.run(["netsh", "advfirewall", "show", "allprofiles", "state"], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            if "OFF" in res.stdout.upper():
                return "Firewall Disabled on some profiles", "Critical"
            return "Firewall Enabled", "Low"
        except: return "Error checking Firewall", "Medium"

    def _check_uac(self):
        try:
            ps_cmd = "(Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System).EnableLUA"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            if "0" in res.stdout:
                return "UAC Disabled", "High"
            return "UAC Enabled", "Low"
        except: return "Error checking UAC", "Medium"

    def _check_smbv1(self):
        try:
            ps_cmd = "(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            if "Enabled" in res.stdout:
                return "SMBv1 Enabled (Security Risk)", "High"
            return "SMBv1 Disabled", "Low"
        except: return "Error checking SMBv1", "Low"

    def _check_shares(self):
        try:
            res = subprocess.run(["net", "share"], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            shares = [line for line in res.stdout.split('\n') if line and not line.startswith(('Share name', '----------', 'The command completed')) and '$' not in line]
            if shares:
                return f"{len(shares)} Active Network Shares", "Low"
            return "No Active Network Shares", "Low"
        except: return "Error checking Shares", "Low"

    def get_report(self):
        issues = []
        issues.append(self._check_windows_defender())
        issues.append(self._check_firewall())
        issues.append(self._check_uac())
        issues.append(self._check_smbv1())
        issues.append(self._check_shares())
        return issues
