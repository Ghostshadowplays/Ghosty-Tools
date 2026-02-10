import os
import sqlite3
import json
import logging
import base64
import secrets
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

class PasswordManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.key = None
        self.cipher = None
        self.passwords = {}
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database tables."""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value BLOB
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS passwords (
                    site TEXT PRIMARY KEY,
                    encrypted_password BLOB
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def exists(self):
        """Checks if a vault already exists in the database (has a salt)."""
        try:
            if not os.path.exists(self.db_path):
                return False
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'salt'")
            row = cursor.fetchone()
            conn.close()
            return row is not None
        except Exception:
            return False

    def initialize_vault(self, master_password):
        """Creates a new vault with master password and salt."""
        salt = secrets.token_bytes(16)
        self.key = self._derive_key(master_password, salt)
        self.cipher = Fernet(self.key)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('salt', ?)", (salt,))
            # Store a verification block to check password later
            verify_block = self.cipher.encrypt(b"VERIFY_KEY_OK")
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('verify', ?)", (verify_block,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize vault: {e}")
            return False

    def unlock(self, master_password):
        """Verifies master password and prepares for decryption."""
        try:
            if not os.path.exists(self.db_path):
                return False
                
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'salt'")
            salt_row = cursor.fetchone()
            if not salt_row:
                conn.close()
                return False
            
            salt = salt_row[0]
            cursor.execute("SELECT value FROM metadata WHERE key = 'verify'")
            verify_row = cursor.fetchone()
            conn.close()
            
            if not verify_row:
                return False
            
            self.key = self._derive_key(master_password, salt)
            self.cipher = Fernet(self.key)
            
            # This will raise InvalidToken if password is wrong
            self.cipher.decrypt(verify_row[0])
            
            # If we reached here, password is correct. Load all entries.
            return self._load_all()
        except (InvalidToken, Exception) as e:
            if not isinstance(e, InvalidToken):
                logger.error(f"Error unlocking vault: {e}")
            self.key = None
            self.cipher = None
            return False

    def _load_all(self):
        """Loads and decrypts all passwords from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT site, encrypted_password FROM passwords")
            rows = cursor.fetchall()
            conn.close()
            
            self.passwords = {}
            for site, enc_pw in rows:
                try:
                    self.passwords[site] = self.cipher.decrypt(enc_pw).decode()
                except Exception:
                    continue # Skip entries that fail to decrypt
            return True
        except Exception as e:
            logger.error(f"Failed to load passwords: {e}")
            return False

    def save_password(self, site, password):
        """Encrypts and saves a single password entry."""
        if not self.cipher: return False
        if not self.is_safe_input(site) or not self.is_safe_input(password):
            return False
            
        try:
            enc_pw = self.cipher.encrypt(password.encode())
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO passwords (site, encrypted_password) VALUES (?, ?)", (site, enc_pw))
            conn.commit()
            conn.close()
            self.passwords[site] = password
            return True
        except Exception as e:
            logger.error(f"Failed to save password: {e}")
            return False

    def delete_password(self, site):
        """Deletes a password entry."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM passwords WHERE site = ?", (site,))
            conn.commit()
            conn.close()
            if site in self.passwords:
                del self.passwords[site]
            return True
        except Exception as e:
            logger.error(f"Failed to delete password: {e}")
            return False

    def _derive_key(self, password, salt):
        """Derives a 32-byte key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def is_safe_input(self, user_input):
        if not isinstance(user_input, str) or len(user_input) > 4096:
            return False
        return all(ord(c) >= 32 for c in user_input)

    def get_all_sites(self):
        return sorted(list(self.passwords.keys()))

    def clear_memory(self):
        """Best effort to clear sensitive data from memory."""
        for site in list(self.passwords.keys()):
            self.passwords[site] = ""
        self.passwords.clear()
        self.key = None
        self.cipher = None

    def migrate_from_json(self, json_path, salt_path, master_password):
        """Attempts to migrate data from old JSON/salt files."""
        if not os.path.exists(json_path) or not os.path.exists(salt_path):
            return False
            
        try:
            # 1. Ensure the current SQLite vault is ready to accept passwords
            if not self.cipher:
                if not self.exists():
                    if not self.initialize_vault(master_password):
                        return False
                else:
                    if not self.unlock(master_password):
                        return False

            # 2. Open and decrypt the old legacy vault
            with open(salt_path, "rb") as f:
                old_salt = f.read()
            
            # Derive the OLD key using the same logic
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=old_salt,
                iterations=390000,
                backend=default_backend()
            )
            old_key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            old_cipher = Fernet(old_key)
            
            with open(json_path, "r") as f:
                data = json.load(f)
            
            # Verify the old password works for the JSON vault if it has __verify__
            if "__verify__" in data:
                try:
                    old_cipher.decrypt(data["__verify__"].encode())
                except InvalidToken:
                    logger.error("Migration failed: Master password incorrect for legacy vault.")
                    return False
            
            # 3. Migrate entries to the current SQLite vault
            count = 0
            for site, enc_pw_str in data.items():
                if site in ("__verify__", "__version__"): continue
                try:
                    raw_pw = old_cipher.decrypt(enc_pw_str.encode()).decode()
                    if self.save_password(site, raw_pw):
                        count += 1
                except Exception:
                    continue
            
            logger.info(f"Successfully migrated {count} passwords from old JSON vault.")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
