import sys
import logging
from src.utils.helpers import run_command
from src.core.platform_tools.factory import get_platform_tools

logger = logging.getLogger(__name__)

class DNSManager:
    DNS_PRESETS = {
        "Google": ("8.8.8.8", "8.8.4.4"),
        "Cloudflare": ("1.1.1.1", "1.0.0.1"),
        "Quad9": ("9.9.9.9", "149.112.112.112"),
        "OpenDNS": ("208.67.222.222", "208.67.220.220")
    }

    @staticmethod
    def set_dns(primary, secondary=None):
        """Set DNS servers for all active adapters (Windows only for now)."""
        if sys.platform != "win32": return False, "Only supported on Windows."
        
        try:
            # Using PowerShell to set DNS
            cmd = f"Get-NetAdapter | Where-Object {{ $_.Status -eq 'Up' }} | Set-DnsClientServerAddress -ServerAddresses ('{primary}'"
            if secondary:
                cmd += f", '{secondary}'"
            cmd += ")"
            
            proc = run_command(["powershell", "-Command", cmd])
            if proc.returncode == 0:
                return True, f"DNS set to {primary}, {secondary}"
            return False, proc.stderr
        except Exception as e:
            return False, str(e)

    @staticmethod
    def reset_dns():
        """Reset DNS to automatic (DHCP)."""
        if sys.platform != "win32": return False
        try:
            cmd = "Get-NetAdapter | Where-Object {{ $_.Status -eq 'Up' }} | Set-DnsClientServerAddress -ResetServerAddresses"
            proc = run_command(["powershell", "-Command", cmd])
            return proc.returncode == 0, "DNS reset to automatic."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def flush_dns():
        """Cross-platform DNS flush."""
        tools = get_platform_tools()
        return tools.flush_dns()
