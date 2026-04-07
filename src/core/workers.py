import subprocess
import logging
import json
import os
import sys

import requests
import zipfile
import winreg
import platform
import psutil

# speedtest-cli tries to access sys.stdout.fileno() which can be None in noconsole EXE
# We will import it inside the worker to ensure sys.stdout is properly handled
speedtest = None

from PyQt6.QtCore import QThread, pyqtSignal
from src.core.security_scanner import SecurityScanner

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

class UpdateCheckWorker(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, update_manager):
        super().__init__()
        self.update_manager = update_manager
        
    def run(self):
        try:
            res = self.update_manager.check_for_updates()
            self.finished.emit(res)
        except Exception as e:
            logger.error(f"UpdateCheckWorker error: {e}")
            self.finished.emit({"available": False, "error": str(e)})

class ReleaseInfoWorker(QThread):
    finished = pyqtSignal(object)
    
    def __init__(self, update_manager):
        super().__init__()
        self.update_manager = update_manager
        
    def run(self):
        try:
            res = self.update_manager.get_release_info()
            self.finished.emit(res)
        except Exception as e:
            logger.error(f"ReleaseInfoWorker error: {e}")
            self.finished.emit(None)

class SensorWorker(QThread):
    finished = pyqtSignal(object)
    
    def run(self):
        try:
            r = requests.get("http://localhost:8085/data.json", timeout=1)
            data = r.json()
            
            sensors = {}
            def walk(node):
                if "Children" in node:
                    for child in node["Children"]:
                        walk(child)
                if "Sensors" in node:
                    for s in node["Sensors"]:
                        sensors[s["Name"]] = {
                            "value": s["Value"],
                            "type": s["SensorType"],
                            "unit": s["Unit"]
                        }
            walk(data)
            self.finished.emit(sensors)
        except:
            self.finished.emit(None)

class SpecsWorker(QThread):
    finished = pyqtSignal(str)
    
    def run(self):
        try:
            # CPU
            cpu_res = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            cpu_lines = [line.strip() for line in cpu_res.stdout.split('\n') if line.strip()]
            cpu_info = cpu_lines[1] if len(cpu_lines) > 1 else "Unknown CPU"

            # GPU
            gpu_res = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name,PNPDeviceID,AdapterRAM,DriverVersion", "/format:csv"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )

            lines = [l.strip() for l in gpu_res.stdout.split("\n") if l.strip()]
            if len(lines) < 2:
                gpu_info = "Unknown GPU"
            else:
                header = lines[0].split(",")
                gpus = []
                for line in lines[1:]:
                    parts = line.split(",")
                    row = dict(zip(header, parts))
                    name = row.get("Name", "").strip()
                    pnp = row.get("PNPDeviceID", "").strip()
                    vram = row.get("AdapterRAM", "").strip()
                    driver = row.get("DriverVersion", "").strip()
                    try:
                        vram_gb = f"{int(vram) / (1024**3):.1f} GB"
                    except:
                        vram_gb = "Unknown VRAM"
                    gpu_type = "PCIe GPU" if "PCI\\" in pnp.upper() else "Integrated GPU"
                    gpus.append(f"{gpu_type}: {name} ({vram_gb}, Driver {driver})")
                gpu_info = "<br>".join(gpus) if gpus else "Unknown GPU"

            # Motherboard
            mobo_res = subprocess.run(
                ["wmic", "baseboard", "get", "product,manufacturer"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            mobo_lines = [line.strip() for line in mobo_res.stdout.split('\n') if line.strip()]
            mobo_info = mobo_lines[1] if len(mobo_lines) > 1 else "Unknown Motherboard"

            # OS Info
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                build_number = int(winreg.QueryValueEx(key, "CurrentBuild")[0])
                product_name = winreg.QueryValueEx(key, "ProductName")[0]
                try:
                    display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
                except FileNotFoundError:
                    try:
                        display_version = winreg.QueryValueEx(key, "ReleaseId")[0]
                    except FileNotFoundError:
                        display_version = "Unknown"
                os_name = "Windows 11" if build_number >= 22000 else "Windows 10"
                winreg.CloseKey(key)
            except Exception:
                os_name = platform.system()
                product_name = "Unknown Edition"
                display_version = "Unknown"
                build_number = 0

            # Install Date
            try:
                ps_cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem).InstallDate.ToString('yyyy-MM-dd HH:mm')"]
                ins = subprocess.run(ps_cmd, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                install_date = ins.stdout.strip()
            except Exception:
                install_date = ""

            specs = f"<b>OS:</b> {os_name} (Build {build_number})<br>"
            specs += f"<b>Edition:</b> {product_name} (Version {display_version})<br>"
            if install_date:
                specs += f"<b>Install Date:</b> {install_date}<br>"
            specs += f"<b>CPU:</b> {cpu_info}<br>"
            specs += f"<b>GPU:</b><br>{gpu_info}<br>"
            specs += f"<b>Motherboard:</b> {mobo_info}<br>"
            self.finished.emit(specs)
        except Exception as e:
            logger.error(f"SpecsWorker error: {e}")
            self.finished.emit(f"Error gathering specs: {e}")

class MainDiskWorker(QThread):
    finished = pyqtSignal(str, str) # main_disk, system_drive
    
    def run(self):
        try:
            system_drive = os.environ.get('SystemDrive', 'C').replace(':', '')
            powershell_script = f"Get-Partition -DriveLetter {system_drive} | Get-Disk | Select-Object -ExpandProperty Number"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", powershell_script],
                capture_output=True,
                text=True,
                shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            main_disk = result.stdout.strip()
            if not main_disk:
                main_disk = "0"
            self.finished.emit(main_disk, system_drive)
        except Exception as e:
            logger.error(f"Error getting main disk: {e}")
            self.finished.emit("0", "C")

class MonitoringSetupWorker(QThread):
    finished = pyqtSignal(bool, str) # success, message
    output = pyqtSignal(str, str) # message, level
    
    def run(self):
        url = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest/download/LibreHardwareMonitor.zip"
        install_dir = os.path.join(os.getenv("APPDATA"), "GhostyTools", "LHM")
        zip_path = os.path.join(install_dir, "lhm.zip")

        os.makedirs(install_dir, exist_ok=True)

        # Download
        try:
            self.output.emit("Downloading LibreHardwareMonitor...", "info")
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                self.finished.emit(False, f"Download failed: HTTP {r.status_code}")
                return

            with open(zip_path, "wb") as f:
                f.write(r.content)

            self.output.emit("Download complete.", "success")

        except Exception as e:
            self.finished.emit(False, f"Download error: {e}")
            return

        # Extract
        try:
            self.output.emit("Extracting ZIP...", "info")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(install_dir)
            self.output.emit("Extraction complete.", "success")

        except Exception as e:
            self.finished.emit(False, f"Extraction error: {e}")
            return

        # Config
        try:
            self.output.emit("Writing configuration...", "info")
            config_path = os.path.join(os.getenv("APPDATA"), "LibreHardwareMonitor", "LibreHardwareMonitor.config")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            config_xml = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
<RemoteWebServer Enabled="true" Port="8085" />
</configuration>
"""
            with open(config_path, "w") as f:
                f.write(config_xml)

            self.output.emit("Configuration written.", "success")

        except Exception as e:
            self.finished.emit(False, f"Config write error: {e}")
            return

        # Launch EXE
        exe_path = os.path.join(install_dir, "LibreHardwareMonitor.exe")
        if not os.path.exists(exe_path):
            self.finished.emit(False, "LibreHardwareMonitor.exe not found after extraction!")
            return

        try:
            self.output.emit("Launching LibreHardwareMonitor...", "info")
            subprocess.Popen([exe_path], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.finished.emit(True, "LibreHardwareMonitor launched successfully.")
        except Exception as e:
            self.finished.emit(False, f"Launch error: {e}")
