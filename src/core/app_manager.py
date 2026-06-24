import sys
import logging
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class AppManager:
    @staticmethod
    def get_installed_apps():
        """List installed apps using platform-specific tools."""
        if sys.platform == "win32":
            # winget list or registry
            proc = run_command(["winget", "list"])
            return proc.stdout
        elif sys.platform == "darwin":
            proc = run_command(["brew", "list"])
            return proc.stdout
        elif sys.platform == "linux":
            # apt list --installed (Debian/Ubuntu)
            proc = run_command(["apt", "list", "--installed"])
            return proc.stdout
        return "Unsupported platform."

    @staticmethod
    def install_app(app_id):
        """Install an app."""
        if sys.platform == "win32":
            return run_command(["winget", "install", "--id", app_id, "--silent", "--accept-package-agreements", "--accept-source-agreements"])
        elif sys.platform == "darwin":
            return run_command(["brew", "install", app_id])
        elif sys.platform == "linux":
            return run_command(["sudo", "apt-get", "install", "-y", app_id])
        return None

    @staticmethod
    def uninstall_app(app_id):
        """Uninstall an app and try to clean up residue."""
        if sys.platform == "win32":
            return run_command(["winget", "uninstall", "--id", app_id, "--silent"])
        elif sys.platform == "darwin":
            return run_command(["brew", "uninstall", app_id])
        elif sys.platform == "linux":
            return run_command(["sudo", "apt-get", "remove", "-y", app_id])
        return None

    @staticmethod
    def search_apps(query):
        """Search for apps in the catalog."""
        if sys.platform == "win32":
            return run_command(["winget", "search", query]).stdout
        elif sys.platform == "darwin":
            return run_command(["brew", "search", query]).stdout
        return "Search not implemented for this platform."
