"""Independent local recovery process, authenticated by the journal and ticket."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .models import RecoveryError


class ConnectivityWatchdog:
    def __init__(self, store, launcher=subprocess.Popen):
        self.store = store
        self.launcher = launcher

    def arm(self, transaction_id: str, seconds: int) -> None:
        if not re.fullmatch(r"GT-\d{8}-\d{6}-[a-f0-9]{32}", transaction_id):
            raise RecoveryError("Invalid watchdog transaction identity")
        if not 10 <= seconds <= 600:
            raise RecoveryError("Connectivity confirmation must be between 10 and 600 seconds")
        now = datetime.now(timezone.utc)
        self.store.write_signed(f"watchdog-{transaction_id}.json", {
            "transaction_id": transaction_id, "created": now.isoformat(),
            "deadline": (now + timedelta(seconds=max(60, seconds))).isoformat(), "seconds": seconds,
            "phase": "Armed", "ready": False,
        })
        from src.core.update_handoff import clean_restart_environment
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--ghosty-recovery-watchdog", transaction_id]
        else:
            command = [sys.executable, str(Path(__file__).resolve().parents[3] / "main.py"),
                       "--ghosty-recovery-watchdog", transaction_id]
        environment = clean_restart_environment(os.environ, getattr(sys, "_MEIPASS", None))
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        process = self.launcher(command, env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                close_fds=True, creationflags=0x08000000 if os.name == "nt" else 0)
        if process.poll() is not None:
            raise RecoveryError("Connectivity watchdog did not remain running; no network changes started")
        until = time.monotonic() + 20
        while time.monotonic() < until:
            if process.poll() is not None:
                raise RecoveryError("Connectivity watchdog exited before accepting the recovery ticket")
            if self.store.read_signed(f"watchdog-{transaction_id}.json").get("ready"):
                return
            time.sleep(0.1)
        raise RecoveryError("Connectivity watchdog did not acknowledge readiness; network changes were not started")

    def expired(self, transaction_id):
        ticket = self.store.read_signed(f"watchdog-{transaction_id}.json")
        return datetime.now(timezone.utc) >= datetime.fromisoformat(ticket["deadline"])

    def applied(self, transaction_id):
        name = f"watchdog-{transaction_id}.json"
        ticket = self.store.read_signed(name)
        ticket.update(phase="Applied", deadline=(datetime.now(timezone.utc) + timedelta(seconds=ticket["seconds"])).isoformat())
        self.store.write_signed(name, ticket)

    def disarm(self, transaction_id):
        name = f"watchdog-{transaction_id}.json"
        ticket = self.store.read_signed(name)
        ticket["phase"] = "Disarmed"
        self.store.write_signed(name, ticket)


def main(transaction_id: str) -> int:
    if not re.fullmatch(r"GT-\d{8}-\d{6}-[a-f0-9]{32}", transaction_id):
        return 1
    from src.utils.helpers import get_config_dir, is_admin
    from .engine import SecurityRecoveryEngine
    from .store import RecoveryStore
    from .windows import handlers
    engine = None
    try:
        store = RecoveryStore(Path(get_config_dir()) / "Security" / "Recovery", open_existing=True)
        name = f"watchdog-{transaction_id}.json"
        ticket = store.read_signed(name)
        if ticket["transaction_id"] != transaction_id or not 10 <= ticket["seconds"] <= 600:
            raise RecoveryError("Invalid watchdog authorization")
        ticket["ready"] = True
        store.write_signed(name, ticket)
        # A separate protected ticket can be read while the main process owns the
        # resource lock. State restoration still waits for exclusive ownership.
        maximum = time.monotonic() + 2 * max(60, ticket["seconds"]) + 30
        while time.monotonic() < maximum:
            ticket = store.read_signed(name)
            if ticket["phase"] == "Disarmed":
                return 0
            if datetime.now(timezone.utc) >= datetime.fromisoformat(ticket["deadline"]):
                break
            time.sleep(0.25)
        engine = SecurityRecoveryEngine(store, handlers(), is_admin=is_admin)
        with engine.store.locked():
            engine.store.verify_security()
            record, snapshot = engine._record(transaction_id)
            if record.get("connectivity_confirmed") or record["status"] in {"Prepared", "Cancelled", "Recovered"}:
                return 0
            result = engine._rollback_locked(record, snapshot, automatic=True)
            return 0 if result.status == "Recovered" else 2
    except Exception as error:
        try:
            if engine is not None:
                engine.enter_safe_mode(f"Connectivity watchdog could not validate/recover {transaction_id}: {error}")
        except Exception:
            pass
        return 1
