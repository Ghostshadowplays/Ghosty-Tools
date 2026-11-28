"""Immutable snapshots and a durable authenticated SQLite write-ahead journal."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import sqlite3
import stat
import subprocess
import threading
import time
import uuid

from .models import ENGINE_VERSION, IntegrityError, RecoveryError, canonical


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix="GT") -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex}"


def reject_link(path: Path) -> None:
    if path.exists():
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise IntegrityError(f"Recovery storage must not use a link or reparse point: {path.name}")


def windows_identity() -> str:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value"],
        capture_output=True, text=True, timeout=15, check=True, creationflags=0x08000000,
    )
    identity = result.stdout.strip()
    if not identity.startswith("S-1-") or any(c not in "S-0123456789" for c in identity):
        raise IntegrityError("Could not establish recovery storage owner")
    return identity


def secure_directory(root: Path, identity: str) -> None:
    reject_link(root)
    root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        script = """
        $ErrorActionPreference='Stop';
        $acl=[System.Security.AccessControl.DirectorySecurity]::new();
        $owner=[System.Security.Principal.SecurityIdentifier]::new($env:GHOSTY_RECOVERY_OWNER);
        $acl.SetOwner($owner); $acl.SetAccessRuleProtection($true,$false);
        foreach ($sid in @($env:GHOSTY_RECOVERY_OWNER,'S-1-5-18')) {
          $identity=[System.Security.Principal.SecurityIdentifier]::new($sid);
          $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow');
          $acl.AddAccessRule($rule)
        };
        Set-Acl -LiteralPath $env:GHOSTY_RECOVERY_ROOT -AclObject $acl
        """
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "GHOSTY_RECOVERY_OWNER": identity, "GHOSTY_RECOVERY_ROOT": str(root)},
            capture_output=True, check=True, timeout=15, creationflags=0x08000000,
        )
    else:
        root.chmod(0o700)


def dpapi(data: bytes, decrypt=False) -> bytes:
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.windll.crypt32
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise IntegrityError("Windows could not protect/unlock the recovery integrity key")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class RecoveryStore:
    def __init__(self, root: Path, *, key: bytes | None = None, identity: str | None = None,
                 secure=True, minimum_free_bytes=16 * 1024 * 1024, open_existing=False):
        self.root = Path(root)
        self.identity = identity or (windows_identity() if os.name == "nt" else getpass.getuser())
        self.machine = hashlib.sha256(platform.node().casefold().encode()).hexdigest()
        self.minimum_free_bytes = minimum_free_bytes
        self._secure = secure
        self._injected_key = key is not None
        self._thread_lock = threading.RLock()
        if open_existing:
            if not self.root.is_dir() or any(not (self.root / name).exists() for name in
                    ("integrity.key", "journal.sqlite3", "control.json", "snapshots")):
                raise IntegrityError("Existing recovery storage is incomplete")
            reject_link(self.root)
        elif secure:
            secure_directory(self.root, self.identity)
        else:
            # Explicit dependency injection for isolated tests, never a UI preference.
            self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots = self.root / "snapshots"
        reject_link(self.snapshots)
        self.snapshots.mkdir(exist_ok=True)
        self.database = self.root / "journal.sqlite3"
        reject_link(self.database)
        existing_control = (self.root / "control.json").exists()
        if not self.database.exists() and (existing_control or (self.root / "journal-head.json").exists()):
            raise IntegrityError("Recovery journal is missing; existing evidence was preserved")
        existing_database = self.database.exists()
        self.key = key if key is not None else self._load_key()
        if len(self.key) != 32:
            raise IntegrityError("Invalid recovery integrity key")
        if not open_existing:
            with self.locked(), self.connection() as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                                   "payload TEXT NOT NULL, previous TEXT NOT NULL, signature TEXT NOT NULL)")
        if not (self.root / "control.json").exists():
            if existing_database:
                raise IntegrityError("Recovery control record is missing; Safe Mode cannot be silently reset")
            self.write_signed("control.json", {"safe_mode": False, "reason": "", "retention_days": 90,
                                              "restore_points": False, "monitor_seconds": 300,
                                              "watchdog_seconds": 60, "profiles": {}})

    def _load_key(self) -> bytes:
        path = self.root / "integrity.key"
        reject_link(path)
        if path.exists():
            data = path.read_bytes()
            return dpapi(data, decrypt=True) if os.name == "nt" else data
        if self.database.exists() or any(self.snapshots.iterdir()):
            raise IntegrityError("Recovery integrity key is missing; existing records were preserved")
        key = secrets.token_bytes(32)
        data = dpapi(key) if os.name == "nt" else key
        self._write(path, data, exclusive=True)
        return key

    @contextmanager
    def locked(self, timeout=30):
        with self._thread_lock:
            path = self.root / "engine.lock"
            reject_link(path)
            with path.open("a+b") as stream:
                if stream.tell() == 0:
                    stream.write(b"0")
                    stream.flush()
                deadline = time.monotonic() + timeout
                while True:
                    try:
                        stream.seek(0)
                        if os.name == "nt":
                            import msvcrt
                            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except (OSError, BlockingIOError):
                        if time.monotonic() >= deadline:
                            raise RecoveryError("Another recovery operation is active; try again when it finishes")
                        time.sleep(0.05)
                try:
                    yield
                finally:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream, fcntl.LOCK_UN)

    @contextmanager
    def connection(self):
        reject_link(self.database)
        connection = sqlite3.connect(self.database, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _write(path: Path, data: bytes, *, exclusive=False) -> None:
        reject_link(path)
        temporary = path if exclusive else path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        with temporary.open("xb") as stream:
            if os.name != "nt":
                os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if not exclusive:
            os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def sign(self, value) -> str:
        return hmac.new(self.key, canonical(value), hashlib.sha256).hexdigest()

    def envelope(self, payload) -> dict:
        return {"payload": payload, "sha256": hashlib.sha256(canonical(payload)).hexdigest(),
                "hmac_sha256": self.sign(payload)}

    def unwrap(self, record) -> dict:
        if not isinstance(record, dict) or set(record) != {"payload", "sha256", "hmac_sha256"}:
            raise IntegrityError("Invalid recovery envelope")
        expected = self.envelope(record["payload"])
        if not hmac.compare_digest(str(record["sha256"]), expected["sha256"]) or not hmac.compare_digest(
                str(record["hmac_sha256"]), expected["hmac_sha256"]):
            raise IntegrityError("Recovery record integrity/authentication failed")
        return record["payload"]

    def read_signed(self, filename: str) -> dict:
        path = self.root / filename
        if path.parent != self.root:
            raise IntegrityError("Invalid recovery record path")
        reject_link(path)
        try:
            return self.unwrap(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as error:
            raise IntegrityError(f"Cannot validate {filename}: {error}") from error

    def write_signed(self, filename: str, payload: dict) -> None:
        path = self.root / filename
        if path.parent != self.root:
            raise IntegrityError("Invalid recovery record path")
        self._write(path, canonical(self.envelope(payload)))

    def check_space(self) -> None:
        if shutil.disk_usage(self.root).free < self.minimum_free_bytes:
            raise RecoveryError("Insufficient space for durable recovery records; no changes were started")

    def verify_security(self) -> None:
        reject_link(self.root)
        reject_link(self.snapshots)
        if not self._injected_key:
            path = self.root / "integrity.key"
            reject_link(path)
            if not path.exists():
                raise IntegrityError("Recovery integrity key is missing")
            value = path.read_bytes()
            unlocked = dpapi(value, decrypt=True) if os.name == "nt" else value
            if not hmac.compare_digest(unlocked, self.key):
                raise IntegrityError("Recovery integrity key changed while the engine was running")
        if self._secure and os.name == "nt":
            paths = [self.root, self.snapshots, *[path for path in self.root.iterdir() if path.is_file()],
                     *self.snapshots.glob("*.json")]
            for path in paths:
                reject_link(path)
            script = """
            $ErrorActionPreference='Stop'; $p=ConvertFrom-Json $env:GHOSTY_RECOVERY_PERMISSIONS;
            foreach ($path in $p.paths) {
              $acl=Get-Acl -LiteralPath $path;
              foreach ($rule in $acl.Access) {
                $sid=$rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;
                if ($rule.AccessControlType -eq 'Allow' -and $sid -ne $p.owner -and $sid -ne 'S-1-5-18') {
                  throw 'Recovery files grant access outside the owner and SYSTEM'
                }
              }
            }
            """
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                env={**os.environ, "GHOSTY_RECOVERY_PERMISSIONS": json.dumps({"owner": self.identity,
                                                                           "paths": [str(path) for path in paths]})},
                capture_output=True, check=True, timeout=30, creationflags=0x08000000)
        elif self._secure and os.name != "nt":
            if self.root.stat().st_mode & 0o077:
                raise IntegrityError("Recovery directory permissions are too broad")

    def snapshot(self, payload: dict) -> str:
        self.check_space()
        name = f"recovery_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex}.json"
        self._write(self.snapshots / name, canonical(self.envelope(payload)), exclusive=True)
        self.load_snapshot(name)
        return name

    def load_snapshot(self, name: str) -> dict:
        if Path(name).name != name or not name.startswith("recovery_") or not name.endswith(".json"):
            raise IntegrityError("Invalid snapshot identifier")
        path = self.snapshots / name
        reject_link(path)
        try:
            value = self.unwrap(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as error:
            raise IntegrityError(f"Snapshot missing or damaged: {name}") from error
        required = {"schema", "transaction_id", "snapshot_id", "created", "app_version", "engine_version",
                    "machine", "user", "windows_version", "operations", "boot_id"}
        if not isinstance(value, dict) or set(value) != required or value["schema"] != 1:
            raise IntegrityError("Unsupported recovery snapshot schema")
        if value["engine_version"] != ENGINE_VERSION or value["machine"] != self.machine or value["user"] != self.identity:
            raise IntegrityError("Recovery snapshot belongs to another machine/user or engine version")
        if not isinstance(value["operations"], list) or not value["operations"]:
            raise IntegrityError("Snapshot has no valid operations")
        return value

    def append(self, record: dict) -> None:
        # The caller owns locked() across the whole read/modify/write sequence.
        payload = canonical(record).decode("utf-8")
        if shutil.disk_usage(self.root).free < len(payload.encode("utf-8")) * 4 + 65536:
            raise RecoveryError("Recovery journal cannot be flushed: insufficient disk space")
        with self.connection() as connection:
            row = connection.execute("SELECT signature FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
            previous = row[0] if row else ""
            signature = self.sign({"previous": previous, "payload": payload})
            cursor = connection.execute("INSERT INTO events(payload, previous, signature) VALUES(?,?,?)",
                                        (payload, previous, signature))
            sequence = cursor.lastrowid
        self.write_signed("journal-head.json", {"sequence": sequence, "signature": signature})

    def records(self) -> dict:
        latest = {}
        previous = ""
        sequence = 0
        try:
            with self.connection() as connection:
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise IntegrityError("Recovery journal database is corrupt")
                for sequence, payload, prior, signature in connection.execute("SELECT * FROM events ORDER BY sequence"):
                    if prior != previous or not hmac.compare_digest(signature, self.sign({"previous": prior, "payload": payload})):
                        raise IntegrityError("Recovery journal has been modified")
                    record = json.loads(payload)
                    if record.get("schema") != 1 or not isinstance(record.get("transaction_id"), str):
                        raise IntegrityError("Unsupported recovery journal schema")
                    latest[record["transaction_id"]] = record
                    previous = signature
            anchor = self.root / "journal-head.json"
            if sequence or anchor.exists():
                if self.read_signed(anchor.name) != {"sequence": sequence, "signature": previous}:
                    raise IntegrityError("Recovery journal has an incomplete or missing durable commit")
            return latest
        except (sqlite3.Error, ValueError, TypeError) as error:
            raise IntegrityError(f"Recovery journal cannot be validated: {error}") from error
