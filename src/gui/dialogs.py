import os
import secrets
import base64
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

class MasterPasswordDialog(QDialog):
    def __init__(self, salt_file_path):
        super().__init__()
        self.setWindowTitle("ShadowKeys - Master Password")
        self.salt_file_path = salt_file_path
        self.setFixedSize(400, 250)
        self.key = None
        self.is_new = not os.path.exists(self.salt_file_path)
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
            salt = secrets.token_bytes(16)
            with open(self.salt_file_path, "wb") as f:
                f.write(salt)
        else:
            with open(self.salt_file_path, "rb") as f:
                salt = f.read()

        self.key = self.derive_key(pw.encode(), salt)
        self.accept()

    @staticmethod
    def derive_key(password: bytes, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password))
