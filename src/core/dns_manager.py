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
        if sys.platform != "win32":
            return False, "Only supported on Windows."
        from src.core.recovery.integration import get_engine, run_operations
        from src.core.recovery.models import Operation
        backend = get_engine().handlers["network.dns.v1"].backend
        servers = [primary] + ([secondary] if secondary else [])
        operations = [Operation("network.dns.v1", {"interface": adapter["guid"]},
                      {"source": "static", "servers": servers}, f"Set DNS for {adapter['name']}")
                      for adapter in backend.adapters()]
        return run_operations("Change DNS servers", operations)

    @staticmethod
    def reset_dns():
        if sys.platform != "win32":
            return False, "Only supported on Windows."
        from src.core.recovery.integration import get_engine, run_operations
        from src.core.recovery.models import Operation
        backend = get_engine().handlers["network.dns.v1"].backend
        operations = [Operation("network.dns.v1", {"interface": adapter["guid"]},
                      {"source": "dhcp", "servers": []}, f"Use automatic DNS for {adapter['name']}")
                      for adapter in backend.adapters()]
        return run_operations("Reset DNS to automatic", operations)

    @staticmethod
    def flush_dns():
        """Cross-platform DNS flush."""
        tools = get_platform_tools()
        return tools.flush_dns()
