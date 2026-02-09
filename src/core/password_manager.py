import os
import json
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class PasswordManager:
    def __init__(self, key):
        self.key = key
        self.cipher = Fernet(self.key)
        self.passwords = {}
        self.password_file_path = None

    def set_file_path(self, path):
        self.password_file_path = path

    def load_passwords(self):
        if self.password_file_path and os.path.exists(self.password_file_path):
            try:
                with open(self.password_file_path, "r") as f:
                    encrypted_passwords = json.load(f)
                self.passwords = {site: self.decrypt(pw.encode()) for site, pw in encrypted_passwords.items()}
                return True
            except Exception as e:
                logger.error(f"Failed to decrypt password file: {e}")
                return False
        return False

    def save_to_file(self):
        if self.password_file_path:
            try:
                with open(self.password_file_path, "w") as f:
                    encrypted_passwords = {site: self.encrypt(pw).decode() for site, pw in self.passwords.items()}
                    json.dump(encrypted_passwords, f, indent=4)
            except Exception as e:
                logger.error(f"Failed to save password file: {e}")

    def encrypt(self, password):
        return self.cipher.encrypt(password.encode())

    def decrypt(self, encrypted_password):
        return self.cipher.decrypt(encrypted_password).decode()

    def save_password(self, site, password):
        if self.is_safe_input(site) and self.is_safe_input(password):
            self.passwords[site] = password
            self.save_to_file()
            return True
        return False

    def is_safe_input(self, user_input):
        allowed_special_chars = "!#$%&'()*+,-./:;<=\\>?@[]^_{|}~\"`"
        return isinstance(user_input, str) and all(
            c.isalnum() or c in (' ', '-', '_') or c in allowed_special_chars for c in user_input)

    def delete_password(self, site):
        if site in self.passwords:
            del self.passwords[site]
            self.save_to_file()
            return True
        return False

    def get_all_sites(self):
        return list(self.passwords.keys())
