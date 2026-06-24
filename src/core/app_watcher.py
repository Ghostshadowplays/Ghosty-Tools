import sys
import logging
import time
import threading
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class AppWatcher:
    def __init__(self):
        self.running = False
        self.history = []
        self._last_snapshot = set()

    def start(self):
        self.running = True
        self._last_snapshot = self._take_snapshot()
        threading.Thread(target=self._watch_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _take_snapshot(self):
        if sys.platform == "win32":
            # Simplified: just list display names from registry or winget
            proc = run_command(["powershell", "-Command", "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName"])
            return set(proc.stdout.splitlines())
        return set()

    def _watch_loop(self):
        while self.running:
            time.sleep(60) # Poll every minute
            current = self._take_snapshot()
            new_apps = current - self._last_snapshot
            if new_apps:
                for app in new_apps:
                    if app.strip():
                        msg = f"New app detected: {app.strip()}"
                        logger.info(msg)
                        self.history.append({"time": time.time(), "app": app.strip(), "event": "install"})
            self._last_snapshot = current

    @staticmethod
    def block_app(exe_name):
        """Block an app using Image File Execution Options (Windows)."""
        if sys.platform != "win32": return False
        try:
            import winreg
            key_path = rf"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\{exe_name}"
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            winreg.SetValueEx(key, "Debugger", 0, winreg.REG_SZ, "ntsd -d")
            winreg.CloseKey(key)
            return True, f"App {exe_name} blocked."
        except Exception as e:
            return False, str(e)
