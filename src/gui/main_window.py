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
import shutil
import platform
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QCheckBox, QGroupBox, 
                             QScrollArea, QMessageBox, QProgressBar, QStackedWidget,
                             QFrame, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QTreeWidgetItemIterator, QComboBox, QTextEdit, QLineEdit, QDialog, QFormLayout,
                             QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QTextCursor, QTextCharFormat
import psutil
try:
    import winreg
except Exception:
    winreg = None 
import pyperclip

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
CREATE_NEW_CONSOLE = 0x00000010
import zipfile
import requests
from PIL import Image

# Internal imports
from src.core.workers import (
    SpeedTestWorker,
    MaintenanceWorker,
    GenericCommandWorker,
    SecurityScanWorker,
    BloatScanWorker,
    UpdateCheckWorker,
    ReleaseInfoWorker,
    SensorWorker,
    SpecsWorker,
    MainDiskWorker,
    MonitoringSetupWorker,
    DownloadWorker,
    NetworkWorker,
    TaskManagerWorker,
    PrivacyAuditWorker
)
from src.core.password_manager import PasswordManager
from src.core.bloat_remover import BloatRemover, BloatwareCategory, SafetyLevel
from src.core.system_tools_installer import SystemToolsInstaller, ToolCategory
from src.core.security_scanner import SecurityScanner
from src.core.update_manager import UpdateManager, UpdateWorker
from src.core.diagnostics import Diagnostics
from src.gui.dialogs import MasterPasswordDialog, HostsEditorDialog
from src.utils.helpers import is_admin, elevate_privileges, get_config_dir, ensure_private_file, get_resource_path, get_logs_dir, get_os_info
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction

logger = logging.getLogger(__name__)

class GhostyTool(QMainWindow):
    log_signal = pyqtSignal(str, str)
    cleanup_item_signal = pyqtSignal(str, dict)
    status_update_signal = pyqtSignal(object, bool) # (QTreeWidgetItem, is_installed)
    scan_cleanup_signal = pyqtSignal()
    check_tools_signal = pyqtSignal(bool) # force
    finish_cleanup_signal = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.project_root = get_resource_path("")
        self.setWindowTitle("Ghosty Tool - Professional System Utility")
        self.setGeometry(100, 100, 900, 750)
        
        icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.log_signal.connect(self.log_to_terminal)
        self.cleanup_item_signal.connect(self._add_cleanup_item)
        self.status_update_signal.connect(self._perform_status_update)
        self.scan_cleanup_signal.connect(self.scan_cleanup_items)
        self.check_tools_signal.connect(self.check_tools_status)
        self.finish_cleanup_signal.connect(self._finish_cleanup_scan)

        self.main_disk = "0"
        self.system_drive = "C"
        
        # Async disk identification
        self.disk_id_worker = MainDiskWorker()
        self.disk_id_worker.finished.connect(self._on_disk_identified)
        self.disk_id_worker.start()

        config_dir = get_config_dir()
        self.db_path = os.path.join(config_dir, "vault.db")
        self.password_manager = PasswordManager(self.db_path)

        # Clipboard security
        self.clipboard_timer = QTimer()
        self.clipboard_timer.setSingleShot(True)
        self.clipboard_timer.timeout.connect(self.clear_clipboard)

        # Initialize Update Manager
        self.update_manager = UpdateManager()
        self.diagnostics = Diagnostics(self.update_manager.current_version)
        self._latest_update_info = None

        self.init_ui()
        self.init_tray()
        
        QTimer.singleShot(1000, self.check_for_updates)
        QTimer.singleShot(2000, self.check_for_whats_new)

        # Timer for system usage updates
        self.usage_timer = QTimer()
        self.usage_timer.timeout.connect(self.update_system_usage)
        self.usage_timer.start(2000)
        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self.update_sensor_panel)
        self.sensor_timer.start(2000)

    def _on_disk_identified(self, main_disk, system_drive):
        self.main_disk = main_disk
        self.system_drive = system_drive
        logger.info(f"Main system disk identified as Disk {self.main_disk} (Drive {self.system_drive}:)")


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
        self.add_nav_button("Network", 3)
        self.add_nav_button("Processes", 4)
        self.add_nav_button("Privacy", 5)
        self.add_nav_button("Debloat", 6)
        self.add_nav_button("Install", 7)
        self.add_nav_button("Cleanup", 8)
        self.add_nav_button("Advanced Tools", 9)
        self.add_nav_button("Passwords", 10)
        self.add_nav_button("Tweaks", 11)
        self.add_nav_button("About", 12)

        self.sidebar_layout.addStretch()

        # Theme toggle in sidebar
        self.dark_mode_btn = QPushButton("Toggle Theme")
        self.dark_mode_btn.clicked.connect(self.toggle_windows_theme)
        self.sidebar_layout.addWidget(self.dark_mode_btn)

        # Platform check - Custom Linux GUI
        if sys.platform != 'win32':
            # Hide Windows-specific tabs
            for i in [6, 11]:
                if i < len(self.nav_buttons):
                    self.nav_buttons[i].setVisible(False)
            
            self.dark_mode_btn.setVisible(False)
            
            # Update labels for Linux to be more generic
            self.nav_buttons[1].setText("System Maintenance")
            self.nav_buttons[8].setText("System Cleanup")
            
            # Branding update for Linux
            title_label.setText("GHOSTY TOOLS 🐧")

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
        self.terminal_output.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
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
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4158D0, stop:1 #C850C0);
                border-radius: 6px;
            }
        """)
        self.progress_bar.hide()
        terminal_layout.addWidget(self.progress_bar)
        
        self.right_layout.addWidget(self.terminal_container)
        self.main_layout.addWidget(self.right_container)

        self.setup_dashboard_page()
        self.setup_maintenance_page()
        self.setup_security_page()
        self.setup_network_page()
        self.setup_processes_page()
        self.setup_privacy_page()
        self.setup_debloat_page()
        self.setup_tools_page()
        self.setup_cleanup_page()
        self.setup_advanced_tools_page()
        self.setup_password_page()
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
        if message is None:
            return
            
        # Handle multi-line messages by recursing for each line
        if "\n" in message:
            for line in message.splitlines():
                self.log_to_terminal(line, level)
            return
        
        # Pre-clean message from corrupted encoding characters
        message = message.replace("â–ˆ", "█").replace("â–’", "▒").replace("â–‘", "░").replace("â–“", "▓")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "#d4d4d4"
        
        if level == "error": color = "#f44747"
        elif level == "success": color = "#6a9955"
        elif level == "warning": color = "#d7ba7d"
        elif level == "debug": color = "#808080"
        elif level == "info": color = "#569cd6"
        
        # Progress/Status indicator detection
        is_progress = "%" in message or "█" in message or "▒" in message
        is_spinner = any(message.endswith(f" {s}") for s in ["-", "\\", "|", "/"])
        
        # Clean message from spinner for comparison
        clean_msg = message
        if is_spinner:
            clean_msg = message[:-2]

        should_replace = is_progress or is_spinner

        # Extract percentage for UI progress bar
        if is_progress:
            match = re.search(r"(\d+(?:\.\d+)?)%", message)
            if match:
                try:
                    val = float(match.group(1))
                    self.progress_bar.setValue(int(val))
                    self.progress_bar.show()
                except: pass

        cursor = self.terminal_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # If last message was progress and this is also progress (and same task prefix), replace
        last_was_replace = getattr(self, "_last_msg_was_replace", False)
        last_prefix = getattr(self, "_last_msg_prefix", "")
        last_clean_msg = getattr(self, "_last_clean_msg", "")
        
        current_prefix = ""
        if "]" in message:
            current_prefix = message.split("]")[0]

        # Only replace if prefixes match AND it's a progress update OR it's a spinner update for the SAME message
        if should_replace and last_was_replace and (not current_prefix or current_prefix == last_prefix) and (is_progress or clean_msg == last_clean_msg):
            # Replace last block
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            
            # Re-insert with timestamp and color
            cursor.insertHtml(f'<span style="color: #808080;">[{timestamp}]</span> ')
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontFamily("Consolas")
            cursor.setCharFormat(fmt)
            cursor.insertText(message)
        else:
            if self.terminal_output.toPlainText():
                cursor.insertBlock()
            
            cursor.insertHtml(f'<span style="color: #808080;">[{timestamp}]</span> ')
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontFamily("Consolas")
            cursor.setCharFormat(fmt)
            cursor.insertText(message)
            
        self.terminal_output.moveCursor(QTextCursor.MoveOperation.End)
        
        self._last_msg_was_replace = should_replace
        self._last_msg_prefix = current_prefix
        self._last_clean_msg = clean_msg
        
        if level == "error": logger.error(message)
        elif level == "warning": logger.warning(message)
        else: logger.info(message)

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)
        self.page_title.setText(self.nav_buttons[index].text())
        
        # Auto-trigger checks for certain pages
        if index == 4: # Install page
            self.check_tools_status()
        elif index == 3: # Debloat page
            # Auto-scan bloatware if not yet scanned
            if not getattr(self, "_bloat_ever_scanned", False):
                self.scan_bloatware()
                self._bloat_ever_scanned = True

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
        self.specs_label.setText("Gathering system specifications...")
        self.specs_worker = SpecsWorker()
        self.specs_worker.finished.connect(self._on_specs_ready)
        self.specs_worker.start()

    def _on_specs_ready(self, specs):
        self.specs_label.setText(specs)
        self.specs_label.setTextFormat(Qt.TextFormat.RichText)

    def update_sensor_panel(self):
        if hasattr(self, "sensor_worker") and self.sensor_worker.isRunning():
            return
        self.sensor_worker = SensorWorker()
        self.sensor_worker.finished.connect(self._on_sensors_ready)
        self.sensor_worker.start()

    def _on_sensors_ready(self, sensors):
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
        self.monitoring_worker = MonitoringSetupWorker()
        self.monitoring_worker.output.connect(self.log_to_terminal)
        self.monitoring_worker.finished.connect(self._on_monitoring_setup_finished)
        self.monitoring_worker.start()

    def _on_monitoring_setup_finished(self, success, message):
        if success:
            self.log_signal.emit(message, "success")
        else:
            self.log_signal.emit(message, "error")
            QMessageBox.critical(self, "Setup Error", message)

    def setup_maintenance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        maint_btn = QPushButton("Run Full System Maintenance")
        if sys.platform == 'win32':
            maint_btn.setText("Run Full System Maintenance (SFC, DISM, CHKDSK)")
        else:
            maint_btn.setText("Run Full System Maintenance (APT Update/Upgrade)")

        maint_btn.setMinimumHeight(40)
        maint_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        maint_btn.clicked.connect(self.run_system_maintenance)
        layout.addWidget(maint_btn)

        dns_btn = QPushButton("Flush DNS Cache")
        dns_btn.setMinimumHeight(40)
        dns_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        dns_btn.clicked.connect(self.flush_dns)
        layout.addWidget(dns_btn)

        cleanup_btn = QPushButton("Run System Cleanup")
        cleanup_btn.setMinimumHeight(40)
        cleanup_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        cleanup_btn.clicked.connect(self.run_disk_cleanup)
        layout.addWidget(cleanup_btn)

        update_group_title = "System Updates" if sys.platform != 'win32' else "Windows Updates"
        update_group = QGroupBox(update_group_title)
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

        if sys.platform == 'win32':
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

    def setup_network_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # IP Info Group
        ip_group = QGroupBox("Network Intelligence")
        ip_layout = QFormLayout()
        self.local_ip_label = QLabel("Loading...")
        self.public_ip_label = QLabel("Loading...")
        self.isp_label = QLabel("Loading...")
        self.location_label = QLabel("Loading...")
        ip_layout.addRow("Local IP:", self.local_ip_label)
        ip_layout.addRow("Public IP:", self.public_ip_label)
        ip_layout.addRow("ISP:", self.isp_label)
        ip_layout.addRow("Location:", self.location_label)
        
        refresh_ip_btn = QPushButton("Refresh Network Info")
        refresh_ip_btn.clicked.connect(self.refresh_network_info)
        ip_layout.addRow(refresh_ip_btn)
        ip_group.setLayout(ip_layout)
        layout.addWidget(ip_group)
        
        # DNS Benchmark Group
        dns_group = QGroupBox("DNS Benchmarker")
        dns_layout = QVBoxLayout()
        self.dns_results_list = QListWidget()
        dns_layout.addWidget(self.dns_results_list)
        run_dns_btn = QPushButton("Benchmark DNS")
        run_dns_btn.clicked.connect(self.run_dns_benchmark)
        dns_layout.addWidget(run_dns_btn)
        dns_group.setLayout(dns_layout)
        layout.addWidget(dns_group)
        
        # Port Scanner Group
        port_group = QGroupBox("Simple Port Scanner")
        port_layout = QVBoxLayout()
        self.port_results_text = QTextEdit()
        self.port_results_text.setReadOnly(True)
        self.port_results_text.setMaximumHeight(100)
        port_layout.addWidget(self.port_results_text)
        run_port_btn = QPushButton("Scan Local Ports")
        run_port_btn.clicked.connect(self.run_port_scan)
        port_layout.addWidget(run_port_btn)
        port_group.setLayout(port_layout)
        layout.addWidget(port_group)
        
        layout.addStretch()
        self.content_stack.addWidget(page)
        self.refresh_network_info()

    def refresh_network_info(self):
        self.local_ip_label.setText("Fetching...")
        self.public_ip_label.setText("Fetching...")
        self.network_worker = NetworkWorker(task="ip")
        self.network_worker.finished.connect(self._on_network_task_finished)
        self.network_worker.start()

    def run_dns_benchmark(self):
        self.dns_results_list.clear()
        self.dns_results_list.addItem("Benchmarking... please wait.")
        self.dns_worker = NetworkWorker(task="dns")
        self.dns_worker.finished.connect(self._on_network_task_finished)
        self.dns_worker.start()

    def run_port_scan(self):
        self.port_results_text.setText("Scanning common ports on localhost...")
        self.port_worker = NetworkWorker(task="port")
        self.port_worker.finished.connect(self._on_network_task_finished)
        self.port_worker.start()

    def _on_network_task_finished(self, result):
        task = result.get("task")
        data = result.get("data")
        
        if task == "ip":
            self.local_ip_label.setText(data["local_ip"])
            self.public_ip_label.setText(data["public_ip"])
            self.isp_label.setText(data["isp"])
            self.location_label.setText(data["location"])
        elif task == "dns":
            self.dns_results_list.clear()
            for res in data:
                latency = f"{res['latency']:.2f} ms" if res['latency'] > 0 else "Failed"
                self.dns_results_list.addItem(f"{res['name']}: {latency}")
        elif task == "port":
            if data:
                self.port_results_text.setText(f"Open Ports: {', '.join(map(str, data))}")
            else:
                self.port_results_text.setText("No common open ports found.")

    def setup_processes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Resource Hog Detector (Top 5)"))
        
        self.proc_tree = QTreeWidget()
        self.proc_tree.setHeaderLabels(["PID", "Name", "CPU %", "MEM %"])
        layout.addWidget(self.proc_tree)
        
        refresh_btn = QPushButton("Refresh Processes")
        refresh_btn.clicked.connect(self.refresh_processes)
        layout.addWidget(refresh_btn)
        
        kill_btn = QPushButton("Terminate Selected Process")
        kill_btn.setStyleSheet("background-color: #f44747; color: white;")
        kill_btn.clicked.connect(self.kill_selected_process)
        layout.addWidget(kill_btn)
        
        layout.addStretch()
        self.content_stack.addWidget(page)
        self.refresh_processes()

    def refresh_processes(self):
        self.proc_worker = TaskManagerWorker()
        self.proc_worker.finished.connect(self._on_processes_ready)
        self.proc_worker.start()

    def _on_processes_ready(self, hogs):
        self.proc_tree.clear()
        # Combine and deduplicate
        combined = {p['pid']: p for p in hogs['cpu'] + hogs['memory']}
        for pid, info in combined.items():
            item = QTreeWidgetItem([str(pid), info['name'], f"{info['cpu_percent']:.1f}%", f"{info['memory_percent']:.1f}%"])
            self.proc_tree.addTopLevelItem(item)

    def kill_selected_process(self):
        item = self.proc_tree.currentItem()
        if not item:
            return
        pid = int(item.text(0))
        from src.core.task_manager import TaskManager
        success, msg = TaskManager.kill_process(pid)
        if success:
            self.log_signal.emit(msg, "success")
            self.refresh_processes()
        else:
            self.log_signal.emit(msg, "error")

    def setup_privacy_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Privacy Audit
        audit_group = QGroupBox("Privacy Audit")
        audit_layout = QVBoxLayout()
        self.audit_results = QListWidget()
        audit_layout.addWidget(self.audit_results)
        run_audit_btn = QPushButton("Run Privacy Audit")
        run_audit_btn.clicked.connect(self.run_privacy_audit)
        audit_layout.addWidget(run_audit_btn)
        audit_group.setLayout(audit_layout)
        layout.addWidget(audit_group)
        
        # Browser Cleaner
        browser_group = QGroupBox("Browser Privacy Cleaner")
        browser_layout = QVBoxLayout()
        self.browser_list = QListWidget()
        browser_layout.addWidget(self.browser_list)
        clean_btn = QPushButton("Clean Selected Browser Data")
        clean_btn.clicked.connect(self.clean_browser_data)
        browser_layout.addWidget(clean_btn)
        browser_group.setLayout(browser_layout)
        layout.addWidget(browser_group)
        
        layout.addStretch()
        self.content_stack.addWidget(page)
        self.refresh_browser_list()

    def run_privacy_audit(self):
        self.audit_results.clear()
        self.audit_results.addItem("Auditing...")
        self.audit_worker = PrivacyAuditWorker()
        self.audit_worker.finished.connect(self._on_privacy_audit_finished)
        self.audit_worker.start()

    def _on_privacy_audit_finished(self, results):
        self.audit_results.clear()
        for res in results:
            self.audit_results.addItem(f"{res['name']}: {res['status']} -> {res['recommendation']}")

    def refresh_browser_list(self):
        from src.core.privacy_cleaner import PrivacyCleaner
        self.browser_list.clear()
        paths = PrivacyCleaner.get_browser_paths()
        for p in paths:
            item = QListWidgetItem(p["name"])
            item.setData(Qt.ItemDataRole.UserRole, p["path"])
            item.setCheckState(Qt.CheckState.Unchecked)
            self.browser_list.addItem(item)

    def clean_browser_data(self):
        from src.core.privacy_cleaner import PrivacyCleaner
        cleaned_count = 0
        for i in range(self.browser_list.count()):
            item = self.browser_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                path = item.data(Qt.ItemDataRole.UserRole)
                success, msg = PrivacyCleaner.clean_browser_data(path)
                if success:
                    cleaned_count += 1
                    self.log_signal.emit(msg, "success")
        
        if cleaned_count > 0:
            QMessageBox.information(self, "Success", f"Cleaned data for {cleaned_count} browsers.")
        else:
            QMessageBox.warning(self, "No Selection", "Please select at least one browser to clean.")

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
        self.debloat_tree.expandAll()

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
        info_label = QLabel("Windows Installer")
        info_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_layout.addWidget(info_label)
        info_layout.addWidget(QLabel("Easily install essential apps and system tools using Winget."))
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
        check_btn.clicked.connect(lambda: self.check_tools_status(force=True))
        install_btn = QPushButton("Install Selected Tools")
        install_btn.setMinimumHeight(40)
        install_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        install_btn.clicked.connect(self.install_tools)
        uninstall_btn = QPushButton("Uninstall Selected")
        uninstall_btn.setMinimumHeight(40)
        uninstall_btn.setStyleSheet("QPushButton { background-color: #f44747; color: white; font-weight: bold; border: 1px solid #c43030; border-radius: 6px; } QPushButton:hover { background-color: #f65d5d; } QPushButton:pressed { background-color: #d13b3b; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        uninstall_btn.clicked.connect(self.uninstall_tools)
        update_all_btn = QPushButton("Update All Apps")
        update_all_btn.setMinimumHeight(40)
        update_all_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; } QPushButton:disabled { background-color: #2a2a2a; color: #777; border-color: #2a2a2a; }")
        update_all_btn.clicked.connect(self.update_all_apps)
        btn_layout.addWidget(check_btn)
        btn_layout.addWidget(install_btn)
        btn_layout.addWidget(uninstall_btn)
        btn_layout.addWidget(update_all_btn)
        layout.addLayout(btn_layout)
        self.content_stack.addWidget(page)

    def setup_cleanup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 5px;")
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel("System Cleanup & Optimization")
        info_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_layout.addWidget(info_label)
        info_layout.addWidget(QLabel("Identify and remove unused applications and old files to free up space."))
        layout.addWidget(info_frame)

        self.cleanup_tree = QTreeWidget()
        self.cleanup_tree.setHeaderLabels(["Item", "Type", "Details", "Actionable"])
        self.cleanup_tree.setAlternatingRowColors(True)
        self.cleanup_tree.setColumnWidth(0, 250)
        self.cleanup_tree.setStyleSheet("QTreeWidget::item { padding: 5px; }")
        layout.addWidget(self.cleanup_tree)

        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("Scan for Unused Items")
        scan_btn.setMinimumHeight(40)
        scan_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: 1px solid #2e46a9; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; } QPushButton:pressed { background-color: #3a55c5; }")
        scan_btn.clicked.connect(self.scan_cleanup_items)
        
        cleanup_btn = QPushButton("Remove Selected Items")
        cleanup_btn.setMinimumHeight(40)
        cleanup_btn.setStyleSheet("QPushButton { background-color: #f44747; color: white; font-weight: bold; border: 1px solid #c43030; border-radius: 6px; } QPushButton:hover { background-color: #f65d5d; } QPushButton:pressed { background-color: #d13b3b; }")
        cleanup_btn.clicked.connect(self.perform_cleanup)
        
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(cleanup_btn)
        layout.addLayout(btn_layout)
        
        self.content_stack.addWidget(page)

    def scan_cleanup_items(self):
        self.log_signal.emit("Scanning for unused applications and old files...", "info")
        self.cleanup_tree.clear()
        
        # Create category nodes immediately
        self.file_cat = QTreeWidgetItem(self.cleanup_tree, ["Old Files (>3 months)"])
        self.app_cat = QTreeWidgetItem(self.cleanup_tree, ["Potentially Unused Apps (>6 months)"])
        self.cleanup_tree.expandAll()
        
        # Show progress bar in indeterminate mode to show activity
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        
        def run_scan():
            spinner = ["-", "\\", "|", "/"]
            spinner_idx = 0
            
            def log_step(msg):
                nonlocal spinner_idx
                s = spinner[spinner_idx % len(spinner)]
                spinner_idx += 1
                self.log_signal.emit(f"{msg} {s}", "info")

            found_files_count = 0
            found_apps_count = 0

            try:
                # 1. Scan for old files in Downloads and Temp
                paths_to_scan = [
                    os.path.join(os.environ['USERPROFILE'], 'Downloads'),
                    os.environ.get('TEMP', 'C:\\Windows\\Temp')
                ]
                
                now = datetime.now()
                for path in paths_to_scan:
                    if not os.path.exists(path): continue
                    log_step(f"Scanning directory: {path}")
                    try:
                        # Use os.scandir for better performance
                        with os.scandir(path) as entries:
                            for entry in entries:
                                try:
                                    if entry.is_file():
                                        stat = entry.stat()
                                        mtime = datetime.fromtimestamp(stat.st_mtime)
                                        days_old = (now - mtime).days
                                        if days_old > 90: # Older than 3 months
                                            size_mb = stat.st_size / (1024 * 1024)
                                            item_data = {
                                                "name": entry.name,
                                                "path": entry.path,
                                                "type": "File",
                                                "details": f"{days_old} days old, {size_mb:.1f} MB"
                                            }
                                            found_files_count += 1
                                            self.cleanup_item_signal.emit("file", item_data)
                                            if found_files_count % 10 == 0:
                                                log_step(f"Found {found_files_count} old files so far...")
                                except: pass
                    except: pass

                # 2. Scan for apps (Listing apps with install date > 6 months)
                log_step("Scanning system registry for unused applications...")
                try:
                    ps_cmd = '$paths = @("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*", "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*", "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*"); Get-ItemProperty $paths -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -ne $null } | Select-Object DisplayName, InstallDate | ConvertTo-Json'
                    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
                    if res.stdout:
                        try:
                            app_data = json.loads(res.stdout)
                            if isinstance(app_data, dict): app_data = [app_data]
                            
                            seen_names = set()
                            for app in app_data:
                                name = app.get("DisplayName")
                                if not name or name in seen_names: continue
                                seen_names.add(name)
                                
                                try:
                                    inst_date_str = str(app.get("InstallDate", ""))
                                    months_old = -1
                                    details = "Installation date unknown"
                                    
                                    if len(inst_date_str) == 8: # YYYYMMDD
                                        inst_date = datetime.strptime(inst_date_str, "%Y%m%d")
                                        months_old = (now.year - inst_date.year) * 12 + (now.month - inst_date.month)
                                        details = f"Installed {months_old} months ago"
                                    
                                    # Show if older than 6 months OR if date is unknown (better to show than hide potentially old apps)
                                    if months_old >= 6 or months_old == -1:
                                        item_data = {
                                            "name": name,
                                            "type": "Application",
                                            "details": details,
                                            "id": name
                                        }
                                        found_apps_count += 1
                                        self.cleanup_item_signal.emit("app", item_data)
                                except: pass
                        except json.JSONDecodeError: pass
                except: pass

                self.finish_cleanup_signal.emit(found_files_count, found_apps_count)
            except Exception as e:
                self.log_signal.emit(f"Error during cleanup scan: {e}", "error")
                self.finish_cleanup_signal.emit(0, 0)

        threading.Thread(target=run_scan, daemon=True).start()

    def _add_cleanup_item(self, cat_type, data):
        parent = self.file_cat if cat_type == "file" else self.app_cat
        child = QTreeWidgetItem(parent, [data["name"], data["type"], data["details"]])
        child.setCheckState(0, Qt.CheckState.Unchecked)
        # Use path for files, name for apps (as ID for uninstallation)
        child.setData(0, Qt.ItemDataRole.UserRole, data.get("path") or data.get("id"))
        self.cleanup_tree.expandAll()

    def _finish_cleanup_scan(self, file_count, app_count):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()
        self.log_signal.emit(f"Scan complete. Found {file_count} old files and {app_count} potentially unused apps.", "success")

    def perform_cleanup(self):
        selected_files = []
        selected_apps = []
        
        iterator = QTreeWidgetItemIterator(self.cleanup_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if item.text(1) == "File":
                    selected_files.append(data)
                elif item.text(1) == "Application":
                    selected_apps.append(data)
            iterator += 1
            
        if not selected_files and not selected_apps:
            QMessageBox.information(self, "Selection Required", "Please select items to remove.")
            return
            
        msg = f"Are you sure you want to delete {len(selected_files)} files and attempt to uninstall {len(selected_apps)} applications?"
        if QMessageBox.question(self, "Confirm Cleanup", msg) != QMessageBox.StandardButton.Yes:
            return
            
        self.log_signal.emit("Starting cleanup process...", "info")
        
        def run_cleanup():
            # Delete files
            for f_path in selected_files:
                try:
                    if os.path.exists(f_path):
                        os.remove(f_path)
                        self.log_signal.emit(f"Deleted file: {os.path.basename(f_path)}", "success")
                except Exception as e:
                    self.log_signal.emit(f"Failed to delete {f_path}: {e}", "error")
            
            # Uninstall apps (Attempt via winget if possible)
            for app_name in selected_apps:
                self.log_signal.emit(f"Attempting to uninstall application: {app_name}...", "info")
                try:
                    # Search for winget ID first
                    search_cmd = f'winget search "{app_name}" --exact --source winget'
                    
                    # Use a safer way to run the search
                    from src.utils.helpers import run_command
                    res = run_command(["powershell", "-NoProfile", "-Command", search_cmd], timeout=30)
                    
                    winget_id = None
                    # Simple parsing of winget search output (first ID column)
                    lines = res.stdout.splitlines()
                    for line in lines:
                        if app_name.lower() in line.lower() and "ID" not in line and "---" not in line:
                            parts = re.split(r'\s{2,}', line.strip())
                            if len(parts) >= 2:
                                winget_id = parts[1]
                                break
                    
                    if winget_id:
                        uninst_cmd = f'winget uninstall --id {winget_id} --silent --force --accept-source-agreements'
                        self.log_signal.emit(f"Found Winget ID: {winget_id}. Running silent uninstall...", "debug")
                        
                        # Use Popen to capture output if we wanted streaming, but here we just wait
                        uninst_res = run_command(["powershell", "-NoProfile", "-Command", uninst_cmd], timeout=120)
                        
                        # Log output cleanly
                        if uninst_res.stdout:
                            for line in uninst_res.stdout.splitlines():
                                clean_line = line.strip()
                                if clean_line and clean_line not in ["-", "\\", "|", "/", ".", "??"]:
                                    self.log_signal.emit(f"[{app_name}] {clean_line}", "debug")

                        if uninst_res.returncode == 0:
                            self.log_signal.emit(f"Successfully uninstalled {app_name}.", "success")
                        else:
                            msg = f"Uninstallation failed for {app_name} (Code: {uninst_res.returncode})."
                            if "Edge" in winget_id:
                                msg += " Note: Microsoft Edge is a system component and may require manual removal."
                            self.log_signal.emit(msg, "error")
                    else:
                        self.log_signal.emit(f"Could not find Winget ID for {app_name}. Please uninstall manually via Control Panel.", "warning")
                except Exception as e:
                    self.log_signal.emit(f"Error during uninstallation of {app_name}: {e}", "error")
            
            self.log_signal.emit("Cleanup process finished.", "success")
            self.scan_cleanup_signal.emit()

        threading.Thread(target=run_cleanup, daemon=True).start()

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
        icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
        ghosty_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        
        for tool in self.tools_installer.tools.values():
            cat_name = tool.category.value
            if cat_name not in categories:
                cat_item = QTreeWidgetItem(self.tools_tree, [cat_name])
                categories[cat_name] = cat_item
            child = QTreeWidgetItem(categories[cat_name], [tool.name, "Unknown", tool.description])
            child.setIcon(0, ghosty_icon)
            child.setCheckState(0, Qt.CheckState.Unchecked)
            child.setData(0, Qt.ItemDataRole.UserRole, tool.id)
        self.tools_tree.expandAll()

    def check_tools_status(self, force=False):
        if getattr(self, "_checking_tools", False):
            return
        if not force and getattr(self, "_tools_status_ever_checked", False):
            return
            
        self._tools_status_ever_checked = True
        self._checking_tools = True
        self.log_signal.emit("Checking tools status in background...", "info")
        
        def run_check():
            try:
                # Prime the winget cache once on Windows to avoid multiple slow calls
                if sys.platform == "win32":
                    self.log_signal.emit("Refreshing WinGet package cache...", "info")
                    self.tools_installer.refresh_installed_cache()

                items_to_check = []
                iterator = QTreeWidgetItemIterator(self.tools_tree)
                while iterator.value():
                    item = iterator.value()
                    tool_id = item.data(0, Qt.ItemDataRole.UserRole)
                    if tool_id in self.tools_installer.tools:
                        items_to_check.append((item, self.tools_installer.tools[tool_id]))
                    iterator += 1
                
                # Parallel status checking
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = []
                    for item, tool in items_to_check:
                        # Pass a copy of the item and future to lambda
                        future = executor.submit(self.tools_installer.check_tool_status, tool)
                        futures.append((item, future))
                    
                    for item, future in futures:
                        is_inst = future.result()
                        # Use a closure helper to avoid lambda capture issues
                        self._dispatch_status_update(item, is_inst)
                
                self.log_signal.emit("Tools status check complete.", "success")
            except Exception as e:
                logger.error(f"Error in tools status check: {e}")
            finally:
                self._checking_tools = False

        threading.Thread(target=run_check, daemon=True).start()

    def _dispatch_status_update(self, item, is_installed):
        self.status_update_signal.emit(item, is_installed)

    def _perform_status_update(self, item, is_installed):
        item.setText(1, "Installed" if is_installed else "Not Installed")
        if is_installed:
            item.setForeground(1, Qt.GlobalColor.green)
        else:
            item.setForeground(1, Qt.GlobalColor.gray)

    def _update_tools_tree(self, results):
        # Legacy method kept for compatibility if called elsewhere, but we prefer incremental updates now
        iterator = QTreeWidgetItemIterator(self.tools_tree)
        while iterator.value():
            item = iterator.value()
            tool_id = item.data(0, Qt.ItemDataRole.UserRole)
            if tool_id in results:
                self._dispatch_status_update(item, results[tool_id])
            iterator += 1

    def update_all_apps(self):
        self.log_signal.emit("Checking for updates for all installed applications...", "info")
        
        def run_update():
            try:
                # Use --silent for non-interactive and --accept-* flags for automation
                cmd = "winget upgrade --all --silent --accept-package-agreements --accept-source-agreements"
                self.log_signal.emit(f"Executing: {cmd}", "debug")
                
                process = subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd], 
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                         shell=False, creationflags=CREATE_NO_WINDOW)
                
                for line in process.stdout:
                    try:
                        text = line.decode('utf-8', errors='replace')
                    except:
                        text = line.decode('cp1252', errors='replace')
                    
                    for part in text.split('\r'):
                        clean_line = part.strip()
                        if clean_line and clean_line not in ["-", "\\", "|", "/", ".", "??"]:
                            if not re.match(r'^[\.\-\s]+$', clean_line):
                                self.log_signal.emit(f"[Update All] {clean_line}", "debug")
                
                process.wait()
                # Winget exit codes: 0 = Success, 0x8A15003B (-1978236869) = No updates found
                if process.returncode == 0:
                    self.log_signal.emit("Successfully updated all eligible applications.", "success")
                elif process.returncode in [0x8A15003B, -1978236869]:
                    self.log_signal.emit("No updates found. All applications are up to date.", "info")
                else:
                    self.log_signal.emit(f"Update all process finished with code {process.returncode}", "info")
                
                # Refresh status
                self.check_tools_signal.emit(True)
                
            except Exception as e:
                self.log_signal.emit(f"Error during update all: {e}", "error")
            finally:
                QTimer.singleShot(2000, self.progress_bar.hide)

        threading.Thread(target=run_update, daemon=True).start()

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

    def uninstall_tools(self):
        selected_ids = []
        iterator = QTreeWidgetItemIterator(self.tools_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                tool_id = item.data(0, Qt.ItemDataRole.UserRole)
                if tool_id:
                    selected_ids.append(tool_id)
            iterator += 1
        
        if not selected_ids:
            QMessageBox.information(self, "Selection Required", "Please select tools to uninstall.")
            return

        if QMessageBox.question(self, "Confirm Uninstall", f"Uninstall {len(selected_ids)} selected tools?") != QMessageBox.StandardButton.Yes:
            return

        if sys.platform == 'win32' and not is_admin():
            self.log_signal.emit("Warning: Administrator privileges are recommended for tool uninstallation.", "warning")

        self.log_signal.emit(f"Starting uninstallation of {len(selected_ids)} tools...", "info")
        
        def run_uninstalls():
            for tid in selected_ids:
                tool = self.tools_installer.tools.get(tid)
                if not tool: continue
                
                # Use detected ID if available, otherwise fallback to extracted ID
                winget_id = getattr(tool, 'detected_winget_id', None) or getattr(tool, 'winget_id', None)
                
                if not winget_id:
                    self.log_signal.emit(f"Could not determine winget ID for {tool.name}. Trying name-based uninstall.", "warning")
                    uninst_cmd = f'winget uninstall "{tool.name}" --silent --force --accept-source-agreements'
                else:
                    uninst_cmd = f'winget uninstall --id "{winget_id}" --silent --force --accept-source-agreements'

                self.log_signal.emit(f"Uninstalling {tool.name}...", "info")
                self.log_signal.emit(f"Executing: {uninst_cmd}", "debug")
                
                def execute_and_log(cmd, name):
                    proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd], 
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                           shell=False, creationflags=CREATE_NO_WINDOW)
                    full_output = []
                    while True:
                        line = proc.stdout.readline()
                        if not line: break
                        try:
                            text = line.decode('utf-8', errors='replace')
                        except:
                            text = line.decode('cp1252', errors='replace')
                        
                        for part in text.split('\r'):
                            clean = part.strip()
                            if clean and clean not in ["-", "\\", "|", "/", ".", "??"]:
                                if not re.match(r'^[\.\-\s]+$', clean):
                                    full_output.append(clean)
                                    self.log_signal.emit(f"[{name}] {clean}", "debug")
                    proc.wait()
                    return proc.returncode, "\n".join(full_output)

                try:
                    returncode, output_str = execute_and_log(uninst_cmd, tool.name)
                    
                    if returncode == 0:
                        self.log_signal.emit(f"Successfully uninstalled {tool.name}.", "success")
                    else:
                        # Fallback: try uninstalling by name if ID-based fails
                        if "--id" in uninst_cmd:
                            self.log_signal.emit(f"ID-based uninstall failed for {tool.name}. Trying name-based fallback...", "warning")
                            fallback_cmd = f'winget uninstall "{tool.name}" --silent --force --accept-source-agreements'
                            fb_returncode, fb_output = execute_and_log(fallback_cmd, tool.name)
                            if fb_returncode == 0:
                                self.log_signal.emit(f"Successfully uninstalled {tool.name} via name fallback.", "success")
                                continue
                            returncode = fb_returncode
                            output_str = fb_output

                        # Third Fallback: PowerShell Appx/System removal for known Microsoft apps
                        low_name = tool.name.lower()
                        low_id = (winget_id or "").lower()
                        
                        if any(x in low_name or x in low_id for x in ["teams", "onedrive", "edge", "microsoft", "xbox", "cortana", "office", "skype", "solitaire"]):
                            self.log_signal.emit(f"Winget methods failed. Trying specialized PowerShell removal for {tool.name}...", "warning")
                            
                            ps_fallback = ""
                            if "teams" in low_name or "teams" in low_id:
                                ps_fallback = "Get-AppxPackage -AllUsers *Teams* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "onedrive" in low_name or "onedrive" in low_id:
                                ps_fallback = 'taskkill /f /im OneDrive.exe; if (Test-Path "$env:SystemRoot\\System32\\OneDriveSetup.exe") { Start-Process -FilePath "$env:SystemRoot\\System32\\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait }'
                            elif "edge" in low_name or "edge" in low_id:
                                # Edge is stubborn; try removing the Appx packages and clearing the installation directory
                                ps_fallback = "Get-AppxPackage -AllUsers *MicrosoftEdge* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "cortana" in low_name or "cortana" in low_id:
                                ps_fallback = "Get-AppxPackage -AllUsers *549981C3F5F10* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "xbox" in low_name or "xbox" in low_id:
                                ps_fallback = "Get-AppxPackage -AllUsers *Xbox* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "solitaire" in low_name or "solitaire" in low_id:
                                ps_fallback = "Get-AppxPackage -AllUsers *SolitaireCollection* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "skype" in low_name or "skype" in low_id:
                                ps_fallback = "Get-AppxPackage -AllUsers *SkypeApp* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "microsoft" in low_id:
                                # Generic Appx removal for Microsoft IDs (e.g. Microsoft.WindowsCalculator)
                                ps_fallback = f"Get-AppxPackage -AllUsers *{winget_id}* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            elif "microsoft" in low_name:
                                # Generic Appx removal for Microsoft names (e.g. "Microsoft Photos")
                                clean_name = tool.name.replace("Microsoft ", "").replace(" ", "")
                                ps_fallback = f"Get-AppxPackage -AllUsers *{clean_name}* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue"
                            
                            if ps_fallback:
                                self.log_signal.emit(f"Executing PowerShell fallback: {ps_fallback}", "debug")
                                ps_returncode, ps_output = execute_and_log(ps_fallback, tool.name)
                                if ps_returncode == 0:
                                    self.log_signal.emit(f"Successfully removed {tool.name} via PowerShell fallback.", "success")
                                    continue
                        
                        error_msg = f"Uninstallation failed for {tool.name} with code {returncode}"
                        
                        # Special handling for common errors
                        if "No installed package found matching input criteria" in output_str:
                            error_msg += ". This tool was detected but is not managed by Winget (likely installed manually)."
                        elif "Microsoft.Edge" in (winget_id or "") or returncode == 93:
                            error_msg += ". Note: Microsoft Edge is a system component protected by Windows."
                        elif any(x in (winget_id or "").lower() for x in ["microsoft.teams", "microsoft.onedrive", "microsoft.windows"]):
                            error_msg += ". Note: This is a built-in Windows component and may be protected."
                        
                        self.log_signal.emit(error_msg, "error")
                except Exception as e:
                    self.log_signal.emit(f"Error uninstalling {tool.name}: {e}", "error")
            
            self.check_tools_signal.emit(True)

        threading.Thread(target=run_uninstalls, daemon=True).start()

    def _update_item_status_by_id(self, tool_id, is_installed):
        iterator = QTreeWidgetItemIterator(self.tools_tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole) == tool_id:
                self._dispatch_status_update(item, is_installed)
                break
            iterator += 1

    def _install_tool_bg(self, tool):
        self.log_signal.emit(f"Installing {tool.name}...", "info")
        for cmd in tool.install_commands:
            # Check for download command to show progress bar (flexible detection)
            uri_match = re.search(r'-Uri\s+["\']?([^"\']+)["\']?', cmd, re.IGNORECASE)
            outfile_match = re.search(r'-OutFile\s+["\']?([^"\']+)["\']?', cmd, re.IGNORECASE)
            
            if "Invoke-WebRequest" in cmd and uri_match and outfile_match:
                url = uri_match.group(1)
                dest = outfile_match.group(1).replace('$env:USERPROFILE', os.environ['USERPROFILE'])
                dest = os.path.expandvars(dest)
                
                self.log_signal.emit(f"Starting prioritized download for {tool.name}...", "info")
                
                is_done = threading.Event()
                worker = DownloadWorker(url, dest, tool_name=tool.name)
                worker.output.connect(self.log_to_terminal)
                
                def on_finish(success, msg):
                    if not success:
                        self.log_signal.emit(f"Download failed for {tool.name}: {msg}", "error")
                    is_done.set()
                
                worker.finished.connect(on_finish)
                worker.start()
                is_done.wait()
                QTimer.singleShot(2000, self.progress_bar.hide)
                continue

            # Platform translation for Linux
            if sys.platform != 'win32':
                if "winget install" in cmd.lower():
                    pkg = tool.id
                    # Basic mapping for common tools in the catalog
                    mapping = {
                        "brave": "brave-browser", 
                        "vscode": "code", 
                        "7zip": "p7zip-full", 
                        "git": "git", 
                        "python": "python3", 
                        "vlc": "vlc",
                        "chrome": "google-chrome-stable",
                        "discord": "discord"
                    }
                    pkg = mapping.get(tool.id, tool.id)
                    cmd = f"sudo apt-get install -y {pkg}"
                elif ".exe" in cmd.lower() or "powershell" in cmd.lower() or "msiexec" in cmd.lower():
                    self.log_signal.emit(f"Skipping Windows-only command for {tool.name}", "debug")
                    continue

            self.log_signal.emit(f"Executing: {cmd}", "debug")
            try:
                cmd_prefix = ["powershell", "-NoProfile", "-Command"] if sys.platform == 'win32' else ["bash", "-c"]
                process = subprocess.Popen(cmd_prefix + [cmd], 
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                         shell=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                
                output_captured = []
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    
                    try:
                        text = line.decode('utf-8', errors='replace')
                    except:
                        text = line.decode('cp1252', errors='replace')

                    for part in text.split('\r'):
                        clean_line = part.strip()
                        if clean_line and clean_line not in ["-", "\\", "|", "/", ".", "??"]:
                            if not re.match(r'^[\.\-\s]+$', clean_line):
                                output_captured.append(clean_line)
                                self.log_signal.emit(f"[{tool.name}] {clean_line}", "debug")
                
                process.wait()
                if process.returncode != 0:
                    # Check for winget "already installed" or "no upgrade available" which can return code 1 or 0x8A15003B
                    is_winget = "winget" in cmd.lower()
                    already_installed = any("already installed" in l.lower() or "no newer package versions" in l.lower() or "no available upgrade" in l.lower() for l in output_captured)
                    
                    if is_winget and already_installed:
                        self.log_signal.emit(f"[{tool.name}] Package is already installed and up to date.", "info")
                    else:
                        self.log_signal.emit(f"Command failed for {tool.name} with code {process.returncode}", "error")
            except Exception as e:
                self.log_signal.emit(f"Error installing {tool.name}: {e}", "error")
        self.log_signal.emit(f"Verifying installation for {tool.name}...", "info")
        self.tools_installer.check_tool_status(tool)
        if tool.is_installed:
            self._update_item_status_by_id(tool.id, True)
            self._brand_tool_installation(tool)
            self.log_signal.emit(f"Successfully installed {tool.name}", "success")
        else:
            self._update_item_status_by_id(tool.id, False)
            self.log_signal.emit(f"Installation of {tool.name} may have failed or requires restart.", "warning")
        if tool.post_install_message:
            self.log_signal.emit(f"[{tool.name}] {tool.post_install_message}", "info")

    def _brand_tool_installation(self, tool):
        """Creates a branded shortcut for the installed tool with icon overlay."""
        if sys.platform != 'win32':
            return # Branding/Shortcuts are currently Windows-only
        try:
            self.log_signal.emit(f"Applying Ghosty branding to {tool.name}...", "info")
            # 1. Determine EXE path
            self.log_signal.emit(f"Locating executable for {tool.name}...", "debug")
            exe_path = None
            
            # Use executable_name if available, fallback to tool name
            lookup_names = []
            if getattr(tool, 'executable_name', None):
                lookup_names.append(tool.executable_name)
            lookup_names.append(tool.name)
            if not tool.name.lower().endswith(".exe"):
                lookup_names.append(f"{tool.name}.exe")

            # A. Look for -OutFile patterns in install commands (manual downloads)
            for cmd in tool.install_commands:
                match = re.search(r'-OutFile\s+["\']?([^"\']+\.exe)["\']?', cmd, re.IGNORECASE)
                if match:
                    potential_path = match.group(1).replace('$env:USERPROFILE', os.environ['USERPROFILE'])
                    potential_path = os.path.expandvars(potential_path)
                    if os.path.exists(potential_path):
                        exe_path = potential_path
                        break
            
            # B. Try Get-Command via PowerShell for each lookup name
            if not exe_path:
                for name in lookup_names:
                    try:
                        from src.utils.helpers import run_command
                        ps_cmd = ["powershell.exe", "-NoProfile", "-Command", f"Write-Host (Get-Command '{name}' -ErrorAction SilentlyContinue).Source"]
                        res = run_command(ps_cmd, timeout=5)
                        if res.stdout.strip() and os.path.exists(res.stdout.strip()):
                            exe_path = res.stdout.strip()
                            break
                    except:
                        continue
            
            # C. Robust search in common directories
            if not exe_path:
                common_roots = [
                    os.environ.get('ProgramFiles', 'C:\\Program Files'),
                    os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
                    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')
                ]
                
                for root in common_roots:
                    if not os.path.exists(root): continue
                    for name in lookup_names:
                        # Try exact match in root (unlikely but possible)
                        # More likely: root/ToolName/ToolName.exe or root/Manufacturer/ToolName.exe
                        # We'll search one level deep for performance
                        try:
                            for item in os.listdir(root):
                                item_path = os.path.join(root, item)
                                if os.path.isdir(item_path):
                                    # Check if name is in this folder
                                    target = os.path.join(item_path, name if name.lower().endswith(".exe") else f"{name}.exe")
                                    if os.path.exists(target):
                                        exe_path = target
                                        break
                            if exe_path: break
                        except:
                            continue
                    if exe_path: break

            if not exe_path:
                self.log_signal.emit(f"Could not find executable for {tool.name} to create branded shortcut.", "debug")
                return

            self.log_signal.emit(f"Found executable at: {exe_path}", "debug")

            # 2. Find Ghosty Icon
            ghosty_icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
            if not os.path.exists(ghosty_icon_path):
                self.log_signal.emit("Ghosty icon not found, skipping branding.", "debug")
                return

            # 3. Create branded icon (Overlay)
            branded_icon_path = ghosty_icon_path
            
            try:
                temp_dir = os.path.join(os.environ['TEMP'], 'GhostyBranding')
                os.makedirs(temp_dir, exist_ok=True)
                # Use a unique name to avoid conflicts
                clean_tool_name = "".join([c for c in tool.name if c.isalnum()])
                original_icon_png = os.path.join(temp_dir, f"{clean_tool_name}_orig.png")
                final_icon_ico = os.path.join(temp_dir, f"{clean_tool_name}_branded.ico")
                
                # Extract original icon via PowerShell
                ps_extract_cmd = f"""
                Add-Type -AssemblyName System.Drawing
                [System.Drawing.Icon]::ExtractAssociatedIcon('{exe_path}').ToBitmap().Save('{original_icon_png}', [System.Drawing.Imaging.ImageFormat]::Png)
                """
                
                subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_extract_cmd], 
                             shell=False, capture_output=True, creationflags=CREATE_NO_WINDOW)
                
                if os.path.exists(original_icon_png):
                    # Load images
                    base = Image.open(original_icon_png).convert("RGBA")
                    overlay = Image.open(ghosty_icon_path).convert("RGBA")
                    
                    # Resize overlay (small in top right)
                    w, h = base.size
                    # User requested "small in the top right corner"
                    ov_w = int(w * 0.4)
                    ov_h = int(h * 0.4)
                    overlay = overlay.resize((ov_w, ov_h), Image.Resampling.LANCZOS)
                    
                    # Paste in top right
                    # (w - ov_w) is the X coordinate for top-right
                    base.paste(overlay, (w - ov_w, 0), overlay)
                    
                    # Save as ICO (keeping original size)
                    base.save(final_icon_ico, format="ICO", sizes=[(w, h)])
                    branded_icon_path = final_icon_ico
                    self.log_signal.emit("Created composite branded icon with Ghosty overlay.", "debug")
            except Exception as e:
                logger.error(f"Failed to create composite icon: {e}")
                self.log_signal.emit(f"Using standard Ghosty icon (Overlay failed: {e})", "debug")

            # 4. Create Shortcut
            self.log_signal.emit(f"Creating branded desktop shortcut for {tool.name}...", "info")
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            # Sanitize name for filename
            safe_name = "".join([c for c in tool.name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            shortcut_name = f"{safe_name}.lnk"
            shortcut_path = os.path.join(desktop, shortcut_name)
            
            # Using PowerShell to create the COM object and shortcut
            ps_shortcut_cmd = f"""
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
            $Shortcut.TargetPath = '{exe_path}'
            $Shortcut.IconLocation = '{branded_icon_path}'
            $Shortcut.Description = 'Installed via Ghosty Tools'
            $Shortcut.Save()
            """
            
            subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_shortcut_cmd], 
                         shell=False, creationflags=CREATE_NO_WINDOW)
            self.log_signal.emit(f"Created branded shortcut for {tool.name} on Desktop.", "success")
            
        except Exception as e:
            logger.error(f"Branding failed for {tool.name}: {e}")
            self.log_signal.emit(f"Ghosty branding failed for {tool.name}: {e}", "warning")

    def setup_advanced_tools_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # System Overview
        sys_group = QGroupBox("System Overview")
        sys_layout = QGridLayout()
        
        cpu_info = platform.processor() or "Unknown"
        cpu_label = QLabel(f"<b>CPU:</b> {cpu_info}")
        sys_layout.addWidget(cpu_label, 0, 0)
        
        mem = psutil.virtual_memory()
        mem_label = QLabel(f"<b>Memory:</b> {mem.total // (1024**3)} GB ({mem.percent}% used)")
        sys_layout.addWidget(mem_label, 0, 1)
        
        os_label = QLabel(f"<b>OS:</b> {platform.system()} {platform.release()}")
        sys_layout.addWidget(os_label, 1, 0)
        
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        boot_label = QLabel(f"<b>Boot Time:</b> {boot_time}")
        sys_layout.addWidget(boot_label, 1, 1)
        
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)
        
        # Secure File Shredder
        shred_group = QGroupBox("Secure File Shredder")
        shred_layout = QVBoxLayout()
        self.shred_path_label = QLabel("No file selected")
        shred_layout.addWidget(self.shred_path_label)
        select_file_btn = QPushButton("Select File to Shred")
        select_file_btn.clicked.connect(self.select_file_to_shred)
        shred_layout.addWidget(select_file_btn)
        self.shred_btn = QPushButton("Shred File Permanently")
        self.shred_btn.setStyleSheet("background-color: #f44747; color: white; font-weight: bold;")
        self.shred_btn.setEnabled(False)
        self.shred_btn.clicked.connect(self.run_file_shredder)
        shred_layout.addWidget(self.shred_btn)
        shred_group.setLayout(shred_layout)
        layout.addWidget(shred_group)
        
        # Platform Specific Tools
        plat_group = QGroupBox(f"{sys.platform.capitalize()} Specific Tools")
        plat_layout = QVBoxLayout()
        
        if sys.platform == "win32":
            win_grid = QGridLayout()
            
            gaming_btn = QPushButton("Toggle Gaming Mode")
            gaming_btn.clicked.connect(lambda: self.run_win_tool("gaming"))
            win_grid.addWidget(gaming_btn, 0, 0)
            
            winget_btn = QPushButton("Check WinGet Apps")
            winget_btn.clicked.connect(lambda: self.run_win_tool("winget"))
            win_grid.addWidget(winget_btn, 0, 1)
            
            dns_btn = QPushButton("Flush DNS Cache")
            dns_btn.clicked.connect(lambda: self.run_win_tool("dns"))
            win_grid.addWidget(dns_btn, 1, 0)
            
            spool_btn = QPushButton("Reset Print Spooler")
            spool_btn.clicked.connect(lambda: self.run_win_tool("spooler"))
            win_grid.addWidget(spool_btn, 1, 1)
            
            sfc_btn = QPushButton("Verify System Files (SFC)")
            sfc_btn.clicked.connect(lambda: self.run_win_tool("sfc"))
            win_grid.addWidget(sfc_btn, 2, 0)
            
            hosts_btn = QPushButton("Open Hosts File Editor")
            hosts_btn.clicked.connect(lambda: self.run_win_tool("hosts"))
            win_grid.addWidget(hosts_btn, 2, 1)
            
            plat_layout.addLayout(win_grid)
            
        elif sys.platform == "linux":
            lin_grid = QGridLayout()
            
            ufw_btn = QPushButton("Toggle UFW Firewall")
            ufw_btn.clicked.connect(lambda: self.run_linux_tool("ufw"))
            lin_grid.addWidget(ufw_btn, 0, 0)
            
            repo_btn = QPushButton("List Repositories")
            repo_btn.clicked.connect(lambda: self.run_linux_tool("repos"))
            lin_grid.addWidget(repo_btn, 0, 1)
            
            log_btn = QPushButton("View System Logs")
            log_btn.clicked.connect(lambda: self.run_linux_tool("logs"))
            lin_grid.addWidget(log_btn, 1, 0)
            
            df_btn = QPushButton("Disk Usage Summary")
            df_btn.clicked.connect(lambda: self.run_linux_tool("disk"))
            lin_grid.addWidget(df_btn, 1, 1)
            
            plat_layout.addLayout(lin_grid)
            
        elif sys.platform == "darwin":
            mac_grid = QGridLayout()
            
            brew_btn = QPushButton("Update Homebrew")
            brew_btn.clicked.connect(lambda: self.run_macos_tool("brew"))
            mac_grid.addWidget(brew_btn, 0, 0)
            
            maint_btn = QPushButton("Periodic Maintenance")
            maint_btn.clicked.connect(lambda: self.run_macos_tool("maint"))
            mac_grid.addWidget(maint_btn, 0, 1)
            
            sip_btn = QPushButton("Check SIP Status")
            sip_btn.clicked.connect(lambda: self.run_macos_tool("sip"))
            mac_grid.addWidget(sip_btn, 1, 0)
            
            residue_btn = QPushButton("Scan App Residue")
            residue_btn.clicked.connect(lambda: self.run_macos_tool("residue"))
            mac_grid.addWidget(residue_btn, 1, 1)
            
            plat_layout.addLayout(mac_grid)
            
        plat_group.setLayout(plat_layout)
        layout.addWidget(plat_group)
        
        layout.addStretch()
        self.content_stack.addWidget(page)

    def select_file_to_shred(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Shred")
        if file_path:
            self.shred_path_label.setText(file_path)
            self.shred_btn.setEnabled(True)

    def run_file_shredder(self):
        file_path = self.shred_path_label.text()
        if not os.path.exists(file_path): return
        
        reply = QMessageBox.warning(self, "Confirm Shredding", 
                                  "Are you sure? This file will be PERMANENTLY deleted and CANNOT be recovered.",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            from src.core.file_shredder import FileShredder
            success, msg = FileShredder.shred(file_path)
            if success:
                self.log_signal.emit(msg, "success")
                self.shred_path_label.setText("No file selected")
                self.shred_btn.setEnabled(False)
            else:
                self.log_signal.emit(msg, "error")

    def run_win_tool(self, tool):
        from src.core.platform_tools.windows import WindowsTools
        from src.utils.helpers import is_admin
        
        # Admin check for privileged tools
        if tool in ["gaming", "spooler", "sfc", "hosts"]:
            if not is_admin():
                self.log_signal.emit(f"Error: Administrator privileges are required to run {tool}.", "error")
                return

        if tool == "gaming":
            success, msg = WindowsTools.toggle_gaming_mode(True)
            self.log_signal.emit(msg, "info" if success else "error")
        elif tool == "winget":
            self.log_signal.emit("Fetching WinGet apps list... Please wait.", "info")
            def run_winget():
                success, msg = WindowsTools.get_winget_apps()
                self.log_signal.emit(msg, "info")
            import threading
            threading.Thread(target=run_winget, daemon=True).start()
        elif tool == "dns":
            success, msg = WindowsTools.flush_dns()
            self.log_signal.emit(msg, "success" if success else "error")
        elif tool == "spooler":
            success, msg = WindowsTools.clear_print_spooler()
            self.log_signal.emit(msg, "success" if success else "error")
        elif tool == "sfc":
            self.log_signal.emit("Starting System File Check (Verify Only)... This may take a few minutes.", "info")
            # Run in background to avoid freezing UI
            def run_sfc():
                success, msg = WindowsTools.check_system_files()
                self.log_signal.emit(msg, "info")
            import threading
            threading.Thread(target=run_sfc, daemon=True).start()
        elif tool == "hosts":
            dialog = HostsEditorDialog(self)
            dialog.exec()

    def run_linux_tool(self, tool):
        from src.core.platform_tools.linux import LinuxTools
        import threading
        if tool == "ufw":
            success, msg = LinuxTools.manage_ufw(True)
            self.log_signal.emit(msg, "info" if success else "error")
        elif tool == "repos":
            success, msg = LinuxTools.manage_repositories("list")
            self.log_signal.emit(msg, "info")
        elif tool == "logs":
            self.log_signal.emit("Fetching system logs...", "info")
            def run_logs():
                success, msg = LinuxTools.get_system_logs()
                self.log_signal.emit(msg, "info")
            threading.Thread(target=run_logs, daemon=True).start()
        elif tool == "disk":
            self.log_signal.emit("Checking disk usage...", "info")
            def run_disk():
                success, msg = LinuxTools.get_disk_usage()
                self.log_signal.emit(msg, "info")
            threading.Thread(target=run_disk, daemon=True).start()

    def run_macos_tool(self, tool):
        from src.core.platform_tools.macos import MacOSTools
        import threading
        if tool == "brew":
            self.log_signal.emit("Updating Homebrew... This may take a while.", "info")
            def run_brew():
                success, msg = MacOSTools.manage_homebrew("update")
                self.log_signal.emit(msg, "info")
            threading.Thread(target=run_brew, daemon=True).start()
        elif tool == "maint":
            self.log_signal.emit("Running macOS maintenance scripts...", "info")
            def run_maint():
                success, msg = MacOSTools.run_maintenance_scripts()
                self.log_signal.emit(msg, "info" if success else "error")
            threading.Thread(target=run_maint, daemon=True).start()
        elif tool == "sip":
            success, msg = MacOSTools.get_sip_status()
            self.log_signal.emit(msg, "info")
        elif tool == "residue":
            results = MacOSTools.scan_app_residue()
            if results:
                msg = "Found potential residue folders:\n" + "\n".join(results)
                self.log_signal.emit(msg, "info")
            else:
                self.log_signal.emit("No app residue folders found.", "info")

    def setup_password_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        from PyQt6.QtWidgets import QTabWidget
        tabs = QTabWidget()
        
        # Generator Tab
        gen_tab = QWidget()
        gen_layout = QVBoxLayout(gen_tab)
        
        group = QGroupBox("Secure Password Generator")
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
        gen_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 6px; }")
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
        self.pass_analysis.setFixedHeight(80)
        group_layout.addWidget(self.pass_analysis)
        group.setLayout(group_layout)
        gen_layout.addWidget(group)
        gen_layout.addStretch()
        
        # Vault Tab
        vault_tab = QWidget()
        vault_layout = QVBoxLayout(vault_tab)
        self.vault_stack = QStackedWidget()
        
        login_widget = QWidget()
        login_layout = QVBoxLayout(login_widget)
        login_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unlock_btn = QPushButton("Unlock Password Vault")
        unlock_btn.setFixedSize(250, 60)
        unlock_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 10px; font-size: 16px; }")
        unlock_btn.clicked.connect(self.unlock_vault)
        login_layout.addWidget(unlock_btn)
        self.vault_stack.addWidget(login_widget)
        
        self.vault_main_widget = QWidget()
        v_main_layout = QVBoxLayout(self.vault_main_widget)
        form_group = QGroupBox("Vault Entries")
        v_form_layout = QFormLayout()
        self.vault_site_entry = QLineEdit()
        self.vault_pass_entry = QLineEdit()
        v_form_layout.addRow("Site:", self.vault_site_entry)
        v_form_layout.addRow("Password:", self.vault_pass_entry)
        save_btn = QPushButton("Save to Vault")
        save_btn.clicked.connect(self.save_vault_entry)
        v_form_layout.addRow(save_btn)
        form_group.setLayout(v_form_layout)
        v_main_layout.addWidget(form_group)
        
        self.vault_list = QListWidget()
        self.vault_list.itemClicked.connect(self.on_vault_item_clicked)
        v_main_layout.addWidget(self.vault_list)
        
        v_actions = QHBoxLayout()
        del_v_btn = QPushButton("Delete Selected")
        del_v_btn.clicked.connect(self.delete_vault_entry)
        v_actions.addWidget(del_v_btn)
        v_main_layout.addLayout(v_actions)
        
        self.vault_stack.addWidget(self.vault_main_widget)
        vault_layout.addWidget(self.vault_stack)
        
        tabs.addTab(gen_tab, "Password Generator")
        tabs.addTab(vault_tab, "Password Vault")
        layout.addWidget(tabs)
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
                if self.password_manager.initialize_vault(password):
                    success = True
                    if os.path.exists(old_json) and os.path.exists(old_salt):
                        self.log_signal.emit("Legacy vault found. Attempting migration...", "info")
                        if self.password_manager.migrate_from_json(old_json, old_salt, password):
                            self.log_signal.emit("Migration successful.", "success")
            else:
                success = self.password_manager.unlock(password)
            
            if success:
                try: ensure_private_file(self.db_path)
                except: pass
                self.refresh_vault_list()
                self.vault_stack.setCurrentIndex(1)
                self.log_signal.emit("Vault unlocked.", "success")
            else:
                self.log_signal.emit("Failed to unlock vault.", "error")
                QMessageBox.critical(self, "Unlock Failed", "Invalid password.")

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
                self.log_signal.emit("Failed to save password.", "error")

    def delete_vault_entry(self):
        item = self.vault_list.currentItem()
        if item and self.password_manager:
            site = item.text()
            if self.password_manager.delete_password(site):
                self.refresh_vault_list()
                self.log_signal.emit(f"Deleted password for {site}.", "warning")

    def on_vault_item_clicked(self, item):
        site = item.text()
        if self.password_manager and hasattr(self.password_manager, "passwords"):
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
            "disable_game_mode": QCheckBox("Disable Game Mode"),
            "disable_background_apps": QCheckBox("Disable Background Apps"),
            "disable_reserved_storage": QCheckBox("Disable Reserved Storage"),
            "disable_fast_startup": QCheckBox("Disable Fast Startup"),
            "disable_search_indexing": QCheckBox("Disable Search Indexing"),
            "disable_sysmain": QCheckBox("Disable Superfetch (SysMain)"),
        }

        # Categories mapping
        categories = {
            "Privacy & Security": ["disable_telemetry", "disable_activity", "disable_location", "disable_wifi_sense", "disable_web_search", "disable_ad_id", "disable_spotlight", "disable_background_apps"],
            "System Performance": ["delete_temp", "disable_gamedvr", "disable_hibernation", "disable_storage_sense", "prefer_ipv4", "ultimate_performance", "disable_game_mode", "disable_reserved_storage", "disable_fast_startup", "disable_sysmain"],
            "Interface & Services": ["enable_end_task", "disable_homegroup", "set_services_manual", "classic_context_menu", "disable_copilot", "disable_news", "show_file_ext", "show_hidden", "disable_search_indexing"]
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
        
        ver = self.update_manager.current_version
        info_label = QLabel(f"Ghosty Tool {ver}")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        info_label.setStyleSheet("color: #4158D0; margin-top: 20px;")
        layout.addWidget(info_label)

        sub_label_text = "The Ultimate Windows Optimization & Security Suite"
        if sys.platform != 'win32':
            sub_label_text = "The Ultimate Cross-Platform Optimization & Security Suite"
        sub_label = QLabel(sub_label_text)
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        sub_label.setStyleSheet("color: #888; margin-bottom: 20px;")
        layout.addWidget(sub_label)

        site_label = QLabel('Official Website: <a href="https://ghostyware.com" style="color: #4158D0; text-decoration: none;">ghostyware.com</a>')
        site_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        site_label.setFont(QFont("Segoe UI", 11))
        site_label.setOpenExternalLinks(True)
        layout.addWidget(site_label)

        features_group = QGroupBox(f"What's New in {ver}")
        features_layout = QVBoxLayout()
        features_text = QLabel(
            f"• 🏆 <b>{ver} Milestone:</b> Professional All-in-One Hub!<br>"
            "• 🌐 <b>Network Hub:</b> New IP Intelligence, DNS Benchmarker, and Port Scanner.<br>"
            "• 📊 <b>Task Manager:</b> Resource Hog detector with one-click optimization.<br>"
            "• 🛡️ <b>Privacy & Security:</b> Added Privacy Audit and Browser Cleaner for all major browsers.<br>"
            "• 🗑️ <b>Secure Shredder:</b> Permanently delete sensitive files beyond recovery.<br>"
            "• 🍎 <b>macOS Tools:</b> Integrated Homebrew management and maintenance scripts.<br>"
            "• 🐧 <b>Linux Tools:</b> Added UFW firewall management and repository tools.<br>"
            "• 📥 <b>Tray Support:</b> Minimize to system tray with quick access actions.<br>"
            "• 🎨 <b>Modern UX:</b> Refined tabbed interface and theme switching."
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
        
        diag_btn = QPushButton("Run Diagnostics")
        diag_btn.clicked.connect(self.run_diagnostics)
        
        logs_btn = QPushButton("Open Logs Folder")
        logs_btn.clicked.connect(self.open_logs_folder)
        
        links_layout.addWidget(github_btn)
        links_layout.addWidget(twitch_btn)
        links_layout.addWidget(update_btn)
        links_layout.addWidget(diag_btn)
        links_layout.addWidget(logs_btn)
        layout.addLayout(links_layout)
        layout.addStretch()
        self.content_stack.addWidget(page)


    def run_diagnostics(self):
        """Runs self-diagnostics and shows results."""
        self.log_signal.emit("Running self-diagnostics...", "info")
        results = self.diagnostics.run_all()
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Ghosty Tools - Self-Diagnostics")
        dlg.setMinimumSize(600, 450)
        vbox = QVBoxLayout(dlg)
        
        title = QLabel("Diagnostics Results")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        vbox.addWidget(title)
        
        table = QTreeWidget()
        table.setHeaderLabels(["Check", "Status", "Message"])
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 80)
        
        for res in results:
            item = QTreeWidgetItem([res["name"], res["status"], res["message"]])
            if res["status"] == "PASS":
                item.setForeground(1, QColor("#2ecc71"))
            elif res["status"] == "FAIL":
                item.setForeground(1, QColor("#e74c3c"))
            elif res["status"] == "WARNING":
                item.setForeground(1, QColor("#f39c12"))
            table.addTopLevelItem(item)
            
        vbox.addWidget(table)
        
        btn_layout = QHBoxLayout()
        open_log_btn = QPushButton("Open Detailed Log")
        open_log_btn.clicked.connect(lambda: self.open_logs_folder())
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(open_log_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        vbox.addLayout(btn_layout)
        
        self.log_signal.emit("Diagnostics complete. Detailed log saved to logs folder.", "success")
        dlg.exec()

    def open_logs_folder(self):
        """Opens the platform-specific logs folder."""
        logs_dir = get_logs_dir()
        if sys.platform == 'win32':
            os.startfile(logs_dir)
        elif sys.platform == 'darwin':
            subprocess.Popen(["open", logs_dir])
        else:
            subprocess.Popen(["xdg-open", logs_dir])

    def check_for_whats_new(self):
        """Shows a one-time 'What's New' popup after an update."""
        last_version = self.update_manager.get_last_seen_version()
        
        # If we have a stored version and it's different from current, we just updated
        if last_version and last_version != self.update_manager.current_version:
            self.release_info_worker = ReleaseInfoWorker(self.update_manager)
            self.release_info_worker.finished.connect(self._on_release_info_ready)
            self.release_info_worker.start()
            
        # Always acknowledge the current version so we don't show it again for this version
        self.update_manager.acknowledge_current_version()

    def _on_release_info_ready(self, release_info):
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

    def check_for_updates(self, manual=False):
        self.update_check_worker = UpdateCheckWorker(self.update_manager)
        self.update_check_worker.finished.connect(lambda info: self._on_update_check_finished(info, manual))
        self.update_check_worker.start()

    def _on_update_check_finished(self, update_info, manual):
        if not update_info:
            if manual: self.log_signal.emit("Update check failed.", "warning")
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
            if asset["name"].lower().endswith(".exe") and "updater" not in asset["name"].lower():
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            self.log_signal.emit("No executable asset found in the latest release. Opening GitHub releases page...", "warning")
            webbrowser.open(update_info.get("html_url", "https://github.com/Ghostshadowplays/Ghosty-Tools/releases"))
            return
        
        # Use %LOCALAPPDATA%\GhostyTools\update\GhostyTools_new.exe as requested
        local_app_data = os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', get_config_dir()))
        update_dir = os.path.join(local_app_data, "GhostyTools", "update")
        os.makedirs(update_dir, exist_ok=True)
        target_path = os.path.join(update_dir, "GhostyTools_new.exe")
        
        self.update_dialog = QDialog(self)
        self.update_dialog.setWindowTitle("Ghosty Tools Update")
        self.update_dialog.setFixedSize(400, 150)
        vbox = QVBoxLayout(self.update_dialog)
        
        self.update_status_label = QLabel("Initializing update...")
        self.update_status_label.setWordWrap(True)
        vbox.addWidget(self.update_status_label)
        
        self.update_progress = QProgressBar()
        vbox.addWidget(self.update_progress)
        
        # Determine if we should look for delta
        delta_url = None
        # Logic to find delta asset if available...
        
        self.update_worker = UpdateWorker(download_url, target_path, delta_url)
        self.update_worker.status.connect(self.update_status_label.setText)
        self.update_worker.progress.connect(self.update_progress.setValue)
        self.update_worker.finished.connect(self._on_update_download_finished)
        
        self.log_signal.emit(f"Starting update process...", "info")
        self.update_worker.start()
        self.update_dialog.exec()

    def _on_update_download_finished(self, success, result):
        self.update_dialog.close()
        if success:
            self.log_signal.emit(f"Update prepared: {result}", "success")
            
            res = QMessageBox.question(self, "Restart Required", 
                                     "The update has been downloaded and is ready to be applied.\n\n"
                                     "Do you want to restart now to apply the update?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if res == QMessageBox.StandardButton.Yes:
                # Backup before applying
                self.update_manager.backup_current_binary()
                self.apply_update(result)
        else:
            self.log_signal.emit(f"Update failed: {result}", "error")
            QMessageBox.critical(self, "Update Error", f"Failed to complete update: {result}")

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
                subprocess.Popen(["explorer", "/select,", os.path.normpath(new_file)])
            except Exception:
                pass
            return

        # Automatic update for Windows EXE
        if is_frozen and sys.platform == 'win32':
            if not new_file.lower().endswith(".exe"):
                QMessageBox.warning(self, "Update Error", "The downloaded update is not an executable file. Please update manually.")
                return

            # Create a dynamic batch script to handle the update
            # This avoids needing a separate GhostyUpdater.exe
            update_dir = os.path.dirname(new_file)
            script_path = os.path.join(update_dir, "apply_update.bat")
            current_pid = os.getpid()
            
            # Use short paths or quotes to handle spaces in filenames
            safe_new = new_file
            safe_current = current_file
            
            # The batch script will:
            # 1. Wait for the main app to close
            # 2. Delete the old EXE
            # 3. Move the new EXE to the old location
            # 4. Restart the app
            # 5. Delete itself
            batch_content = f"""@echo off
setlocal enabledelayedexpansion
title Ghosty Tools Update Assistant

echo.
echo ==========================================
echo    Ghosty Tools Update Assistant
echo ==========================================
echo.
echo Waiting for Ghosty Tools (PID {current_pid}) to close...

:wait_loop
tasklist /FI "PID eq {current_pid}" 2>NUL | find /I "{current_pid}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

echo.
echo Applying update...
echo Source: "{safe_new}"
echo Target: "{safe_current}"
echo.

:: We use a loop for deletion too, in case of lingering locks
set /a retry=0
:delete_loop
del /f /q "{safe_current}" >nul 2>&1
if exist "{safe_current}" (
    set /a retry+=1
    if !retry! GTR 10 (
        echo ERROR: Could not remove old version. It might be locked.
        echo Please close all Ghosty Tools instances and try again.
        pause
        exit /b 1
    )
    timeout /t 1 /nobreak >nul
    goto delete_loop
)

:: Copy new file to target
copy /y "{safe_new}" "{safe_current}" >nul
if errorlevel 1 (
    echo.
    echo ERROR: Failed to apply update.
    echo Please make sure you have permission to write to:
    echo "{safe_current}"
    echo.
    echo You can find the new version at:
    echo "{safe_new}"
    echo.
    pause
    exit /b 1
)

echo.
echo Update applied successfully!
echo.
echo Cleanup...
del /f /q "{safe_new}" >nul 2>&1

echo Restarting Ghosty Tools...
start "" "{safe_current}"

:: Self-destruct and exit
(goto) 2>nul & del "%~f0"
"""
            try:
                # Use cp1252 (Standard Windows CMD encoding) for the batch file
                with open(script_path, "w", encoding="cp1252") as f:
                    f.write(batch_content)
                
                self.log_signal.emit(f"Launching update script: {script_path}", "info")
                
                # Launch the script. We don't use CREATE_NO_WINDOW here so the user can see 
                # "Updating..." if it takes a moment, providing better feedback.
                subprocess.Popen(["cmd.exe", "/c", script_path], 
                                 creationflags=CREATE_NEW_CONSOLE,
                                 close_fds=True)
                
                QApplication.quit()
                os._exit(0) # Force immediate exit to release all file locks
            except Exception as e:
                logger.error(f"Failed to launch update script: {e}")
                QMessageBox.warning(self, "Update Error", f"Failed to start automatic update: {e}\n\nPlease update manually.")
        
        elif is_frozen and (sys.platform == 'linux' or sys.platform == 'darwin'):
            # Basic support for Linux/macOS binary replacement
            script_path = os.path.join(os.path.dirname(new_file), "apply_update.sh")
            current_pid = os.getpid()
            
            sh_content = f"""#!/bin/bash
echo "Waiting for Ghosty Tools (PID {current_pid}) to close..."
while kill -0 {current_pid} 2>/dev/null; do
    sleep 1
done

echo "Applying update..."
cp -f "{new_file}" "{current_file}"
if [ $? -eq 0 ]; then
    echo "Update successful. Restarting..."
    chmod +x "{current_file}"
    "{current_file}" &
else
    echo "Update failed. Please check permissions."
    read -p "Press enter to exit"
fi
rm -- "$0"
"""
            try:
                with open(script_path, "w") as f:
                    f.write(sh_content)
                os.chmod(script_path, 0o755)
                
                subprocess.Popen(["/bin/bash", script_path], close_fds=True)
                QApplication.quit()
                os._exit(0)
            except Exception as e:
                logger.error(f"Failed to launch update script: {e}")
                QMessageBox.warning(self, "Update Error", f"Failed to start automatic update: {e}\n\nPlease update manually.")
        else:
            QMessageBox.information(self, "Update Downloaded", 
                                   f"The update has been downloaded to:\n{new_file}\n\n"
                                   "Please replace the existing file manually to complete the update.")

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
        if sys.platform != 'win32':
            self.disk_label.setText("Disk health check only available on Windows.")
            return
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
            if sys.platform == 'win32':
                subprocess.run(["ipconfig", "/flushdns"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
            else:
                # Common linux ways to flush DNS
                subprocess.run(["resolvectl", "flush-caches"], shell=False)
                # Fallback for older systems
                subprocess.run(["sudo", "systemd-resolve", "--flush-caches"], shell=False)
            
            self.log_signal.emit("DNS Cache flushed successfully.", "success")
            QMessageBox.information(self, "DNS Flush", "DNS Cache flushed successfully.")
        except Exception as e:
            logger.error(f"Error flushing DNS: {e}")
            self.log_signal.emit(f"Failed to flush DNS: {e}", "error")

    def get_physical_disks(self):
        if sys.platform != 'win32':
            return []
        try:
            from src.utils.helpers import run_command
            ps_command = "Get-PhysicalDisk | Select-Object DeviceID, FriendlyName, Size, MediaType | ConvertTo-Json"
            result = run_command(["powershell", "-NoProfile", "-Command", ps_command])
            if not result.stdout.strip(): return []
            disks = json.loads(result.stdout)
            return disks if isinstance(disks, list) else [disks]
        except Exception as e:
            logger.error(f"Error getting physical disks: {e}")
            return []

    def refresh_disk_list(self):
        if not hasattr(self, 'disk_combo'):
            return
        self.disk_combo.clear()
        try:
            disks = self.get_physical_disks()
            for d in disks:
                if isinstance(d, dict) and 'Size' in d and 'DeviceID' in d:
                    try:
                        size_gb = int(d['Size']) // (1024**3)
                        self.disk_combo.addItem(f"Disk {d['DeviceID']}: {d.get('FriendlyName', 'Unknown')} ({size_gb}GB, {d.get('MediaType', 'Unknown')})", d['DeviceID'])
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error parsing disk size: {e}")
        except Exception as e:
            logger.error(f"Error refreshing disk list: {e}")

    def validate_mbr2gpt(self):
        if not hasattr(self, 'disk_combo'):
            return
        disk_id = self.disk_combo.currentData()
        if disk_id is None: return
        self.log_signal.emit(f"Starting MBR2GPT Validation for Disk {disk_id}...", "info")
        cmd = f"mbr2gpt /validate /disk:{disk_id} /allowfullos"
        self.maint_worker = GenericCommandWorker("MBR2GPT Validate", cmd)
        self.maint_worker.output.connect(self.log_to_terminal)
        self.maint_worker.finished.connect(lambda s, m: self.log_signal.emit(m if m else "Validation finished successfully.", "success" if s else "error"))
        self.maint_worker.start()

    def convert_mbr2gpt(self):
        if not hasattr(self, 'disk_combo'):
            return
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
        QTimer.singleShot(2000, self.progress_bar.hide)
        QMessageBox.information(self, "Maintenance", res)

    def run_disk_cleanup(self):
        self.log_signal.emit("Launching System Cleanup...", "info")
        try:
            if sys.platform == 'win32':
                subprocess.Popen(["cleanmgr", "/d", "C"], shell=False, creationflags=CREATE_NO_WINDOW)
            else:
                self.log_signal.emit("Running Linux APT cleanup...", "info")
                # Use a simple popen to avoid blocking GUI
                subprocess.Popen(["bash", "-c", "sudo apt-get clean && sudo apt-get autoremove -y"], shell=False)
                self.log_signal.emit("Linux cleanup started in background.", "success")
        except Exception as e:
            logger.error(f"Error launching cleanup: {e}")
            self.log_signal.emit(f"Failed to launch Cleanup: {e}", "error")

    def run_windows_update_check(self):
        if sys.platform == 'win32':
            self.log_signal.emit("Checking for Windows Updates...", "info")
            self.update_status.setText("Status: Checking...")
            threading.Thread(target=self._update_check_thread, daemon=True).start()
        else:
            self.log_signal.emit("Checking for Linux Updates...", "info")
            self.update_status.setText("Status: Checking...")
            threading.Thread(target=self._linux_update_check_thread, daemon=True).start()

    def _linux_update_check_thread(self):
        from src.utils.helpers import run_command
        try:
            res = run_command(["apt", "list", "--upgradable"])
            lines = [l for l in res.stdout.split('\n') if l and '/' in l]
            count = len(lines)
            self.update_status.setText(f"Status: {count} updates found")
            self.log_signal.emit(f"Linux update check finished: {count} updates found.", "info")
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            self.log_signal.emit(f"Linux update check failed: {e}", "error")

    def install_windows_updates(self):
        if sys.platform == 'win32':
            self.log_signal.emit("Initiating Windows Update installation (GUI)...", "info")
            subprocess.run(["control", "update"], shell=False, creationflags=CREATE_NO_WINDOW)
        else:
            self.log_signal.emit("Initiating Linux Update installation...", "info")
            self.log_signal.emit("Running 'apt upgrade'...", "info")
            subprocess.Popen(["bash", "-c", "sudo apt-get upgrade -y"], shell=False)

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
                elif name == "disable_game_mode": self._disable_game_mode()
                elif name == "disable_background_apps": self._disable_background_apps()
                elif name == "disable_reserved_storage": self._disable_reserved_storage()
                elif name == "disable_fast_startup": self._disable_fast_startup()
                elif name == "disable_search_indexing": self._disable_search_indexing()
                elif name == "disable_sysmain": self._disable_sysmain()
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

    def _disable_game_mode(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar")
            winreg.SetValueEx(key, "AllowAutoGameMode", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Game Mode tweak failed: {e}")

    def _disable_background_apps(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications")
            winreg.SetValueEx(key, "GlobalUserDisabled", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            key2 = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Search")
            winreg.SetValueEx(key2, "BackgroundAppGlobalToggle", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key2)
        except Exception as e: logger.error(f"Background Apps tweak failed: {e}")

    def _disable_reserved_storage(self):
        try:
            subprocess.run(["DISM.exe", "/Online", "/Set-ReservedStorageState", "/State:Disabled"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
        except Exception as e: logger.error(f"Reserved Storage tweak failed: {e}")

    def _disable_fast_startup(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Power")
            winreg.SetValueEx(key, "HiberbootEnabled", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e: logger.error(f"Fast Startup tweak failed: {e}")

    def _disable_search_indexing(self):
        try:
            subprocess.run(["sc", "stop", "WSearch"], shell=False, check=False, creationflags=CREATE_NO_WINDOW)
            subprocess.run(["sc", "config", "WSearch", "start=", "disabled"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
        except Exception as e: logger.error(f"Search Indexing tweak failed: {e}")

    def _disable_sysmain(self):
        try:
            subprocess.run(["sc", "stop", "SysMain"], shell=False, check=False, creationflags=CREATE_NO_WINDOW)
            subprocess.run(["sc", "config", "SysMain", "start=", "disabled"], shell=False, check=True, creationflags=CREATE_NO_WINDOW)
        except Exception as e: logger.error(f"SysMain tweak failed: {e}")
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        
        tray_menu = QMenu()
        show_action = QAction("Show Ghosty Tools", self)
        show_action.triggered.connect(self.show_and_raise)
        
        clean_action = QAction("Quick Clean", self)
        clean_action.triggered.connect(self.run_disk_cleanup)
        
        speed_action = QAction("Speed Test", self)
        speed_action.triggered.connect(self.run_speed_test)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(clean_action)
        tray_menu.addAction(speed_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def show_and_raise(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_raise()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                QTimer.singleShot(0, self.hide)
        super().changeEvent(event)
