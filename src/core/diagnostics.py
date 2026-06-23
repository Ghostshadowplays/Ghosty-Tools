import os
import sys
import platform
import socket
import requests
import psutil
import logging
import shutil
from datetime import datetime
from src.utils.helpers import get_logs_dir, get_config_dir

logger = logging.getLogger(__name__)

class Diagnostics:
    def __init__(self, version):
        self.version = version
        self.results = []

    def run_all(self):
        self.results = []
        self._check_system_info()
        self._check_dependencies()
        self._check_permissions()
        self._check_network()
        self._check_update_server()
        self._check_disk_space()
        
        self.save_to_log()
        return self.results

    def _add_result(self, name, status, message):
        self.results.append({
            "name": name,
            "status": status,
            "message": message
        })
        logger.info(f"Diag: {name} - {status} - {message}")

    def _check_system_info(self):
        info = f"OS: {platform.system()} {platform.release()}, Arch: {platform.machine()}, Python: {sys.version.split()[0]}"
        self._add_result("System Info", "INFO", info)

    def _check_dependencies(self):
        deps = ["requests", "PyQt6", "psutil", "pyperclip", "PIL"]
        missing = []
        for dep in deps:
            try:
                __import__(dep)
            except ImportError:
                missing.append(dep)
        
        if not missing:
            self._add_result("Dependencies", "PASS", "All core dependencies are present.")
        else:
            self._add_result("Dependencies", "FAIL", f"Missing dependencies: {', '.join(missing)}")

    def _check_permissions(self):
        # Check if we can write to config and logs dir
        config_dir = get_config_dir()
        logs_dir = get_logs_dir()
        
        try:
            test_file = os.path.join(config_dir, ".perm_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
            test_file = os.path.join(logs_dir, ".perm_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
            self._add_result("File Permissions", "PASS", "Write access to config and logs directories verified.")
        except Exception as e:
            self._add_result("File Permissions", "FAIL", f"Insufficient permissions: {e}")

    def _check_network(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self._add_result("Network Connectivity", "PASS", "Internet access is available.")
        except Exception:
            self._add_result("Network Connectivity", "FAIL", "No internet access detected.")

    def _check_update_server(self):
        try:
            from src.core.update_manager import REPO_URL
            response = requests.head(REPO_URL, timeout=5)
            if response.status_code < 400:
                self._add_result("Update Server", "PASS", "Update server is reachable.")
            else:
                self._add_result("Update Server", "FAIL", f"Update server returned status {response.status_code}.")
        except Exception as e:
            self._add_result("Update Server", "FAIL", f"Update server is unreachable: {e}")

    def _check_disk_space(self):
        try:
            usage = psutil.disk_usage(os.path.abspath(os.sep))
            free_gb = usage.free / (1024**3)
            if free_gb > 1.0:
                self._add_result("Disk Space", "PASS", f"{free_gb:.2f} GB free on system drive.")
            else:
                self._add_result("Disk Space", "WARNING", f"Low disk space: {free_gb:.2f} GB free.")
        except Exception as e:
            self._add_result("Disk Space", "FAIL", f"Failed to check disk space: {e}")

    def save_to_log(self):
        logs_dir = get_logs_dir()
        diag_file = os.path.join(logs_dir, f"diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(diag_file, "w") as f:
                f.write(f"Ghosty Tools Diagnostics Report\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"App Version: {self.version}\n")
                f.write("-" * 40 + "\n")
                for res in self.results:
                    f.write(f"[{res['status']}] {res['name']}: {res['message']}\n")
            return diag_file
        except Exception as e:
            logger.error(f"Failed to save diagnostics log: {e}")
            return None
