import os
import sys
import secrets
import base64
import shutil
import platform
import threading
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSlider, QGridLayout, QFrame,
                             QWidget, QProgressBar, QTextEdit, QTreeWidget, QTreeWidgetItem,
                             QCheckBox, QScrollArea, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QDragEnterEvent, QDropEvent
from src.utils.theme_manager import ThemeManager
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from src.utils.helpers import ensure_private_file, get_resource_path

class MasterPasswordDialog(QDialog):
    def __init__(self, is_new=False):
        super().__init__()
        self.setWindowTitle("ShadowKeys - Master Password")
        self.setFixedSize(400, 250)
        self.password = None
        self.is_new = is_new
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        title = QLabel("Password Vault Login" if not self.is_new else "Setup Master Password")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4158D0;")
        layout.addWidget(title)

        self.password_entry = QLineEdit()
        self.password_entry.setPlaceholderText("Enter Master Password")
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_entry.setMinimumHeight(35)
        layout.addWidget(self.password_entry)

        if self.is_new:
            self.confirm_entry = QLineEdit()
            self.confirm_entry.setPlaceholderText("Confirm Master Password")
            self.confirm_entry.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_entry.setMinimumHeight(35)
            layout.addWidget(self.confirm_entry)

        self.btn = QPushButton("Unlock Vault" if not self.is_new else "Create Vault")
        self.btn.setFixedHeight(40)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #4158D0;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #569cd6;
            }
        """)
        self.btn.clicked.connect(self.on_submit)
        layout.addWidget(self.btn)
        self.setLayout(layout)

    def on_submit(self):
        pw = self.password_entry.text()
        if not pw:
            QMessageBox.warning(self, "Error", "Password cannot be empty.")
            return

        if self.is_new:
            if pw != self.confirm_entry.text():
                QMessageBox.warning(self, "Error", "Passwords do not match.")
                return

        self.password = pw
        self.accept()

class HostsEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ShadowHosts - Hosts File Editor")
        self.setMinimumSize(600, 500)
        self.raw_content = ""
        self.init_ui()
        self.load_hosts()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("Hosts File Manager")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4158D0;")
        layout.addWidget(header)
        
        info = QLabel("Map hostnames to IP addresses. Use 127.0.0.1 to block unwanted domains (telemetry, ads, etc.).")
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaaaaa; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["IP Address", "Hostname"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("QTableWidget { background-color: #1e1e1e; color: #ffffff; gridline-color: #333333; }")
        layout.addWidget(self.table)
        
        # Add Entry Group
        add_layout = QHBoxLayout()
        self.ip_input = QLineEdit("127.0.0.1")
        self.ip_input.setPlaceholderText("IP Address")
        self.ip_input.setFixedWidth(120)
        
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("e.g. telemetry.microsoft.com")
        
        add_btn = QPushButton("Add Entry")
        add_btn.setFixedWidth(100)
        add_btn.clicked.connect(self.add_entry)
        
        add_layout.addWidget(self.ip_input)
        add_layout.addWidget(self.host_input)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Delete Selected")
        del_btn.setFixedWidth(120)
        del_btn.clicked.connect(self.delete_entry)
        
        save_btn = QPushButton("Save Changes")
        save_btn.setFixedWidth(150)
        save_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.save_hosts)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def load_hosts(self):
        from src.core.platform_tools.windows import WindowsTools
        success, content = WindowsTools.get_hosts_content()
        if not success:
            QMessageBox.critical(self, "Error", f"Could not read hosts file: {content}")
            return

        self.table.setRowCount(0)
        self.raw_content = content
        
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Split by whitespace but ignore if it's just a comment at end of line
            parts = line.split("#")[0].split()
            if len(parts) >= 2:
                ip = parts[0]
                host = parts[1]
                self.add_table_row(ip, host)

    def add_table_row(self, ip, host):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(ip))
        self.table.setItem(row, 1, QTableWidgetItem(host))

    def add_entry(self):
        ip = self.ip_input.text().strip()
        host = self.host_input.text().strip()
        if not ip or not host:
            return
        
        # Check for duplicates
        for r in range(self.table.rowCount()):
            if self.table.item(r, 1).text().strip() == host:
                QMessageBox.warning(self, "Duplicate", f"Hostname '{host}' is already in the list.")
                return

        self.add_table_row(ip, host)
        self.host_input.clear()

    def delete_entry(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
        else:
            QMessageBox.information(self, "Select Row", "Please select an entry to delete.")

    def save_hosts(self):
        new_entries = []
        for row in range(self.table.rowCount()):
            ip = self.table.item(row, 0).text().strip()
            host = self.table.item(row, 1).text().strip()
            if ip and host:
                new_entries.append(f"{ip.ljust(15)} {host}")
        
        # Reconstruct file: keep original comments/structure but replace active entries?
        # That's hard to do perfectly. Let's keep comments from top and append our new list.
        lines = self.raw_content.splitlines()
        header_comments = []
        for line in lines:
            if line.strip().startswith("#") or not line.strip():
                header_comments.append(line)
            else:
                # Once we hit a non-comment line, we stop collecting headers
                # (Unless we want to preserve inline comments, but let's keep it simple)
                break
        
        final_content = "\n".join(header_comments).rstrip() + "\n\n# Active Entries (Managed by GhostyTools)\n"
        final_content += "\n".join(new_entries) + "\n"
        
        from src.core.platform_tools.windows import WindowsTools
        success, msg = WindowsTools.save_hosts_content(final_content)
        if success:
            QMessageBox.information(self, "Success", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to save: {msg}")

class AppearanceDialog(QFrame):
    theme_changed = pyqtSignal()

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.tm = theme_manager
        self.preset_buttons = {}
        self.setFixedSize(400, 520) # Slightly smaller
        self.setObjectName("AppearanceOverlay")
        self.hide()
        
        # Apply initial styling
        self.init_ui()
        self.update_style()
        self.update_preset_buttons()
        
        if hasattr(self, 'bg_slider'):
            self.bg_slider.setValue(self.tm.bg_intensity)

    def update_style(self):
        colors = self.tm.get_theme_colors()
        self.setStyleSheet(f"""
            QFrame#AppearanceOverlay {{
                background-color: {colors['background']};
                border: 1px solid #333;
                border-radius: 15px;
            }}
            QLabel {{ color: white; background: transparent; }}
        """)
        if hasattr(self, 'bg_slider'):
            self.bg_slider.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    border: 1px solid #333;
                    height: 4px;
                    background: #222;
                    margin: 2px 0;
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: {colors['primary']};
                    border: 1px solid {colors['primary']};
                    width: 16px;
                    height: 16px;
                    margin: -6px 0;
                    border-radius: 8px;
                }}
            """)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(10)

        # Header with Close Button
        header_layout = QHBoxLayout()
        header = QLabel("Appearance")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover {
                color: white;
                background-color: #333;
                border-radius: 14px;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)
        layout.addLayout(header_layout)

        sub_header = QLabel("Personalize your workspace")
        sub_header.setStyleSheet("color: #666; font-size: 11px; margin-top: -5px;")
        layout.addWidget(sub_header)

        # Theme Type (Dark, Light, Custom)
        from PyQt6.QtWidgets import QButtonGroup
        self.mode_group = QButtonGroup(self)
        type_layout = QHBoxLayout()
        type_layout.setSpacing(10)
        
        self.dark_btn = QPushButton("Dark")
        self.light_btn = QPushButton("Light")
        self.custom_btn = QPushButton("Custom")
        
        for i, btn in enumerate([self.dark_btn, self.light_btn, self.custom_btn]):
            btn.setCheckable(True)
            btn.setFixedHeight(45)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.mode_group.addButton(btn, i)
            # ...
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a1a1f;
                    border: 1px solid #333;
                    border-radius: 8px;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:checked {
                    background-color: #333;
                    border: 2px solid #4158D0;
                }
                QPushButton:hover {
                    border-color: #555;
                }
            """)
            type_layout.addWidget(btn)
        
        self.dark_btn.setChecked(True)
        layout.addLayout(type_layout)

        # Presets Section
        presets_label = QLabel("PRESETS")
        presets_label.setStyleSheet("color: #888; font-weight: bold; margin-top: 15px; font-size: 11px;")
        layout.addWidget(presets_label)

        presets_grid = QGridLayout()
        presets_grid.setSpacing(12)

        presets = list(ThemeManager.DEFAULT_THEMES.keys())
        for i, name in enumerate(presets):
            btn = self.create_preset_button(name)
            self.preset_buttons[name] = btn
            presets_grid.addWidget(btn, i // 2, i % 2)
        
        layout.addLayout(presets_grid)

        # Background Slider
        bg_label = QLabel("BACKGROUND")
        bg_label.setStyleSheet("color: #888; font-weight: bold; margin-top: 15px; font-size: 11px;")
        layout.addWidget(bg_label)

        self.bg_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_slider.setRange(0, 100)
        self.bg_slider.setValue(50)
        self.bg_slider.setMinimumHeight(30)
        self.bg_slider.valueChanged.connect(self.on_bg_adjustment)
        layout.addWidget(self.bg_slider)

        layout.addStretch()

    def on_bg_adjustment(self, value):
        self.tm.bg_intensity = value
        self.tm.save_settings()
        self.theme_changed.emit()
        self.update_style()

    def create_preset_button(self, name):
        colors = ThemeManager.DEFAULT_THEMES[name]
        btn = QPushButton()
        btn.setFixedHeight(55)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Initial styling (will be updated by update_preset_buttons)
        self.style_preset_button(btn, name, colors)
        
        # Layout for squares and text
        h_layout = QHBoxLayout(btn)
        h_layout.setContentsMargins(12, 0, 12, 0)
        h_layout.setSpacing(10)
        
        # Color squares
        sq_container = QWidget()
        sq_layout = QHBoxLayout(sq_container)
        sq_layout.setContentsMargins(0, 0, 0, 0)
        sq_layout.setSpacing(5)
        
        # Use primary, secondary, and text for a better representation in the UI
        for color_key in ['primary', 'secondary', 'text']:
            sq = QFrame()
            sq.setFixedSize(14, 14)
            sq_color = colors.get(color_key, "#ffffff")
            sq.setStyleSheet(f"background-color: {sq_color}; border-radius: 4px;")
            sq_layout.addWidget(sq)
        
        h_layout.addWidget(sq_container)
        
        name_label = QLabel(name)
        name_label.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        h_layout.addWidget(name_label)
        h_layout.addStretch()
        
        btn.clicked.connect(lambda _, n=name: self.apply_preset(n))
        return btn

    def style_preset_button(self, btn, name, colors):
        is_current = self.tm.current_theme == name
        border_color = colors['primary'] if is_current else "#333"
        border_width = "2px" if is_current else "1px"
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['surface']};
                border: {border_width} solid {border_color};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                border-color: {colors['primary']};
            }}
        """)

    def apply_preset(self, name):
        self.tm.set_theme(name)
        self.theme_changed.emit()
        self.update_style()
        self.update_preset_buttons()

    def update_preset_buttons(self):
        for name, btn in self.preset_buttons.items():
            colors = ThemeManager.DEFAULT_THEMES.get(name, {})
            if colors:
                self.style_preset_button(btn, name, colors)

class UpdateDialog(QDialog):
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle("Ghosty Tool Update")
        self.setFixedSize(500, 420)
        self.setStyleSheet("background-color: #0f0f12; color: white;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header with Logo/Name
        header_layout = QHBoxLayout()
        
        # Logo placeholder
        logo_label = QLabel()
        icon_path = os.path.join(get_resource_path(""), "images", "ghosty icon.ico")
        if os.path.exists(icon_path):
            pixmap = QIcon(icon_path).pixmap(48, 48)
            logo_label.setPixmap(pixmap)
        else:
            logo_label.setText("👻")
            logo_label.setStyleSheet("font-size: 32px; background: transparent;")
        header_layout.addWidget(logo_label)
        
        title_info = QVBoxLayout()
        title_info.setSpacing(2)
        
        title_row = QHBoxLayout()
        name_label = QLabel("Ghosty Tool")
        name_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white; background: transparent;")
        title_row.addWidget(name_label)
        
        version_badge = QLabel(self.update_info.get("latest_version", "v7.3.2"))
        version_badge.setStyleSheet("""
            background-color: #4158D0;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 5px;
        """)
        title_row.addWidget(version_badge)
        title_row.addStretch()
        title_info.addLayout(title_row)
        
        subtitle = QLabel("A new version is available for download.")
        subtitle.setStyleSheet("color: #888; font-size: 13px; background: transparent;")
        title_info.addWidget(subtitle)
        
        header_layout.addLayout(title_info)
        layout.addLayout(header_layout)

        # Release Notes
        notes_label = QLabel("WHAT'S NEW")
        notes_label.setStyleSheet("color: #666; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(notes_label)
        
        self.notes_area = QTextEdit()
        self.notes_area.setReadOnly(True)
        # Handle cases where release_notes might be missing
        notes = self.update_info.get("body", self.update_info.get("release_notes", "No release notes provided."))
        self.notes_area.setPlainText(notes)
        self.notes_area.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1f;
                border: 1px solid #333;
                border-radius: 10px;
                color: #d4d4d4;
                padding: 12px;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.notes_area)

        # Progress Section (Hidden initially)
        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        
        self.status_label = QLabel("Ready to update")
        self.status_label.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #2a2a2a; border: none; border-radius: 4px; }
            QProgressBar::chunk { background-color: #4158D0; border-radius: 4px; }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_container.hide()
        layout.addWidget(self.progress_container)

        # Buttons
        self.btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("Later")
        self.close_btn.setFixedHeight(45)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                border: 1px solid #333; 
                border-radius: 8px; 
                color: white; 
                font-weight: bold;
            } 
            QPushButton:hover { background-color: #1a1a1f; border-color: #444; }
        """)
        self.close_btn.clicked.connect(self.reject)
        
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setFixedHeight(45)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet("""
            QPushButton { 
                background-color: #4158D0; 
                border: none; 
                border-radius: 8px; 
                color: white; 
                font-weight: bold;
            } 
            QPushButton:hover { background-color: #4b6de3; }
            QPushButton:disabled { background-color: #25252b; color: #555; }
        """)
        
        self.btn_layout.addWidget(self.close_btn)
        self.btn_layout.addWidget(self.update_btn)
        layout.addLayout(self.btn_layout)

    def set_progress(self, value):
        self.progress_container.show()
        self.update_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress_bar.setValue(value)

    def set_status(self, text):
        self.status_label.setText(text)


class TidyDesktopDialog(QDialog):
    """Scans the desktop, groups loose files by type, and lets the user
    move them to the appropriate user library folder."""

    # Maps extension → (destination folder name, display category)
    _EXT_MAP = {
        # Images
        ".jpg": ("Pictures", "Images"), ".jpeg": ("Pictures", "Images"),
        ".png": ("Pictures", "Images"), ".gif": ("Pictures", "Images"),
        ".bmp": ("Pictures", "Images"), ".webp": ("Pictures", "Images"),
        ".svg": ("Pictures", "Images"), ".ico": ("Pictures", "Images"),
        ".tiff": ("Pictures", "Images"), ".tif": ("Pictures", "Images"),
        ".heic": ("Pictures", "Images"), ".raw": ("Pictures", "Images"),
        # Videos
        ".mp4": ("Videos", "Videos"), ".mkv": ("Videos", "Videos"),
        ".avi": ("Videos", "Videos"), ".mov": ("Videos", "Videos"),
        ".wmv": ("Videos", "Videos"), ".flv": ("Videos", "Videos"),
        ".webm": ("Videos", "Videos"), ".m4v": ("Videos", "Videos"),
        # Audio
        ".mp3": ("Music", "Music"), ".wav": ("Music", "Music"),
        ".flac": ("Music", "Music"), ".aac": ("Music", "Music"),
        ".ogg": ("Music", "Music"), ".m4a": ("Music", "Music"),
        ".wma": ("Music", "Music"),
        # Documents
        ".pdf": ("Documents", "Documents"), ".doc": ("Documents", "Documents"),
        ".docx": ("Documents", "Documents"), ".xls": ("Documents", "Documents"),
        ".xlsx": ("Documents", "Documents"), ".ppt": ("Documents", "Documents"),
        ".pptx": ("Documents", "Documents"), ".txt": ("Documents", "Documents"),
        ".odt": ("Documents", "Documents"), ".ods": ("Documents", "Documents"),
        ".csv": ("Documents", "Documents"), ".rtf": ("Documents", "Documents"),
        # Archives
        ".zip": ("Downloads", "Archives"), ".rar": ("Downloads", "Archives"),
        ".7z": ("Downloads", "Archives"), ".tar": ("Downloads", "Archives"),
        ".gz": ("Downloads", "Archives"), ".bz2": ("Downloads", "Archives"),
        ".xz": ("Downloads", "Archives"),
        # Executables / Installers
        ".exe": ("Downloads", "Installers"), ".msi": ("Downloads", "Installers"),
        ".dmg": ("Downloads", "Installers"), ".pkg": ("Downloads", "Installers"),
        ".deb": ("Downloads", "Installers"), ".rpm": ("Downloads", "Installers"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tidy Desktop")
        self.setMinimumSize(620, 500)
        self.setStyleSheet("background-color: #16161a; color: #d4d4d4;")
        self._pending = {}   # {dest_folder: [src_path, ...]}
        self._init_ui()
        self._scan()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title = QLabel("Tidy Desktop")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #4158D0;")
        layout.addWidget(title)

        desc = QLabel(
            "Files will be moved to the corresponding user library folder.\n"
            "Shortcuts (.lnk) and folders are never touched."
        )
        desc.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(desc)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Destination"])
        self.tree.setColumnWidth(0, 340)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet(
            "QTreeWidget { background-color: #1e1e24; border: 1px solid #333; border-radius: 5px; }"
            "QTreeWidget::item:alternate { background-color: #202025; }"
            "QTreeWidget::item { padding: 2px; }"
        )
        layout.addWidget(self.tree)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()

        self.rescan_btn = QPushButton("Re-scan")
        self.rescan_btn.setFixedHeight(36)
        self.rescan_btn.setStyleSheet(
            "QPushButton { background-color: #1e1e1e; border: 1px solid #444; border-radius: 6px; color: #ccc; }"
            "QPushButton:hover { background-color: #28282e; }"
        )
        self.rescan_btn.clicked.connect(self._scan)
        btn_row.addWidget(self.rescan_btn)

        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setStyleSheet(
            "QPushButton { background-color: #1e1e1e; border: 1px solid #444; border-radius: 6px; color: #ccc; }"
            "QPushButton:hover { background-color: #28282e; }"
        )
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.tidy_btn = QPushButton("Tidy Now")
        self.tidy_btn.setFixedHeight(36)
        self.tidy_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; border: none; border-radius: 6px; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #4b6de3; }"
            "QPushButton:disabled { background-color: #25252b; color: #555; }"
        )
        self.tidy_btn.clicked.connect(self._apply)
        btn_row.addWidget(self.tidy_btn)

        layout.addLayout(btn_row)

    def _scan(self):
        self.tree.clear()
        self._pending.clear()
        self.tidy_btn.setEnabled(False)

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(desktop):
            self.status_lbl.setText("Desktop folder not found.")
            return

        user_home = os.path.expanduser("~")
        groups = {}  # category → [(src_path, dest_folder)]

        for name in os.listdir(desktop):
            src = os.path.join(desktop, name)
            if os.path.isdir(src):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext == ".lnk":
                continue  # keep shortcuts
            if ext not in self._EXT_MAP:
                continue
            dest_folder, category = self._EXT_MAP[ext]
            groups.setdefault(category, []).append((src, dest_folder))

        if not groups:
            self.status_lbl.setText("Desktop is already tidy — nothing to move.")
            return

        total = 0
        for category, items in sorted(groups.items()):
            cat_item = QTreeWidgetItem(self.tree, [category, ""])
            cat_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
            cat_item.setForeground(0, QColor("#4158D0"))
            for src, dest_folder in sorted(items, key=lambda x: os.path.basename(x[0])):
                dest_dir = os.path.join(user_home, dest_folder)
                child = QTreeWidgetItem(cat_item, [os.path.basename(src), dest_dir])
                child.setToolTip(0, src)
                self._pending.setdefault(dest_folder, []).append(src)
                total += 1
            cat_item.setExpanded(True)

        self.status_lbl.setText(f"{total} file(s) will be moved.")
        self.tidy_btn.setEnabled(True)

    def _apply(self):
        if not self._pending:
            return

        user_home = os.path.expanduser("~")
        moved, errors = 0, []

        for dest_folder, src_list in self._pending.items():
            dest_dir = os.path.join(user_home, dest_folder)
            os.makedirs(dest_dir, exist_ok=True)
            for src in src_list:
                try:
                    name = os.path.basename(src)
                    dest = os.path.join(dest_dir, name)
                    # Avoid overwriting — append a number suffix if needed
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(name)
                        counter = 1
                        while os.path.exists(dest):
                            dest = os.path.join(dest_dir, f"{base} ({counter}){ext}")
                            counter += 1
                    shutil.move(src, dest)
                    moved += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(src)}: {e}")

        if errors:
            QMessageBox.warning(
                self, "Tidy Desktop — Partial Success",
                f"Moved {moved} file(s).\n\nErrors:\n" + "\n".join(errors)
            )
        else:
            QMessageBox.information(
                self, "Tidy Desktop",
                f"Done! {moved} file(s) moved to their library folders."
            )
        self.accept()


class GameCompatibilityDialog(QDialog):
    """Analyze a game's system requirements against current hardware."""

    _DB = {
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
        "csgo": {"name": "CS:GO / CS2", "min": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 15}, "rec": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 15}},
        "cs2": {"name": "CS2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 30}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 30}},
        "counter-strike": {"name": "CS2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 30}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 30}},
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
        "bg3": {"name": "Baldur's Gate 3", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 150}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 150}},
        "dota 2": {"name": "Dota 2", "min": {"ram_gb": 4, "cpu_cores": 2, "gpu_vram_gb": 0.5, "storage_gb": 15}, "rec": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 1, "storage_gb": 15}},
        "rust": {"name": "Rust", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 20}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 20}},
        "pubg": {"name": "PUBG: Battlegrounds", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 2, "storage_gb": 40}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 4, "storage_gb": 40}},
        "palworld": {"name": "Palworld", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 40}, "rec": {"ram_gb": 32, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 40}},
        "helldivers 2": {"name": "Helldivers 2", "min": {"ram_gb": 8, "cpu_cores": 4, "gpu_vram_gb": 4, "storage_gb": 100}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 100}},
        "black myth wukong": {"name": "Black Myth: Wukong", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 8, "storage_gb": 130}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 16, "storage_gb": 130}},
        "black myth: wukong": {"name": "Black Myth: Wukong", "min": {"ram_gb": 16, "cpu_cores": 4, "gpu_vram_gb": 8, "storage_gb": 130}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 16, "storage_gb": 130}},
        "star wars outlaws": {"name": "Star Wars Outlaws", "min": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 8, "storage_gb": 65}, "rec": {"ram_gb": 16, "cpu_cores": 8, "gpu_vram_gb": 12, "storage_gb": 65}},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Compatibility Analyzer")
        self.setMinimumSize(680, 540)
        self.setStyleSheet("background-color: #16161a; color: #d4d4d4;")
        self.setAcceptDrops(True)
        self._sys_specs = {}
        self._init_ui()
        threading.Thread(target=self._fetch_specs, daemon=True).start()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title = QLabel("Game Compatibility Analyzer")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #4158D0;")
        layout.addWidget(title)

        desc = QLabel("Type a game name or drop an .exe onto this window to check compatibility against your hardware.")
        desc.setStyleSheet("color: #888; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        input_row = QHBoxLayout()
        self.game_input = QLineEdit()
        self.game_input.setPlaceholderText("Game name or drag & drop .exe here...")
        self.game_input.setMinimumHeight(36)
        self.game_input.setStyleSheet(
            "QLineEdit { background-color: #1e1e24; border: 1px solid #333; border-radius: 6px; "
            "padding: 4px 8px; color: #d4d4d4; }"
            "QLineEdit:focus { border: 1px solid #4158D0; }"
        )
        self.game_input.returnPressed.connect(self._analyze)
        # Disable drops on the text field so drag events reach the dialog
        self.game_input.setAcceptDrops(False)
        input_row.addWidget(self.game_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedHeight(36)
        browse_btn.setStyleSheet(
            "QPushButton { background-color: #1e1e1e; border: 1px solid #444; border-radius: 6px; "
            "color: #ccc; padding: 0 12px; } QPushButton:hover { background-color: #28282e; }"
        )
        browse_btn.clicked.connect(self._browse_exe)
        input_row.addWidget(browse_btn)

        analyze_btn = QPushButton("Analyze")
        analyze_btn.setFixedHeight(36)
        analyze_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; border: none; border-radius: 6px; "
            "color: white; font-weight: bold; padding: 0 18px; } QPushButton:hover { background-color: #4b6de3; }"
        )
        analyze_btn.clicked.connect(self._analyze)
        input_row.addWidget(analyze_btn)
        layout.addLayout(input_row)

        self.specs_lbl = QLabel("Detecting system specs...")
        self.specs_lbl.setStyleSheet(
            "background-color: #1e1e24; border: 1px solid #2a2a30; border-radius: 6px; "
            "padding: 8px; color: #888; font-size: 11px;"
        )
        self.specs_lbl.setWordWrap(True)
        layout.addWidget(self.specs_lbl)

        # Visual drop zone hint
        drop_hint = QLabel("⬇  Drop .exe here to auto-detect game")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_hint.setStyleSheet(
            "QLabel { border: 2px dashed #333; border-radius: 7px; color: #555; "
            "font-size: 11px; padding: 8px; background-color: #1a1a1f; }"
        )
        drop_hint.setAcceptDrops(False)
        layout.addWidget(drop_hint)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setAcceptDrops(False)
        self.result_area.setStyleSheet(
            "QTextEdit { background-color: #1e1e24; border: 1px solid #333; border-radius: 6px; "
            "color: #d4d4d4; font-family: Consolas, monospace; font-size: 12px; }"
        )
        layout.addWidget(self.result_area)

        self.apply_btn = QPushButton("Apply Gaming Mode Settings")
        self.apply_btn.setFixedHeight(38)
        self.apply_btn.setVisible(False)
        self.apply_btn.setStyleSheet(
            "QPushButton { background-color: #4158D0; border: none; border-radius: 6px; "
            "color: white; font-weight: bold; } QPushButton:hover { background-color: #4b6de3; }"
        )
        self.apply_btn.clicked.connect(self._apply_gaming_mode)
        layout.addWidget(self.apply_btn)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #1e1e1e; border: 1px solid #444; border-radius: 6px; color: #ccc; }"
            "QPushButton:hover { background-color: #28282e; }"
        )
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(".exe") for u in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".exe"):
                name = os.path.splitext(os.path.basename(path))[0]
                # Try to read ProductName from PE version info on Windows
                if sys.platform == "win32":
                    try:
                        from src.utils.helpers import run_command
                        res = run_command(
                            ["powershell", "-NoProfile", "-Command",
                             f"(Get-Item '{path}').VersionInfo.ProductName"],
                            timeout=5
                        )
                        product = res.stdout.strip()
                        if product and product.lower() not in ("", "null"):
                            name = product
                    except Exception:
                        pass
                self.game_input.setText(name)
                self._analyze()
                break

    def _fetch_specs(self):
        try:
            import psutil
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
            self._sys_specs = {
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
                self.specs_lbl, "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, spec_text)
            )
        except Exception as e:
            from PyQt6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(
                self.specs_lbl, "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"Could not detect specs: {e}")
            )

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Game Executable", "", "Executables (*.exe)")
        if path:
            self.game_input.setText(os.path.splitext(os.path.basename(path))[0])

    def _analyze(self):
        query = self.game_input.text().strip()
        if not query:
            return
        self.result_area.clear()
        self.apply_btn.setVisible(False)
        entry = self._DB.get(query.lower())
        if not entry:
            for key, val in self._DB.items():
                if query.lower() in key or key in query.lower():
                    entry = val
                    break
        if not entry:
            db_list = ", ".join(sorted(set(v["name"] for v in self._DB.values())))
            self.result_area.setHtml(
                f"<p style='color:#f0a050;'>&#9888; <b>{query}</b> is not in the built-in database.</p>"
                f"<p style='color:#888;'>Try a shorter or alternate name (e.g. 'cyberpunk', 'bg3', 'cs2').<br><br>"
                f"<b>Tip:</b> Use the full <b>Gaming</b> page (sidebar) to enter manual requirements "
                f"for any game not in the database.<br><br>"
                f"Built-in games: {db_list}</p>"
            )
            return
        if not self._sys_specs:
            self.result_area.setHtml("<p style='color:#888;'>Still detecting system specs - please wait a moment and try again.</p>")
            return
        s = self._sys_specs
        mn = entry["min"]
        rc = entry["rec"]

        def check(label, have, need_min, need_rec, unit=""):
            ok_rec = have >= need_rec
            ok_min = have >= need_min
            if ok_rec:
                icon, color, verdict = "&#10003;", "#4ec994", "Exceeds recommended"
            elif ok_min:
                icon, color, verdict = "&#9888;", "#f0a050", f"Meets minimum (rec: {need_rec}{unit})"
            else:
                icon, color, verdict = "&#10007;", "#f44747", f"Below minimum (need: {need_min}{unit}, rec: {need_rec}{unit})"
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
        score = sum(25 if h >= r else (12 if h >= m else 0) for h, m, r in checks)
        if score >= 90:
            verdict_color, verdict_text = "#4ec994", "Ready to Play (High Settings)"
        elif score >= 60:
            verdict_color, verdict_text = "#f0a050", "Playable (Low/Medium Settings)"
        elif score >= 30:
            verdict_color, verdict_text = "#f0a050", "Barely Playable (Minimum Settings)"
        else:
            verdict_color, verdict_text = "#f44747", "Not Recommended"

        tip = ""
        if score < 100:
            tip = "<p style='color:#888; font-size:11px; margin-top:10px;'>Tip: Apply Gaming Mode settings below to improve in-game performance.</p>"

        self.result_area.setHtml(
            f"<h3 style='color:#4158D0; margin:0 0 6px 0;'>{entry['name']}</h3>"
            f"<p style='color:{verdict_color}; font-size:14px; margin:0 0 10px 0;'>"
            f"<b>Compatibility Score: {score}/100 &mdash; {verdict_text}</b></p>"
            f"<table style='width:100%; border-collapse:collapse;'>"
            f"<tr style='background-color:#25252b;'>"
            f"<th style='text-align:left; padding:4px 8px; color:#888;'>Component</th>"
            f"<th style='text-align:left; padding:4px 8px; color:#888;'>Your System</th>"
            f"<th style='text-align:left; padding:4px 8px; color:#888;'>Status</th></tr>"
            f"{rows}</table>{tip}"
        )
        self.apply_btn.setVisible(score < 100 and sys.platform == "win32")

    def _apply_gaming_mode(self):
        try:
            from src.core.platform_tools.windows import WindowsTools
            success, msg = WindowsTools.toggle_gaming_mode(True)
            title = "Gaming Mode Applied" if success else "Gaming Mode"
            QMessageBox.information(self, title, msg[:600]) if success else QMessageBox.warning(self, title, msg[:600])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
