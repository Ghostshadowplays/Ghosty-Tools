import os
import json
import logging
from cryptography.fernet import Fernet, InvalidToken

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
        """Loads and decrypts passwords from file with key verification."""
        if self.password_file_path and os.path.exists(self.password_file_path):
            try:
                with open(self.password_file_path, "r") as f:
                    data = json.load(f)
                
                # 1. Key Verification
                if "__verify__" in data:
                    try:
                        self.decrypt(data["__verify__"].encode())
                    except InvalidToken:
                        logger.error("Master password verification failed (InvalidToken).")
                        return False
                
                # 2. Decrypt all entries
                new_passwords = {}
                for site, pw in data.items():
                    if site == "__verify__":
                        continue
                    new_passwords[site] = self.decrypt(pw.encode())
                
                self.passwords = new_passwords
                return True
            except (InvalidToken, json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to load password file (Security/Format error): {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error loading passwords: {e}")
                return False
        return False

    def save_to_file(self):
        """Encrypts and saves passwords to file with a verification block."""
        if self.password_file_path:
            try:
                # Add verification block to allow key checking on next load
                encrypted_data = {
                    "__version__": 1,
                    "__verify__": self.encrypt("VERIFY_KEY_OK").decode()
                }
                for site, pw in self.passwords.items():
                    encrypted_data[site] = self.encrypt(pw).decode()
                
                with open(self.password_file_path, "w") as f:
                    json.dump(encrypted_data, f, indent=4)
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
        """Validate input to prevent injection and handle size limits."""
        if not isinstance(user_input, str):
            return False
        if len(user_input) > 4096: # Prevent massive memory allocation
            return False
        # Disallow control characters that could be used for JSON trickery 
        # although json.dump handles escaping, it's good practice.
        return all(ord(c) >= 32 for c in user_input)

    def delete_password(self, site):
        if site in self.passwords:
            # Overwrite with empty before deletion (best effort in Python)
            self.passwords[site] = "" 
            del self.passwords[site]
            self.save_to_file()
            return True
        return False

    def clear_memory(self):
        """Best effort to clear sensitive data from memory."""
        for site in list(self.passwords.keys()):
            self.passwords[site] = ""
        self.passwords.clear()

    def get_all_sites(self):
        return list(self.passwords.keys())
