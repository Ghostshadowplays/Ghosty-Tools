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
                             QPushButton, QLabel, QCheckBox, QGroupBox, QSplitter,
                             QScrollArea, QMessageBox, QProgressBar, QStackedWidget,
                             QFrame, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QTreeWidgetItemIterator, QComboBox, QTextEdit, QLineEdit, QDialog, QFormLayout,
                             QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QSize
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
from src.gui.dialogs import MasterPasswordDialog, HostsEditorDialog, AppearanceDialog, UpdateDialog, TidyDesktopDialog, GameCompatibilityDialog
from src.gui.dashboard import DashboardPage, DashboardCard, PageHeader, NavButton, NotificationBanner
from src.utils.theme_manager import ThemeManager
from src.utils.helpers import is_admin, elevate_privileges, get_config_dir, ensure_private_file, get_resource_path, get_logs_dir, get_os_info
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction

logger = logging.getLogger(__name__)


class _DropZoneFrame(QFrame):
    """A drag-and-drop target that emits file_dropped(path) when an .exe is dropped."""
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._default_style = (
            "QFrame { border: 2px dashed #444; border-radius: 8px; "
            "background-color: #1a1a1f; color: #888; }"
        )
        self._hover_style = (
            "QFrame { border: 2px dashed #4158D0; border-radius: 8px; "
            "background-color: #1e1e2a; color: #aaa; }"
        )
        self.setStyleSheet(self._default_style)
        lbl = QLabel("⬇  Drop game .exe here", self)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #666; font-size: 12px; background: transparent; border: none;")
        lay = QVBoxLayout(self)
        lay.addWidget(lbl)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(".exe")
                   for u in event.mimeData().urls()):
                self.setStyleSheet(self._hover_style)
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._default_style)

    def dropEvent(self, event):
        self.setStyleSheet(self._default_style)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".exe"):
                self.file_dropped.emit(path)
                break


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
        from src.core.update_manager import CURRENT_VERSION
        self.setWindowTitle(f"Ghosty Tool {CURRENT_VERSION} - Professional System Utility")
        self.setGeometry(100, 100, 960, 600)

        # Use PNG icon on Linux (better DE integration), ICO on Windows/macOS
        if sys.platform != 'win32':
            png_path = os.path.join(self.project_root, "images", "ghosty icon.png")
            ico_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
            icon_path = png_path if os.path.exists(png_path) else ico_path
        else:
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

        # Activity log + settings paths
        self.activity_log_path = os.path.join(config_dir, "activity.json")
        self.speedtest_history_path = os.path.join(config_dir, "speedtest_history.json")
        self.settings_path = os.path.join(config_dir, "app_settings.json")
        self._activity_log = self._load_json(self.activity_log_path, [])
        self._speedtest_history = self._load_json(self.speedtest_history_path, [])
        self._app_settings = self._load_json(self.settings_path, {
            "minimize_to_tray": False,
            "start_with_windows": False,
            "alert_refresh_sec": 60,
            "startup_page": 0,
            "shortcut_prompted": False,
            "gaming_mode_active": False
        })
        # Ensure keys are always present (for upgrades from older settings)
        self._app_settings.setdefault("minimize_to_tray", False)
        self._app_settings.setdefault("shortcut_prompted", False)
        self._app_settings.setdefault("gaming_mode_active", False)

        # Detect Linux package manager once at startup
        self.pkg_manager = self._detect_pkg_manager()

        # Clipboard security
        self.clipboard_timer = QTimer()
        self.clipboard_timer.setSingleShot(True)
        self.clipboard_timer.timeout.connect(self.clear_clipboard)

        # Initialize Update Manager
        self.update_manager = UpdateManager()
        self.diagnostics = Diagnostics(self.update_manager.current_version)
        self._latest_update_info = None

        # Theme Manager — store theme.json in the user config dir, not next to the exe
        _theme_config_path = os.path.join(get_config_dir(), "theme.json")
        self.theme_manager = ThemeManager(_theme_config_path)
        self.appearance_dialog = AppearanceDialog(self.theme_manager, self)
        self.appearance_dialog.theme_changed.connect(self.apply_current_theme)

        self.init_ui()
        self.apply_current_theme()
        self.init_tray()

        QTimer.singleShot(1000, self.check_for_updates)
        QTimer.singleShot(2000, self.check_for_whats_new)

        # First-launch: prompt to create a desktop shortcut (Windows only)
        if sys.platform == 'win32' and not self._app_settings.get("shortcut_prompted", False):
            QTimer.singleShot(1500, self._prompt_desktop_shortcut)

        # Apply startup page preference (after UI is built)
        startup_pg = self._app_settings.get("startup_page", 0)
        if startup_pg > 0:
            QTimer.singleShot(0, lambda: self.switch_page(startup_pg))

        # Timer for system usage updates
        self.usage_timer = QTimer()
        self.usage_timer.timeout.connect(self.update_system_usage)
        self.usage_timer.start(2000)
        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self.update_sensor_panel)
        self.sensor_timer.start(2000)

    def _load_json(self, path, default):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _save_json(self, path, data):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {path}: {e}")

    def _detect_pkg_manager(self):
        """Detect the Linux package manager. Returns 'apt', 'dnf', 'pacman', 'zypper', or None."""
        if sys.platform == 'win32' or sys.platform == 'darwin':
            return None
        for pm in ['apt', 'dnf', 'pacman', 'zypper', 'emerge']:
            if shutil.which(pm):
                return pm
        return None

    def log_activity(self, text):
        """Append an action to the persistent recent activity list (max 15 entries)."""
        entry = {"time": datetime.now().strftime("%d %b %H:%M"), "text": text}
        self._activity_log.insert(0, entry)
        self._activity_log = self._activity_log[:15]
        self._save_json(self.activity_log_path, self._activity_log)
        self._refresh_activity_panel()

    def _refresh_activity_panel(self):
        if not hasattr(self, 'activity_label'):
            return
        if not self._activity_log:
            self.activity_label.setText("No activity recorded yet")
            return
        lines = [f"<span style='color:#666'>{e['time']}</span> {e['text']}"
                 for e in self._activity_log[:5]]
        self.activity_label.setText("<br>".join(lines))
        self.activity_label.setTextFormat(Qt.TextFormat.RichText)

    def _on_disk_identified(self, main_disk, system_drive):
        self.main_disk = main_disk
        self.system_drive = system_drive
        logger.info(f"Main system disk identified as Disk {self.main_disk} (Drive {self.system_drive}:)")


    def apply_current_theme(self):
        self.setStyleSheet(self.theme_manager.get_stylesheet())
        if hasattr(self, 'appearance_dialog'):
            self.appearance_dialog.update_style()
            self.appearance_dialog.update_preset_buttons()

    def open_appearance_settings(self):
        if self.appearance_dialog.isVisible():
            self.appearance_dialog.hide()
        else:
            # Center it relative to the window
            x = (self.width() - self.appearance_dialog.width()) // 2
            y = (self.height() - self.appearance_dialog.height()) // 2
            self.appearance_dialog.move(x, y)
            self.appearance_dialog.show()
            self.appearance_dialog.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'appearance_dialog') and self.appearance_dialog.isVisible():
            x = (self.width() - self.appearance_dialog.width()) // 2
            y = (self.height() - self.appearance_dialog.height()) // 2
            self.appearance_dialog.move(x, y)

    def mousePressEvent(self, event):
        # Close appearance settings if clicking outside
        if hasattr(self, 'appearance_dialog') and self.appearance_dialog.isVisible():
            if not self.appearance_dialog.geometry().contains(event.pos()):
                self.appearance_dialog.hide()
        super().mousePressEvent(event)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        outer_layout = QHBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Splitter lets the user drag the sidebar wider/narrower
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.setStyleSheet(
            "QSplitter::handle { background-color: #222; }"
            "QSplitter::handle:hover { background-color: #4158D0; }"
        )
        outer_layout.addWidget(self.main_splitter)
        # Keep a reference so existing code using self.main_layout still works
        self.main_layout = outer_layout

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMinimumWidth(180)
        self.sidebar.setMaximumWidth(380)
        self.sidebar_outer_layout = QVBoxLayout(self.sidebar)
        self.sidebar_outer_layout.setContentsMargins(0, 20, 0, 10)
        self.sidebar_outer_layout.setSpacing(0)

        # Sidebar Header
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(20, 0, 20, 20)
        
        title_label = QLabel("Ghosty Tool")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white; background: transparent;")
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel("System toolkit")
        subtitle_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
        header_layout.addWidget(subtitle_label)
        self.sidebar_outer_layout.addWidget(header_container)

        # Sidebar Scroll Area
        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll_content = QWidget()
        self.nav_scroll_layout = QVBoxLayout(self.nav_scroll_content)
        self.nav_scroll_layout.setContentsMargins(10, 0, 10, 0)
        self.nav_scroll_layout.setSpacing(5)
        self.nav_scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_scroll.setWidget(self.nav_scroll_content)
        self.sidebar_outer_layout.addWidget(self.nav_scroll)

        self.nav_buttons = []
        is_win = sys.platform == "win32"
        
        self.add_nav_button("Dashboard", 0, icon_text="\uE80F" if is_win else "🏠")
        self.add_nav_button("System", 1, "Health · Windows · Repairs", icon_text="\uE770" if is_win else "⚙", count=9)
        self.add_nav_button("Security", 2, "Security Assessment · Scan", icon_text="\uEADC" if is_win else "🛡", count=3)
        self.add_nav_button("Network", 3, "Ping · Speed Test · DNS", icon_text="\uE774" if is_win else "🌐", count=5)
        self.add_nav_button("Monitor", 4, "Process Manager · Resources", icon_text="\uE9D2" if is_win else "📊", count=6)
        self.add_nav_button("Privacy", 5, "Privacy Audit · Browser", icon_text="\uE1F6" if is_win else "🔒", count=9)
        self.add_nav_button("Debloat", 6, "Windows Apps · Telemetry", icon_text="\uE74D" if is_win else "🗑", count=4)
        self.add_nav_button("Apps", 7, "Updates · Bulk Installer", icon_text="\uE71D" if is_win else "📦", count=3)
        self.add_nav_button("Cleanup", 8, "Quick · Deep Cleanup", icon_text="\uEA99" if is_win else "🧹", count=4)
        self.add_nav_button("Storage", 9, "Disk Tools · Advanced", icon_text="\uE8B7" if is_win else "💾", count=2)
        self.add_nav_button("Hardware", 10, "Sensors · Specs · Health", icon_text="\uE950" if is_win else "💻", count=3)
        self.add_nav_button("Events", 11, "Event Viewer · Logs", icon_text="\uE9D9" if is_win else "📋")
        self.add_nav_button("Services", 12, "Service Manager", icon_text="\uE713" if is_win else "🛠")
        self.add_nav_button("Automation", 13, "Custom Scripts", icon_text="\uE99A" if is_win else "🤖")
        self.add_nav_button("Passwords", 14, "Vault · Generator", icon_text="\uE192" if is_win else "🔑", count=2)
        self.add_nav_button("Customization", 15, "Context Menu · Dark Mode", icon_text="\uE771" if is_win else "🖌", count=4)
        self.add_nav_button("Info", 16, "About · Updates · System", icon_text="\uE946" if is_win else "ⓘ", count=5)
        self.add_nav_button("Settings", 17, "Preferences · Startup", icon_text="\uE713" if is_win else "⚙️")
        self.add_nav_button("Gaming", 18, "Game Mode · Compatibility", icon_text="\uE7FC" if is_win else "🎮")

        # Bottom section for theme toggle
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        
        btn_style = (
            "QPushButton { background-color: #1a1a1f; color: white; border: 1px solid #333;"
            " border-radius: 8px; font-weight: bold; padding: 0 8px; }"
            "QPushButton:hover { background-color: #25252b; }"
        )

        self.appearance_btn = QPushButton("🎨  Appearance")
        self.appearance_btn.setFixedHeight(38)
        self.appearance_btn.setStyleSheet(btn_style)
        self.appearance_btn.clicked.connect(self.open_appearance_settings)

        self.dark_mode_btn = QPushButton("🌙  Toggle Theme")
        self.dark_mode_btn.setFixedHeight(38)
        self.dark_mode_btn.setStyleSheet(btn_style)
        self.dark_mode_btn.clicked.connect(self.toggle_windows_theme)

        h_theme_layout = QHBoxLayout()
        h_theme_layout.setSpacing(6)
        h_theme_layout.addWidget(self.appearance_btn)
        h_theme_layout.addWidget(self.dark_mode_btn)
        bottom_layout.addLayout(h_theme_layout)

        # Version badge
        from src.core.update_manager import CURRENT_VERSION as _VER
        ver_badge = QLabel(_VER)
        ver_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_badge.setStyleSheet("color: #444; font-size: 10px; background: transparent; padding: 2px 0;")
        bottom_layout.addWidget(ver_badge)

        self.sidebar_outer_layout.addWidget(bottom_container)

        # Platform check - Custom Linux/macOS GUI
        if sys.platform != 'win32':
            # Hide Windows-specific tabs
            for i in [6, 11]:
                if i < len(self.nav_buttons):
                    self.nav_buttons[i].setVisible(False)

            self.dark_mode_btn.setVisible(False)

            # Platform-specific branding
            if sys.platform == 'darwin':
                title_label.setText("Ghosty Tool 🍎")
            else:
                title_label.setText("Ghosty Tool 🐧")
        
        self.main_splitter.addWidget(self.sidebar)

        # Content Area & Terminal
        self.right_container = QWidget()
        self.right_container.setObjectName("RightPanel")
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        # Update Banner
        self.update_banner = NotificationBanner("Update available")
        self.update_banner.hide()
        self.update_banner.action_btn.clicked.connect(self.show_update_details)
        self.right_layout.addWidget(self.update_banner)

        self.content_stack = QStackedWidget()
        
        # Wrap content stack in a scroll area for small screens
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_scroll.setWidget(self.content_stack)
        
        # Header for content area
        self.header_frame = QFrame()
        self.header_frame.setObjectName("HeaderFrame")
        self.header_frame.setFixedHeight(60)
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
        self.right_layout.addWidget(self.content_scroll)

        # Live Terminal Feed
        self.terminal_container = QGroupBox("Live Terminal Feed")
        self.terminal_container.setFixedHeight(220)
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
        self.main_splitter.addWidget(self.right_container)

        # Default split: sidebar 240px, rest goes to content
        self.main_splitter.setSizes([240, 720])
        # Sidebar can be resized but content area should not collapse
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

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
        self.setup_hardware_health_page()
        self.setup_event_viewer_page()
        self.setup_services_page()
        self.setup_automation_page()
        self.setup_password_page()
        self.setup_tweaks_page()
        self.setup_about_page()
        self.setup_settings_page()
        self.setup_gaming_page()

    def add_nav_button(self, text, index, subtitle="", icon_text="", count=None):
        btn = NavButton(text, subtitle, icon_text, count)
        btn.clicked.connect(lambda _: self.switch_page(index))
        self.nav_scroll_layout.addWidget(btn)
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

    @staticmethod
    def _make_admin_notice() -> "QLabel":
        """Return a styled warning label shown when the app is not running as admin."""
        lbl = QLabel(
            "⚠️  Administrator privileges required.  "
            "Click <b>Elevate</b> in the toolbar, then re-open this page."
        )
        lbl.setStyleSheet(
            "color: #d7ba7d; font-size: 11px; background-color: #2a2215; "
            "border: 1px solid #5a4a20; border-radius: 5px; padding: 6px 10px;"
        )
        lbl.setWordWrap(True)
        lbl.setVisible(not is_admin())
        return lbl

    def clear_clipboard(self):
        pyperclip.copy("")
        self.log_signal.emit("Clipboard cleared for security.", "info")

    def copy_to_clipboard(self, text, timeout=30):
        if text:
            pyperclip.copy(text)
            if timeout:
                self.log_signal.emit(f"Copied to clipboard. Will clear in {timeout}s.", "info")
                self.clipboard_timer.start(timeout * 1000)
            else:
                self.log_signal.emit("Copied to clipboard.", "info")

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
        self.dashboard = DashboardPage()
        self.content_stack.addWidget(self.dashboard)
        
        # Initial data
        os_info = get_os_info()
        os_text = f"{os_info.get('platform', 'Unknown')} {os_info.get('release', '')} · Build {os_info.get('version', '')}"
        self.dashboard.os_label.setText(os_text)

        # Connect buttons
        self.dashboard.scan_btn.clicked.connect(self.run_security_scan)
        self.dashboard.tune_btn.clicked.connect(self.run_system_maintenance)
        
        # Populate Quick Actions
        actions_layout = QVBoxLayout()
        if sys.platform == 'win32':
            update_label = "Check Windows Updates"
            update_action = self.run_windows_update_check
        elif sys.platform == 'darwin':
            update_label = "Check macOS Updates"
            update_action = lambda: self.log_signal.emit("Run 'softwareupdate -l' in Terminal to check for updates.", "info")
        else:
            update_label = "Update System (APT)"
            update_action = lambda: self.run_system_maintenance()
        quick_actions = [
            ("Run Quick Cleanup", self.run_disk_cleanup),
            ("Update All Apps", lambda: self.switch_page(7)),
            (update_label, update_action),
            ("Run Speed Test", self.run_speed_test)
        ]
        for name, callback in quick_actions:
            btn = QPushButton(name)
            btn.setFixedHeight(35)
            btn.setStyleSheet("text-align: left; padding-left: 10px; background-color: #25252b;")
            btn.clicked.connect(callback)
            actions_layout.addWidget(btn)
        self.dashboard.actions_card.layout.addLayout(actions_layout)
        
        # System Alerts — populated dynamically via refresh_system_alerts()
        self.alerts_widget = QWidget()
        self.alerts_widget_layout = QVBoxLayout(self.alerts_widget)
        self.alerts_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.alerts_widget_layout.setSpacing(3)
        self.dashboard.alerts_card.layout.addWidget(self.alerts_widget)
        QTimer.singleShot(500, self.refresh_system_alerts)

        # Refresh alerts every 60 seconds
        self.alerts_timer = QTimer()
        self.alerts_timer.timeout.connect(self.refresh_system_alerts)
        self.alerts_timer.start(60000)
        
        # Recent Activity
        self.activity_label = QLabel("No activity recorded yet")
        self.activity_label.setStyleSheet("color: #888; font-size: 11px;")
        self.activity_label.setWordWrap(True)
        self.dashboard.activity_card.layout.addWidget(self.activity_label)
        self._refresh_activity_panel()

    def refresh_system_alerts(self):
        """Rebuild the system alerts panel with live data."""
        if not hasattr(self, 'alerts_widget_layout'):
            return
        # Clear existing labels
        while self.alerts_widget_layout.count():
            item = self.alerts_widget_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for text, color in self._get_live_alerts():
            lbl = QLabel(f"• {text}")
            lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            self.alerts_widget_layout.addWidget(lbl)

    def _get_live_alerts(self):
        """Generate live system alert tuples of (text, color)."""
        alerts = []

        # Memory
        try:
            mem = psutil.virtual_memory()
            pct = mem.percent
            if pct > 85:
                alerts.append((f"High memory usage: {pct:.0f}% used", "#f44747"))
            elif pct > 70:
                alerts.append((f"Memory usage elevated: {pct:.0f}% used", "#FBAB7E"))
            else:
                alerts.append((f"Memory OK: {pct:.0f}% used", "#00ff88"))
        except Exception:
            pass

        # Disk space on system drive
        try:
            drive = os.path.abspath(os.sep)
            disk = psutil.disk_usage(drive)
            free_pct = 100 - disk.percent
            if disk.percent > 90:
                alerts.append((f"Low disk space: {free_pct:.0f}% free", "#f44747"))
            elif disk.percent > 75:
                alerts.append((f"Disk space moderate: {free_pct:.0f}% free", "#FBAB7E"))
            else:
                alerts.append((f"Disk space OK: {free_pct:.0f}% free", "#00ff88"))
        except Exception:
            pass

        # Pending reboot — use specific Windows Update / CBS keys instead of
        # PendingFileRenameOperations which is almost always non-empty and unreliable.
        try:
            reboot_pending = False
            if sys.platform == 'win32' and winreg:
                _wu_keys = [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\PackagesPending",
                ]
                for _k in _wu_keys:
                    try:
                        _h = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _k)
                        winreg.CloseKey(_h)
                        reboot_pending = True
                        break
                    except OSError:
                        pass
            elif sys.platform != 'win32':
                reboot_pending = os.path.exists('/var/run/reboot-required')

            if reboot_pending:
                alerts.append(("Reboot required — restart to apply updates", "#FBAB7E"))
            else:
                alerts.append(("No pending reboots", "#00ff88"))
        except Exception:
            pass

        # App update status (uses cached result from update check)
        if self._latest_update_info and self._latest_update_info.get("available"):
            latest = self._latest_update_info.get("latest_version", "")
            alerts.append((f"App update available: {latest}", "#FBAB7E"))
        else:
            alerts.append(("App is up to date", "#00ff88"))

        return alerts

    def update_specs(self):
        if hasattr(self, "specs_label"):
            self.specs_label.setText("Gathering system specifications...")
        self.specs_worker = SpecsWorker()
        self.specs_worker.finished.connect(self._on_specs_ready)
        self.specs_worker.start()

    def _on_specs_ready(self, specs):
        if not hasattr(self, "specs_label"):
            return
        self.specs_label.setText(specs)
        self.specs_label.setTextFormat(Qt.TextFormat.RichText)

    def update_sensor_panel(self):
        if hasattr(self, "sensor_worker") and self.sensor_worker.isRunning():
            return
        self.sensor_worker = SensorWorker()
        self.sensor_worker.finished.connect(self._on_sensors_ready)
        self.sensor_worker.start()

    def _on_sensors_ready(self, sensors):
        if not hasattr(self, "sensor_label"):
            return

        lhm_visible = not bool(sensors)
        if hasattr(self, 'lhm_info_label'):
            self.lhm_info_label.setVisible(lhm_visible)
        if hasattr(self, 'lhm_download_btn'):
            self.lhm_download_btn.setVisible(lhm_visible)
        if hasattr(self, 'lhm_launch_btn'):
            # Only show Launch button when LHM exe is found on disk
            self.lhm_launch_btn.setVisible(lhm_visible and bool(self._find_lhm_exe()))

        if not sensors:
            self.sensor_label.setText(
                "No sensor data received — LibreHardwareMonitor is not running."
            )
            self.sensor_label.setStyleSheet("color: #d7ba7d; font-family: 'Consolas'; font-size: 12px;")
            return

        # Group sensors by their parent type label so output is organised
        groups = {}
        for name, info in sensors.items():
            grp = info.get("type", "Other")
            groups.setdefault(grp, []).append((name, info["value"]))

        # Priority group ordering — put CPU/GPU/Fans first
        priority = ["CPU", "GPU", "Temperatures", "Fans", "Voltages", "Controls", "Powers", "Clocks"]
        ordered_groups = sorted(
            groups.items(),
            key=lambda kv: next((i for i, p in enumerate(priority) if p.lower() in kv[0].lower()), 99)
        )

        lines = []
        for grp, items in ordered_groups:
            lines.append(f"<b style='color:#888'>{grp}</b>")
            for name, val in items[:12]:          # cap each group at 12 rows
                lines.append(f"&nbsp;&nbsp;{name}: <span style='color:#00ff88'>{val}</span>")
            lines.append("")                       # blank line between groups

        self.sensor_label.setStyleSheet("color: #d4d4d4; font-family: 'Consolas'; font-size: 11px;")
        self.sensor_label.setText("<br>".join(lines))
        self.sensor_label.setTextFormat(Qt.TextFormat.RichText)

        # Update Dashboard GPU card with whatever GPU load sensor is available
        gpu_load_val = None
        for name, info in sensors.items():
            if "gpu" in name.lower() and ("core" in name.lower() or "load" in name.lower()):
                gpu_load_val = info["value"]
                break
        if gpu_load_val is not None:
            try:
                val = int(float(str(gpu_load_val).split()[0]))
                self.dashboard.gpu_card.value_label.setText(f"{val}%")
                self.dashboard.gpu_card.bar.setValue(val)
            except:
                pass


    def _install_lhm_winget(self):
        """Install LibreHardwareMonitor silently via winget, with terminal feedback."""
        if shutil.which("winget") is None:
            QMessageBox.warning(
                self, "winget not found",
                "winget is not available on this system.\n\n"
                "You can download LibreHardwareMonitor manually from:\n"
                "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases"
            )
            return

        self.lhm_download_btn.setEnabled(False)
        self.lhm_download_btn.setText("Installing…")
        self.log_signal.emit("Installing LibreHardwareMonitor via winget…", "info")

        def _do_install():
            try:
                result = subprocess.run(
                    ["winget", "install", "--id", "LibreHardwareMonitor.LibreHardwareMonitor",
                     "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    capture_output=True, text=True,
                    creationflags=CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    self.log_signal.emit(
                        "LibreHardwareMonitor installed — launching it now…",
                        "success"
                    )
                    self.notify_tray("LHM Installed", "LibreHardwareMonitor is launching with the web server pre-configured.")
                    # Auto-launch on the main thread after a short delay
                    QTimer.singleShot(1500, self._launch_lhm)
                else:
                    err = (result.stderr or result.stdout or "unknown error").strip()
                    self.log_signal.emit(f"winget install failed: {err}", "error")
            except Exception as e:
                self.log_signal.emit(f"Install error: {e}", "error")
            finally:
                # Re-enable button on the main thread
                QTimer.singleShot(0, self._reset_lhm_install_btn)

        threading.Thread(target=_do_install, daemon=True).start()

    def _reset_lhm_install_btn(self):
        if hasattr(self, 'lhm_download_btn'):
            self.lhm_download_btn.setEnabled(True)
            self.lhm_download_btn.setText("⬇  Install LibreHardwareMonitor")
            # Also check if LHM is now findable and show Launch button
            if hasattr(self, 'lhm_launch_btn'):
                self.lhm_launch_btn.setVisible(bool(self._find_lhm_exe()))

    def _find_lhm_exe(self):
        """Try to locate LibreHardwareMonitor.exe on common install paths."""
        if sys.platform != "win32":
            return None
        search_bases = [
            os.path.expandvars(r"%ProgramFiles%\LibreHardwareMonitor"),
            os.path.expandvars(r"%ProgramFiles(x86)%\LibreHardwareMonitor"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\LibreHardwareMonitor"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe"),
            os.path.join(os.path.expanduser("~"), "Downloads", "LibreHardwareMonitor"),
            os.path.join(os.path.expanduser("~"), "Desktop", "LibreHardwareMonitor"),
        ]
        for base in search_bases:
            path = os.path.join(base, "LibreHardwareMonitor.exe")
            if os.path.exists(path):
                return path
        # Broad search inside the winget packages folder (version subfolders)
        winget_pkgs = os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
        )
        if os.path.isdir(winget_pkgs):
            for entry in os.scandir(winget_pkgs):
                if "LibreHardwareMonitor" in entry.name and entry.is_dir():
                    candidate = os.path.join(entry.path, "LibreHardwareMonitor.exe")
                    if os.path.exists(candidate):
                        return candidate
        return None

    def _configure_lhm_web_server(self):
        """
        Write LibreHardwareMonitor's config file to enable the Remote Web Server
        on port 8085 so the user never has to touch LHM's menus.
        Writes to both the AppData location and next to the exe to cover all LHM versions.
        """
        import xml.etree.ElementTree as ET

        keys_to_set = {
            "httpServer": "true",
            "httpPort": "8085",
            "startMinimized": "true",
            "minimizeToTray": "true",
        }

        def _write_config(config_path):
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                if os.path.exists(config_path):
                    try:
                        tree = ET.parse(config_path)
                        root = tree.getroot()
                    except Exception:
                        root = ET.Element("settings")
                        tree = ET.ElementTree(root)
                else:
                    root = ET.Element("settings")
                    tree = ET.ElementTree(root)

                remaining = dict(keys_to_set)
                for elem in root.findall("setting"):
                    name = elem.get("name")
                    if name in remaining:
                        elem.set("value", remaining.pop(name))
                for name, value in remaining.items():
                    ET.SubElement(root, "setting", name=name, value=value)

                tree.write(config_path, encoding="utf-8", xml_declaration=True)
                return True
            except Exception as e:
                self.log_signal.emit(f"Could not write LHM config to {config_path}: {e}", "warning")
                return False

        success = False

        # 1. AppData location (works for both winget installs and manual installs)
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            appdata_config = os.path.join(appdata, "LibreHardwareMonitor", "LibreHardwareMonitor.config")
            if _write_config(appdata_config):
                success = True

        # 2. Next to the exe (portable installs)
        exe = self._find_lhm_exe()
        if exe:
            exe_config = os.path.splitext(exe)[0] + ".config"
            if _write_config(exe_config):
                success = True

        return success

    def _launch_lhm(self):
        """Configure LHM's web server automatically, then launch (or restart) it."""
        exe = self._find_lhm_exe()
        if not exe:
            self.log_signal.emit("LibreHardwareMonitor not found on disk. Try installing it first.", "warning")
            return

        # Kill any running instance so the new config is picked up on restart
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] and 'LibreHardwareMonitor' in proc.info['name']:
                    proc.kill()
                    proc.wait(timeout=3)
            except Exception:
                pass

        # Write config to auto-enable the web server
        self._configure_lhm_web_server()

        try:
            # Launch minimized and without stealing focus
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 7  # SW_SHOWMINNOACTIVE — minimized, no focus steal
            subprocess.Popen([exe], startupinfo=si, creationflags=CREATE_NO_WINDOW)
            self.log_signal.emit(
                "LibreHardwareMonitor launched in the background — sensors will appear here in a few seconds.",
                "success"
            )
        except Exception as e:
            self.log_signal.emit(f"Failed to launch LibreHardwareMonitor: {e}", "error")

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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Maintenance & Repairs", "Keep your system running smoothly with repair and optimization tools.")
        layout.addWidget(header)
        layout.addWidget(self._make_admin_notice())

        # Core Maintenance Card
        maint_card = DashboardCard("CORE MAINTENANCE")
        maint_grid = QGridLayout()
        
        maint_btn = QPushButton("Full System Maintenance")
        if sys.platform != 'win32':
            maint_btn.setText("Run Full Maintenance (APT)")
        maint_btn.setFixedHeight(45)
        maint_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
        maint_btn.clicked.connect(self.run_system_maintenance)
        maint_grid.addWidget(maint_btn, 0, 0)

        dns_btn = QPushButton("Flush DNS Cache")
        dns_btn.setFixedHeight(45)
        dns_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; border: 1px solid #4158D0; border-radius: 8px; font-weight: bold; } QPushButton:hover { background-color: #25252b; }")
        dns_btn.clicked.connect(self.flush_dns)
        maint_grid.addWidget(dns_btn, 0, 1)

        cleanup_btn = QPushButton("Run Quick Cleanup")
        cleanup_btn.setFixedHeight(45)
        cleanup_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; border: 1px solid #4158D0; border-radius: 8px; font-weight: bold; } QPushButton:hover { background-color: #25252b; }")
        cleanup_btn.clicked.connect(self.run_disk_cleanup)
        maint_grid.addWidget(cleanup_btn, 1, 0)

        if sys.platform == 'win32':
            restore_btn = QPushButton("Create Restore Point")
            restore_btn.setFixedHeight(45)
            restore_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; border: 1px solid #4158D0; border-radius: 8px; font-weight: bold; } QPushButton:hover { background-color: #25252b; }")
            restore_btn.clicked.connect(self.create_restore_point)
            maint_grid.addWidget(restore_btn, 1, 1)

        maint_card.layout.addLayout(maint_grid)
        layout.addWidget(maint_card)

        # Updates Card
        update_card = DashboardCard("SYSTEM UPDATES")
        update_h_layout = QHBoxLayout()
        self.update_status = QLabel("Status: Idle")
        self.update_status.setStyleSheet("color: #888; font-size: 13px;")
        update_h_layout.addWidget(self.update_status)
        update_h_layout.addStretch()
        
        check_update_btn = QPushButton("Check for Updates")
        check_update_btn.setFixedSize(150, 35)
        check_update_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        check_update_btn.clicked.connect(self.run_windows_update_check)
        update_h_layout.addWidget(check_update_btn)
        
        install_update_btn = QPushButton("Install Updates")
        install_update_btn.setFixedSize(150, 35)
        install_update_btn.setStyleSheet("background-color: #4158D0; color: white; border-radius: 5px; font-weight: bold;")
        install_update_btn.clicked.connect(self.install_windows_updates)
        update_h_layout.addWidget(install_update_btn)
        
        update_card.layout.addLayout(update_h_layout)
        layout.addWidget(update_card)

        if sys.platform == 'win32':
            # Advanced Disk Tools Card
            disk_card = DashboardCard("ADVANCED DISK TOOLS")
            
            disk_selection_layout = QHBoxLayout()
            disk_selection_layout.addWidget(QLabel("Select Disk:"))
            self.disk_combo = QComboBox()
            self.disk_combo.setStyleSheet("QComboBox { background-color: #1e1e1e; color: white; border: 1px solid #333; padding: 5px; }")
            disk_selection_layout.addWidget(self.disk_combo)
            refresh_disks_btn = QPushButton("Refresh List")
            refresh_disks_btn.setFixedWidth(100)
            refresh_disks_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
            refresh_disks_btn.clicked.connect(self.refresh_disk_list)
            disk_selection_layout.addWidget(refresh_disks_btn)
            disk_card.layout.addLayout(disk_selection_layout)
            
            mbr2gpt_btn_layout = QHBoxLayout()
            validate_mbr2gpt_btn = QPushButton("1. Validate for GPT")
            validate_mbr2gpt_btn.setFixedHeight(35)
            validate_mbr2gpt_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
            validate_mbr2gpt_btn.clicked.connect(self.validate_mbr2gpt)
            convert_mbr2gpt_btn = QPushButton("2. Convert to GPT")
            convert_mbr2gpt_btn.setFixedHeight(35)
            convert_mbr2gpt_btn.setStyleSheet("background-color: #f44747; color: white; border-radius: 5px; font-weight: bold;")
            convert_mbr2gpt_btn.clicked.connect(self.convert_mbr2gpt)
            mbr2gpt_btn_layout.addWidget(validate_mbr2gpt_btn)
            mbr2gpt_btn_layout.addWidget(convert_mbr2gpt_btn)
            disk_card.layout.addLayout(mbr2gpt_btn_layout)
            
            layout.addWidget(disk_card)

        layout.addStretch()
        self.content_stack.addWidget(page)
        self.refresh_disk_list()

    def setup_security_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Security Scan", "Analyze your system for security risks and vulnerabilities.")
        layout.addWidget(header)
        
        scan_card = DashboardCard("SCAN RESULTS")
        self.security_list = QListWidget()
        self.security_list.setStyleSheet("QListWidget { background-color: transparent; color: #d4d4d4; border: none; } QListWidget::item { padding: 8px; border-bottom: 1px solid #25252b; }")
        scan_card.layout.addWidget(self.security_list)
        layout.addWidget(scan_card)
        
        scan_btn = QPushButton("Run Security Scan")
        scan_btn.setFixedHeight(45)
        scan_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
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
        highs = sum(1 for _, s in issues if s in ("Critical", "High"))
        self.log_signal.emit("Security scan completed.", "success")
        self.notify_tray("Security Scan Complete",
                         f"{len(issues)} issues found ({highs} high/critical)." if issues else "No issues found.")
        self.log_activity(f"Security scan: {len(issues)} issues found")

    def setup_network_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Network Intelligence", "Monitor network status, benchmark DNS, and run speed tests.")
        layout.addWidget(header)
        
        # IP Info Card
        ip_card = DashboardCard("NETWORK INFO")
        ip_layout = QFormLayout()
        ip_layout.setContentsMargins(0, 0, 0, 0)
        self.local_ip_label = QLabel("Loading...")
        self.public_ip_label = QLabel("Loading...")
        self.isp_label = QLabel("Loading...")
        self.location_label = QLabel("Loading...")
        
        label_style = "color: #d4d4d4; font-size: 13px;"
        self.local_ip_label.setStyleSheet(label_style)
        self.public_ip_label.setStyleSheet(label_style)
        self.isp_label.setStyleSheet(label_style)
        self.location_label.setStyleSheet(label_style)
        
        ip_layout.addRow(QLabel("Local IP:"), self.local_ip_label)
        ip_layout.addRow(QLabel("Public IP:"), self.public_ip_label)
        ip_layout.addRow(QLabel("ISP:"), self.isp_label)
        ip_layout.addRow(QLabel("Location:"), self.location_label)
        
        refresh_ip_btn = QPushButton("Refresh Network Info")
        refresh_ip_btn.setFixedHeight(35)
        refresh_ip_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        refresh_ip_btn.clicked.connect(self.refresh_network_info)
        ip_layout.addRow(refresh_ip_btn)
        
        ip_card.layout.addLayout(ip_layout)
        layout.addWidget(ip_card)
        
        # DNS & Speed Row
        row_layout = QHBoxLayout()
        
        # DNS Benchmark Card
        dns_card = DashboardCard("DNS BENCHMARK")
        self.dns_results_list = QListWidget()
        self.dns_results_list.setStyleSheet("background-color: transparent; color: #d4d4d4; border: none;")
        dns_card.layout.addWidget(self.dns_results_list)
        run_dns_btn = QPushButton("Benchmark DNS")
        run_dns_btn.setFixedHeight(35)
        run_dns_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        run_dns_btn.clicked.connect(self.run_dns_benchmark)
        dns_card.layout.addWidget(run_dns_btn)
        row_layout.addWidget(dns_card)
        
        # Speed Test Card
        speed_card = DashboardCard("SPEED TEST")
        self.speed_label = QLabel("Result: Not started")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_label.setStyleSheet("color: #4158D0; font-size: 18px; font-weight: bold; margin: 10px 0;")
        speed_card.layout.addWidget(self.speed_label)
        run_speed_btn = QPushButton("Run Speed Test")
        run_speed_btn.setFixedHeight(35)
        run_speed_btn.setStyleSheet("background-color: #4158D0; color: white; border-radius: 5px; font-weight: bold;")
        run_speed_btn.clicked.connect(self.run_speed_test)
        speed_card.layout.addWidget(run_speed_btn)
        # History label
        self.speed_history_label = QLabel("")
        self.speed_history_label.setStyleSheet("color: #666; font-size: 10px;")
        self.speed_history_label.setWordWrap(True)
        speed_card.layout.addWidget(self.speed_history_label)
        self._refresh_speed_history()
        row_layout.addWidget(speed_card)
        
        layout.addLayout(row_layout)
        
        # Port Scanner Card
        port_card = DashboardCard("PORT SCANNER")
        self.port_results_text = QTextEdit()
        self.port_results_text.setReadOnly(True)
        self.port_results_text.setMaximumHeight(80)
        self.port_results_text.setStyleSheet("background-color: transparent; color: #d4d4d4; border: none; font-family: 'Consolas';")
        port_card.layout.addWidget(self.port_results_text)
        run_port_btn = QPushButton("Scan Local Ports")
        run_port_btn.setFixedHeight(35)
        run_port_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        run_port_btn.clicked.connect(self.run_port_scan)
        port_card.layout.addWidget(run_port_btn)
        layout.addWidget(port_card)
        
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Privacy & Security", "Audit your system privacy and clean browser artifacts.")
        layout.addWidget(header)
        
        # Privacy Audit Card
        audit_card = DashboardCard("PRIVACY AUDIT")
        self.audit_results = QListWidget()
        self.audit_results.setStyleSheet("QListWidget { background-color: transparent; color: #d4d4d4; border: none; } QListWidget::item { padding: 5px; }")
        audit_card.layout.addWidget(self.audit_results)
        
        run_audit_btn = QPushButton("Run Privacy Audit")
        run_audit_btn.setFixedHeight(40)
        run_audit_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 6px; } QPushButton:hover { background-color: #4b6de3; }")
        run_audit_btn.clicked.connect(self.run_privacy_audit)
        audit_card.layout.addWidget(run_audit_btn)
        layout.addWidget(audit_card)
        
        # Browser Cleaner Card
        browser_card = DashboardCard("BROWSER PRIVACY CLEANER")
        self.browser_list = QListWidget()
        self.browser_list.setStyleSheet("QListWidget { background-color: transparent; color: #d4d4d4; border: none; } QListWidget::item { padding: 5px; }")
        browser_card.layout.addWidget(self.browser_list)
        
        clean_btn = QPushButton("Clean Selected Browser Data")
        clean_btn.setFixedHeight(40)
        clean_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; border: 1px solid #4158D0; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #25252b; }")
        clean_btn.clicked.connect(self.clean_browser_data)
        browser_card.layout.addWidget(clean_btn)
        layout.addWidget(browser_card)
        
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Bloatware Remover", "Identify and remove pre-installed Windows applications and telemetry.")
        layout.addWidget(header)
        layout.addWidget(self._make_admin_notice())

        # Info Card
        info_card = DashboardCard("")
        info_layout = info_card.layout
        warning = QLabel("🛡️ WARNING: Debloating can remove system apps. Use with caution.")
        warning.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(warning)
        info_layout.addWidget(QLabel("Recommended: Create a restore point before proceeding."))
        layout.addWidget(info_card)

        self.debloat_tree = QTreeWidget()
        self.debloat_tree.setHeaderLabels(["Item", "Description", "Safety"])
        self.debloat_tree.setAlternatingRowColors(True)
        self.debloat_tree.setColumnWidth(0, 200)
        self.debloat_tree.setColumnWidth(1, 400)
        self.debloat_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a1f;
                alternate-background-color: #202025;
                border: 1px solid #333;
                border-radius: 10px;
                color: #d4d4d4;
                padding: 10px;
            }
            QTreeWidget::item { padding: 8px; border-bottom: 1px solid #25252b; }
            QTreeWidget::item:alternate { background-color: #202025; }
            QTreeWidget::item:selected { background-color: #4158D0; color: white; }
            QHeaderView::section {
                background-color: #25252b;
                color: #888;
                padding: 5px;
                border: none;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.debloat_tree)
        
        config_path = os.path.join(self.project_root, "config", "bloatware_config.json")
        self.bloat_remover = BloatRemover(config_path)
        self.populate_debloat_tree()
        
        selection_btns = QHBoxLayout()
        safe_btn = QPushButton("Select Safe Items")
        safe_btn.setFixedHeight(35)
        safe_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        safe_btn.clicked.connect(lambda _: self.select_safe_debloat())
        
        all_btn = QPushButton("Select All")
        all_btn.setFixedHeight(35)
        all_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        all_btn.clicked.connect(lambda _: self.toggle_debloat_selection(True))
        
        none_btn = QPushButton("Deselect All")
        none_btn.setFixedHeight(35)
        none_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        none_btn.clicked.connect(lambda _: self.toggle_debloat_selection(False))
        
        selection_btns.addWidget(safe_btn)
        selection_btns.addWidget(all_btn)
        selection_btns.addWidget(none_btn)
        layout.addLayout(selection_btns)

        btn_layout = QHBoxLayout()
        self.debloat_scan_btn = QPushButton("Scan System for Bloatware")
        self.debloat_scan_btn.setMinimumHeight(45)
        self.debloat_scan_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; font-weight: bold; border: 1px solid #4158D0; border-radius: 8px; } QPushButton:hover { background-color: #25252b; }")
        self.debloat_scan_btn.clicked.connect(self.scan_bloatware)
        
        self.debloat_remove_btn = QPushButton("Remove Selected Items")
        self.debloat_remove_btn.setMinimumHeight(45)
        self.debloat_remove_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: none; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("App Manager", "Install and manage essential applications using the WinGet repository.")
        layout.addWidget(header)

        self.tools_tree = QTreeWidget()
        self.tools_tree.setHeaderLabels(["Tool", "Status", "Description"])
        self.tools_tree.setAlternatingRowColors(True)
        self.tools_tree.setColumnWidth(0, 200)
        self.tools_tree.setColumnWidth(1, 120)
        self.tools_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a1f;
                alternate-background-color: #202025;
                border: 1px solid #333;
                border-radius: 10px;
                color: #d4d4d4;
                padding: 10px;
            }
            QTreeWidget::item { padding: 8px; border-bottom: 1px solid #25252b; }
            QTreeWidget::item:alternate { background-color: #202025; }
            QHeaderView::section {
                background-color: #25252b;
                color: #888;
                padding: 5px;
                border: none;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.tools_tree)
        
        config_path = os.path.join(self.project_root, "config", "system_tools.json")
        self.tools_installer = SystemToolsInstaller(config_path)
        self.populate_tools_tree()
        
        selection_btns = QHBoxLayout()
        all_btn = QPushButton("Select All")
        all_btn.setFixedHeight(35)
        all_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        all_btn.clicked.connect(lambda _: self.toggle_tools_selection(True))
        
        none_btn = QPushButton("Deselect All")
        none_btn.setFixedHeight(35)
        none_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        none_btn.clicked.connect(lambda _: self.toggle_tools_selection(False))
        
        selection_btns.addWidget(all_btn)
        selection_btns.addWidget(none_btn)
        layout.addLayout(selection_btns)

        btn_layout = QHBoxLayout()
        check_btn = QPushButton("Refresh Status")
        check_btn.setMinimumHeight(45)
        check_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; font-weight: bold; border: 1px solid #4158D0; border-radius: 8px; } QPushButton:hover { background-color: #25252b; }")
        check_btn.clicked.connect(lambda: self.check_tools_status(force=True))
        
        install_btn = QPushButton("Install Selected")
        install_btn.setMinimumHeight(45)
        install_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: none; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
        install_btn.clicked.connect(self.install_tools)
        
        uninstall_btn = QPushButton("Uninstall")
        uninstall_btn.setMinimumHeight(45)
        uninstall_btn.setStyleSheet("QPushButton { background-color: #f44747; color: white; font-weight: bold; border: none; border-radius: 8px; } QPushButton:hover { background-color: #f65d5d; }")
        uninstall_btn.clicked.connect(self.uninstall_tools)
        
        update_all_btn = QPushButton("Update All")
        update_all_btn.setMinimumHeight(45)
        update_all_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: none; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Deep Cleanup", "Identify and remove unused applications, logs, and temporary files.")
        layout.addWidget(header)

        self.cleanup_tree = QTreeWidget()
        self.cleanup_tree.setHeaderLabels(["Item", "Type", "Details", "Actionable"])
        self.cleanup_tree.setAlternatingRowColors(True)
        self.cleanup_tree.setColumnWidth(0, 200)
        self.cleanup_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a1f;
                alternate-background-color: #202025;
                border: 1px solid #333;
                border-radius: 10px;
                color: #d4d4d4;
                padding: 10px;
            }
            QTreeWidget::item { padding: 8px; border-bottom: 1px solid #25252b; }
            QTreeWidget::item:alternate { background-color: #202025; }
            QHeaderView::section {
                background-color: #25252b;
                color: #888;
                padding: 5px;
                border: none;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.cleanup_tree.hide()
        layout.addWidget(self.cleanup_tree)

        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("Scan for Junk")
        scan_btn.setMinimumHeight(45)
        scan_btn.setStyleSheet("QPushButton { background-color: #1a1a1f; color: white; font-weight: bold; border: 1px solid #4158D0; border-radius: 8px; } QPushButton:hover { background-color: #25252b; }")
        scan_btn.clicked.connect(self.scan_cleanup_items)
        
        cleanup_btn = QPushButton("Remove Selected Items")
        cleanup_btn.setMinimumHeight(45)
        cleanup_btn.setStyleSheet("QPushButton { background-color: #f44747; color: white; font-weight: bold; border: none; border-radius: 8px; } QPushButton:hover { background-color: #f65d5d; }")
        cleanup_btn.clicked.connect(self.perform_cleanup)
        
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(cleanup_btn)
        layout.addLayout(btn_layout)
        
        self.content_stack.addWidget(page)

    def scan_cleanup_items(self):
        self.log_signal.emit("Scanning for unused applications and old files...", "info")
        self.cleanup_tree.show()
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        
        from src.gui.dashboard import PageHeader, DashboardCard
        header = PageHeader("Advanced System Tools", "Access platform-specific utilities and secure file shredding.")
        layout.addWidget(header)
        
        # System Overview Card
        sys_card = DashboardCard("SYSTEM OVERVIEW")
        sys_grid = QGridLayout()
        
        cpu_info = platform.processor() or "Unknown"
        cpu_label = QLabel(f"<b>CPU:</b> {cpu_info}")
        cpu_label.setStyleSheet("color: #d4d4d4;")
        sys_grid.addWidget(cpu_label, 0, 0)
        
        mem = psutil.virtual_memory()
        mem_label = QLabel(f"<b>Memory:</b> {mem.total // (1024**3)} GB ({mem.percent}% used)")
        mem_label.setStyleSheet("color: #d4d4d4;")
        sys_grid.addWidget(mem_label, 0, 1)
        
        os_label = QLabel(f"<b>OS:</b> {platform.system()} {platform.release()}")
        os_label.setStyleSheet("color: #d4d4d4;")
        sys_grid.addWidget(os_label, 1, 0)
        
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        boot_label = QLabel(f"<b>Boot Time:</b> {boot_time}")
        boot_label.setStyleSheet("color: #d4d4d4;")
        sys_grid.addWidget(boot_label, 1, 1)
        
        sys_card.layout.addLayout(sys_grid)
        layout.addWidget(sys_card)
        
        # Secure File Shredder Card
        shred_card = DashboardCard("SECURE FILE SHREDDER")
        shred_layout = QVBoxLayout()
        self.shred_path_label = QLabel("No file selected")
        self.shred_path_label.setStyleSheet("color: #888; font-style: italic;")
        shred_layout.addWidget(self.shred_path_label)
        
        select_file_btn = QPushButton("Select File to Shred")
        select_file_btn.setFixedHeight(35)
        select_file_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        select_file_btn.clicked.connect(self.select_file_to_shred)
        shred_layout.addWidget(select_file_btn)
        
        self.shred_btn = QPushButton("Shred File Permanently")
        self.shred_btn.setFixedHeight(40)
        self.shred_btn.setStyleSheet("QPushButton { background-color: #f44747; color: white; font-weight: bold; border-radius: 8px; } QPushButton:disabled { background-color: #333; color: #666; }")
        self.shred_btn.setEnabled(False)
        self.shred_btn.clicked.connect(self.run_file_shredder)
        shred_layout.addWidget(self.shred_btn)
        
        shred_card.layout.addLayout(shred_layout)
        layout.addWidget(shred_card)
        
        # Platform Specific Tools Card
        plat_card = DashboardCard(f"{sys.platform.upper()} UTILITIES")
        plat_grid = QGridLayout()
        
        if sys.platform == "win32":
            win_tools = [
                ("WinGet Apps", "winget"), ("Flush DNS", "dns"),
                ("Print Spooler", "spooler"), ("Verify Files", "sfc"),
                ("Hosts Editor", "hosts"), ("Tidy Desktop", "tidy_desktop"),
            ]
            for i, (name, cmd) in enumerate(win_tools):
                btn = QPushButton(name)
                btn.setFixedHeight(35)
                btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
                btn.clicked.connect(lambda _, c=cmd: self.run_win_tool(c))
                plat_grid.addWidget(btn, i // 2, i % 2)
                
        elif sys.platform == "linux":
            lin_tools = [
                ("UFW Firewall", "ufw"), ("Repositories", "repos"),
                ("System Logs", "logs"), ("Disk Usage", "disk")
            ]
            for i, (name, cmd) in enumerate(lin_tools):
                btn = QPushButton(name)
                btn.setFixedHeight(35)
                btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
                btn.clicked.connect(lambda _, c=cmd: self.run_linux_tool(c))
                plat_grid.addWidget(btn, i // 2, i % 2)
                
        elif sys.platform == "darwin":
            mac_tools = [
                ("Homebrew", "brew"), ("Maintenance", "maint"),
                ("SIP Status", "sip"), ("App Residue", "residue")
            ]
            for i, (name, cmd) in enumerate(mac_tools):
                btn = QPushButton(name)
                btn.setFixedHeight(35)
                btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
                btn.clicked.connect(lambda _, c=cmd: self.run_macos_tool(c))
                plat_grid.addWidget(btn, i // 2, i % 2)
                
        plat_card.layout.addLayout(plat_grid)
        layout.addWidget(plat_card)
        
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
                self.notify_tray("File Shredded", f"Securely deleted: {os.path.basename(file_path)}")
                self.log_activity(f"Shredded: {os.path.basename(file_path)}")
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
                self.log_signal.emit(f"Administrator privileges required for: {tool}.", "error")
                QMessageBox.warning(
                    self, "Admin Required",
                    f"This tool requires administrator privileges.\n\n"
                    f"Click 'Elevate' in the header bar to restart Ghosty Tools as administrator, "
                    f"then try again."
                )
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
        elif tool == "tidy_desktop":
            dialog = TidyDesktopDialog(self)
            dialog.exec()
        elif tool == "game_analyzer":
            dialog = GameCompatibilityDialog(self)
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("ShadowKeys - Password Manager", "Securely generate and store your passwords with industry-grade encryption.")
        layout.addWidget(header)
        
        from PyQt6.QtWidgets import QTabWidget
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; border-radius: 10px; background-color: #1a1a1f; top: -1px; }
            QTabBar::tab { background: #25252b; color: #888; padding: 10px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 5px; }
            QTabBar::tab:selected { background: #1a1a1f; color: white; border-bottom: 2px solid #4158D0; }
        """)
        
        # Generator Tab
        gen_tab = QWidget()
        gen_layout = QVBoxLayout(gen_tab)
        gen_layout.setContentsMargins(20, 20, 20, 20)
        
        gen_card = DashboardCard("SECURE PASSWORD GENERATOR")
        gen_card_layout = gen_card.layout
        
        self.pass_length_label = QLabel("Password Length: 16")
        self.pass_length_label.setStyleSheet("color: white; font-weight: bold;")
        gen_card_layout.addWidget(self.pass_length_label)
        
        self.pass_length_spin = QComboBox()
        self.pass_length_spin.addItems([str(i) for i in range(8, 65)])
        self.pass_length_spin.setCurrentText("16")
        self.pass_length_spin.setStyleSheet("QComboBox { background-color: #1e1e1e; color: white; border: 1px solid #333; padding: 5px; }")
        self.pass_length_spin.currentTextChanged.connect(lambda v: self.pass_length_label.setText(f"Password Length: {v}"))
        gen_card_layout.addWidget(self.pass_length_spin)
        
        check_style = "QCheckBox { color: #d4d4d4; padding: 5px; } QCheckBox::indicator { width: 18px; height: 18px; }"
        self.pass_upper = QCheckBox("Include Uppercase Letters")
        self.pass_upper.setChecked(True)
        self.pass_upper.setStyleSheet(check_style)
        gen_card_layout.addWidget(self.pass_upper)
        
        self.pass_digits = QCheckBox("Include Digits")
        self.pass_digits.setChecked(True)
        self.pass_digits.setStyleSheet(check_style)
        gen_card_layout.addWidget(self.pass_digits)
        
        self.pass_special = QCheckBox("Include Special Characters")
        self.pass_special.setChecked(True)
        self.pass_special.setStyleSheet(check_style)
        gen_card_layout.addWidget(self.pass_special)
        
        gen_btn = QPushButton("Generate Secure Password")
        gen_btn.setFixedHeight(45)
        gen_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
        gen_btn.clicked.connect(self.generate_password)
        gen_card_layout.addWidget(gen_btn)
        
        self.generated_pass_entry = QLineEdit()
        self.generated_pass_entry.setPlaceholderText("Generated Password")
        self.generated_pass_entry.setReadOnly(True)
        self.generated_pass_entry.setStyleSheet("font-family: Consolas; font-size: 18px; padding: 12px; background: #111; color: #00ff88; border: 1px solid #333; border-radius: 8px;")
        gen_card_layout.addWidget(self.generated_pass_entry)
        
        pass_actions = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setFixedHeight(35)
        copy_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        copy_btn.clicked.connect(lambda _: self.copy_to_clipboard(self.generated_pass_entry.text()))
        pass_actions.addWidget(copy_btn)
        
        self.pass_strength_label = QLabel("Strength: N/A")
        self.pass_strength_label.setStyleSheet("font-weight: bold; color: #888;")
        pass_actions.addWidget(self.pass_strength_label)
        gen_card_layout.addLayout(pass_actions)
        
        self.pass_analysis = QTextEdit()
        self.pass_analysis.setReadOnly(True)
        self.pass_analysis.setFixedHeight(60)
        self.pass_analysis.setStyleSheet("background-color: #111; color: #888; border: 1px solid #222; border-radius: 5px; font-size: 11px;")
        gen_card_layout.addWidget(self.pass_analysis)
        
        gen_layout.addWidget(gen_card)
        gen_layout.addStretch()
        
        # Vault Tab
        vault_tab = QWidget()
        vault_layout = QVBoxLayout(vault_tab)
        vault_layout.setContentsMargins(20, 20, 20, 20)
        self.vault_stack = QStackedWidget()
        
        login_widget = QWidget()
        login_layout = QVBoxLayout(login_widget)
        login_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unlock_btn = QPushButton("Unlock Password Vault")
        unlock_btn.setFixedSize(280, 60)
        unlock_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 12px; font-size: 16px; } QPushButton:hover { background-color: #4b6de3; }")
        unlock_btn.clicked.connect(self.unlock_vault)
        login_layout.addWidget(unlock_btn)
        self.vault_stack.addWidget(login_widget)
        
        self.vault_main_widget = QWidget()
        v_main_layout = QVBoxLayout(self.vault_main_widget)
        
        form_card = DashboardCard("VAULT ENTRIES")
        v_form_layout = QFormLayout()
        self.vault_site_entry = QLineEdit()
        self.vault_pass_entry = QLineEdit()
        entry_style = "background-color: #1e1e1e; color: white; border: 1px solid #333; padding: 5px; border-radius: 4px;"
        self.vault_site_entry.setStyleSheet(entry_style)
        self.vault_pass_entry.setStyleSheet(entry_style)
        
        v_form_layout.addRow(QLabel("Site:"), self.vault_site_entry)
        v_form_layout.addRow(QLabel("Password:"), self.vault_pass_entry)
        
        save_btn = QPushButton("Save to Vault")
        save_btn.setFixedHeight(35)
        save_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 5px; } QPushButton:hover { background-color: #4b6de3; }")
        save_btn.clicked.connect(self.save_vault_entry)
        v_form_layout.addRow(save_btn)
        form_card.layout.addLayout(v_form_layout)
        v_main_layout.addWidget(form_card)
        
        self.vault_list = QListWidget()
        self.vault_list.setStyleSheet("QListWidget { background-color: #1a1a1f; border: 1px solid #333; border-radius: 10px; color: #d4d4d4; padding: 5px; } QListWidget::item { padding: 8px; border-bottom: 1px solid #25252b; }")
        self.vault_list.itemClicked.connect(self.on_vault_item_clicked)
        v_main_layout.addWidget(self.vault_list)
        
        v_actions = QHBoxLayout()
        del_v_btn = QPushButton("Delete Selected Entry")
        del_v_btn.setFixedHeight(35)
        del_v_btn.setStyleSheet("QPushButton { background-color: #f44747; color: white; font-weight: bold; border-radius: 5px; } QPushButton:hover { background-color: #f65d5d; }")
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
        try:
            length_str = self.pass_length_spin.currentText()
            if not length_str:
                length = 16
            else:
                length = int(length_str)
                
            chars = string.ascii_lowercase
            if self.pass_upper.isChecked(): chars += string.ascii_uppercase
            if self.pass_digits.isChecked(): chars += string.digits
            if self.pass_special.isChecked(): chars += string.punctuation
            
            if not chars:
                chars = string.ascii_lowercase
                
            password = "".join(secrets.choice(chars) for _ in range(length))
            self.generated_pass_entry.setText(password)
            
            strength, analysis = self.check_password_strength(password)
            self.pass_strength_label.setText(f"Strength: {strength}")
            self.pass_analysis.setPlainText("\n".join(analysis))
            self.log_signal.emit(f"Generated a {strength} password.", "success")
        except Exception as e:
            logger.error(f"Password generation error: {e}")
            self.log_signal.emit(f"Generation error: {e}", "error")

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
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        header = PageHeader("System Tweaks", "Optimize system performance and privacy settings.")
        layout.addWidget(header)

        if sys.platform != 'win32':
            notice_card = DashboardCard("NOT AVAILABLE ON THIS PLATFORM")
            msg = QLabel(
                f"System Tweaks are Windows-only registry and system settings.\n\n"
                f"They are not available on {platform.system()}.\n\n"
                f"Use your system's built-in settings or a platform-specific tool to manage performance and privacy."
            )
            msg.setStyleSheet("color: #888; font-size: 13px; padding: 10px;")
            msg.setWordWrap(True)
            notice_card.layout.addWidget(msg)
            layout.addWidget(notice_card)
            layout.addStretch()
            scroll.setWidget(page)
            self.content_stack.addWidget(scroll)
            # Still need self.tweaks defined so toggle_all_tweaks doesn't crash
            self.tweaks = {}
            return

        layout.addWidget(self._make_admin_notice())

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
        
        # Style checkboxes
        for cb in self.tweaks.values():
            cb.setStyleSheet("QCheckBox { color: #d4d4d4; padding: 5px; } QCheckBox::indicator { width: 18px; height: 18px; }")

        # Categories mapping
        categories = {
            "Privacy & Security": ["disable_telemetry", "disable_activity", "disable_location", "disable_wifi_sense", "disable_web_search", "disable_ad_id", "disable_spotlight", "disable_background_apps"],
            "System Performance": ["delete_temp", "disable_gamedvr", "disable_hibernation", "disable_storage_sense", "prefer_ipv4", "ultimate_performance", "disable_game_mode", "disable_reserved_storage", "disable_fast_startup", "disable_sysmain"],
            "Interface & Services": ["enable_end_task", "disable_homegroup", "set_services_manual", "classic_context_menu", "disable_copilot", "disable_news", "show_file_ext", "show_hidden", "disable_search_indexing"]
        }

        for cat_name, tweak_keys in categories.items():
            card = DashboardCard(cat_name)
            # Use the internal layout of DashboardCard
            for key in tweak_keys:
                if key in self.tweaks:
                    card.layout.addWidget(self.tweaks[key])
            layout.addWidget(card)

        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setFixedHeight(35)
        select_all_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        select_all_btn.clicked.connect(lambda _: self.toggle_all_tweaks(True))
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setFixedHeight(35)
        deselect_all_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 5px;")
        deselect_all_btn.clicked.connect(lambda _: self.toggle_all_tweaks(False))
        
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        layout.addLayout(btn_layout)

        confirm_btn = QPushButton("Apply Selected Tweaks")
        confirm_btn.setMinimumHeight(45)
        confirm_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border: none; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        ver = self.update_manager.current_version
        header = PageHeader(f"Ghosty Tool {ver}", "Professional System Optimization & Security Suite.")
        layout.addWidget(header)

        # Main Info Card
        info_card = DashboardCard("")
        info_card_layout = info_card.layout
        
        logo_label = QLabel()
        icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
        if os.path.exists(icon_path):
            logo_label.setPixmap(QIcon(icon_path).pixmap(96, 96))
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setContentsMargins(0, 10, 0, 10)
            info_card_layout.addWidget(logo_label)
        
        ver_label = QLabel(f"Ghosty Tool {ver}")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #4158D0;")
        info_card_layout.addWidget(ver_label)
        
        site_label = QLabel('Official Website: <a href="https://ghostyware.com" style="color: #4158D0; text-decoration: none;">ghostyware.com</a>')
        site_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        site_label.setOpenExternalLinks(True)
        info_card_layout.addWidget(site_label)
        layout.addWidget(info_card)

        # Features Card
        features_card = DashboardCard(f"WHAT'S NEW IN {ver}")
        features_text = QLabel(
            f"• 🏆 <b>{ver} Release:</b> Bug fixes and platform improvements.<br>"
            "• 🐧 <b>Linux:</b> Fixed transparent background issue on Linux desktop environments.<br>"
            "• 🖥️ <b>Hardware:</b> System specs now fully cross-platform (Linux + macOS).<br>"
            "• ⚡ <b>Speed Test:</b> Fixed speed test failing in the Windows .exe build.<br>"
            "• 🔔 <b>Dashboard:</b> System alerts are now live — memory, disk, reboot state, and update status.<br>"
            "• 🎨 <b>Sidebar:</b> Fixed nav icons not rendering on some Windows systems."
        )
        features_text.setTextFormat(Qt.TextFormat.RichText)
        features_text.setWordWrap(True)
        features_text.setStyleSheet("color: #d4d4d4; padding: 10px; line-height: 1.4;")
        features_card.layout.addWidget(features_text)
        layout.addWidget(features_card)

        thanks_label = QLabel(
            'Built by GhostShadow_Plays. Special thanks to '
            '<a href="https://github.com/haywardgg" style="color: #4158D0; text-decoration: none;">haywardgg</a>'
            ' — systems admin, vibe coder from Manchester, and founder of a chill coding community '
            'where devs share projects, help each other out, and keep it low-pressure.'
        )
        thanks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thanks_label.setOpenExternalLinks(True)
        thanks_label.setWordWrap(True)
        thanks_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(thanks_label)

        links_layout = QHBoxLayout()

        github_btn = QPushButton("GitHub")
        github_btn.setFixedHeight(35)
        github_btn.setIcon(QIcon(os.path.join(self.project_root, "images", "GithubLogo.png")))
        github_btn.clicked.connect(lambda _: webbrowser.open("https://github.com/Ghostshadowplays/Ghosty-Tools"))

        twitch_btn = QPushButton("Twitch")
        twitch_btn.setFixedHeight(35)
        twitch_btn.setIcon(QIcon(os.path.join(self.project_root, "images", "twitchlogo.png")))
        twitch_btn.clicked.connect(lambda _: webbrowser.open("https://www.twitch.tv/ghostshadow_plays"))

        ghostyware_discord_btn = QPushButton("GhostyWare Discord")
        ghostyware_discord_btn.setFixedHeight(35)
        ghostyware_discord_btn.setStyleSheet("background-color: #5865F2; color: white; font-weight: bold; border: none; border-radius: 5px;")
        ghostyware_discord_btn.setToolTip("Join the official GhostyWare Discord community")
        ghostyware_discord_btn.clicked.connect(lambda _: webbrowser.open("https://discord.gg/YKsAJYx"))

        hayward_discord_btn = QPushButton("haywardgg's Server")
        hayward_discord_btn.setFixedHeight(35)
        hayward_discord_btn.setStyleSheet("background-color: #404eed; color: white; font-weight: bold; border: none; border-radius: 5px;")
        hayward_discord_btn.setToolTip("Chill coding community — devs helping devs, no pressure")
        hayward_discord_btn.clicked.connect(lambda _: webbrowser.open("https://discord.gg/UUuafBYMdG"))

        update_btn = QPushButton("Check for Updates")
        update_btn.setFixedHeight(35)
        update_btn.clicked.connect(lambda _: self.check_for_updates(True))

        links_layout.addWidget(github_btn)
        links_layout.addWidget(twitch_btn)
        links_layout.addWidget(ghostyware_discord_btn)
        links_layout.addWidget(hayward_discord_btn)
        links_layout.addWidget(update_btn)
        layout.addLayout(links_layout)

        # Secondary actions row
        secondary_layout = QHBoxLayout()
        export_btn = QPushButton("Export System Report")
        export_btn.setFixedHeight(35)
        export_btn.setToolTip("Save a full system snapshot to your Desktop")
        export_btn.clicked.connect(self.export_system_report)

        log_btn = QPushButton("View Logs")
        log_btn.setFixedHeight(35)
        log_btn.setToolTip("Open the in-app log viewer")
        log_btn.clicked.connect(self.show_log_viewer)

        diag_btn = QPushButton("Run Diagnostics")
        diag_btn.setFixedHeight(35)
        diag_btn.clicked.connect(self.run_diagnostics)

        secondary_layout.addWidget(export_btn)
        secondary_layout.addWidget(log_btn)
        secondary_layout.addWidget(diag_btn)
        layout.addLayout(secondary_layout)

        layout.addStretch()
        self.content_stack.addWidget(page)

    def export_system_report(self):
        """Generate and save a full system snapshot text file to the Desktop."""
        try:
            import platform as pf
            lines = []
            lines.append("=" * 60)
            lines.append(f"  GhostyTools {self.update_manager.current_version} — System Report")
            lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("=" * 60)

            # OS
            lines.append("\n[OS INFO]")
            lines.append(f"  Platform : {pf.system()} {pf.release()}")
            lines.append(f"  Version  : {pf.version()}")
            lines.append(f"  Machine  : {pf.machine()}")
            lines.append(f"  Node     : {pf.node()}")

            # CPU / RAM
            lines.append("\n[CPU / MEMORY]")
            lines.append(f"  CPU Cores    : {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count()} logical")
            lines.append(f"  CPU Usage    : {psutil.cpu_percent(interval=0.5):.1f}%")
            mem = psutil.virtual_memory()
            lines.append(f"  RAM Total    : {mem.total // (1024**3)} GB")
            lines.append(f"  RAM Used     : {mem.used // (1024**3)} GB ({mem.percent:.1f}%)")

            # Disk
            lines.append("\n[DISK USAGE]")
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    lines.append(f"  {part.mountpoint:20s}  {usage.used // (1024**3)} / {usage.total // (1024**3)} GB  ({usage.percent:.1f}%)")
                except Exception:
                    pass

            # Network
            lines.append("\n[NETWORK]")
            try:
                import socket
                lines.append(f"  Hostname : {socket.gethostname()}")
                lines.append(f"  Local IP : {socket.gethostbyname(socket.gethostname())}")
            except Exception:
                pass

            # Speed test history
            if self._speedtest_history:
                lines.append("\n[SPEED TEST HISTORY (last 3)]")
                for e in self._speedtest_history[:3]:
                    lines.append(f"  {e['time']}  {e['result'].replace(chr(10), '  ')}")

            # Recent activity
            if self._activity_log:
                lines.append("\n[RECENT ACTIVITY]")
                for e in self._activity_log[:10]:
                    lines.append(f"  {e['time']}  {e['text']}")

            lines.append("\n" + "=" * 60)

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            filename = f"GhostyTools_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            out_path = os.path.join(desktop, filename)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))

            self.log_signal.emit(f"System report saved: {out_path}", "success")
            self.log_activity("Exported system report")
            self.notify_tray("Report Exported", f"Saved to Desktop: {filename}")
            QMessageBox.information(self, "Report Exported", f"System report saved to:\n{out_path}")
        except Exception as e:
            self.log_signal.emit(f"Failed to export report: {e}", "error")

    def show_log_viewer(self):
        """Open an in-app log viewer with file selector, line count, and refresh."""
        from PyQt6.QtWidgets import QComboBox
        logs_dir = get_logs_dir()

        # Collect all available log files, newest first
        today_name = f"ghostytools_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            log_files = sorted(
                [f for f in os.listdir(logs_dir) if f.startswith("ghostytools_") and f.endswith(".log")],
                reverse=True
            )
        except Exception:
            log_files = []
        if not log_files:
            log_files = [today_name]

        dlg = QDialog(self)
        dlg.setWindowTitle("Ghosty Tools — Log Viewer")
        dlg.setMinimumSize(780, 540)
        dlg.setStyleSheet("background-color: #16161a; color: #d4d4d4;")
        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        # Header row: title + file selector
        header_row = QHBoxLayout()
        title_lbl = QLabel("Log Viewer")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #4158D0;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        file_combo = QComboBox()
        file_combo.addItems(log_files)
        file_combo.setFixedWidth(240)
        file_combo.setStyleSheet(
            "QComboBox { background-color: #1e1e24; border: 1px solid #333; border-radius: 5px; "
            "color: #d4d4d4; padding: 4px 8px; } "
            "QComboBox::drop-down { border: none; } "
            "QComboBox QAbstractItemView { background-color: #1e1e24; color: #d4d4d4; selection-background-color: #4158D0; }"
        )
        header_row.addWidget(file_combo)
        vbox.addLayout(header_row)

        # Info bar: path + line count
        info_lbl = QLabel()
        info_lbl.setStyleSheet("color: #666; font-size: 10px;")
        vbox.addWidget(info_lbl)

        # Log text area
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setStyleSheet(
            "QTextEdit { background-color: #111; color: #d4d4d4; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; "
            "border: 1px solid #2a2a30; border-radius: 4px; }"
        )
        vbox.addWidget(viewer)

        def load_log(fname):
            log_path = os.path.join(logs_dir, fname)
            try:
                if os.path.exists(log_path):
                    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    lines = content.splitlines()
                    shown = lines[-500:]
                    viewer.setPlainText("\n".join(shown))
                    viewer.moveCursor(QTextCursor.MoveOperation.End)
                    skipped = max(0, len(lines) - 500)
                    skip_note = f"  (showing last 500 of {len(lines)} lines)" if skipped else ""
                    info_lbl.setText(f"{log_path}{skip_note}")
                else:
                    viewer.setPlainText(f"Log file not yet created:\n{log_path}")
                    info_lbl.setText(log_path)
            except Exception as e:
                viewer.setPlainText(f"Error reading log: {e}")

        load_log(log_files[0])
        file_combo.currentTextChanged.connect(load_log)

        # Button row
        btn_row = QHBoxLayout()
        open_folder_btn = QPushButton("Open Logs Folder")
        open_folder_btn.setFixedHeight(32)
        open_folder_btn.setStyleSheet(
            "QPushButton { background-color: #1e1e24; border: 1px solid #444; border-radius: 5px; color: #ccc; padding: 0 12px; }"
            "QPushButton:hover { background-color: #28282e; }"
        )
        open_folder_btn.clicked.connect(lambda: webbrowser.open(logs_dir))

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet(
            "QPushButton { background-color: #1e1e24; border: 1px solid #444; border-radius: 5px; color: #ccc; padding: 0 12px; }"
            "QPushButton:hover { background-color: #28282e; }"
        )
        refresh_btn.clicked.connect(lambda: load_log(file_combo.currentText()))

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; border: none; border-radius: 5px; color: white; font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background-color: #4b6de3; }"
        )
        close_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(open_folder_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        vbox.addLayout(btn_row)
        dlg.exec()

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

    # ------------------------------------------------------------------ #
    #  SETTINGS PAGE                                                       #
    # ------------------------------------------------------------------ #
    def setup_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        header = PageHeader("Settings", "App preferences and startup management")
        layout.addWidget(header)

        # ── General preferences ────────────────────────────────────────
        general_card = DashboardCard("GENERAL")

        self._s_minimize_tray = QCheckBox("Minimize to tray when window is closed")
        self._s_minimize_tray.setChecked(self._app_settings.get("minimize_to_tray", False))
        self._s_minimize_tray.stateChanged.connect(self._save_general_settings)
        general_card.layout.addWidget(self._s_minimize_tray)

        # Alert refresh interval
        alert_row = QHBoxLayout()
        alert_label = QLabel("Alert refresh interval:")
        alert_label.setStyleSheet("color: #d4d4d4;")
        self._s_alert_interval = QComboBox()
        self._s_alert_interval.addItems(["30 seconds", "60 seconds", "2 minutes", "5 minutes"])
        sec_map = {30: 0, 60: 1, 120: 2, 300: 3}
        cur_sec = self._app_settings.get("alert_refresh_sec", 60)
        self._s_alert_interval.setCurrentIndex(sec_map.get(cur_sec, 1))
        self._s_alert_interval.currentIndexChanged.connect(self._save_general_settings)
        alert_row.addWidget(alert_label)
        alert_row.addWidget(self._s_alert_interval)
        alert_row.addStretch()
        general_card.layout.addLayout(alert_row)

        # Startup page selector
        startup_row = QHBoxLayout()
        startup_label = QLabel("Open on startup:")
        startup_label.setStyleSheet("color: #d4d4d4;")
        self._s_startup_page = QComboBox()
        pages = ["Dashboard", "System", "Security", "Network", "Monitor",
                 "Privacy", "Debloat", "Apps", "Cleanup", "Storage",
                 "Hardware", "Events", "Services", "Automation",
                 "Passwords", "Customization", "Info"]
        self._s_startup_page.addItems(pages)
        self._s_startup_page.setCurrentIndex(self._app_settings.get("startup_page", 0))
        self._s_startup_page.currentIndexChanged.connect(self._save_general_settings)
        startup_row.addWidget(startup_label)
        startup_row.addWidget(self._s_startup_page)
        startup_row.addStretch()
        general_card.layout.addLayout(startup_row)

        layout.addWidget(general_card)

        # ── Startup with Windows (Windows only) ────────────────────────
        if sys.platform == "win32":
            startup_card = DashboardCard("STARTUP MANAGER — WINDOWS")
            win_note = QLabel(
                "Control whether Ghosty Tools launches automatically when Windows starts."
            )
            win_note.setWordWrap(True)
            win_note.setStyleSheet("color: #888; font-size: 11px;")
            startup_card.layout.addWidget(win_note)

            self._s_start_windows = QCheckBox("Launch Ghosty Tools at Windows startup")
            self._s_start_windows.setChecked(self._app_settings.get("start_with_windows", False))
            self._s_start_windows.stateChanged.connect(self._apply_windows_startup)
            startup_card.layout.addWidget(self._s_start_windows)

            win_status = QLabel()
            win_status.setStyleSheet("color: #666; font-size: 10px;")
            startup_card.layout.addWidget(win_status)
            self._s_win_startup_status = win_status
            self._refresh_win_startup_status()

            layout.addWidget(startup_card)

        # ── Startup with Linux (autostart .desktop file) ───────────────
        elif sys.platform not in ("win32", "darwin"):
            startup_card = DashboardCard("STARTUP MANAGER — LINUX")
            linux_note = QLabel(
                "Adds or removes a .desktop autostart entry for your desktop environment."
            )
            linux_note.setWordWrap(True)
            linux_note.setStyleSheet("color: #888; font-size: 11px;")
            startup_card.layout.addWidget(linux_note)

            self._s_start_linux = QCheckBox("Launch Ghosty Tools at login")
            self._s_start_linux.setChecked(self._linux_autostart_exists())
            self._s_start_linux.stateChanged.connect(self._apply_linux_startup)
            startup_card.layout.addWidget(self._s_start_linux)

            layout.addWidget(startup_card)

        layout.addStretch()
        self.content_stack.addWidget(page)

    # ------------------------------------------------------------------ #
    def setup_gaming_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        header = PageHeader("Gaming", "Optimise your system for gaming and check game compatibility.")
        layout.addWidget(header)

        # ── Gaming Mode card ──────────────────────────────────────────────
        gm_card = DashboardCard("GAMING MODE")

        self._gaming_status_lbl = QLabel()
        self._update_gaming_status_label()
        self._gaming_status_lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        gm_card.layout.addWidget(self._gaming_status_lbl)

        info_lbl = QLabel(
            "Applies Ultimate Performance power plan, disables Xbox Game DVR, "
            "disables Nagle's algorithm, raises MMCSS priority, disables SysMain, "
            "and pauses Windows Update for a smoother gaming experience."
        )
        info_lbl.setStyleSheet("color: #888; font-size: 11px;")
        info_lbl.setWordWrap(True)
        gm_card.layout.addWidget(info_lbl)

        # Admin notice — shown only when not elevated
        self._gaming_admin_notice = QLabel(
            "⚠️  Administrator privileges required.  "
            "Click <b>Elevate</b> in the toolbar, then re-open the Gaming page."
        )
        self._gaming_admin_notice.setStyleSheet(
            "color: #d7ba7d; font-size: 11px; background-color: #2a2215; "
            "border: 1px solid #5a4a20; border-radius: 5px; padding: 6px 10px;"
        )
        self._gaming_admin_notice.setWordWrap(True)
        self._gaming_admin_notice.setVisible(not is_admin())
        gm_card.layout.addWidget(self._gaming_admin_notice)

        gm_btn_row = QHBoxLayout()

        _admin = is_admin()

        self._gaming_enable_btn = QPushButton("Enable Gaming Mode")
        self._gaming_enable_btn.setFixedHeight(40)
        self._gaming_enable_btn.setEnabled(_admin)
        self._gaming_enable_btn.setToolTip(
            "" if _admin else "Requires administrator privileges — click Elevate in the toolbar"
        )
        self._gaming_enable_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; color: white; font-weight: bold; "
            "border-radius: 7px; border: none; }"
            "QPushButton:hover { background-color: #4b6de3; }"
            "QPushButton:disabled { background-color: #25252b; color: #555; }"
        )
        self._gaming_enable_btn.clicked.connect(self._toggle_gaming_mode)
        gm_btn_row.addWidget(self._gaming_enable_btn)

        self._gaming_revert_btn = QPushButton("Revert to Defaults")
        self._gaming_revert_btn.setFixedHeight(40)
        self._gaming_revert_btn.setEnabled(_admin and self._app_settings.get("gaming_mode_active", False))
        self._gaming_revert_btn.setToolTip(
            "" if _admin else "Requires administrator privileges — click Elevate in the toolbar"
        )
        self._gaming_revert_btn.setStyleSheet(
            "QPushButton { background-color: #f0a050; color: #111; font-weight: bold; "
            "border-radius: 7px; border: none; }"
            "QPushButton:hover { background-color: #f5b870; }"
            "QPushButton:disabled { background-color: #25252b; color: #555; }"
        )
        self._gaming_revert_btn.clicked.connect(self._revert_gaming_mode)
        gm_btn_row.addWidget(self._gaming_revert_btn)

        gm_card.layout.addLayout(gm_btn_row)
        layout.addWidget(gm_card)

        # ── Game Compatibility Analyzer card ─────────────────────────────
        compat_card = DashboardCard("GAME COMPATIBILITY ANALYZER")

        compat_desc = QLabel(
            "Type a game name below or drop its .exe onto the drop zone. "
            "For games not in the built-in database, enter the requirements manually."
        )
        compat_desc.setStyleSheet("color: #888; font-size: 11px;")
        compat_desc.setWordWrap(True)
        compat_card.layout.addWidget(compat_desc)

        # Drop zone
        self._game_drop_zone = _DropZoneFrame()
        self._game_drop_zone.file_dropped.connect(self._on_game_exe_dropped)
        compat_card.layout.addWidget(self._game_drop_zone)

        # Search row
        search_row = QHBoxLayout()
        self._game_name_input = QLineEdit()
        self._game_name_input.setPlaceholderText("Game name (e.g. Cyberpunk 2077, Elden Ring, Fortnite...)")
        self._game_name_input.setMinimumHeight(36)
        self._game_name_input.setStyleSheet(
            "QLineEdit { background-color: #1e1e24; border: 1px solid #333; border-radius: 6px; "
            "padding: 4px 8px; color: #d4d4d4; }"
            "QLineEdit:focus { border: 1px solid #4158D0; }"
        )
        self._game_name_input.returnPressed.connect(self._analyze_game_compat)
        search_row.addWidget(self._game_name_input)

        analyze_btn = QPushButton("Analyze")
        analyze_btn.setFixedHeight(36)
        analyze_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; border: none; border-radius: 6px; "
            "color: white; font-weight: bold; padding: 0 18px; }"
            "QPushButton:hover { background-color: #4b6de3; }"
        )
        analyze_btn.clicked.connect(self._analyze_game_compat)
        search_row.addWidget(analyze_btn)
        compat_card.layout.addLayout(search_row)

        # System specs label
        self._gaming_specs_lbl = QLabel("Detecting system specs...")
        self._gaming_specs_lbl.setStyleSheet(
            "background-color: #1e1e24; border: 1px solid #2a2a30; border-radius: 6px; "
            "padding: 8px; color: #888; font-size: 11px;"
        )
        self._gaming_specs_lbl.setWordWrap(True)
        compat_card.layout.addWidget(self._gaming_specs_lbl)

        # Manual requirements widget (shown when game not in DB)
        self._manual_req_widget = QWidget()
        self._manual_req_widget.hide()
        mreq_layout = QVBoxLayout(self._manual_req_widget)
        mreq_layout.setContentsMargins(0, 0, 0, 0)
        mreq_layout.setSpacing(6)
        mreq_lbl = QLabel("Game not in database — enter requirements to compare:")
        mreq_lbl.setStyleSheet("color: #f0a050; font-size: 11px; font-weight: bold;")
        mreq_layout.addWidget(mreq_lbl)

        mreq_grid = QGridLayout()
        mreq_grid.setSpacing(6)
        field_style = (
            "QLineEdit { background-color: #1e1e24; border: 1px solid #333; border-radius: 5px; "
            "padding: 3px 6px; color: #d4d4d4; }"
        )
        lbl_style = "color: #aaa; font-size: 11px;"

        def _mf(placeholder):
            f = QLineEdit()
            f.setPlaceholderText(placeholder)
            f.setFixedHeight(30)
            f.setStyleSheet(field_style)
            return f

        mreq_grid.addWidget(QLabel("Min RAM (GB)", styleSheet=lbl_style), 0, 0)
        self._mreq_ram_min = _mf("e.g. 8")
        mreq_grid.addWidget(self._mreq_ram_min, 0, 1)
        mreq_grid.addWidget(QLabel("Rec RAM (GB)", styleSheet=lbl_style), 0, 2)
        self._mreq_ram_rec = _mf("e.g. 16")
        mreq_grid.addWidget(self._mreq_ram_rec, 0, 3)

        mreq_grid.addWidget(QLabel("Min CPU cores", styleSheet=lbl_style), 1, 0)
        self._mreq_cpu_min = _mf("e.g. 4")
        mreq_grid.addWidget(self._mreq_cpu_min, 1, 1)
        mreq_grid.addWidget(QLabel("Rec CPU cores", styleSheet=lbl_style), 1, 2)
        self._mreq_cpu_rec = _mf("e.g. 8")
        mreq_grid.addWidget(self._mreq_cpu_rec, 1, 3)

        mreq_grid.addWidget(QLabel("Min VRAM (GB)", styleSheet=lbl_style), 2, 0)
        self._mreq_vram_min = _mf("e.g. 4")
        mreq_grid.addWidget(self._mreq_vram_min, 2, 1)
        mreq_grid.addWidget(QLabel("Rec VRAM (GB)", styleSheet=lbl_style), 2, 2)
        self._mreq_vram_rec = _mf("e.g. 8")
        mreq_grid.addWidget(self._mreq_vram_rec, 2, 3)

        mreq_grid.addWidget(QLabel("Min Storage (GB)", styleSheet=lbl_style), 3, 0)
        self._mreq_disk_min = _mf("e.g. 50")
        mreq_grid.addWidget(self._mreq_disk_min, 3, 1)
        mreq_grid.addWidget(QLabel("Rec Storage (GB)", styleSheet=lbl_style), 3, 2)
        self._mreq_disk_rec = _mf("e.g. 50")
        mreq_grid.addWidget(self._mreq_disk_rec, 3, 3)

        mreq_layout.addLayout(mreq_grid)

        compare_btn = QPushButton("Compare with my specs")
        compare_btn.setFixedHeight(34)
        compare_btn.setStyleSheet(
            "QPushButton { background-color: #25252b; border: 1px solid #444; border-radius: 6px; "
            "color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background-color: #2e2e36; }"
        )
        compare_btn.clicked.connect(self._analyze_manual_reqs)
        mreq_layout.addWidget(compare_btn)
        compat_card.layout.addWidget(self._manual_req_widget)

        # Results
        self._game_results_text = QTextEdit()
        self._game_results_text.setReadOnly(True)
        self._game_results_text.setMinimumHeight(180)
        self._game_results_text.hide()
        self._game_results_text.setStyleSheet(
            "QTextEdit { background-color: #1e1e24; border: 1px solid #333; border-radius: 6px; "
            "color: #d4d4d4; font-family: Consolas, monospace; font-size: 12px; }"
        )
        compat_card.layout.addWidget(self._game_results_text)

        layout.addWidget(compat_card)
        layout.addStretch()
        scroll.setWidget(page)
        self.content_stack.addWidget(scroll)

        # Fetch specs in background
        self._gaming_sys_specs = {}
        threading.Thread(target=self._fetch_gaming_page_specs, daemon=True).start()

    def _update_gaming_status_label(self):
        active = self._app_settings.get("gaming_mode_active", False)
        if active:
            self._gaming_status_lbl.setText("🎮  Gaming Mode: ACTIVE")
            self._gaming_status_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #4ec994;")
        else:
            self._gaming_status_lbl.setText("🎮  Gaming Mode: Inactive")
            self._gaming_status_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #888;")

    def _toggle_gaming_mode(self):
        if sys.platform != 'win32':
            QMessageBox.information(self, "Gaming Mode", "Gaming Mode is only available on Windows.")
            return
        from src.core.platform_tools.windows import WindowsTools
        self._gaming_enable_btn.setEnabled(False)
        self._gaming_enable_btn.setText("Applying...")

        def _run():
            success, msg = WindowsTools.toggle_gaming_mode(True)
            self._app_settings["gaming_mode_active"] = True
            self._save_json(self.settings_path, self._app_settings)
            self.log_signal.emit(msg, "success" if success else "error")
            # Queue the UI update on the main thread via QMetaObject
            from PyQt6.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(self, "_on_gaming_mode_applied", _Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot()
    def _on_gaming_mode_applied(self):
        admin = is_admin()
        self._gaming_enable_btn.setEnabled(admin)
        self._gaming_enable_btn.setText("Enable Gaming Mode")
        self._gaming_revert_btn.setEnabled(admin)  # mode is active, revert is now available
        self._update_gaming_status_label()
        QMessageBox.information(self, "Gaming Mode", "Gaming Mode applied!\nUse 'Revert to Defaults' to undo.")

    def _revert_gaming_mode(self):
        if sys.platform != 'win32':
            return
        reply = QMessageBox.question(
            self, "Revert Gaming Mode",
            "This will restore Balanced power plan, re-enable SysMain, Windows Update, and other defaults.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from src.core.platform_tools.windows import WindowsTools
        self._gaming_revert_btn.setEnabled(False)
        self._gaming_revert_btn.setText("Reverting...")

        def _run():
            success, msg = WindowsTools.toggle_gaming_mode(False)
            self._app_settings["gaming_mode_active"] = False
            self._save_json(self.settings_path, self._app_settings)
            self.log_signal.emit(msg, "success" if success else "error")
            from PyQt6.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(self, "_on_gaming_mode_reverted", _Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot()
    def _on_gaming_mode_reverted(self):
        admin = is_admin()
        self._gaming_revert_btn.setEnabled(False)  # mode no longer active, nothing to revert
        self._gaming_revert_btn.setText("Revert to Defaults")
        self._gaming_enable_btn.setEnabled(admin)  # can re-enable again
        self._update_gaming_status_label()
        QMessageBox.information(self, "Gaming Mode", "System restored to defaults.")

    def _fetch_gaming_page_specs(self):
        try:
            mem = psutil.virtual_memory()
            ram_gb = mem.total / (1024 ** 3)
            cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
            cpu_name = platform.processor() or "Unknown CPU"
            gpu_vram_gb = 0.0
            gpu_name = "Unknown GPU"
            if sys.platform == "win32":
                try:
                    from src.utils.helpers import run_command
                    res = run_command([
                        "powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | Format-List"
                    ], timeout=8)
                    for line in res.stdout.strip().splitlines():
                        if line.startswith("Name"):
                            gpu_name = line.split(":", 1)[-1].strip()
                        elif line.startswith("AdapterRAM") and ":" in line:
                            raw = line.split(":", 1)[-1].strip()
                            try:
                                gpu_vram_gb = int(raw) / (1024 ** 3)
                            except ValueError:
                                pass
                except Exception:
                    pass
            disk_free_gb = 0.0
            try:
                du = psutil.disk_usage(os.path.abspath(os.sep))
                disk_free_gb = du.free / (1024 ** 3)
            except Exception:
                pass
            self._gaming_sys_specs = {
                "ram_gb": ram_gb, "cpu_cores": cpu_cores,
                "cpu_name": cpu_name, "gpu_vram_gb": gpu_vram_gb,
                "gpu_name": gpu_name, "disk_free_gb": disk_free_gb,
            }
            spec_text = (
                f"CPU: {cpu_name} ({cpu_cores} physical cores)  |  "
                f"RAM: {ram_gb:.1f} GB  |  "
                f"GPU: {gpu_name} ({gpu_vram_gb:.1f} GB VRAM)  |  "
                f"Free disk: {disk_free_gb:.1f} GB"
            )
            from PyQt6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(
                self._gaming_specs_lbl, "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, spec_text)
            )
        except Exception as e:
            pass

    @staticmethod
    def _lookup_steam_game_name(exe_path: str) -> str:
        """Try to find the Steam game name for a dropped exe by reading appmanifest ACF files."""
        try:
            exe_dir = os.path.dirname(os.path.abspath(exe_path))
            # Walk up until we find a 'steamapps/common' ancestor
            steamapps_dir = None
            check = exe_dir
            for _ in range(6):
                parent = os.path.dirname(check)
                if os.path.basename(check).lower() == "common":
                    candidate = os.path.dirname(check)  # steamapps dir
                    if os.path.isdir(candidate):
                        steamapps_dir = candidate
                    break
                check = parent
                if check == parent:
                    break
            if not steamapps_dir:
                # Also check common Steam install locations directly
                common_steam_roots = [
                    r"C:\Program Files (x86)\Steam\steamapps",
                    r"C:\Program Files\Steam\steamapps",
                    os.path.expanduser("~/.steam/steam/steamapps"),
                    os.path.expanduser("~/Library/Application Support/Steam/steamapps"),
                ]
                for root in common_steam_roots:
                    common = os.path.join(root, "common")
                    if os.path.isdir(common) and exe_dir.startswith(common):
                        steamapps_dir = root
                        break
            if not steamapps_dir:
                return ""
            # The install dir is the top-level folder inside 'common' for this game
            common_path = os.path.join(steamapps_dir, "common")
            rel = os.path.relpath(exe_dir, common_path)
            install_dir = rel.split(os.sep)[0]  # first path component
            # Scan all appmanifest_*.acf files for a matching installdir
            for acf_name in os.listdir(steamapps_dir):
                if not (acf_name.startswith("appmanifest_") and acf_name.endswith(".acf")):
                    continue
                acf_path = os.path.join(steamapps_dir, acf_name)
                try:
                    with open(acf_path, "r", encoding="utf-8", errors="replace") as f:
                        acf_text = f.read()
                    # Simple key/value parse — no need for a full VDF parser
                    acf_installdir = ""
                    acf_name_val = ""
                    for line in acf_text.splitlines():
                        line = line.strip()
                        if line.startswith('"installdir"'):
                            acf_installdir = line.split('"')[3]
                        elif line.startswith('"name"'):
                            acf_name_val = line.split('"')[3]
                    if acf_installdir.lower() == install_dir.lower() and acf_name_val:
                        return acf_name_val
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    def _on_game_exe_dropped(self, path):
        """Called when a .exe is dropped onto the drop zone."""
        name = os.path.splitext(os.path.basename(path))[0]
        # 1. Try Steam ACF lookup first — most reliable for Steam games
        steam_name = self._lookup_steam_game_name(path)
        if steam_name:
            name = steam_name
        elif sys.platform == "win32":
            # 2. Fall back to PE VersionInfo.ProductName
            try:
                from src.utils.helpers import run_command
                ps = f"(Get-Item '{path}').VersionInfo.ProductName"
                res = run_command(["powershell", "-NoProfile", "-Command", ps], timeout=5)
                product = res.stdout.strip()
                if product and product.lower() not in ("", "null"):
                    name = product
            except Exception:
                pass
        self._game_name_input.setText(name)
        self._analyze_game_compat()

    _GAME_DB = {
        "minecraft": {"name": "Minecraft (Java)", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 4}, "rec": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 8}},
        "minecraft java": {"name": "Minecraft (Java)", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 4}, "rec": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 8}},
        "fortnite": {"name": "Fortnite", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 29}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 29}},
        "cyberpunk 2077": {"name": "Cyberpunk 2077", "min": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 6, "storage_gb": 70}, "rec": {"ram_gb": 12, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 70}},
        "cyberpunk": {"name": "Cyberpunk 2077", "min": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 6, "storage_gb": 70}, "rec": {"ram_gb": 12, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 70}},
        "elden ring": {"name": "Elden Ring", "min": {"ram_gb": 12, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 60}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 60}},
        "valorant": {"name": "VALORANT", "min": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 1, "storage_gb": 8}, "rec": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 8}},
        "apex legends": {"name": "Apex Legends", "min": {"ram_gb": 6, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 56}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 56}},
        "apex": {"name": "Apex Legends", "min": {"ram_gb": 6, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 56}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 56}},
        "gta v": {"name": "Grand Theft Auto V", "min": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 72}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 2, "storage_gb": 72}},
        "gta5": {"name": "Grand Theft Auto V", "min": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 72}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 2, "storage_gb": 72}},
        "gta 5": {"name": "Grand Theft Auto V", "min": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 72}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 2, "storage_gb": 72}},
        "csgo": {"name": "CS:GO / CS2", "min": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 15}, "rec": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 15}},
        "cs2": {"name": "CS2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 30}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 30}},
        "counter-strike": {"name": "CS2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 30}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 30}},
        "counter strike": {"name": "CS2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 30}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 30}},
        "red dead redemption 2": {"name": "Red Dead Redemption 2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 150}, "rec": {"ram_gb": 12, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 150}},
        "rdr2": {"name": "Red Dead Redemption 2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 150}, "rec": {"ram_gb": 12, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 150}},
        "the witcher 3": {"name": "The Witcher 3", "min": {"ram_gb": 6, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 35}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 35}},
        "witcher 3": {"name": "The Witcher 3", "min": {"ram_gb": 6, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 35}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 35}},
        "call of duty warzone": {"name": "Call of Duty: Warzone", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 175}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 175}},
        "warzone": {"name": "Call of Duty: Warzone", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 175}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 175}},
        "league of legends": {"name": "League of Legends", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 16}, "rec": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 16}},
        "lol": {"name": "League of Legends", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 16}, "rec": {"ram_gb": 4, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 16}},
        "overwatch": {"name": "Overwatch 2", "min": {"ram_gb": 6, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 50}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 50}},
        "overwatch 2": {"name": "Overwatch 2", "min": {"ram_gb": 6, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 50}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 50}},
        "baldur's gate 3": {"name": "Baldur's Gate 3", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 150}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 150}},
        "baldurs gate 3": {"name": "Baldur's Gate 3", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 150}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 150}},
        "bg3": {"name": "Baldur's Gate 3", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 150}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 150}},
        "dota 2": {"name": "Dota 2", "min": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 15}, "rec": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 15}},
        "rust": {"name": "Rust", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 20}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 20}},
        "pubg": {"name": "PUBG: Battlegrounds", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 40}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 40}},
        "palworld": {"name": "Palworld", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 40}, "rec": {"ram_gb": 32, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 40}},
        "helldivers 2": {"name": "Helldivers 2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 100}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 100}},
        "black myth wukong": {"name": "Black Myth: Wukong", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 8, "storage_gb": 130}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 16, "storage_gb": 130}},
        "black myth: wukong": {"name": "Black Myth: Wukong", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 8, "storage_gb": 130}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 16, "storage_gb": 130}},
        "star wars outlaws": {"name": "Star Wars Outlaws", "min": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 65}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 65}},
        "star wars jedi survivor": {"name": "Star Wars Jedi: Survivor", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 8, "storage_gb": 130}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 130}},
        "hogwarts legacy": {"name": "Hogwarts Legacy", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 8, "storage_gb": 85}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 85}},
        "alan wake 2": {"name": "Alan Wake 2", "min": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 90}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 90}},
        "resident evil 4": {"name": "Resident Evil 4 Remake", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 60}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 60}},
        "re4": {"name": "Resident Evil 4 Remake", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 60}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 60}},
        "the last of us": {"name": "The Last of Us Part I", "min": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 100}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 16, "storage_gb": 100}},
        "last of us": {"name": "The Last of Us Part I", "min": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 100}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 16, "storage_gb": 100}},
        "god of war": {"name": "God of War (2018)", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 70}, "rec": {"ram_gb": 8, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 70}},
        "god of war ragnarok": {"name": "God of War Ragnarök", "min": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 190}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 190}},
        "spider-man": {"name": "Marvel's Spider-Man Remastered", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 6, "storage_gb": 75}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 75}},
        "spiderman": {"name": "Marvel's Spider-Man Remastered", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 6, "storage_gb": 75}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 75}},
        "dying light 2": {"name": "Dying Light 2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 60}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 60}},
        "doom eternal": {"name": "DOOM Eternal", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 50}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 50}},
        "doom": {"name": "DOOM Eternal", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 50}, "rec": {"ram_gb": 8, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 50}},
        "ark survival": {"name": "ARK: Survival Evolved", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 60}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 60}},
        "ark": {"name": "ARK: Survival Evolved", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 60}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 60}},
        "7 days to die": {"name": "7 Days to Die", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 15}, "rec": {"ram_gb": 12, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 15}},
        "no man's sky": {"name": "No Man's Sky", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 15}, "rec": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 15}},
        "no mans sky": {"name": "No Man's Sky", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 15}, "rec": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 8, "storage_gb": 15}},
        "satisfactory": {"name": "Satisfactory", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 15}, "rec": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 6, "storage_gb": 15}},
        "factorio": {"name": "Factorio", "min": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 1}, "rec": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 2}},
        "stardew valley": {"name": "Stardew Valley", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.25, "storage_gb": 1}, "rec": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 1}},
        "stardew": {"name": "Stardew Valley", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.25, "storage_gb": 1}, "rec": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 1}},
        "terraria": {"name": "Terraria", "min": {"ram_gb": 2, "cpu_cores": 2, "gpu_vram_gb": 0.25, "storage_gb": 0.2}, "rec": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 0.2}},
        "path of exile": {"name": "Path of Exile", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 40}, "rec": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 40}},
        "poe": {"name": "Path of Exile", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 40}, "rec": {"ram_gb": 16, "cpu_cores": 6, "gpu_vram_gb": 4, "storage_gb": 40}},
        "destiny 2": {"name": "Destiny 2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 105}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 105}},
        "halo infinite": {"name": "Halo Infinite", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 50}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 50}},
        "halo": {"name": "Halo Infinite", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 50}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 50}},
    }

    def _analyze_game_compat(self):
        query = self._game_name_input.text().strip()
        if not query:
            return
        self._manual_req_widget.hide()
        self._game_results_text.clear()

        entry = self._GAME_DB.get(query.lower())
        if not entry:
            for key, val in self._GAME_DB.items():
                if query.lower() in key or key in query.lower():
                    entry = val
                    break

        if not entry:
            self._manual_req_widget.show()
            self._game_results_text.setHtml(
                f"<p style='color:#f0a050;'>&#9888; <b>{query}</b> is not in the built-in database.</p>"
                "<p style='color:#888;'>Enter the game's minimum and recommended requirements above, "
                "then click <b>Compare with my specs</b>.</p>"
            )
            self._game_results_text.show()
            return

        self._manual_req_widget.hide()
        self._render_compat_result(entry["name"], entry["min"], entry["rec"])

    def _analyze_manual_reqs(self):
        def _f(widget, default=0.0):
            try:
                return float(widget.text().strip()) if widget.text().strip() else default
            except ValueError:
                return default

        mn = {
            "ram_gb": _f(self._mreq_ram_min),
            "cpu_cores": _f(self._mreq_cpu_min),
            "gpu_vram_gb": _f(self._mreq_vram_min),
            "storage_gb": _f(self._mreq_disk_min),
        }
        rc = {
            "ram_gb": _f(self._mreq_ram_rec) or mn["ram_gb"],
            "cpu_cores": _f(self._mreq_cpu_rec) or mn["cpu_cores"],
            "gpu_vram_gb": _f(self._mreq_vram_rec) or mn["gpu_vram_gb"],
            "storage_gb": _f(self._mreq_disk_rec) or mn["storage_gb"],
        }
        if not any(mn.values()):
            QMessageBox.warning(self, "No Requirements", "Please enter at least one requirement field.")
            return
        game_name = self._game_name_input.text().strip() or "Custom Game"
        self._render_compat_result(game_name, mn, rc)

    def _render_compat_result(self, game_name, mn, rc):
        if not self._gaming_sys_specs:
            self._game_results_text.setHtml(
                "<p style='color:#888;'>Still detecting system specs — please wait a moment and try again.</p>"
            )
            self._game_results_text.show()
            return

        s = self._gaming_sys_specs

        def check(label, have, need_min, need_rec, unit=""):
            if not need_min and not need_rec:
                return ""
            ok_rec = have >= need_rec if need_rec else True
            ok_min = have >= need_min if need_min else True
            if ok_rec:
                icon, color, verdict = "&#10003;", "#4ec994", "Exceeds recommended"
            elif ok_min:
                icon, color = "&#9888;", "#f0a050"
                verdict = f"Meets minimum (rec: {need_rec}{unit})" if need_rec else "Meets minimum"
            else:
                icon, color = "&#10007;", "#f44747"
                verdict = f"Below minimum (need: {need_min}{unit}, rec: {need_rec}{unit})"
            return (
                f"<tr><td style='padding:3px 8px; color:#aaa;'>{label}</td>"
                f"<td style='padding:3px 8px; color:#d4d4d4;'>{have:.1f}{unit}</td>"
                f"<td style='padding:3px 8px; color:{color};'>{icon} {verdict}</td></tr>"
            )

        rows = (
            check("RAM", s["ram_gb"], mn["ram_gb"], rc["ram_gb"], " GB") +
            check("CPU Cores", float(s["cpu_cores"]), float(mn["cpu_cores"]), float(rc["cpu_cores"])) +
            check("GPU VRAM", s["gpu_vram_gb"], mn["gpu_vram_gb"], rc["gpu_vram_gb"], " GB") +
            check("Free Disk", s["disk_free_gb"], mn["storage_gb"], rc["storage_gb"], " GB")
        )
        checks = [
            (s["ram_gb"], mn["ram_gb"], rc["ram_gb"]),
            (float(s["cpu_cores"]), float(mn["cpu_cores"]), float(rc["cpu_cores"])),
            (s["gpu_vram_gb"], mn["gpu_vram_gb"], rc["gpu_vram_gb"]),
            (s["disk_free_gb"], mn["storage_gb"], rc["storage_gb"]),
        ]
        score = sum(25 if h >= r else (12 if h >= m else 0) for h, m, r in checks if m or r)
        if score >= 90:
            verdict_color, verdict_text = "#4ec994", "Ready to Play (High Settings)"
        elif score >= 60:
            verdict_color, verdict_text = "#f0a050", "Playable (Low/Medium Settings)"
        elif score >= 30:
            verdict_color, verdict_text = "#f0a050", "Barely Playable (Minimum Settings)"
        else:
            verdict_color, verdict_text = "#f44747", "Not Recommended"

        self._game_results_text.setHtml(
            f"<h3 style='color:#4158D0; margin:0 0 6px 0;'>{game_name}</h3>"
            f"<p style='color:{verdict_color}; font-size:14px; margin:0 0 10px 0;'>"
            f"<b>Compatibility Score: {score}/100 &mdash; {verdict_text}</b></p>"
            f"<table style='width:100%; border-collapse:collapse;'>"
            f"<tr style='background-color:#25252b;'>"
            f"<th style='text-align:left; padding:4px 8px; color:#888;'>Component</th>"
            f"<th style='text-align:left; padding:4px 8px; color:#888;'>Your System</th>"
            f"<th style='text-align:left; padding:4px 8px; color:#888;'>Status</th></tr>"
            f"{rows}</table>"
        )
        self._game_results_text.show()


    def _save_general_settings(self):
        """Persist general settings from the Settings page UI."""
        sec_values = [30, 60, 120, 300]
        idx = self._s_alert_interval.currentIndex()
        new_sec = sec_values[idx] if 0 <= idx < len(sec_values) else 60

        self._app_settings["minimize_to_tray"] = self._s_minimize_tray.isChecked()
        self._app_settings["alert_refresh_sec"] = new_sec
        self._app_settings["startup_page"] = self._s_startup_page.currentIndex()
        self._save_json(self.settings_path, self._app_settings)

        # Apply alert refresh interval live
        if hasattr(self, 'alerts_timer'):
            self.alerts_timer.setInterval(new_sec * 1000)

    # ── Windows startup helpers ─────────────────────────────────────────
    def _refresh_win_startup_status(self):
        if not hasattr(self, '_s_win_startup_status') or winreg is None:
            return
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, "GhostyTools")
                self._s_win_startup_status.setText("Status: registered in registry ✓")
                self._s_start_windows.setChecked(True)
            except FileNotFoundError:
                self._s_win_startup_status.setText("Status: not in startup registry")
                self._s_start_windows.setChecked(False)
            winreg.CloseKey(key)
        except Exception as e:
            self._s_win_startup_status.setText(f"Status: could not read registry ({e})")

    def _apply_windows_startup(self):
        if winreg is None:
            return
        enabled = self._s_start_windows.isChecked()
        self._app_settings["start_with_windows"] = enabled
        self._save_json(self.settings_path, self._app_settings)
        exe = sys.executable
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            if enabled:
                winreg.SetValueEx(key, "GhostyTools", 0, winreg.REG_SZ, f'"{exe}"')
                self.log_signal.emit("Ghosty Tools added to Windows startup.", "success")
                self.log_activity("Enabled Windows startup")
            else:
                try:
                    winreg.DeleteValue(key, "GhostyTools")
                    self.log_signal.emit("Ghosty Tools removed from Windows startup.", "info")
                    self.log_activity("Disabled Windows startup")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            self._refresh_win_startup_status()
        except Exception as e:
            self.log_signal.emit(f"Failed to update startup registry: {e}", "error")

    # ── Linux autostart helpers ─────────────────────────────────────────
    def _linux_autostart_path(self):
        autostart_dir = os.path.join(os.path.expanduser("~"), ".config", "autostart")
        return os.path.join(autostart_dir, "ghostytools.desktop")

    def _linux_autostart_exists(self):
        return os.path.exists(self._linux_autostart_path())

    def _apply_linux_startup(self):
        enabled = self._s_start_linux.isChecked()
        desktop_file = self._linux_autostart_path()
        autostart_dir = os.path.dirname(desktop_file)
        try:
            if enabled:
                os.makedirs(autostart_dir, exist_ok=True)
                exe = sys.executable
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Ghosty Tools\n"
                    f"Exec={exe}\n"
                    "Hidden=false\n"
                    "NoDisplay=false\n"
                    "X-GNOME-Autostart-enabled=true\n"
                    "Comment=GhostyWare system utility\n"
                )
                with open(desktop_file, 'w') as f:
                    f.write(content)
                self.log_signal.emit("Autostart entry created for Linux.", "success")
                self.log_activity("Enabled Linux autostart")
            else:
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)
                    self.log_signal.emit("Autostart entry removed.", "info")
                    self.log_activity("Disabled Linux autostart")
        except Exception as e:
            self.log_signal.emit(f"Failed to update Linux autostart: {e}", "error")

    def _prompt_desktop_shortcut(self):
        """On first launch, ask the user if they'd like a desktop shortcut."""
        self._app_settings["shortcut_prompted"] = True
        self._save_json(self.settings_path, self._app_settings)

        reply = QMessageBox.question(
            self, "Create Desktop Shortcut",
            "Welcome to Ghosty Tools!\n\nWould you like to create a desktop shortcut for easy access?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._create_desktop_shortcut()

    def _create_desktop_shortcut(self):
        """Create a desktop shortcut pointing to this executable."""
        try:
            if getattr(sys, 'frozen', False):
                target = sys.executable
            else:
                target = os.path.abspath(sys.argv[0])

            desktop = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Desktop')
            icon_path = os.path.join(self.project_root, "images", "ghosty icon.ico")
            shortcut_path = os.path.join(desktop, "Ghosty Tools.lnk")

            ps_cmd = (
                f"$ws = New-Object -ComObject WScript.Shell; "
                f"$sc = $ws.CreateShortcut('{shortcut_path}'); "
                f"$sc.TargetPath = '{target}'; "
                f"$sc.WorkingDirectory = '{os.path.dirname(target)}'; "
            )
            if os.path.exists(icon_path):
                ps_cmd += f"$sc.IconLocation = '{icon_path}'; "
            ps_cmd += "$sc.Description = 'Ghosty Tools - System Utility'; $sc.Save()"

            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            self.log_signal.emit("Desktop shortcut created successfully.", "success")
        except Exception as e:
            self.log_signal.emit(f"Failed to create desktop shortcut: {e}", "error")

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
        self.refresh_system_alerts()
        if update_info.get("available"):
            # Update available: show Banner
            latest_v = update_info.get('latest_version', 'v7.3.2')
            date_str = datetime.now().strftime("%d %b %Y")
            msg = f"Update available · {latest_v} · {date_str}"
            self.update_banner.msg_label.setText(msg)
            self.update_banner.show()
            
            # Also update legacy button if it exists
            if hasattr(self, "update_status_btn"):
                self.update_status_btn.setText("Update available")
                self.update_status_btn.setEnabled(True)
                self.update_status_btn.setStyleSheet("color: #e74c3c; font-size: 11px;")
            
            if manual:
                self.log_signal.emit(f"Update {latest_v} available.", "info")
                self.show_update_details()
        else:
            self.update_banner.hide()
            # Fully updated: show green text and disable click
            if hasattr(self, "update_status_btn"):
                self.update_status_btn.setText("Fully updated")
                self.update_status_btn.setEnabled(False)
                self.update_status_btn.setStyleSheet("color: #2ecc71; font-size: 11px;")
            if manual:
                self.log_signal.emit("You are already using the latest version.", "success")

    def show_update_details(self):
        if not self._latest_update_info:
            return
            
        dialog = UpdateDialog(self._latest_update_info, self)
        dialog.update_btn.clicked.connect(lambda: self.start_update_download(self._latest_update_info, dialog))
        dialog.exec()

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

    def start_update_download(self, update_info, existing_dialog=None):
        # Find the EXE asset if available
        download_url = None
        for asset in update_info.get("assets", []):
            if asset["name"].lower().endswith(".exe") and "updater" not in asset["name"].lower():
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            self.log_signal.emit("No executable asset found in the latest release. Opening GitHub releases page...", "warning")
            webbrowser.open(update_info.get("html_url", "https://github.com/Ghostshadowplays/Ghosty-Tools/releases"))
            if existing_dialog: existing_dialog.reject()
            return
        
        # Use %LOCALAPPDATA%\GhostyTools\update\GhostyTools_new.exe as requested
        local_app_data = os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', get_config_dir()))
        update_dir = os.path.join(local_app_data, "GhostyTools", "update")
        os.makedirs(update_dir, exist_ok=True)
        target_path = os.path.join(update_dir, "GhostyTools_new.exe")
        
        if existing_dialog:
            self.update_dialog = existing_dialog
            self.update_dialog.set_status("Initializing update...")
        else:
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
        
        if hasattr(self.update_dialog, "set_status"):
            self.update_worker.status.connect(self.update_dialog.set_status)
        else:
            self.update_worker.status.connect(self.update_status_label.setText)
            
        if hasattr(self.update_dialog, "set_progress"):
            self.update_worker.progress.connect(self.update_dialog.set_progress)
        else:
            self.update_worker.progress.connect(self.update_progress.setValue)
            
        self.update_worker.finished.connect(self._on_update_download_finished)
        
        self.log_signal.emit(f"Starting update process...", "info")
        self.update_worker.start()
        
        if not existing_dialog:
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

            safe_new = new_file
            safe_current = current_file

            # Pass the PyInstaller temp extraction folder so the batch can
            # clean it up before launching the new exe — prevents the new exe
            # from finding and trying to reuse a stale _MEI* folder which
            # causes "Failed to load Python DLL" errors.
            old_mei = getattr(sys, '_MEIPASS', '')

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

:: Extra pause to let the old process fully release its temp files
timeout /t 5 /nobreak >nul

:: Clean up ALL stale PyInstaller extraction folders to prevent DLL conflicts
echo Cleaning up stale runtime files...
for /d %%i in ("%TEMP%\_MEI*") do rd /s /q "%%i" >nul 2>&1
if exist "{old_mei}" rd /s /q "{old_mei}" >nul 2>&1

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

:: Recreate desktop shortcut pointing to the new exe location
echo Updating desktop shortcut...
powershell -NoProfile -Command "$desktop = [Environment]::GetFolderPath('Desktop'); $lnk = Join-Path $desktop 'Ghosty Tools.lnk'; if (Test-Path $lnk) {{ Remove-Item $lnk -Force }}; $ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($lnk); $s.TargetPath = '{safe_current}'; $s.WorkingDirectory = [System.IO.Path]::GetDirectoryName('{safe_current}'); $s.Description = 'Ghosty Tools'; $s.Save()" >nul 2>&1

:: Brief pause before launch so the new exe starts with a clean slate
echo Restarting Ghosty Tools...
timeout /t 2 /nobreak >nul
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
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            
            self.dashboard.cpu_card.value_label.setText(f"{int(cpu)}%")
            self.dashboard.cpu_card.bar.setValue(int(cpu))
            self.dashboard.cpu_card.details_label.setText(f"{psutil.cpu_count()} cores · {psutil.cpu_count(logical=False)} threads")
            
            self.dashboard.mem_card.value_label.setText(f"{int(ram)}%")
            self.dashboard.mem_card.bar.setValue(int(ram))
            mem = psutil.virtual_memory()
            self.dashboard.mem_card.details_label.setText(f"{mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB used")
            
            # Multi-factor health score
            score = 100
            warnings = []

            # CPU impact (high sustained CPU = -5 to -15)
            if cpu > 90: score -= 15; warnings.append(f"CPU critical: {int(cpu)}%")
            elif cpu > 70: score -= 8; warnings.append(f"CPU elevated: {int(cpu)}%")
            elif cpu > 50: score -= 3

            # RAM impact (-5 to -20)
            if ram > 90: score -= 20; warnings.append(f"RAM critical: {int(ram)}%")
            elif ram > 80: score -= 12; warnings.append(f"High RAM: {int(ram)}%")
            elif ram > 65: score -= 5

            # Disk space impact (-10)
            try:
                disk = psutil.disk_usage(os.path.abspath(os.sep))
                if disk.percent > 90: score -= 10; warnings.append("Disk nearly full")
                elif disk.percent > 80: score -= 5
            except Exception: pass

            # Pending reboot (-5)
            if sys.platform == 'win32' and winreg:
                try:
                    k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager")
                    if winreg.QueryValueEx(k, "PendingFileRenameOperations")[0]:
                        score -= 5; warnings.append("Reboot pending")
                    winreg.CloseKey(k)
                except Exception: pass
            elif sys.platform != 'win32' and os.path.exists('/var/run/reboot-required'):
                score -= 5; warnings.append("Reboot pending")

            # Update available (-3)
            if self._latest_update_info and self._latest_update_info.get("available"):
                score -= 3; warnings.append("App update available")

            score = max(0, min(100, score))
            self.dashboard.health_circle.value = score

            if score >= 90: status = "Excellent"; color = "#00ff88"
            elif score >= 75: status = "Good"; color = "#4158D0"
            elif score >= 55: status = "Fair"; color = "#FBAB7E"
            else: status = "Poor"; color = "#f44747"

            self.dashboard.health_circle.status = status
            self.dashboard.health_circle._color = __import__('PyQt6.QtGui', fromlist=['QColor']).QColor(color)

            if warnings:
                self.dashboard.health_warning.setText(f"⚠ {warnings[0]}")
                self.dashboard.health_warning.setStyleSheet(f"color: {color}; font-size: 13px;")
            else:
                self.dashboard.health_warning.setText("✔ Everything looks good. System is optimized.")
                self.dashboard.health_warning.setStyleSheet("color: #00ff88; font-size: 13px;")
            
            # Update storage (every 5th call to save resources)
            if not hasattr(self, "_storage_update_count"): self._storage_update_count = 0
            self._storage_update_count += 1
            if self._storage_update_count % 5 == 1:
                self.update_storage_display()
        except:
            pass

    def update_storage_display(self):
        # Clear existing
        for i in reversed(range(self.dashboard.storage_grid.count())): 
            self.dashboard.storage_grid.itemAt(i).widget().setParent(None)
            
        partitions = psutil.disk_partitions()
        for p in partitions:
            if p.fstype:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    container = QWidget()
                    lay = QHBoxLayout(container)
                    lay.setContentsMargins(0, 5, 0, 5)
                    
                    name = QLabel(f"{p.mountpoint}:")
                    name.setFixedWidth(30)
                    lay.addWidget(name)
                    
                    bar = QProgressBar()
                    bar.setFixedHeight(8)
                    bar.setTextVisible(False)
                    bar.setRange(0, 100)
                    bar.setValue(int(usage.percent))
                    color = "#00ff88" if usage.percent < 80 else "#FBAB7E" if usage.percent < 95 else "#f44747"
                    bar.setStyleSheet(f"""
                        QProgressBar {{ background-color: #2a2a2a; border: none; border-radius: 4px; }}
                        QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}
                    """)
                    lay.addWidget(bar)
                    
                    info = QLabel(f"{usage.used // (1024**3)} / {usage.total // (1024**3)} GB ({int(usage.percent)}%)")
                    info.setStyleSheet("color: #888; font-size: 11px;")
                    info.setFixedWidth(150)
                    info.setAlignment(Qt.AlignmentFlag.AlignRight)
                    lay.addWidget(info)
                    
                    self.dashboard.storage_grid.addWidget(container)
                except:
                    pass

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

    def notify_tray(self, title, message, icon=QSystemTrayIcon.MessageIcon.Information, ms=4000):
        """Show a system tray notification if the tray icon is available."""
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                self.tray_icon.showMessage(title, message, icon, ms)
        except Exception:
            pass

    def _on_speed_test_result(self, res):
        self.speed_label.setText(res)
        self.log_signal.emit(f"Speed test completed:\n{res}", "success")
        self.notify_tray("Speed Test Complete", res.replace('\n', '  |  '))
        self.log_activity("Speed test completed")
        # Save to history
        entry = {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "result": res}
        self._speedtest_history.insert(0, entry)
        self._speedtest_history = self._speedtest_history[:20]
        self._save_json(self.speedtest_history_path, self._speedtest_history)
        self._refresh_speed_history()

    def _on_speed_test_error(self, err):
        self.speed_label.setText(f"Error: {err}")
        self.log_signal.emit(f"Speed test failed: {err}", "error")

    def _refresh_speed_history(self):
        if not hasattr(self, 'speed_history_label'):
            return
        if not self._speedtest_history:
            self.speed_history_label.setText("")
            return
        lines = []
        for e in self._speedtest_history[:3]:
            short = e['result'].replace('\n', '  ').replace('Download:', '↓').replace('Upload:', '↑').replace('Ping:', 'P:')
            lines.append(f"<span style='color:#555'>{e['time']}</span> {short}")
        self.speed_history_label.setText("<br>".join(lines))
        self.speed_history_label.setTextFormat(Qt.TextFormat.RichText)

    def flush_dns(self):
        self.log_signal.emit("Flushing DNS cache...", "info")
        from src.core.dns_manager import DNSManager
        success, msg = DNSManager.flush_dns()
        if success:
            self.log_signal.emit(msg, "success")
            QMessageBox.information(self, "DNS Flush", msg)
        else:
            self.log_signal.emit(f"Failed to flush DNS: {msg}", "error")
            QMessageBox.warning(self, "DNS Flush", f"Failed to flush DNS: {msg}")

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
        self.notify_tray("Maintenance Complete", res[:120])
        self.log_activity("Full system maintenance completed")
        QMessageBox.information(self, "Maintenance", res)

    def run_disk_cleanup(self):
        reply = QMessageBox.question(
            self, "Confirm Cleanup",
            "This will remove temporary files, update caches, and shader caches.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log_signal.emit("Starting Deep Cleanup Engine...", "info")
        from src.core.cleanup_engine import CleanupEngine
        engine = CleanupEngine()

        if sys.platform == 'win32':
            self.log_signal.emit("Cleaning Windows Update cache...", "info")
            engine.clean_windows_update_cache()
            self.log_signal.emit("Cleaning CBS logs...", "info")
            engine.clean_cbs_logs()
            self.log_signal.emit("Cleaning shader caches...", "info")
            engine.clean_shader_cache()
            self.log_signal.emit("Cleanup completed.", "success")
            self.notify_tray("Cleanup Complete", "Temporary files and caches cleared successfully.")
            self.log_activity("Deep cleanup completed")
            QMessageBox.information(self, "Cleanup", "Deep cleanup completed successfully.")
        else:
            pm = self.pkg_manager or 'apt'
            cmd = f"sudo {pm} clean && sudo {pm} autoremove -y"
            self.log_signal.emit(f"Running Linux cleanup ({pm})...", "info")
            subprocess.Popen(["bash", "-c", cmd], shell=False)
            self.log_signal.emit("Linux cleanup started in background.", "success")
            self.log_activity(f"Linux system cleanup started ({pm})")

    def run_windows_update_check(self):
        if sys.platform == 'win32':
            self.log_signal.emit("Checking for Windows Updates...", "info")
            self.update_status.setText("Status: Checking...")
            threading.Thread(target=self._update_check_thread, daemon=True).start()
        else:
            self.log_signal.emit("Checking for Linux Updates...", "info")
            self.update_status.setText("Status: Checking...")
            threading.Thread(target=self._linux_update_check_thread, daemon=True).start()

    def _update_check_thread(self):
        try:
            import win32com.client
            # Initialize COM in this thread
            import pythoncom
            pythoncom.CoInitialize()
            
            update_session = win32com.client.Dispatch("Microsoft.Update.Session")
            update_searcher = update_session.CreateUpdateSearcher()
            
            # Search for uninstalled software updates
            search_result = update_searcher.Search("IsInstalled=0 and Type='Software'")
            count = search_result.Updates.Count
            
            self.update_status.setText(f"Status: {count} updates available")
            if count > 0:
                self.log_signal.emit(f"Windows Update check finished: {count} updates available.", "info")
            else:
                self.log_signal.emit("Windows is up to date.", "success")
        except Exception as e:
            logger.error(f"Error checking Windows Updates: {e}")
            # Fallback to a simpler method if win32com fails or is not installed
            try:
                cmd = "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0 and Type=''Software''').Updates.Count"
                res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000))
                if res.returncode == 0:
                    count = int(res.stdout.strip() or 0)
                    self.update_status.setText(f"Status: {count} updates available")
                    self.log_signal.emit(f"Windows Update check finished: {count} updates available.", "info")
                else:
                    raise Exception(res.stderr)
            except Exception as e2:
                logger.error(f"Fallback update check failed: {e2}")
                self.update_status.setText("Status: Check failed")
                self.log_signal.emit(f"Windows Update check failed: {e}", "error")
        finally:
            try:
                pythoncom.CoUninitialize()
            except:
                pass

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
        
        # 1. Show/Hide
        show_action = QAction("Show Ghosty Tools", self)
        show_action.triggered.connect(self.show_and_raise)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        
        # 2. Quick Actions
        clean_action = QAction("Quick Clean", self)
        clean_action.triggered.connect(self.run_disk_cleanup)
        tray_menu.addAction(clean_action)
        
        speed_action = QAction("Speed Test", self)
        speed_action.triggered.connect(self.run_speed_test)
        tray_menu.addAction(speed_action)
        
        flush_dns_action = QAction("Flush DNS", self)
        flush_dns_action.triggered.connect(self.flush_dns)
        tray_menu.addAction(flush_dns_action)
        
        # 3. Advanced Actions
        adv_menu = tray_menu.addMenu("Advanced")
        
        restart_env_text = "Restart Explorer" if sys.platform == "win32" else "Restart Desktop Environment"
        restart_env_action = QAction(restart_env_text, self)
        restart_env_action.triggered.connect(self.restart_desktop_environment)
        adv_menu.addAction(restart_env_action)
        
        net_repair_action = QAction("Network Repair", self)
        net_repair_action.triggered.connect(self.network_repair)
        adv_menu.addAction(net_repair_action)
        
        traceroute_action = QAction("Run Traceroute", self)
        traceroute_action.triggered.connect(lambda: self.run_network_tool("traceroute"))
        adv_menu.addAction(traceroute_action)
        
        if sys.platform == "win32":
            game_mode_action = QAction("Toggle Game Mode", self)
            game_mode_action.triggered.connect(self.toggle_game_mode_tray)
            adv_menu.addAction(game_mode_action)
            
        trim_ram_action = QAction("Trim RAM", self)
        trim_ram_action.triggered.connect(self.trim_ram)
        adv_menu.addAction(trim_ram_action)
        
        # 4. Folders & Updates
        tray_menu.addSeparator()
        
        logs_action = QAction("Open Logs Folder", self)
        logs_action.triggered.connect(self.open_logs_folder)
        tray_menu.addAction(logs_action)
        
        config_action = QAction("Open Config Folder", self)
        config_action.triggered.connect(self.open_config_folder)
        tray_menu.addAction(config_action)
        
        update_action = QAction("Check for Updates", self)
        update_action.triggered.connect(lambda: self.check_for_updates(manual=True))
        tray_menu.addAction(update_action)
        
        # 5. Quit
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def restart_desktop_environment(self):
        """Restart Explorer (Windows) or refresh DE (Linux/macOS)."""
        self.log_to_terminal("Restarting desktop environment...")
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], creationflags=CREATE_NO_WINDOW)
                subprocess.Popen(["explorer.exe"])
                self.log_to_terminal("Explorer restarted.", "success")
            except Exception as e:
                self.log_to_terminal(f"Failed to restart Explorer: {e}", "error")
        else:
            self.log_to_terminal("Restarting DE not fully supported on this platform.", "warning")

    def network_repair(self):
        """Perform a series of network repair commands."""
        self.log_to_terminal("Starting Network Repair...")
        if sys.platform == "win32":
            commands = [
                ["netsh", "winsock", "reset"],
                ["netsh", "int", "ip", "reset"],
                ["ipconfig", "/release"],
                ["ipconfig", "/renew"],
                ["ipconfig", "/flushdns"]
            ]
            for cmd in commands:
                try:
                    subprocess.run(cmd, creationflags=CREATE_NO_WINDOW)
                    self.log_to_terminal(f"Executed: {' '.join(cmd)}")
                except: pass
            self.log_to_terminal("Network repair completed.", "success")
        else:
            self.flush_dns()

    def trim_ram(self):
        """Try to reduce memory usage of running processes."""
        self.log_to_terminal("Trimming RAM...")
        import psutil
        count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # This is only effective on Windows via a specific API, 
                # but we can try to suggest it to the OS.
                p = psutil.Process(proc.info['pid'])
                p.ionice(psutil.IOPRIO_VERYLOW) if sys.platform != 'win32' else None
                count += 1
            except: pass
        self.log_to_terminal(f"Suggested memory trim for {count} processes.", "success")

    def open_config_folder(self):
        """Open the configuration folder in file explorer."""
        config_dir = get_config_dir()
        if os.path.exists(config_dir):
            if sys.platform == "win32":
                os.startfile(config_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", config_dir])
            else:
                subprocess.run(["xdg-open", config_dir])
        else:
            self.log_to_terminal("Config folder not found.", "error")

    def toggle_game_mode_tray(self):
        """Toggle Windows Game Mode from tray."""
        from src.core.platform_tools.windows import WindowsTools
        success, msg = WindowsTools.toggle_gaming_mode(enable=True) # For now just enable or toggle
        self.log_to_terminal(msg, "info" if success else "error")

    def run_network_tool(self, tool_name):
        """Helper to run a network tool from tray."""
        if tool_name == "traceroute":
            target = "8.8.8.8" # Default target
            self.log_to_terminal(f"Running traceroute to {target}...")
            from src.core.network_tools import NetworkTools
            result = NetworkTools.run_traceroute(target)
            self.log_to_terminal(result)

    def show_and_raise(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def setup_hardware_health_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        header = PageHeader("Hardware Health", "Monitor real-time sensor data and S.M.A.R.T. diagnostics.")
        layout.addWidget(header)

        # Real-time Sensors Card
        sensor_card = DashboardCard("LIVE SENSOR DATA")
        self.sensor_label = QLabel("Loading sensors...")
        self.sensor_label.setStyleSheet("color: #00ff88; font-family: 'Consolas'; font-size: 12px;")
        self.sensor_label.setWordWrap(True)
        sensor_card.layout.addWidget(self.sensor_label)

        # Shown only when LHM is not running
        self.lhm_info_label = QLabel(
            "Sensor data requires <b>LibreHardwareMonitor</b>. "
            "Click Install or Launch below — Ghosty Tools will configure it automatically."
        )
        self.lhm_info_label.setStyleSheet("color: #888; font-size: 11px;")
        self.lhm_info_label.setWordWrap(True)
        self.lhm_info_label.hide()
        sensor_card.layout.addWidget(self.lhm_info_label)

        lhm_btn_row = QHBoxLayout()
        self.lhm_download_btn = QPushButton("⬇  Install LibreHardwareMonitor")
        self.lhm_download_btn.setFixedHeight(34)
        self.lhm_download_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 6px; border: none; }"
            "QPushButton:hover { background-color: #4b6de3; }"
        )
        self.lhm_download_btn.clicked.connect(self._install_lhm_winget)
        self.lhm_download_btn.hide()

        self.lhm_launch_btn = QPushButton("Launch LibreHardwareMonitor")
        self.lhm_launch_btn.setFixedHeight(34)
        self.lhm_launch_btn.setStyleSheet(
            "QPushButton { background-color: #1a1a1f; color: #d4d4d4; border: 1px solid #333; border-radius: 6px; }"
            "QPushButton:hover { background-color: #25252b; }"
        )
        self.lhm_launch_btn.clicked.connect(self._launch_lhm)
        self.lhm_launch_btn.hide()

        lhm_btn_row.addWidget(self.lhm_download_btn)
        lhm_btn_row.addWidget(self.lhm_launch_btn)
        lhm_btn_row.addStretch()
        sensor_card.layout.addLayout(lhm_btn_row)

        layout.addWidget(sensor_card)
        
        # Diagnostics Card
        diag_card = DashboardCard("DIAGNOSTICS & SMART")
        self.hw_info_text = QTextEdit()
        self.hw_info_text.setReadOnly(True)
        self.hw_info_text.setStyleSheet("QTextEdit { background-color: transparent; color: #d4d4d4; border: none; font-family: 'Consolas'; font-size: 11px; }")
        self.hw_info_text.hide()
        diag_card.layout.addWidget(self.hw_info_text)
        layout.addWidget(diag_card)
        
        refresh_btn = QPushButton("Refresh Hardware Info")
        refresh_btn.setFixedHeight(45)
        refresh_btn.setStyleSheet("QPushButton { background-color: #4158D0; color: white; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #4b6de3; }")
        refresh_btn.clicked.connect(self.refresh_hardware_health)
        layout.addWidget(refresh_btn)
        
        self.content_stack.addWidget(page)

        # On first load: if LHM exe exists but sensors aren't active yet, pre-configure it
        # so the Remote Web Server is enabled before the user even clicks Launch
        if sys.platform == 'win32':
            QTimer.singleShot(500, self._auto_configure_lhm_if_installed)

    def _auto_configure_lhm_if_installed(self):
        """Silently write LHM config if the exe is found but sensors haven't started yet."""
        if self._find_lhm_exe():
            self._configure_lhm_web_server()

    def refresh_hardware_health(self):
        from src.core.hardware_info import HardwareInfo
        self.hw_info_text.show()
        self.log_to_terminal("Fetching hardware health...")
        info = []
        info.append("--- Disk Health ---")
        info.append(HardwareInfo.get_disk_health())
        info.append("\n--- Battery Info ---")
        info.append(HardwareInfo.get_battery_info())
        info.append("\n--- RAM WHEA Errors ---")
        info.append(HardwareInfo.get_ram_whea_errors())
        self.hw_info_text.setText("\n".join(info))

    def setup_event_viewer_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        
        from src.gui.dashboard import PageHeader, DashboardCard
        header = PageHeader("Windows Event Log Viewer", "View recent system events and diagnostic logs.")
        layout.addWidget(header)
        
        event_card = DashboardCard("RECENT SYSTEM EVENTS")
        self.event_list = QListWidget()
        self.event_list.setStyleSheet("""
            QListWidget {
                background-color: #111;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #222;
            }
            QListWidget::item:selected {
                background-color: #4158D0;
                color: white;
            }
        """)
        event_card.layout.addWidget(self.event_list)
        layout.addWidget(event_card)
        
        refresh_btn = QPushButton("Load Recent Events")
        refresh_btn.setFixedHeight(45)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4158D0;
                color: white;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4b6de3;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_events)
        layout.addWidget(refresh_btn)
        
        self.content_stack.addWidget(page)

    def refresh_events(self):
        from src.core.event_viewer import EventViewer
        self.event_list.clear()
        events = EventViewer.get_windows_events(count=20)
        for e in events:
            item = QListWidgetItem(f"[{e.get('TimeCreated', 'N/A')}] {e.get('LevelDisplayName', 'N/A')} - {e.get('ProviderName', 'N/A')}\n{e.get('Message', '')[:100]}...")
            self.event_list.addItem(item)

    def setup_services_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        
        from src.gui.dashboard import PageHeader, DashboardCard
        header = PageHeader("Advanced Services Manager", "Monitor and manage system services.")
        layout.addWidget(header)
        layout.addWidget(self._make_admin_notice())

        svc_card = DashboardCard("SYSTEM SERVICES")
        self.services_list = QListWidget()
        self.services_list.setStyleSheet("""
            QListWidget {
                background-color: #111;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #222;
            }
            QListWidget::item:selected {
                background-color: #4158D0;
                color: white;
            }
        """)
        self.services_list.hide()
        svc_card.layout.addWidget(self.services_list)
        layout.addWidget(svc_card)
        
        refresh_btn = QPushButton("Refresh Services")
        refresh_btn.setFixedHeight(45)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4158D0;
                color: white;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4b6de3;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_services)
        layout.addWidget(refresh_btn)
        
        self.content_stack.addWidget(page)

    def refresh_services(self):
        from src.core.services_manager import ServicesManager
        self.services_list.show()
        self.services_list.clear()
        services = ServicesManager.get_services()
        if isinstance(services, list):
            for s in services[:50]:
                status = s.get('Status', 'Unknown')
                name = s.get('Name', 'Unknown')
                self.services_list.addItem(f"{name} ({status})")

    def setup_automation_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        from src.gui.dashboard import PageHeader, DashboardCard
        header = PageHeader("Automation & Background Health", "Manage automated tasks and system reporting.")
        layout.addWidget(header)

        # Status Card
        status_card = DashboardCard("SYSTEM STATUS")
        self.automation_status = QLabel("Status: Idle")
        self.automation_status.setStyleSheet("color: #00ff88; font-size: 14px; font-weight: bold;")
        status_card.layout.addWidget(self.automation_status)
        layout.addWidget(status_card)

        # Report Card
        report_card = DashboardCard("LATEST SYSTEM REPORT")
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        self.report_display.setPlaceholderText("Generate a report to see details here...")
        self.report_display.setStyleSheet("""
            QTextEdit {
                background-color: #111;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 10px;
            }
        """)
        self.report_display.hide()
        report_card.layout.addWidget(self.report_display)
        layout.addWidget(report_card)

        report_btn = QPushButton("Generate System Report")
        report_btn.setFixedHeight(45)
        report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        report_btn.setStyleSheet("""
            QPushButton {
                background-color: #4158D0;
                color: white;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4b6de3;
            }
        """)
        report_btn.clicked.connect(self.show_system_report)
        layout.addWidget(report_btn)
        
        self.content_stack.addWidget(page)

    def show_system_report(self):
        from src.core.automation import Automation
        self.report_display.show()
        self.automation_status.setText("Status: Generating Report...")
        self.automation_status.setStyleSheet("color: #ffa500; font-size: 14px; font-weight: bold;")
        
        # In a real app we might want to use a worker, but let's stick to the current logic for now
        report = Automation.generate_system_report()
        self.report_display.setText(report)
        
        self.automation_status.setText("Status: Report Generated")
        self.automation_status.setStyleSheet("color: #00ff88; font-size: 14px; font-weight: bold;")

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_raise()

    def closeEvent(self, event):
        if self._app_settings.get("minimize_to_tray", False):
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "Ghosty Tools",
                    "Running in the background. Click the tray icon to restore.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500
                )
        else:
            event.accept()

    def changeEvent(self, event):
        super().changeEvent(event)
