import abc
import sys
import logging
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class BasePlatformTools(abc.ABC):
    @abc.abstractmethod
    def flush_dns(self):
        """Flush the DNS resolver cache."""
        pass

    @abc.abstractmethod
    def get_hosts_content(self):
        """Read the hosts file content."""
        pass

    @abc.abstractmethod
    def save_hosts_content(self, content):
        """Save the hosts file content."""
        pass

    @abc.abstractmethod
    def get_system_logs(self, lines=50):
        """Fetch the last N lines of system logs."""
        pass

    @abc.abstractmethod
    def get_disk_usage(self):
        """Get disk usage summary."""
        pass

    @abc.abstractmethod
    def toggle_gaming_mode(self, enable=True):
        """Optimize system for gaming."""
        pass

    def run_shell_command(self, cmd, shell_type=None):
        """
        Run a command using a specific shell.
        shell_type can be 'powershell', 'bash', 'zsh', or None (default system shell).
        """
        if shell_type == 'powershell' and sys.platform == 'win32':
            return run_command(["powershell", "-Command", cmd])
        elif shell_type in ['bash', 'zsh']:
            return run_command([shell_type, "-c", cmd])
        else:
            return run_command(cmd, shell=True)
