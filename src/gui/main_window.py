import os
import sys
import subprocess
import webbrowser
import threading
import json
import secrets
import string
import re
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QCheckBox, QGroupBox, 
                             QScrollArea, QMessageBox, QProgressBar, QStackedWidget,
                             QFrame, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QTreeWidgetItemIterator, QComboBox, QTextEdit, QLineEdit, QDialog, QFormLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QTextCursor
import psutil
try:
    import winreg
except Exception:
    winreg = None 
import pyperclip
import zipfile

# Internal imports
from src.core.workers import SpeedTestWorker, MaintenanceWorker, GenericCommandWorker, SecurityScanWorker, BloatScanWorker
from src.core.password_manager import PasswordManager
from src.core.bloat_remover import BloatRemover, BloatwareCategory, SafetyLevel
from src.core.system_tools_installer import SystemToolsInstaller, ToolCategory
from src.core.security_scanner import SecurityScanner
from src.core.update_manager import UpdateManager, UpdateWorker
from src.gui.dialogs import MasterPasswordDialog
from src.utils.helpers import is_admin, elevate_privileges, get_config_dir, ensure_private_file

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

logger = logging.getLogger(__name__)

class GhostyTool(QMainWindow):
    log_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.setWindowTitle("Ghosty Tool - Professional System Utility")
        self.setGeometry(100, 100, 900, 750)
        
        icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.log_signal.connect(self.log_to_terminal)

        self.main_disk = None
        self.get_main_disk()

        config_dir = get_config_dir()
        self.db_path = os.path.join(config_dir, "vault.db")
        self.password_manager = PasswordManager(self.db_path)

        # Clipboard security
        self.clipboard_timer = QTimer()
        self.clipboard_timer.setSingleShot(True)
        self.clipboard_timer.timeout.connect(self.clear_clipboard)

        self.init_ui()
        
        # Initialize Update Manager
        self.update_manager = UpdateManager()
        self._latest_update_info = None
        QTimer.singleShot(1000, self.check_for_updates)
        QTimer.singleShot(2000, self.check_for_whats_new)

        # Timer for system usage updates
        self.usage_timer = QTimer()
        self.usage_timer.timeout.connect(self.update_system_usage)
        self.usage_timer.start(2000)
        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self.update_sensor_panel)
        self.sensor_timer.start(2000)

    def get_main_disk(self):
        try:
            # Get system drive letter
            self.system_drive = os.environ.get('SystemDrive', 'C').replace(':', '')
            
            # Get the disk number for the system drive
            powershell_script = f"Get-Partition -DriveLetter {self.system_drive} | Get-Disk | Select-Object -ExpandProperty Number"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", powershell_script],
                capture_output=True,
                text=True,
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            self.main_disk = result.stdout.strip()
            if not self.main_disk:
                self.main_disk = "0"
            logger.info(f"Main system disk identified as Disk {self.main_disk} (Drive {self.system_drive}:)")
        except Exception as e:
            logger.error(f"Error getting main disk: {e}")
            self.main_disk = "0"
            self.system_drive = "C"

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-right: 1px solid #333;
            }
        """)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 20, 10, 20)
        self.sidebar_layout.setSpacing(10)

        title_label = QLabel("GHOSTY TOOLS")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4158D0; margin-bottom: 20px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(title_label)

        self.nav_buttons = []
        self.add_nav_button("Dashboard", 0)
        self.add_nav_button("Maintenance", 1)
        self.add_nav_button("Security", 2)
        self.add_nav_button("Debloat", 3)
        self.add_nav_button("System Tools", 4)
        self.add_nav_button("Password Gen", 5)
        self.add_nav_button("Password Vault", 6)
        self.add_nav_button("Tweaks", 7)
        self.add_nav_button("About", 8)

        self.sidebar_layout.addStretch()

        # Theme toggle in sidebar
        self.dark_mode_btn = QPushButton("Toggle Theme")
        self.dark_mode_btn.clicked.connect(self.toggle_windows_theme)
        self.sidebar_layout.addWidget(self.dark_mode_btn)

        self.main_layout.addWidget(self.sidebar)

        # Content Area & Terminal
        self.right_container = QWidget()
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        self.content_stack = QStackedWidget()
        
        # Header for content area
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(60)
        self.header_frame.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.page_title = QLabel("Dashboard")
        self.page_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.page_title.setStyleSheet("color: white;")
        self.header_layout.addWidget(self.page_title)
        self.header_layout.addStretch()

        # Admin status in header
        self.admin_label = QLabel()
        self.admin_label.setStyleSheet("margin-right: 10px;")
        self.update_admin_status_ui()
        self.header_layout.addWidget(self.admin_label)

        self.elevate_btn = QPushButton("Elevate")
        self.elevate_btn.setFixedWidth(80)
        self.elevate_btn.setStyleSheet("background-color: #f44747; color: white; font-weight: bold; border-radius: 3px; height: 30px;")
        self.elevate_btn.clicked.connect(self.request_elevation)
        self.header_layout.addWidget(self.elevate_btn)

        if is_admin():
            self.elevate_btn.hide()
        
        self.right_layout.addWidget(self.header_frame)
        self.right_layout.addWidget(self.content_stack)

        # Live Terminal Feed
        self.terminal_container = QGroupBox("Live Terminal Feed")
        self.terminal_container.setFixedHeight(180)
        self.terminal_container.setStyleSheet("""
            QGroupBox {
                color: #4158D0;
                font-weight: bold;
                border: 1px solid #444;
                margin-top: 10px;
                background-color: #1e1e1e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        terminal_layout = QVBoxLayout(self.terminal_container)
        
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: none;
            }
""")
        terminal_layout.addWidget(self.terminal_output)
        
        self.right_layout.addWidget(self.terminal_container)
        self.main_layout.addWidget(self.right_container)

        self.setup_dashboard_page()
        self.setup_maintenance_page()
        self.setup_security_page()
        self.setup_debloat_page()
        self.setup_tools_page()
        self.setup_passgen_page()
        self.setup_vault_page()
        self.setup_tweaks_page()
        self.setup_about_page()

    def add_nav_button(self, text, index):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaa;
                text-align: left;
                padding-left: 20px;
                border: none;
                border-radius: 0px;
                font-size: 13px;
                font-weight: 500;
                height: 45px;
            }
            QPushButton:hover {
                background-color: #222;
                color: white;
            }
            QPushButton:checked {
                background-color: #4158D0;
                color: white;
                font-weight: bold;
                border-left: 4px solid #fff;
            }
        """)
        btn.clicked.connect(lambda _: self.switch_page(index))
        self.sidebar_layout.addWidget(btn)
        self.nav_buttons.append(btn)
        if index == 0: btn.setChecked(True)

    def update_admin_status_ui(self):
        if is_admin():
            self.admin_label.setText("🛡️ Admin Mode")
            self.admin_label.setStyleSheet("color: #6a9955; font-weight: bold;")
        else:
            self.admin_label.setText("👤 Standard Mode")
            self.admin_label.setStyleSheet("color: #d7ba7d; font-weight: bold;")

    def request_elevation(self):
        if QMessageBox.question(self, "Elevate", "Restart app with administrator privileges?") == QMessageBox.StandardButton.Yes:
            elevate_privileges()

    def clear_clipboard(self):
        pyperclip.copy("")
        self.log_signal.emit("Clipboard cleared for security.", "info")

    def copy_to_clipboard(self, text, timeout=30):
        if text:
            pyperclip.copy(text)
            self.log_signal.emit(f"Copied to clipboard. Will clear in {timeout}s.", "info")
            self.clipboard_timer.start(timeout * 1000)

    def log_to_terminal(self, message, level="info"):
        """Logs a message to the live terminal with color coding."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "#d4d4d4"
        
        if level == "error": color = "#f44747"
        elif level == "success": color = "#6a9955"
        elif level == "warning": color = "#d7ba7d"
        elif level == "debug": color = "#808080"
        elif level == "info": color = "#569cd6"
        
        formatted_message = f'<span style="color: #808080;">[{timestamp}]</span> <span style="color: {color};">{message}</span><br>'
        self.terminal_output.insertHtml(formatted_message)
        self.terminal_output.moveCursor(QTextCursor.MoveOperation.End)
        
        if level == "error": logger.error(message)
        elif level == "warning": logger.warning(message)
        else: logger.info(message)

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)
        self.page_title.setText(self.nav_buttons[index].text())

    def setup_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        usage_group = QGroupBox("Live Monitoring")
        usage_layout = QVBoxLayout()
        self.usage_label = QLabel("CPU: ... | RAM: ...")
        self.usage_label.setFont(QFont("Segoe UI", 12))
        usage_layout.addWidget(self.usage_label)
        # Update status indicator on Dashboard (subtle)
        self.update_status_btn = QPushButton("Checking for updates…")
        self.update_status_btn.setFlat(True)
        self.update_status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_status_btn.setStyleSheet("color: #cccccc; font-size: 11px;")
        self.update_status_btn.setMaximumWidth(180)
        self.update_status_btn.clicked.connect(self.on_update_status_clicked)
        usage_layout.addWidget(self.update_status_btn, 0, Qt.AlignmentFlag.AlignRight)
        usage_group.setLayout(usage_layout)
        content_layout.addWidget(usage_group)

        specs_group = QGroupBox("System Specifications")
        specs_layout = QVBoxLayout()
        self.specs_label = QLabel("Gathering system info...")
        specs_layout.addWidget(self.specs_label)
        refresh_specs_btn = QPushButton("Refresh Specs")
        refresh_specs_btn.setMinimumHeight(36)
        refresh_specs_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        refresh_specs_btn.clicked.connect(self.update_specs)
        specs_layout.addWidget(refresh_specs_btn)
        specs_group.setLayout(specs_layout)
        content_layout.addWidget(specs_group)

        battery_group = QGroupBox("Battery Health")
        battery_layout = QVBoxLayout()
        self.battery_label = QLabel("Click to check battery health")
        battery_btn = QPushButton("Update Battery Health")
        battery_btn.setMinimumHeight(36)
        battery_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        battery_btn.clicked.connect(self.update_battery_health)
        battery_layout.addWidget(self.battery_label)
        battery_layout.addWidget(battery_btn)
        battery_group.setLayout(battery_layout)
        content_layout.addWidget(battery_group)

        disk_group = QGroupBox("Disk Health")
        disk_layout = QVBoxLayout()
        self.disk_label = QLabel(f"Checking health for disk {self.main_disk}...")
        disk_btn = QPushButton("Check Disk Health")
        disk_btn.setMinimumHeight(36)
        disk_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        disk_btn.clicked.connect(self.check_disk_health)
        disk_layout.addWidget(self.disk_label)
        disk_layout.addWidget(disk_btn)
        disk_group.setLayout(disk_layout)
        content_layout.addWidget(disk_group)

        speed_group = QGroupBox("Network Speed Test")
        speed_layout = QVBoxLayout()
        self.speed_label = QLabel("Result: Not started")
        speed_btn = QPushButton("Run Speed Test")
        speed_btn.setMinimumHeight(36)
        speed_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        speed_btn.clicked.connect(self.run_speed_test)
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(speed_btn)
        speed_group.setLayout(speed_layout)
        content_layout.addWidget(speed_group)

        monitor_group = QGroupBox("Full Hardware Monitoring")
        monitor_layout = QVBoxLayout()

        self.full_monitor_button = QPushButton("Enable Full Monitoring")
        self.full_monitor_button.setMinimumHeight(36)
        self.full_monitor_button.setStyleSheet(
            "QPushButton { background-color: #4158D0; color: white; font-weight: bold; "
            "border: 1px solid #2e46a9; border-radius: 6px; } "
            "QPushButton:hover { background-color: #4b6de3; } "
            "QPushButton:pressed { background-color: #3a55c5; }"
        )

        self.full_monitor_button.clicked.connect(self.enable_full_monitoring)

        monitor_layout.addWidget(self.full_monitor_button)

        
        self.sensor_label = QLabel("Monitoring not enabled")
        monitor_layout.addWidget(self.sensor_label)
        

        monitor_group.setLayout(monitor_layout)
        content_layout.addWidget(monitor_group)


        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.content_stack.addWidget(page)
        self.update_specs()

    def update_specs(self):
        try:
            import platform

            cpu_res = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )
            cpu_lines = [line.strip() for line in cpu_res.stdout.split('\n') if line.strip()]
            cpu_info = cpu_lines[1] if len(cpu_lines) > 1 else "Unknown CPU"

            mem = psutil.virtual_memory()

            gpu_res = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name,PNPDeviceID,AdapterRAM,DriverVersion", "/format:csv"],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW
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

                    if "PCI\\" in pnp.upper():
                        gpu_type = "PCIe GPU"
                    else:
                        gpu_type = "Integrated GPU"

                    gpus.append(f"{gpu_type}: {name} ({vram_gb}, Driver {driver})")

                gpu_info = "<br>".join(gpus) if gpus else "Unknown GPU"

            mobo_res = subprocess.run(
                ["wmic", "baseboard", "get", "product,manufacturer"],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )
            mobo_lines = [line.strip() for line in mobo_res.stdout.split('\n') if line.strip()]
            mobo_info = mobo_lines[1] if len(mobo_lines) > 1 else "Unknown Motherboard"

            
            if winreg:
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
                    )

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
            else:
                os_name = platform.system()
                product_name = "Unknown Edition"
                display_version = "Unknown"
                build_number = 0

            arch = platform.machine()
            arch_bits = platform.architecture()[0]

            install_date = ""
            try:
                ps_cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_OperatingSystem).InstallDate.ToString('yyyy-MM-dd HH:mm')"
                ]
                ins = subprocess.run(ps_cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
                install_date = ins.stdout.strip()
            except Exception:
                install_date = ""

            specs = f"<b>OS:</b> {os_name} (Build {build_number})<br>"
            specs += f"<b>Edition:</b> {product_name} (Version {display_version})<br>"
            specs += f"<b>Architecture:</b> {arch} ({arch_bits})<br>"

            if install_date:
                specs += f"<b>Installed:</b> {install_date}<br>"
            specs += f"<b>CPU:</b> {cpu_info}<br>"
            specs += f"<b>RAM:</b> {mem.total / (1024**3):.1f} GB Total<br>"
            specs += f"<b>GPU:</b><br>{gpu_info}<br>"
            specs += f"<b>Motherboard:</b> {mobo_info}<br>"

            self.specs_label.setText(specs)
            self.specs_label.setTextFormat(Qt.TextFormat.RichText)

        except Exception as e:
            logger.error(f"Error gathering specs: {e}")
            self.specs_label.setText(f"Error gathering specs: {e}")

    def get_sensors(self):
        try:
            r = requests.get("http://localhost:8085/data.json", timeout=1)
            data = r.json()
        except:
            return None

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
        return sensors

    def update_sensor_panel(self):
        sensors = self.get_sensors()
        if not sensors:
            self.sensor_label.setText("Sensors unavailable (start LibreHardwareMonitor)")
            return

        text = ""

        def add(name):
            if name in sensors:
                v = sensors[name]
                return f"{name}: {v['value']} {v['unit']}<br>"
            return ""

        text += "<b>CPU:</b><br>"
        text += add("CPU Package")
        text += add("CPU Core #1 Temperature")
        text += add("CPU Core #1 Clock")

        text += "<br><b>GPU:</b><br>"
        text += add("GPU Core")
        text += add("GPU Memory")
        text += add("GPU Fan")

        self.sensor_label.setText(text)
        self.sensor_label.setTextFormat(Qt.TextFormat.RichText)

    def enable_full_monitoring(self):

        self.log_signal.emit("Starting Full Monitoring setup...", "info")

        url = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest/download/LibreHardwareMonitor.zip"
        install_dir = os.path.join(os.getenv("APPDATA"), "GhostyTools", "LHM")
        zip_path = os.path.join(install_dir, "lhm.zip")

        os.makedirs(install_dir, exist_ok=True)

        # Download
        try:
            self.log_signal.emit("Downloading LibreHardwareMonitor...", "info")
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                self.log_signal.emit(f"Download failed: HTTP {r.status_code}", "error")
                return

            with open(zip_path, "wb") as f:
                f.write(r.content)

            self.log_signal.emit("Download complete.", "success")

        except Exception as e:
            self.log_signal.emit(f"Download error: {e}", "error")
            return

        # Extract
        try:
            self.log_signal.emit("Extracting ZIP...", "info")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(install_dir)
            self.log_signal.emit("Extraction complete.", "success")

        except Exception as e:
            self.log_signal.emit(f"Extraction error: {e}", "error")
            return

        # Config
        try:
            self.log_signal.emit("Writing configuration...", "info")
            config_path = os.path.join(os.getenv("APPDATA"), "LibreHardwareMonitor", "LibreHardwareMonitor.config")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            config_xml = """<?xml version="1.0" encoding="utf-8"?>
    <configuration>
    <RemoteWebServer Enabled="true" Port="8085" />
    </configuration>
    """
            with open(config_path, "w") as f:
                f.write(config_xml)

            self.log_signal.emit("Configuration written.", "success")

        except Exception as e:
            self.log_signal.emit(f"Config write error: {e}", "error")
            return

        # Launch EXE
        exe_path = os.path.join(install_dir, "LibreHardwareMonitor.exe")

        if not os.path.exists(exe_path):
            self.log_signal.emit("ERROR: LibreHardwareMonitor.exe not found after extraction!", "error")
            return

        try:
            self.log_signal.emit("Launching LibreHardwareMonitor...", "info")
            subprocess.Popen([exe_path], creationflags=subprocess.CREATE_NO_WINDOW)
            self.log_signal.emit("LibreHardwareMonitor launched.", "success")

        except Exception as e:
            self.log_signal.emit(f"Launch error: {e}", "error")
            return

    def setup_maintenance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        maint_btn = QPushButton("Run Full System Maintenance (SFC, DISM, CHKDSK)")
        maint_btn.setMinimumHeight(40)
        maint_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        maint_btn.clicked.connect(self.run_system_maintenance)
        layout.addWidget(maint_btn)

        dns_btn = QPushButton("Flush DNS Cache")
        dns_btn.setMinimumHeight(40)
        dns_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        dns_btn.clicked.connect(self.flush_dns)
        layout.addWidget(dns_btn)

        cleanup_btn = QPushButton("Run Disk Cleanup")
        cleanup_btn.setMinimumHeight(40)
        cleanup_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        cleanup_btn.clicked.connect(self.run_disk_cleanup)
        layout.addWidget(cleanup_btn)

        update_group = QGroupBox("Windows Updates")
        update_layout = QVBoxLayout()
        self.update_status = QLabel("Status: Idle")
        check_update_btn = QPushButton("Check for Updates")
        check_update_btn.setMinimumHeight(40)
        check_update_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        check_update_btn.clicked.connect(self.run_windows_update_check)
        install_update_btn = QPushButton("Install Updates")
        install_update_btn.setMinimumHeight(40)
        install_update_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        install_update_btn.clicked.connect(self.install_windows_updates)
        update_layout.addWidget(self.update_status)
        update_layout.addWidget(check_update_btn)
        update_layout.addWidget(install_update_btn)
        update_group.setLayout(update_layout)
        layout.addWidget(update_group)

        restore_btn = QPushButton("Create System Restore Point")
        restore_btn.setMinimumHeight(40)
        restore_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        restore_btn.clicked.connect(self.create_restore_point)
        layout.addWidget(restore_btn)

        disk_tools_group = QGroupBox("Advanced Disk Tools")
        disk_tools_layout = QVBoxLayout()
        disk_selection_layout = QHBoxLayout()
        disk_selection_layout.addWidget(QLabel("Select Disk:"))
        self.disk_combo = QComboBox()
        disk_selection_layout.addWidget(self.disk_combo)
        refresh_disks_btn = QPushButton("Refresh List")
        refresh_disks_btn.setFixedWidth(100)
        refresh_disks_btn.clicked.connect(self.refresh_disk_list)
        disk_selection_layout.addWidget(refresh_disks_btn)
        disk_tools_layout.addLayout(disk_selection_layout)
        
        mbr2gpt_btn_layout = QHBoxLayout()
        validate_mbr2gpt_btn = QPushButton("1. Validate Disk for GPT")
        validate_mbr2gpt_btn.setToolTip("Checks if the selected disk can be converted to GPT.")
        validate_mbr2gpt_btn.clicked.connect(self.validate_mbr2gpt)
        convert_mbr2gpt_btn = QPushButton("2. Convert Disk to GPT")
        convert_mbr2gpt_btn.setToolTip("Converts the selected disk from MBR to GPT.")
        convert_mbr2gpt_btn.clicked.connect(self.convert_mbr2gpt)
        mbr2gpt_btn_layout.addWidget(validate_mbr2gpt_btn)
        mbr2gpt_btn_layout.addWidget(convert_mbr2gpt_btn)
        disk_tools_layout.addLayout(mbr2gpt_btn_layout)
        
        disk_tools_group.setLayout(disk_tools_layout)
        layout.addWidget(disk_tools_group)

        layout.addStretch()
        self.content_stack.addWidget(page)
        self.refresh_disk_list()

    def setup_security_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Security Assessment"))
        self.security_list = QListWidget()
        layout.addWidget(self.security_list)
        scan_btn = QPushButton("Run Security Scan")
        scan_btn.setMinimumHeight(40)
        scan_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        scan_btn.clicked.connect(self.run_security_scan)
        layout.addWidget(scan_btn)
        layout.addStretch()
        self.content_stack.addWidget(page)

    def run_security_scan(self):
        self.security_list.clear()
        self.log_signal.emit("Initializing security scan...", "info")
        self.scan_worker = SecurityScanWorker()
        self.scan_worker.output.connect(self.log_to_terminal)
        self.scan_worker.finished.connect(self._on_security_scan_finished)
        self.scan_worker.start()

    def _on_security_scan_finished(self, issues):
        if not issues:
            self.log_signal.emit("Security scan failed or returned no results.", "error")
            return
        
        for issue, severity in issues:
            item = QListWidgetItem(f"[{severity}] {issue}")
            if severity == "Critical" or severity == "High":
                item.setForeground(Qt.GlobalColor.red)
            elif severity == "Medium":
                item.setForeground(QColor("orange"))
            else:
                item.setForeground(Qt.GlobalColor.green)
            self.security_list.addItem(item)
        self.log_signal.emit("Security scan completed.", "success")

    def setup_debloat_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #2d2d2d; border-radius: 5px;")
        info_layout = QVBoxLayout(info_frame)
        warning = QLabel("WARNING: Debloating can remove system apps. Use with caution.")
        warning.setStyleSheet("color: #ff4444; font-weight: bold;")
        info_layout.addWidget(warning)
        info_layout.addWidget(QLabel("Recommended: Create a restore point before proceeding."))
        layout.addWidget(info_frame)

        self.debloat_tree = QTreeWidget()
        self.debloat_tree.setHeaderLabels(["Item", "Description", "Safety"])
        self.debloat_tree.setAlternatingRowColors(True)
        self.debloat_tree.setColumnWidth(0, 200)
        self.debloat_tree.setColumnWidth(1, 400)
        self.debloat_tree.setStyleSheet("QTreeWidget::item { padding: 5px; }")
        layout.addWidget(self.debloat_tree)
        
        config_path = os.path.join(self.project_root, "config", "bloatware_config.json")
        self.bloat_remover = BloatRemover(config_path)
        self.populate_debloat_tree()
        
        selection_btns = QHBoxLayout()
        safe_btn = QPushButton("Select Safe Items")
        safe_btn.clicked.connect(lambda _: self.select_safe_debloat())
        all_btn = QPushButton("Select All")
        all_btn.clicked.connect(lambda _: self.toggle_debloat_selection(True))
        none_btn = QPushButton("Deselect All")
        none_btn.clicked.connect(lambda _: self.toggle_debloat_selection(False))
        selection_btns.addWidget(safe_btn)
        selection_btns.addWidget(all_btn)
        selection_btns.addWidget(none_btn)
        layout.addLayout(selection_btns)

        btn_layout = QHBoxLayout()
        self.debloat_scan_btn = QPushButton("Scan System for Bloatware")
        self.debloat_scan_btn.setMinimumHeight(40)
        self.debloat_scan_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        self.debloat_scan_btn.clicked.connect(self.scan_bloatware)
        self.debloat_remove_btn = QPushButton("Remove Selected Items")
        self.debloat_remove_btn.setMinimumHeight(40)
        self.debloat_remove_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        self.debloat_remove_btn.clicked.connect(self.remove_bloatware)
        btn_layout.addWidget(self.debloat_scan_btn)
        btn_layout.addWidget(self.debloat_remove_btn)
        layout.addLayout(btn_layout)
        self.content_stack.addWidget(page)

    def select_safe_debloat(self):
        iterator = QTreeWidgetItemIterator(self.debloat_tree)
        while iterator.value():
            item = iterator.value()
            safety = item.text(2).lower()
            if safety == "safe":
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1
        self.log_signal.emit("Selected all 'Safe' debloat items.", "info")

    def toggle_debloat_selection(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        iterator = QTreeWidgetItemIterator(self.debloat_tree)
        while iterator.value():
            item = iterator.value()
            if item.parent(): # Only leaf nodes
                item.setCheckState(0, state)
            iterator += 1

    def populate_debloat_tree(self):
        categories = {}
        for item in self.bloat_remover.items.values():
            cat_name = item.category.value
            if cat_name not in categories:
                cat_item = QTreeWidgetItem(self.debloat_tree, [cat_name])
                categories[cat_name] = cat_item
            child = QTreeWidgetItem(categories[cat_name], [item.name, item.description, item.safety_level.value])
            child.setCheckState(0, Qt.CheckState.Unchecked)
            child.setData(0, Qt.ItemDataRole.UserRole, item.id)

    def scan_bloatware(self):
        try:
            self.log_signal.emit("Starting bloatware scan...", "info")
            if hasattr(self, 'debloat_scan_btn') and self.debloat_scan_btn:
                self.debloat_scan_btn.setEnabled(False)
            self.bloat_scan_worker = BloatScanWorker(self.bloat_remover)
            self.bloat_scan_worker.output.connect(self.log_to_terminal)
            self.bloat_scan_worker.finished.connect(self._on_bloat_scan_finished)
            self.bloat_scan_worker.start()
        except Exception as e:
            logger.error(f"Error starting bloatware scan: {e}")
            self.log_signal.emit(f"Error starting bloatware scan: {e}", "error")

    def _update_debloat_tree(self, results):
        self.debloat_tree.setUpdatesEnabled(False)
        try:
            iterator = QTreeWidgetItemIterator(self.debloat_tree)
            while iterator.value():
                item = iterator.value()
                if item.parent():  # only leaf items
                    item_id = item.data(0, Qt.ItemDataRole.UserRole)
                    if item_id in results:
                        base_text = item.text(0).replace(" (Found)", "")
                        if results[item_id]:
                            item.setForeground(0, Qt.GlobalColor.yellow)
                            item.setText(0, f"{base_text} (Found)")
                        else:
                            item.setForeground(0, Qt.GlobalColor.gray)
                            item.setText(0, base_text)
                iterator += 1
            self.log_signal.emit("Bloatware list updated.", "success")
        finally:
            self.debloat_tree.setUpdatesEnabled(True)

    def _on_bloat_scan_finished(self, results):
        if hasattr(self, 'debloat_scan_btn') and self.debloat_scan_btn:
            self.debloat_scan_btn.setEnabled(True)
        if not isinstance(results, dict):
            self.log_signal.emit("Bloatware scan returned no results.", "warning")
            return
        self.log_signal.emit("Scan completed, updating list...", "info")
        self._update_debloat_tree(results)

    def remove_bloatware(self):
        selected_ids = []
        iterator = QTreeWidgetItemIterator(self.debloat_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                item_id = item.data(0, Qt.ItemDataRole.UserRole)
                if item_id: selected_ids.append(item_id)
            iterator += 1
        
        if not selected_ids:
            QMessageBox.warning(self, "Selection", "Please select items to remove.")
            return
            
        if QMessageBox.question(self, "Confirm", f"Remove {len(selected_ids)} items?") == QMessageBox.StandardButton.Yes:
            self.log_signal.emit(f"Starting removal of {len(selected_ids)} items...", "info")
            def output_cb(m, l): 
                self.log_signal.emit(m, l)
            threading.Thread(target=self._run_bloat_removal, args=(selected_ids, output_cb), daemon=True).start()

    def _run_bloat_removal(self, ids, cb):
        self.bloat_remover.remove_items(ids, output_callback=cb)
        self.log_signal.emit("Bloatware removal process finished.", "success")

    def setup_tools_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 5px;")
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel("Windows System Tools Installer")
        info_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_layout.addWidget(info_label)
        info_layout.addWidget(QLabel("Easily install essential developer and system tools using Winget."))
        layout.addWidget(info_frame)

        self.tools_tree = QTreeWidget()
        self.tools_tree.setHeaderLabels(["Tool", "Status", "Description"])
        self.tools_tree.setAlternatingRowColors(True)
        self.tools_tree.setColumnWidth(0, 250)
        self.tools_tree.setColumnWidth(1, 120)
        self.tools_tree.setStyleSheet("QTreeWidget::item { padding: 5px; }")
        layout.addWidget(self.tools_tree)
        
        config_path = os.path.join(self.project_root, "config", "system_tools.json")
        self.tools_installer = SystemToolsInstaller(config_path)
        self.populate_tools_tree()
        
        selection_btns = QHBoxLayout()
        all_btn = QPushButton("Select All")
        all_btn.clicked.connect(lambda _: self.toggle_tools_selection(True))
        none_btn = QPushButton("Deselect All")
        none_btn.clicked.connect(lambda _: self.toggle_tools_selection(False))
        selection_btns.addWidget(all_btn)
        selection_btns.addWidget(none_btn)
        layout.addLayout(selection_btns)

        btn_layout = QHBoxLayout()
        check_btn = QPushButton("Refresh Tools Status")
        check_btn.setMinimumHeight(40)
        check_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        check_btn.clicked.connect(self.check_tools_status)
        install_btn = QPushButton("Install Selected Tools")
        install_btn.setMinimumHeight(40)
        install_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        install_btn.clicked.connect(self.install_tools)
        btn_layout.addWidget(check_btn)
        btn_layout.addWidget(install_btn)
        layout.addLayout(btn_layout)
        self.content_stack.addWidget(page)

    def toggle_tools_selection(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        iterator = QTreeWidgetItemIterator(self.tools_tree)
        while iterator.value():
            item = iterator.value()
            if item.parent(): # Only leaf nodes
                item.setCheckState(0, state)
            iterator += 1

    def populate_tools_tree(self):
        categories = {}
        for tool in self.tools_installer.tools.values():
            cat_name = tool.category.value
            if cat_name not in categories:
                cat_item = QTreeWidgetItem(self.tools_tree, [cat_name])
                categories[cat_name] = cat_item
            child = QTreeWidgetItem(categories[cat_name], [tool.name, "Unknown", tool.description])
            child.setCheckState(0, Qt.CheckState.Unchecked)
            child.setData(0, Qt.ItemDataRole.UserRole, tool.id)

    def check_tools_status(self):
        self.log_signal.emit("Checking tools status in background...", "info")
        
        def run_check():
            try:
                results = {}
                iterator = QTreeWidgetItemIterator(self.tools_tree)
                while iterator.value():
                    item = iterator.value()
                    tool_id = item.data(0, Qt.ItemDataRole.UserRole)
                    if tool_id in self.tools_installer.tools:
                        tool = self.tools_installer.tools[tool_id]
                        is_inst = self.tools_installer.check_tool_status(tool)
                        results[tool_id] = is_inst
                    iterator += 1
                QTimer.singleShot(0, lambda: self._update_tools_tree(results))
            except Exception as e:
                logger.error(f"Error in tools status check: {e}")

        threading.Thread(target=run_check, daemon=True).start()

    def _update_tools_tree(self, results):
        iterator = QTreeWidgetItemIterator(self.tools_tree)
        while iterator.value():
            item = iterator.value()
            tool_id = item.data(0, Qt.ItemDataRole.UserRole)
            if tool_id in results:
                item.setText(1, "Installed" if results[tool_id] else "Not Installed")
                if results[tool_id]:
                    item.setForeground(1, Qt.GlobalColor.green)
                else:
                    item.setForeground(1, Qt.GlobalColor.gray)
            iterator += 1
        self.log_signal.emit("Tools status updated.", "success")

    def install_tools(self):
        selected_ids = []
        iterator = QTreeWidgetItemIterator(self.tools_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                tool_id = item.data(0, Qt.ItemDataRole.UserRole)
                if tool_id: selected_ids.append(tool_id)
            iterator += 1
        
        if not selected_ids: return
        
        self.log_signal.emit(f"Starting installation of {len(selected_ids)} tools...", "info")
        for tid in selected_ids:
            tool = self.tools_installer.tools[tid]
            self.log_signal.emit(f"Queued installation for {tool.name}", "debug")
            threading.Thread(target=self._install_tool_bg, args=(tool,), daemon=True).start()

    def _install_tool_bg(self, tool):
        self.log_signal.emit(f"Installing {tool.name}...", "info")
        for cmd in tool.install_commands:
            self.log_signal.emit(f"Executing: {cmd}", "debug")
            try:
                process = subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd], 
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                         text=True, shell=False, creationflags=CREATE_NO_WINDOW)
                for line in process.stdout:
                    if line.strip():
                        self.log_signal.emit(f"[{tool.name}] {line.strip()}", "debug")
                process.wait()
                if process.returncode != 0:
                    self.log_signal.emit(f"Command failed for {tool.name} with code {process.returncode}", "error")
            except Exception as e:
                self.log_signal.emit(f"Error installing {tool.name}: {e}", "error")
        self.tools_installer.check_tool_status(tool)
        if tool.is_installed:
            self.log_signal.emit(f"Successfully installed {tool.name}", "success")
        else:
            self.log_signal.emit(f"Installation of {tool.name} may have failed or requires restart.", "warning")
        if tool.post_install_message:
            self.log_signal.emit(f"[{tool.name}] {tool.post_install_message}", "info")

    def setup_passgen_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("Professional Password Generator")
        group_layout = QVBoxLayout()
        self.pass_length_label = QLabel("Password Length: 16")
        group_layout.addWidget(self.pass_length_label)
        self.pass_length_spin = QComboBox()
        self.pass_length_spin.addItems([str(i) for i in range(8, 65)])
        self.pass_length_spin.setCurrentText("16")
        self.pass_length_spin.currentTextChanged.connect(lambda v: self.pass_length_label.setText(f"Password Length: {v}"))
        group_layout.addWidget(self.pass_length_spin)
        self.pass_upper = QCheckBox("Include Uppercase Letters")
        self.pass_upper.setChecked(True)
        group_layout.addWidget(self.pass_upper)
        self.pass_digits = QCheckBox("Include Digits")
        self.pass_digits.setChecked(True)
        group_layout.addWidget(self.pass_digits)
        self.pass_special = QCheckBox("Include Special Characters")
        self.pass_special.setChecked(True)
        group_layout.addWidget(self.pass_special)
        gen_btn = QPushButton("Generate Secure Password")
        gen_btn.setFixedHeight(45)
        gen_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; font-size: 14px; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        gen_btn.clicked.connect(self.generate_password)
        group_layout.addWidget(gen_btn)
        self.generated_pass_entry = QLineEdit()
        self.generated_pass_entry.setPlaceholderText("Generated Password")
        self.generated_pass_entry.setReadOnly(True)
        self.generated_pass_entry.setStyleSheet("font-family: Consolas; font-size: 16px; padding: 10px; background: #252525;")
        group_layout.addWidget(self.generated_pass_entry)
        pass_actions = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda _: self.copy_to_clipboard(self.generated_pass_entry.text()))
        pass_actions.addWidget(copy_btn)
        self.pass_strength_label = QLabel("Strength: N/A")
        pass_actions.addWidget(self.pass_strength_label)
        group_layout.addLayout(pass_actions)
        self.pass_analysis = QTextEdit()
        self.pass_analysis.setReadOnly(True)
        self.pass_analysis.setFixedHeight(100)
        self.pass_analysis.setStyleSheet("background: #1e1e1e; color: #888;")
        group_layout.addWidget(self.pass_analysis)
        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        self.content_stack.addWidget(page)

    def generate_password(self):
        length = int(self.pass_length_spin.currentText())
        chars = string.ascii_lowercase
        if self.pass_upper.isChecked(): chars += string.ascii_uppercase
        if self.pass_digits.isChecked(): chars += string.digits
        if self.pass_special.isChecked(): chars += string.punctuation
        password = "".join(secrets.choice(chars) for _ in range(length))
        self.generated_pass_entry.setText(password)
        strength, analysis = self.check_password_strength(password)
        self.pass_strength_label.setText(f"Strength: {strength}")
        self.pass_analysis.setPlainText("\n".join(analysis))
        self.log_signal.emit(f"Generated a {strength} password.", "success")

    def check_password_strength(self, password):
        length = len(password)
        score = 0
        analysis = []
        if length >= 12: score += 2; analysis.append("✓ Excellent length")
        elif length >= 8: score += 1; analysis.append("✓ Good length")
        else: analysis.append("✗ Too short")
        if re.search(r"[A-Z]", password): score += 1; analysis.append("✓ Uppercase included")
        if re.search(r"[0-9]", password): score += 1; analysis.append("✓ Digits included")
        if re.search(r"[!@#$%^&*()_\+\-=\[\]{};':\",.<>/?|]", password): score += 1; analysis.append("✓ Special chars included")
        if score <= 2: strength = "Weak"
        elif score <= 4: strength = "Moderate"
        else: strength = "Strong"
        return strength, analysis

    def copy_to_clipboard(self, text):
        if text:
            pyperclip.copy(text)
            self.log_signal.emit("Copied to clipboard.", "info")

    def setup_vault_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.vault_stack = QStackedWidget()
        login_widget = QWidget()
        login_layout = QVBoxLayout(login_widget)
        login_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unlock_btn = QPushButton("Unlock Password Vault")
        unlock_btn.setFixedSize(250, 60)
        unlock_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 10px; font-size: 16px; border: 1px solid #2e46a9; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        unlock_btn.clicked.connect(self.unlock_vault)
        login_layout.addWidget(unlock_btn)
        self.vault_stack.addWidget(login_widget)
        self.vault_main_widget = QWidget()
        vault_layout = QVBoxLayout(self.vault_main_widget)
        form_group = QGroupBox("Secure Password Management")
        form_layout = QFormLayout()
        self.vault_site_entry = QLineEdit()
        self.vault_site_entry.setPlaceholderText("Site / App Name")
        self.vault_pass_entry = QLineEdit()
        self.vault_pass_entry.setPlaceholderText("Password")
        form_layout.addRow("Site:", self.vault_site_entry)
        form_layout.addRow("Password:", self.vault_pass_entry)
        save_btn = QPushButton("Save to Vault")
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        save_btn.clicked.connect(self.save_vault_entry)
        form_layout.addRow(save_btn)
        form_group.setLayout(form_layout)
        vault_layout.addWidget(form_group)
        self.vault_list = QListWidget()
        self.vault_list.itemClicked.connect(self.on_vault_item_clicked)
        vault_layout.addWidget(self.vault_list)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.setMinimumHeight(40)
        delete_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        delete_btn.clicked.connect(self.delete_vault_entry)
        vault_layout.addWidget(delete_btn)
        self.vault_stack.addWidget(self.vault_main_widget)
        layout.addWidget(self.vault_stack)
        self.content_stack.addWidget(page)

    def unlock_vault(self):
        config_dir = os.path.dirname(self.db_path)
        old_json = os.path.join(config_dir, "vault.json")
        old_salt = os.path.join(config_dir, "salt")
        
        is_new = not self.password_manager.exists()
        dlg = MasterPasswordDialog(is_new=is_new)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            password = dlg.password
            success = False
            
            if is_new:
                # Setup new SQLite vault
                if self.password_manager.initialize_vault(password):
                    success = True
                    # Check if we should migrate from old JSON format
                    if os.path.exists(old_json) and os.path.exists(old_salt):
                        self.log_signal.emit("Legacy vault found. Attempting migration...", "info")
                        if self.password_manager.migrate_from_json(old_json, old_salt, password):
                            self.log_signal.emit("Migration successful. Legacy files can be removed.", "success")
                            # We don't delete them automatically for safety, but they are now redundant
            else:
                # Unlock existing SQLite vault
                success = self.password_manager.unlock(password)
            
            if success:
                try:
                    ensure_private_file(self.db_path)
                except Exception:
                    pass
                self.refresh_vault_list()
                self.vault_stack.setCurrentIndex(1)
                self.log_signal.emit("Vault unlocked successfully.", "success")
            else:
                self.log_signal.emit("Failed to unlock vault. Check master password.", "error")
                QMessageBox.critical(self, "Unlock Failed", "Invalid master password or corrupted vault.")

    def refresh_vault_list(self):
        self.vault_list.clear()
        if self.password_manager:
            self.vault_list.addItems(self.password_manager.get_all_sites())

    def save_vault_entry(self):
        site = self.vault_site_entry.text().strip()
        pw = self.vault_pass_entry.text().strip()
        if site and pw and self.password_manager:
            if self.password_manager.save_password(site, pw):
                self.vault_site_entry.clear()
                self.vault_pass_entry.clear()
                self.refresh_vault_list()
                self.log_signal.emit(f"Saved password for {site}.", "success")
            else:
                self.log_signal.emit("Failed to save: Invalid characters detected.", "error")
                QMessageBox.warning(self, "Invalid Input", "Site or password contains unsupported characters.")

    def delete_vault_entry(self):
        item = self.vault_list.currentItem()
        if item and self.password_manager:
            site = item.text()
            if self.password_manager.delete_password(site):
                self.refresh_vault_list()
                self.log_signal.emit(f"Deleted password for {site}.", "warning")

    def on_vault_item_clicked(self, item):
        site = item.text()
        pw = self.password_manager.passwords.get(site, "")
        self.vault_site_entry.setText(site)
        self.vault_pass_entry.setText(pw)
        self.copy_to_clipboard(pw)
        self.log_signal.emit(f"Password for {site} copied to clipboard.", "info")

    def setup_tweaks_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #2d2d2d; border-radius: 5px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.addWidget(QLabel("System Performance & Privacy Tweaks"))
        info_layout.addWidget(QLabel("Select optimization tweaks to apply to your Windows installation."))
        layout.addWidget(info_frame)

        self.tweaks = {
            "delete_temp": QCheckBox("Delete Temporary Files"),
            "disable_telemetry": QCheckBox("Disable Telemetry"),
            "disable_activity": QCheckBox("Disable Activity History"),
            "disable_gamedvr": QCheckBox("Disable GameDVR"),
            "disable_hibernation": QCheckBox("Disable Hibernation"),
            "disable_homegroup": QCheckBox("Disable HomeGroup"),
            "prefer_ipv4": QCheckBox("Prefer IPv4 over IPv6"),
            "disable_location": QCheckBox("Disable Location Tracking"),
            "disable_storage_sense": QCheckBox("Disable Storage Sense"),
            "disable_wifi_sense": QCheckBox("Disable Wi-Fi Sense"),
            "enable_end_task": QCheckBox("Enable End Task With Right Click"),
            "set_services_manual": QCheckBox("Set Unnecessary Services to Manual"),
            "ultimate_performance": QCheckBox("Enable Ultimate Performance power plan"),
            "disable_web_search": QCheckBox("Disable Start Menu web search"),
            "classic_context_menu": QCheckBox("Windows 11 classic context menu"),
            "disable_ad_id": QCheckBox("Disable Advertising ID"),
            "disable_spotlight": QCheckBox("Disable Lock Screen Spotlight"),
            "disable_copilot": QCheckBox("Disable Windows Copilot"),
            "disable_news": QCheckBox("Disable News and Interests"),
            "show_file_ext": QCheckBox("Show file extensions"),
            "show_hidden": QCheckBox("Show hidden files (incl. protected)"),
        }

        # Categories mapping
        categories = {
            "Privacy & Security": ["disable_telemetry", "disable_activity", "disable_location", "disable_wifi_sense", "disable_web_search", "disable_ad_id", "disable_spotlight"],
            "System Performance": ["delete_temp", "disable_gamedvr", "disable_hibernation", "disable_storage_sense", "prefer_ipv4", "ultimate_performance"],
            "Interface & Services": ["enable_end_task", "disable_homegroup", "set_services_manual", "classic_context_menu", "disable_copilot", "disable_news", "show_file_ext", "show_hidden"]
        }

        for cat_name, tweak_keys in categories.items():
            group = QGroupBox(cat_name)
            group.setStyleSheet("QGroupBox { font-weight: bold; color: #4158D0; }")
            group_layout = QVBoxLayout()
            for key in tweak_keys:
                if key in self.tweaks:
                    group_layout.addWidget(self.tweaks[key])
            group.setLayout(group_layout)
            layout.addWidget(group)

        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda _: self.toggle_all_tweaks(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda _: self.toggle_all_tweaks(False))
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        layout.addLayout(btn_layout)

        confirm_btn = QPushButton("Apply Selected Tweaks")
        confirm_btn.setMinimumHeight(45)
        confirm_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        confirm_btn.clicked.connect(self.confirm_changes)
        layout.addWidget(confirm_btn)
        
        layout.addStretch()
        scroll.setWidget(page)
        self.content_stack.addWidget(scroll)

    def toggle_all_tweaks(self, checked):
        for cb in self.tweaks.values():
            cb.setChecked(checked)

    def setup_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info_label = QLabel("Ghosty Tool v5.0.6")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        info_label.setStyleSheet("color: #4158D0; margin-top: 20px;")
        layout.addWidget(info_label)

        sub_label = QLabel("The Ultimate Windows Optimization & Security Suite")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        sub_label.setStyleSheet("color: #888; margin-bottom: 20px;")
        layout.addWidget(sub_label)

        features_group = QGroupBox("What's New in v5.0.6")
        features_layout = QVBoxLayout()
        features_text = QLabel(
            "• 🛡️ <b>Security Hardening:</b> Full audit with Bandit & pip-audit.<br>"
            "• 🔐 <b>ShadowKeys 2.1:</b> Robust SQLite-backed vault with AES-256 encryption, PBKDF2 verification, and automated legacy migration.<br>"
            "• 👤 <b>Least Privilege:</b> Starts as standard user; elevate only when needed.<br>"
            "• 🚀 <b>Auto-Deploy:</b> Automated high-performance EXE builds via GitHub Actions.<br>"
            "• 💻 <b>Cross-Platform:</b> Core logic now safe for Windows, Linux, and macOS.<br>"
            "• 🧩 <b>New Tweaks:</b> Disable Copilot/News & Interests; show file extensions/hidden files.<br>"
            "• 📦 <b>Installer:</b> Added 7-Zip, VLC, Brave, Discord, HWiNFO, CPU-Z."
        )
        features_text.setTextFormat(Qt.TextFormat.RichText)
        features_text.setWordWrap(True)
        features_text.setStyleSheet("padding: 10px; line-height: 1.5;")
        features_layout.addWidget(features_text)
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)

        thanks_label = QLabel('A big thank you to <a href="https://github.com/haywardgg" style="color: #4158D0; text-decoration: none;">haywardgg</a> for pushing me on my project and inspiring me with new ideas.<br>This project would not be as great as it is without him.')
        thanks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thanks_label.setOpenExternalLinks(True)
        thanks_label.setWordWrap(True)
        thanks_label.setStyleSheet("color: #888; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(thanks_label)
        links_layout = QHBoxLayout()
        github_btn = QPushButton("GitHub")
        github_btn.setIcon(QIcon(os.path.join(self.project_root, "images", "GithubLogo.png")))
        github_btn.clicked.connect(lambda _: webbrowser.open("https://github.com/Ghostshadowplays/Ghosty-Tools")) 
        twitch_btn = QPushButton("Twitch")
        twitch_btn.setIcon(QIcon(os.path.join(self.project_root, "images", "twitchlogo.png")))
        twitch_btn.clicked.connect(lambda _: webbrowser.open("https://www.twitch.tv/ghostshadow_plays"))
        update_btn = QPushButton("Check for Updates")
        update_btn.clicked.connect(lambda _: self.check_for_updates(True))
        links_layout.addWidget(github_btn)
        links_layout.addWidget(twitch_btn)
        links_layout.addWidget(update_btn)
        layout.addLayout(links_layout)
        layout.addStretch()
        self.content_stack.addWidget(page)


    def check_for_whats_new(self):
        """Shows a one-time 'What's New' popup after an update."""
        last_version = self.update_manager.get_last_seen_version()
        
        # If we have a stored version and it's different from current, we just updated
        if last_version and last_version != self.update_manager.current_version:
            def show_dialog():
                release_info = self.update_manager.get_release_info()
                notes = release_info.get("body", "No release notes available.") if release_info else "Check GitHub for full release notes."
                
                # Custom dialog for better formatting of release notes
                dlg = QDialog(self)
                dlg.setWindowTitle(f"What's New in {self.update_manager.current_version}")
                dlg.setMinimumSize(500, 400)
                vbox = QVBoxLayout(dlg)
                
                title = QLabel(f"Ghosty Tool updated to {self.update_manager.current_version}!")
                title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                title.setStyleSheet("color: #4158D0;")
                vbox.addWidget(title)
                
                vbox.addWidget(QLabel("Here are the latest changes:"))
                
                notes_area = QTextEdit()
                notes_area.setReadOnly(True)
                notes_area.setPlainText(notes)
                vbox.addWidget(notes_area)
                
                btn = QPushButton("Got it!")
                btn.setMinimumHeight(40)
                btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
                btn.clicked.connect(dlg.accept)
                vbox.addWidget(btn)
                
                dlg.exec()

            # Run in a small delay to ensure UI is fully up
            QTimer.singleShot(500, show_dialog)
            
        # Always acknowledge the current version so we don't show it again for this version
        self.update_manager.acknowledge_current_version()

    def check_for_updates(self, manual=False):
        try:
            update_info = self.update_manager.check_for_updates()
        except Exception as e:
            self.log_signal.emit(f"Update check failed: {e}", "warning")
            return
        self._latest_update_info = update_info
        if update_info.get("available"):
            # Update available: show subtle red button on Dashboard
            if hasattr(self, "update_status_btn"):
                self.update_status_btn.setText("Update available")
                self.update_status_btn.setEnabled(True)
                self.update_status_btn.setStyleSheet("color: #e74c3c; font-size: 11px;")
            if manual:
                self.log_signal.emit(f"Update {update_info.get('latest_version')} available — open Dashboard to apply.", "info")
        else:
            # Fully updated: show green text and disable click
            if hasattr(self, "update_status_btn"):
                self.update_status_btn.setText("Fully updated")
                self.update_status_btn.setEnabled(False)
                self.update_status_btn.setStyleSheet("color: #2ecc71; font-size: 11px;")
            if manual:
                self.log_signal.emit("You are already using the latest version.", "success")

    def on_update_status_clicked(self):
        if self._latest_update_info and self._latest_update_info.get("available"):
            # Safety check for source installations
            if not getattr(sys, 'frozen', False):
                msg = ("You are running from source code. Automatic updates are optimized for the packaged (.exe) version.\n\n"
                       "Do you want to open the GitHub releases page to download the latest version manually?")
                res = QMessageBox.question(self, "Update Source Code?", msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                
                if res == QMessageBox.StandardButton.Yes:
                    webbrowser.open(self._latest_update_info.get("download_url", "https://github.com/Ghostshadowplays/Ghosty-Tools/releases"))
                    return
                elif res == QMessageBox.StandardButton.Cancel:
                    return
                # If No, we proceed to download but apply_update will handle it safely
            
            self.start_update_download(self._latest_update_info)
        else:
            # If clicked when no update, trigger a quick re-check
            self.check_for_updates(True)

    def start_update_download(self, update_info):
        # Find the EXE asset if available
        download_url = None
        for asset in update_info.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            self.log_signal.emit("No executable asset found in the latest release. Opening GitHub releases page...", "warning")
            webbrowser.open(update_info.get("html_url", "https://github.com/Ghostshadowplays/Ghosty-Tools/releases"))
            return
        
        target_path = os.path.join(get_config_dir(), "update_package.exe")
        
        self.update_dialog = QDialog(self)
        self.update_dialog.setWindowTitle("Downloading Update")
        self.update_dialog.setFixedSize(300, 100)
        vbox = QVBoxLayout(self.update_dialog)
        self.update_progress = QProgressBar()
        vbox.addWidget(QLabel("Downloading latest version..."))
        vbox.addWidget(self.update_progress)
        
        self.update_worker = UpdateWorker(download_url, target_path)
        self.update_worker.progress.connect(self.update_progress.setValue)
        self.update_worker.finished.connect(self._on_update_download_finished)
        self.update_worker.start()
        self.update_dialog.exec()

    def _on_update_download_finished(self, success, result):
        self.update_dialog.close()
        if success:
            QMessageBox.information(self, "Download Complete", "Update downloaded. The application will now close to apply the update.")
            self.apply_update(result)
        else:
            QMessageBox.critical(self, "Update Error", f"Failed to download update: {result}")

    def apply_update(self, new_file):
        is_frozen = getattr(sys, 'frozen', False)
        current_file = sys.executable if is_frozen else os.path.abspath(sys.argv[0])
        
        # Critical Safety: Don't overwrite .py files with downloaded updates (usually .exe)
        if not is_frozen and current_file.lower().endswith(".py"):
            self.log_signal.emit(f"Update downloaded to {new_file}. Manual update required for source installations.", "warning")
            QMessageBox.information(self, "Update Downloaded", 
                                   f"The update has been downloaded to:\n{new_file}\n\n"
                                   "Since you are running from source, please replace your files manually or run the new version directly.\n"
                                   "The source files will not be automatically overwritten to prevent data loss.")
            # Open the folder containing the new file
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(new_file)], creationflags=CREATE_NO_WINDOW)
            except Exception:
                pass
            return

        # Launch updater via PowerShell for frozen (EXE) installations
        # This is more reliable for Windows EXEs as it doesn't depend on a bundled script or interpreter
        if is_frozen:
            if not new_file.lower().endswith(".exe"):
                QMessageBox.warning(self, "Update Error", "The downloaded update is not an executable file. Please update manually.")
                return

            # Prepare environment without PyInstaller variables to ensure the new process extracts itself correctly
            env = os.environ.copy()
            for key in list(env.keys()):
                if key == '_MEIPASS' or key.startswith('PYI'):
                    env.pop(key, None)
            
            # Clean PATH of any _MEI references to prevent loading DLLs from the wrong temp folder
            if 'PATH' in env:
                paths = env['PATH'].split(os.pathsep)
                env['PATH'] = os.pathsep.join([p for p in paths if '_MEI' not in p])

            # Use a more robust PowerShell script that also explicitly clears session variables
            ps_command = (
                f'$env:_MEIPASS = $null; '
                f'$env:PATH = ($env:PATH -split ";" | Where-Object {{ $_ -notmatch "_MEI" }}) -join ";"; '
                f'Start-Sleep -Seconds 5; '
                f'if (Test-Path -LiteralPath "{current_file}") {{ Remove-Item -LiteralPath "{current_file}" -Force -ErrorAction SilentlyContinue }}; '
                f'Move-Item -LiteralPath "{new_file}" -Destination "{current_file}" -Force; '
                f'Start-Process -FilePath "{current_file}"'
            )
            
            try:
                self.log_signal.emit("Launching PowerShell updater...", "info")
                subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_command], 
                                 creationflags=CREATE_NO_WINDOW,
                                 env=env)
                sys.exit(0)
            except Exception as e:
                logger.error(f"Failed to launch PowerShell updater: {e}")
                QMessageBox.warning(self, "Update Error", f"Failed to launch automatic updater: {e}\n\nPlease update manually.")
        else:
            # Fallback for non-frozen, non-py (shouldn't happen with current logic but for safety)
            QMessageBox.warning(self, "Update Error", "Automatic update is only supported for the packaged (.exe) version. Please update manually.")

    def update_system_usage(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        self.usage_label.setText(f"CPU: {cpu}% | RAM: {ram}%")

    def update_battery_health(self):
        try:
            battery = psutil.sensors_battery()
            if battery:
                self.battery_label.setText(f"Charge: {battery.percent}% | Power Plugged: {battery.power_plugged}")
                self.log_signal.emit(f"Battery status updated: {battery.percent}%", "debug")
            else:
                self.battery_label.setText("No battery detected.")
        except Exception as e:
            logger.error(f"Error checking battery: {e}")

    def check_disk_health(self):
        if not self.main_disk:
            self.disk_label.setText("Main disk ID not found.")
            return
        self.log_signal.emit(f"Checking health for disk {self.main_disk}...", "info")
        self.disk_label.setText("Checking...")
        
        cmd = f"Get-Disk -Number {self.main_disk} | Select-Object -ExpandProperty HealthStatus"
        self.health_worker = GenericCommandWorker("Disk Health", cmd)
        self.health_worker.finished.connect(self._on_disk_health_finished)
        self.health_worker.start()

    def _on_disk_health_finished(self, success, status):
        status = status.strip()
        if not success:
            display_status = "Error/Failed"
        else:
            display_status = status if status else "Healthy"
        
        self.disk_label.setText(f"Disk {self.main_disk} Health: {display_status}")
        self.log_signal.emit(f"Disk {self.main_disk} health status: {display_status}", "success" if "Healthy" in display_status or not status else "warning")

    def run_speed_test(self):
        self.log_signal.emit("Starting network speed test. Please wait...", "info")
        self.speed_label.setText("Testing...")
        self.speed_thread = SpeedTestWorker()
        self.speed_thread.result_ready.connect(self._on_speed_test_result)
        self.speed_thread.error_occurred.connect(self._on_speed_test_error)
        self.speed_thread.start()

    def _on_speed_test_result(self, res):
        self.speed_label.setText(res)
        self.log_signal.emit(f"Speed test completed:\n{res}", "success")

    def _on_speed_test_error(self, err):
        self.speed_label.setText(f"Error: {err}")
        self.log_signal.emit(f"Speed test failed: {err}", "error")

    def flush_dns(self):
        self.log_signal.emit("Flushing DNS cache...", "info")
        try:
            subprocess.run(["ipconfig", "/flushdns"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
            self.log_signal.emit("DNS Cache flushed successfully.", "success")
            QMessageBox.information(self, "DNS Flush", "DNS Cache flushed successfully.")
        except Exception as e:
            logger.error(f"Error flushing DNS: {e}")
            self.log_signal.emit(f"Failed to flush DNS: {e}", "error")

    def get_physical_disks(self):
        try:
            ps_command = "Get-PhysicalDisk | Select-Object DeviceID, FriendlyName, Size, MediaType | ConvertTo-Json"
            result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            if not result.stdout.strip(): return []
            disks = json.loads(result.stdout)
            return disks if isinstance(disks, list) else [disks]
        except Exception as e:
            logger.error(f"Error getting physical disks: {e}")
            return []

    def refresh_disk_list(self):
        self.disk_combo.clear()
        disks = self.get_physical_disks()
        for d in disks:
            size_gb = int(d['Size']) // (1024**3)
            self.disk_combo.addItem(f"Disk {d['DeviceID']}: {d['FriendlyName']} ({size_gb}GB, {d['MediaType']})", d['DeviceID'])

    def validate_mbr2gpt(self):
        disk_id = self.disk_combo.currentData()
        if disk_id is None: return
        self.log_signal.emit(f"Starting MBR2GPT Validation for Disk {disk_id}...", "info")
        cmd = f"mbr2gpt /validate /disk:{disk_id} /allowfullos"
        self.maint_worker = GenericCommandWorker("MBR2GPT Validate", cmd)
        self.maint_worker.output.connect(self.log_to_terminal)
        self.maint_worker.finished.connect(lambda s, m: self.log_signal.emit(m if m else "Validation finished successfully.", "success" if s else "error"))
        self.maint_worker.start()

    def convert_mbr2gpt(self):
        disk_id = self.disk_combo.currentData()
        if disk_id is None: return
        reply = QMessageBox.critical(self, "WARNING", f"Are you sure you want to CONVERT Disk {disk_id} to GPT?\n\nThis is a high-risk operation. Backup your data first!", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.log_signal.emit(f"Starting MBR2GPT Conversion for Disk {disk_id}...", "warning")
            cmd = f"mbr2gpt /convert /disk:{disk_id} /allowfullos"
            self.maint_worker = GenericCommandWorker("MBR2GPT Convert", cmd)
            self.maint_worker.output.connect(self.log_to_terminal)
            self.maint_worker.finished.connect(lambda s, m: self.log_signal.emit((m if m else "Conversion process finished.") + "\nRESTART AND CHANGE BIOS TO UEFI!", "success" if s else "error"))
            self.maint_worker.start()

    def run_system_maintenance(self):
        self.log_signal.emit("Starting full system maintenance...", "info")
        self.maint_thread = MaintenanceWorker(self.system_drive, False)
        self.maint_thread.output.connect(self.log_to_terminal)
        self.maint_thread.finished.connect(self._on_maintenance_finished)
        self.maint_thread.start()

    def _on_maintenance_finished(self, res):
        self.log_signal.emit(res, "success")
        QMessageBox.information(self, "Maintenance", res)

    def run_disk_cleanup(self):
        self.log_signal.emit("Launching Disk Cleanup...", "info")
        try:
            subprocess.Popen(["cleanmgr", "/d", "C"], shell=False, creationflags=CREATE_NO_WINDOW)
        except Exception as e:
            logger.error(f"Error launching disk cleanup: {e}")
            self.log_signal.emit(f"Failed to launch Disk Cleanup: {e}", "error")

    def run_windows_update_check(self):
        self.log_signal.emit("Checking for Windows Updates...", "info")
        self.update_status.setText("Status: Checking...")
        threading.Thread(target=self._update_check_thread, daemon=True).start()

    def _update_check_thread(self):
        try:
            ps_script = "$UpdateSession = New-Object -ComObject Microsoft.Update.Session; $UpdateSearcher = $UpdateSession.CreateUpdateSearcher(); $SearchResult = $UpdateSearcher.Search('IsInstalled=0 and IsHidden=0'); $SearchResult.Updates.Count"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, shell=False, creationflags=CREATE_NO_WINDOW)
            count = res.stdout.strip()
            self.update_status.setText(f"Status: {count} updates found")
            self.log_signal.emit(f"Windows update check finished: {count} updates found.", "info")
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            self.log_signal.emit(f"Windows update check failed: {e}", "error")

    def install_windows_updates(self):
        self.log_signal.emit("Initiating Windows Update installation (GUI)...", "info")
        subprocess.run(["control", "update"], shell=False, creationflags=CREATE_NO_WINDOW)

    def create_restore_point(self):
        self.log_signal.emit("Creating System Restore Point...", "info")
        try:
            cmd = 'Checkpoint-Computer -Description "GhostyTool Restore Point" -RestorePointType "MODIFY_SETTINGS"'
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
            self.log_signal.emit("System Restore Point created successfully.", "success")
            QMessageBox.information(self, "Restore Point", "System Restore Point created successfully.")
        except Exception as e:
            logger.error(f"Error creating restore point: {e}")
            self.log_signal.emit(f"Failed to create System Restore Point: {e}", "error")
            QMessageBox.critical(self, "Error", f"Failed to create restore point: {e}")

    def toggle_windows_theme(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_ALL_ACCESS)
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            new_value = 0 if value == 1 else 1
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_value)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_value)
            winreg.CloseKey(key)
            self.log_signal.emit(f"Windows theme toggled to {'Light' if new_value == 1 else 'Dark'} mode.", "success")
        except Exception as e:
            logger.error(f"Error toggling theme: {e}")

    def confirm_changes(self):
        selected = [name for name, cb in self.tweaks.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select at least one tweak.")
            return
        
        reply = QMessageBox.question(self, "Confirm Changes", f"Apply {len(selected)} selected tweaks?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.log_signal.emit(f"Applying {len(selected)} selected tweaks...", "info")
            for name in selected:
                self.log_signal.emit(f"Applying tweak: {name}", "debug")
                if name == "delete_temp": self._delete_temp_files()
                elif name == "disable_telemetry": self._disable_telemetry()
                elif name == "disable_activity": self._disable_activity_history()
                elif name == "disable_gamedvr": self._disable_gamedvr()
                elif name == "disable_hibernation": self._disable_hibernation()
                elif name == "disable_homegroup": self._disable_homegroup()
                elif name == "prefer_ipv4": self._prefer_ipv4()
                elif name == "disable_location": self._disable_location_tracking()
                elif name == "disable_storage_sense": self._disable_storage_sense()
                elif name == "disable_wifi_sense": self._disable_wifi_sense()
                elif name == "enable_end_task": self._enable_end_task()
                elif name == "ultimate_performance": self._enable_ultimate_performance()
                elif name == "disable_web_search": self._disable_web_search()
                elif name == "classic_context_menu": self._enable_classic_context_menu()
                elif name == "disable_ad_id": self._disable_advertising_id()
                elif name == "disable_spotlight": self._disable_spotlight()
                elif name == "disable_copilot": self._disable_copilot()
                elif name == "disable_news": self._disable_news_and_interests()
                elif name == "show_file_ext": self._show_file_extensions()
                elif name == "show_hidden": self._show_hidden_files()
                elif name == "set_services_manual": 
                    self._set_services_to_manual(["DiagTrack", "dmwappushservice", "RemoteRegistry"])
            self.log_signal.emit("Selected tweaks applied successfully.", "success")
            QMessageBox.information(self, "Success", "Selected tweaks applied successfully.")

    def _delete_temp_files(self):
        import shutil
        temp_dirs = [os.environ.get('TEMP'), r'C:\Windows\Temp']
        for d in temp_dirs:
            if not d or not os.path.exists(d): continue
            for item in os.listdir(d):
                item_path = os.path.join(d, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path): os.unlink(item_path)
                    elif os.path.isdir(item_path): shutil.rmtree(item_path)
                except Exception as e:
                    logger.debug(f"Failed to delete {item_path}: {e}")

    def _disable_telemetry(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection")
            winreg.SetValueEx(key, "AllowTelemetry", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Telemetry tweak failed: {e}")

    def _disable_activity_history(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\System")
            winreg.SetValueEx(key, "EnableActivityFeed", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Activity history tweak failed: {e}")

    def _disable_gamedvr(self):
        try:
            key1 = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore")
            winreg.SetValueEx(key1, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key1)
            key2 = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\GameDVR")
            winreg.SetValueEx(key2, "AllowGameDVR", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key2)
        except Exception as e: logger.error(f"GameDVR tweak failed: {e}")

    def _disable_hibernation(self):
        try: subprocess.run(["powercfg", "-h", "off"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
        except Exception as e: logger.error(f"Hibernation tweak failed: {e}")

    def _disable_homegroup(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\CLSID\{B4FB3F98-C1EA-428d-A78A-D1F5659CBA93}\ShellFolder")
            winreg.SetValueEx(key, "Attributes", 0, winreg.REG_DWORD, 0xb094010c)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"HomeGroup tweak failed: {e}")

    def _prefer_ipv4(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters")
            winreg.SetValueEx(key, "DisabledComponents", 0, winreg.REG_DWORD, 0x20)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"IPv4 preference tweak failed: {e}")

    def _disable_location_tracking(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors")
            winreg.SetValueEx(key, "DisableLocation", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Location tracking tweak failed: {e}")

    def _disable_storage_sense(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy")
            winreg.SetValueEx(key, "01", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Storage Sense tweak failed: {e}")

    def _disable_wifi_sense(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config")
            winreg.SetValueEx(key, "AutoConnectAllowedOEM", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Wi-Fi Sense tweak failed: {e}")

    def _enable_end_task(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced")
            winreg.SetValueEx(key, "TaskbarEndTask", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"End Task tweak failed: {e}")

    def _set_services_to_manual(self, services):
        for service in services:
            try: subprocess.run(["sc", "config", service, "start=", "demand"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
            except Exception as e: logger.error(f"Failed to set service {service} to manual: {e}")


    def _enable_ultimate_performance(self):
        try:
            subprocess.run(["powercfg", "-duplicatescheme", "e9a42b02-d5df-448d-aa00-03f14749eb61"], shell=False, check=False, creationflags=CREATE_NO_WINDOW)
            subprocess.run(["powercfg", "-setactive", "e9a42b02-d5df-448d-aa00-03f14749eb61"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
        except Exception as e:
            logger.error(f"Ultimate Performance plan tweak failed: {e}")

    def _disable_web_search(self):
        try:
            # Disable Bing web search in Start
            key1 = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Search")
            winreg.SetValueEx(key1, "BingSearchEnabled", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key1, "CortanaConsent", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key1)
            # Disable SearchBox suggestions via policy
            key2 = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Policies\\Microsoft\\Windows\\Explorer")
            winreg.SetValueEx(key2, "DisableSearchBoxSuggestions", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key2)
        except Exception as e:
            logger.error(f"Disable web search tweak failed: {e}")

    def _enable_classic_context_menu(self):
        try:
            clsid = r"Software\\Classes\\CLSID\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\\InprocServer32"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, clsid)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "")
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"Classic context menu tweak failed: {e}")

    def _disable_advertising_id(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo")
            winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"Disable Advertising ID tweak failed: {e}")

    def _disable_spotlight(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Policies\\Microsoft\\Windows\\CloudContent")
            winreg.SetValueEx(key, "DisableWindowsSpotlightFeatures", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"Disable Spotlight tweak failed: {e}")


    def _disable_copilot(self):
        try:
            if winreg is None:
                return
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot")
            winreg.SetValueEx(key, "TurnOffWindowsCopilot", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            key2 = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced")
            winreg.SetValueEx(key2, "ShowCopilotButton", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key2)
        except Exception as e:
            logger.error(f"Disable Copilot tweak failed: {e}")

    def _disable_news_and_interests(self):
        try:
            if winreg is None:
                return
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\Windows Feeds")
            winreg.SetValueEx(key, "EnableFeeds", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            key2 = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Feeds")
            winreg.SetValueEx(key2, "ShellFeedsTaskbarViewMode", 0, winreg.REG_DWORD, 2)
            winreg.CloseKey(key2)
        except Exception as e:
            logger.error(f"Disable News & Interests tweak failed: {e}")

    def _show_file_extensions(self):
        try:
            if winreg is None:
                return
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced")
            winreg.SetValueEx(key, "HideFileExt", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"Show file extensions tweak failed: {e}")

    def _show_hidden_files(self):
        try:
            if winreg is None:
                return
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced")
            winreg.SetValueEx(key, "Hidden", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ShowSuperHidden", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"Show hidden files tweak failed: {e}")
