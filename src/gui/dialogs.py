import os
import secrets
import base64
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from src.utils.helpers import ensure_private_file

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
