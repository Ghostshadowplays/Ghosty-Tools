import subprocess
import logging
import json
import os
import sys

# speedtest-cli tries to access sys.stdout.fileno() which can be None in noconsole EXE
# We will import it inside the worker to ensure sys.stdout is properly handled
speedtest = None

from PyQt6.QtCore import QThread, pyqtSignal
from core.security_scanner import SecurityScanner

logger = logging.getLogger(__name__)

class SpeedTestWorker(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def run(self):
        # speedtest-cli may fail when sys.stdout is None (in noconsole EXE)
        # We need to ensure it has a valid stream to write to BEFORE importing.
        original_stdout = sys.stdout
        null_file = None
        if sys.stdout is None:
            null_file = open(os.devnull, 'w')
            sys.stdout = null_file

        global speedtest
        if speedtest is None:
            try:
                import speedtest as st_module
                speedtest = st_module
            except Exception as e:
                logger.error(f"Failed to import speedtest: {e}")
                self.error_occurred.emit(f"The 'speedtest-cli' module failed to load: {e}")
                sys.stdout = original_stdout
                if null_file:
                    null_file.close()
                return

        try:
            # Using secure=True and a custom User-Agent to avoid 403 Forbidden errors
            # speedtest-cli's default user agent is often blocked.
            # We check for both 'headers' and '_headers' to support different versions.
            st = speedtest.Speedtest(secure=True)
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            
            if hasattr(st, 'headers'):
                st.headers['User-Agent'] = user_agent
            elif hasattr(st, '_headers'):
                st._headers['User-Agent'] = user_agent
            
            st.get_best_server()
            download_speed = st.download() / 1_000_000
            upload_speed = st.upload() / 1_000_000
            ping = st.results.ping
            result_text = f"Download: {download_speed:.2f} Mbps\nUpload: {upload_speed:.2f} Mbps\nPing: {ping:.2f} ms"
            self.result_ready.emit(result_text)
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg:
                error_msg = "HTTP Error 403: Forbidden. This usually means Speedtest.net is blocking the request. Try again later or check for app updates."
            self.error_occurred.emit(error_msg)
        finally:
            sys.stdout = original_stdout
            if null_file:
                null_file.close()

class MaintenanceWorker(QThread):
    finished = pyqtSignal(str)
    output = pyqtSignal(str, str)

    def __init__(self, drive_letter="C", check_updates=False):
        super().__init__()
        self.drive_letter = drive_letter
        self.check_updates = check_updates

    def run(self):
        try:
            commands = [
                ("DISM CheckHealth", "DISM.exe /Online /Cleanup-Image /CheckHealth"),
                ("DISM ScanHealth", "DISM.exe /Online /Cleanup-Image /ScanHealth"),
                ("DISM RestoreHealth", "DISM.exe /Online /Cleanup-Image /RestoreHealth"),
                ("SFC Scan", "sfc /scannow"),
                ("GPUpdate", "gpupdate /force"),
                ("CHKDSK", f"echo y | chkdsk {self.drive_letter}: /f /r")
            ]
            
            for name, cmd in commands:
                self.output.emit(f"Running {name}...", "info")
                process = subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    shell=False,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                
                for line in process.stdout:
                    if line.strip():
                        self.output.emit(f"[{name}] {line.strip()}", "debug")
                
                process.wait()
                if process.returncode == 0:
                    self.output.emit(f"{name} completed successfully.", "success")
                else:
                    self.output.emit(f"{name} finished with code {process.returncode}.", "warning")

            self.finished.emit("Maintenance tasks completed. Some changes may require a restart.")
        except Exception as e:
            self.output.emit(f"Maintenance Error: {str(e)}", "error")
            self.finished.emit(f"Error: {str(e)}")

class GenericCommandWorker(QThread):
    finished = pyqtSignal(bool, str)
    output = pyqtSignal(str, str)

    def __init__(self, name, command):
        super().__init__()
        self.name = name
        self.command = command

    def run(self):
        try:
            process = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", self.command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            
            full_output = []
            for line in process.stdout:
                if line.strip():
                    clean_line = line.strip()
                    full_output.append(clean_line)
                    self.output.emit(f"[{self.name}] {clean_line}", "debug")
            
            process.wait()
            success = (process.returncode == 0)
            result_str = "\n".join(full_output) if full_output else ""
            
            if success:
                self.finished.emit(True, result_str)
            else:
                self.finished.emit(False, result_str if result_str else f"{self.name} failed with code {process.returncode}.")
        except Exception as e:
            self.output.emit(f"{self.name} Error: {str(e)}", "error")
            self.finished.emit(False, str(e))

class SecurityScanWorker(QThread):
    finished = pyqtSignal(list)
    output = pyqtSignal(str, str)

    def run(self):
        try:
            self.output.emit("Starting background security scan...", "info")
            scanner = SecurityScanner()
            issues = scanner.get_report()
            self.finished.emit(issues)
        except Exception as e:
            logger.error(f"Security Scan Error: {e}")
            self.finished.emit([])

class BloatScanWorker(QThread):
    finished = pyqtSignal(dict)
    output = pyqtSignal(str, str)

    def __init__(self, bloat_remover):
        super().__init__()
        self.bloat_remover = bloat_remover

    def run(self):
        try:
            self.output.emit("Starting background bloatware scan...", "info")
            
            def on_progress(p, m):
                if p % 20 == 0 or p == 100:
                    self.output.emit(f"Scan {p}%: {m}", "debug")
            
            results = self.bloat_remover.scan_system(on_progress)
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Bloat Scan Error: {e}")
            self.output.emit(f"Bloat Scan Error: {str(e)}", "error")
            self.finished.emit({})
