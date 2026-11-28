"""One authority for preparation, execution, conflict detection and recovery."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import platform
import threading
import psutil

from .models import (Capability, ConflictError, ENGINE_VERSION, Handler, IntegrityError,
                     Operation, RecoveryError, Result, Risk, STATES, UNRESOLVED, digest, unresolved, _mutation_scope)
from .store import RecoveryStore, identifier, timestamp


class SecurityRecoveryEngine:
    def __init__(self, store: RecoveryStore, handlers: dict[str, Handler], *, app_version="unknown",
                 is_admin=lambda: False, approve=None, watchdog=None, restore_point=None,
                 boot_id=lambda: int(psutil.boot_time())):
        self.store = store
        self.handlers = dict(handlers)
        self.app_version = app_version
        self.is_admin = is_admin
        self.approve = approve
        self.watchdog = watchdog
        self.restore_point = restore_point
        self.boot_id = boot_id
        self.cancelled = set()
        self._cancel_lock = threading.Lock()
        self._monitor_position = 0
        self.last_health = {"status": "Warning", "issues": ["Recovery health has not been checked"]}

    def _handler(self, name: str) -> Handler:
        if name not in self.handlers:
            raise RecoveryError(f"Recovery handler is unavailable: {name}")
        return self.handlers[name]

    def _health_locked(self) -> dict:
        issues = []
        try:
            self.store.verify_security()
            control = self.store.read_signed("control.json")
            records = self.store.records()
            for record in records.values():
                if record["status"] in UNRESOLVED or not record.get("deleted"):
                    snapshot = self.store.load_snapshot(record["snapshot"])
                    for op in snapshot["operations"]:
                        self._handler(op["handler"]).validate(op["target"], op["desired"])
            self.store.check_space()
            if control.get("safe_mode"):
                issues.append("Recovery Safe Mode: " + control.get("reason", "Manual inspection required"))
            if not self.handlers:
                issues.append("No recovery handlers are registered")
            status = "Fault" if issues else "Healthy"
            if not issues and any(unresolved(record) for record in records.values()):
                status = "Warning"
                issues.append("Unfinished transactions are protected; review Recovery Centre")
        except Exception as error:
            issues.append(str(error))
            status = "Fault"
            try:
                self._safe_mode_locked(str(error))
            except Exception:
                pass
        self.last_health = {"status": status, "issues": issues, "checked": timestamp()}
        return deepcopy(self.last_health)

    def health(self) -> dict:
        try:
            with self.store.locked():
                return self._health_locked()
        except Exception as error:
            self.last_health = {"status": "Fault", "issues": [str(error)], "checked": timestamp()}
            return deepcopy(self.last_health)

    def _require_healthy(self) -> None:
        health = self._health_locked()
        if health["status"] == "Fault":
            raise RecoveryError("Recovery infrastructure is unavailable: " + "; ".join(health["issues"]))

    def settings(self) -> dict:
        with self.store.locked():
            return self.store.read_signed("control.json")

    def configure(self, **changes) -> None:
        allowed = {"retention_days", "restore_points", "monitor_seconds", "watchdog_seconds"}
        if set(changes) - allowed:
            raise RecoveryError("Unsupported recovery setting")
        for key, value in changes.items():
            if key == "restore_points":
                if not isinstance(value, bool):
                    raise RecoveryError("Restore point preference must be true or false")
            elif not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 36500:
                raise RecoveryError("Recovery intervals must be positive bounded integers")
            if key == "watchdog_seconds" and not 10 <= value <= 600:
                raise RecoveryError("Connectivity confirmation must be between 10 and 600 seconds")
        with self.store.locked():
            control = self.store.read_signed("control.json")
            control.update(changes)
            self.store.write_signed("control.json", control)

    def enter_safe_mode(self, reason: str) -> None:
        with self.store.locked():
            self._safe_mode_locked(reason)

    def _safe_mode_locked(self, reason: str) -> None:
        control = self.store.read_signed("control.json")
        control.update(safe_mode=True, reason=reason, activated=timestamp())
        self.store.write_signed("control.json", control)

    def leave_safe_mode(self, *, confirmed=False) -> dict:
        if not confirmed:
            raise RecoveryError("Explicit confirmation is required to leave Recovery Safe Mode")
        with self.store.locked():
            control = self.store.read_signed("control.json")
            records = self.store.records()
            for record in records.values():
                if record.get("deleted"):
                    continue
                self.store.load_snapshot(record["snapshot"])
                if unresolved(record):
                    raise RecoveryError("Resolve or verify unfinished transactions before leaving Safe Mode")
            self.store.check_space()
            control.update(safe_mode=False, reason="")
            self.store.write_signed("control.json", control)
            health = self._health_locked()
            if health["status"] == "Fault":
                self._safe_mode_locked("Health checks still fail")
                raise RecoveryError("Recovery health checks still fail")
            return health

    def _record(self, transaction_id: str) -> tuple[dict, dict]:
        record = self.store.records().get(transaction_id)
        if not isinstance(record, dict) or record.get("deleted"):
            raise RecoveryError("Recovery record not found")
        snapshot = self.store.load_snapshot(record["snapshot"])
        if snapshot["transaction_id"] != transaction_id or record["plan_digest"] != digest(snapshot):
            raise IntegrityError("Recovery journal and snapshot do not describe the same transaction")
        if record["status"] not in STATES:
            raise IntegrityError("Invalid recovery transaction state")
        for op in snapshot["operations"]:
            self._handler(op["handler"]).validate(op["target"], op["desired"])
        return record, snapshot

    def _save(self, record: dict, event: str) -> None:
        record["updated"] = timestamp()
        record["event"] = event
        self.store.append(record)

    @staticmethod
    def _order(operations: list[dict]) -> list[int]:
        result, active, done = [], set(), set()

        def visit(index):
            if not isinstance(index, int) or index < 0 or index >= len(operations):
                raise RecoveryError("Invalid operation dependency")
            if index in active:
                raise RecoveryError("Cyclic recovery dependencies")
            if index in done:
                return
            active.add(index)
            for dependency in operations[index]["dependencies"]:
                visit(dependency)
            active.remove(index)
            done.add(index)
            result.append(index)

        for position in range(len(operations)):
            visit(position)
        return result

    def prepare(self, label: str, operations: list[Operation], *, profile="") -> dict:
        if not operations or len(operations) > 500:
            raise RecoveryError("A transaction must contain between 1 and 500 operations")
        with self.store.locked():
            self._require_healthy()
            plan = []
            resources = set()
            for operation in operations:
                data = operation.data()
                handler = self._handler(operation.handler)
                handler.validate(data["target"], data["desired"])
                risk, capability, admin = handler.classify(data["target"], data["desired"])
                if admin and not self.is_admin():
                    raise RecoveryError("Administrator access is required. Use Elevate, then retry the operation.")
                resource = digest({"handler": handler.resource_group or operation.handler,
                                   "target": handler.resource_identity(operation.target)})
                if resource in resources:
                    raise RecoveryError("Duplicate resource in one transaction; combine its proposed changes")
                resources.add(resource)
                original = handler.capture(data["target"])
                data.update(id=identifier("OP"), original=original, risk=risk.value,
                            capability=capability.value, admin=admin, resource=resource,
                            connectivity=handler.connectivity, reboot_required=handler.requires_reboot(data["target"]))
                plan.append(data)
            # Do not let later operations silently overlap unresolved transactions.
            for record in self.store.records().values():
                if unresolved(record):
                    snapshot = self.store.load_snapshot(record["snapshot"])
                    if resources.intersection(op["resource"] for op in snapshot["operations"]):
                        raise RecoveryError("This resource belongs to an unfinished transaction; review it in Recovery Centre")
            service_indexes = {op["target"]["name"].casefold(): index for index, op in enumerate(plan)
                               if op["handler"] == "service.config.v1"}
            for index, op in enumerate(plan):
                if op["handler"] != "service.config.v1":
                    continue
                for dependency in op["original"].get("dependencies", []):
                    parent = service_indexes.get(dependency.casefold())
                    if parent is None:
                        continue
                    destination, required = (parent, index) if op["desired"].get("running") is False else (index, parent)
                    if required not in plan[destination]["dependencies"]:
                        plan[destination]["dependencies"].append(required)
            order = self._order(plan)
            transaction_id = identifier()
            snapshot = {"schema": 1, "transaction_id": transaction_id, "snapshot_id": identifier("SNAP"),
                        "created": timestamp(), "app_version": self.app_version,
                        "engine_version": ENGINE_VERSION, "machine": self.store.machine,
                        "user": self.store.identity, "windows_version": platform.platform(), "operations": plan,
                        "boot_id": self.boot_id()}
            name = self.store.snapshot(snapshot)
            record = {"schema": 1, "transaction_id": transaction_id, "snapshot": name,
                      "plan_digest": digest(snapshot), "created": snapshot["created"], "label": label,
                      "profile": profile, "status": "Prepared", "order": order,
                      "risk": max((op["risk"] for op in plan), key=lambda risk: [r.value for r in Risk].index(risk)),
                      "operations": [{"id": op["id"], "state": "Prepared", "verification": None, "error": ""}
                                     for op in plan], "attempts": [], "error": "", "deleted": False}
            self._save(record, "Snapshot validated; transaction prepared")
            return {"transaction_id": transaction_id, "plan_digest": record["plan_digest"], "label": label,
                    "risk": record["risk"], "operations": plan, "snapshot": "Ready"}

    def run(self, label: str, operations: list[Operation], *, profile="") -> Result:
        preview = self.prepare(label, operations, profile=profile)
        approved = self.approve(preview) if self.approve else False
        if not approved:
            self.cancel(preview["transaction_id"])
            return Result(preview["transaction_id"], "Cancelled", "Operation cancelled before making changes")
        result = self.execute(preview["transaction_id"], preview["plan_digest"], confirmed=True)
        if result.status == "Completed" and any(op["connectivity"] for op in preview["operations"]):
            if self.approve and self.approve({"type": "connectivity", "transaction_id": result.transaction_id,
                                              "seconds": self.settings()["watchdog_seconds"]}):
                self.confirm_connectivity(result.transaction_id)
            else:
                result = self.rollback(result.transaction_id, confirmed=True)
                result.operation_failed = True
        return result

    def cancel(self, transaction_id: str) -> None:
        with self._cancel_lock:
            self.cancelled.add(transaction_id)
        # A running command is allowed to reach a known result before recovery.
        try:
            with self.store.locked(timeout=0.1):
                record, _ = self._record(transaction_id)
                if record["status"] == "Prepared":
                    record["status"] = "Cancelled"
                    self._save(record, "Cancelled before execution")
        except RecoveryError:
            pass

    def execute(self, transaction_id: str, plan_digest: str, *, confirmed=False) -> Result:
        if not confirmed:
            raise RecoveryError("Operation preview must be approved before execution")
        with self.store.locked():
            self._require_healthy()
            record, snapshot = self._record(transaction_id)
            if record["status"] != "Prepared" or plan_digest != record["plan_digest"]:
                raise RecoveryError("The prepared operation changed or has already started; review a new preview")
            operations = snapshot["operations"]
            for op in operations:
                handler = self._handler(op["handler"])
                if op["admin"] and not self.is_admin():
                    raise RecoveryError("Administrator permission is unavailable; no changes were started")
                if handler.compare_state(handler.capture(op["target"])) != handler.compare_state(op["original"]):
                    record["status"] = "Cancelled"
                    self._save(record, "Configuration changed after preview; no changes started")
                    raise ConflictError("Configuration changed after preparation. Review a new operation preview.")
            control = self.store.read_signed("control.json")
            if record["risk"] == Risk.HIGH.value and control["restore_points"]:
                try:
                    if self.restore_point is None:
                        raise RecoveryError("Windows System Restore is unavailable")
                    self._save(record, "Optional Windows restore point requested")
                    with _mutation_scope():
                        self.restore_point()
                except Exception as error:
                    if not self.approve or not self.approve({"type": "restore_point_failed", "error": str(error)}):
                        record["status"] = "Cancelled"
                        self._save(record, "Restore point failed; cancelled by user")
                        return Result(transaction_id, "Cancelled", "System restore point could not be created")
            network = any(op["connectivity"] for op in operations)
            if network:
                if self.watchdog is None:
                    raise RecoveryError("Connectivity watchdog is unavailable; network changes were not started")
                self.watchdog.arm(transaction_id, control["watchdog_seconds"])
                record["connectivity_confirmed"] = False
            record["status"] = "Running"
            self._save(record, "Transaction started")
            try:
                for index in record["order"]:
                    if network and hasattr(self.watchdog, "expired") and self.watchdog.expired(transaction_id):
                        raise RecoveryError("Connectivity safety deadline expired during execution")
                    with self._cancel_lock:
                        if transaction_id in self.cancelled:
                            raise RecoveryError("Cancellation requested; recovering completed or partial changes")
                    op, progress = operations[index], record["operations"][index]
                    handler = self._handler(op["handler"])
                    progress["state"] = "Applying"
                    self._save(record, f"Intent persisted before applying operation {index + 1}")
                    with _mutation_scope():
                        handler.apply(op["target"], op["desired"])
                    actual = handler.capture(op["target"])
                    progress["after"] = actual
                    progress["verification"] = handler.verify(actual, op["desired"])
                    if handler.pending_reboot(actual, op["desired"]) or op["reboot_required"]:
                        progress["state"] = "Pending Reboot"
                        self._save(record, f"Operation {index + 1} requires post-reboot verification")
                        continue
                    if not progress["verification"]:
                        raise RecoveryError(f"Result could not be verified: {op['description'] or op['handler']}")
                    progress["state"] = "Completed"
                    self._save(record, f"Operation {index + 1} independently verified")
                if any(op["state"] == "Pending Reboot" for op in record["operations"]):
                    record["status"] = "Pending Reboot"
                    self._save(record, "Expected post-reboot state preserved; completion is unverified")
                    return Result(transaction_id, "Pending Reboot", "Windows requires a restart. Verify this transaction after reboot.")
                record["status"] = "Completed"
                self._save(record, "All required operation properties verified")
                if network and hasattr(self.watchdog, "applied"):
                    if self.watchdog.expired(transaction_id):
                        raise RecoveryError("Connectivity safety deadline expired before completion")
                    self.watchdog.applied(transaction_id)
                return Result(transaction_id, "Completed", "Changes applied and verified" +
                              (". Confirm connectivity in Recovery Centre." if network else ""), record["operations"])
            except Exception as error:
                record["error"] = str(error)
                for progress in record["operations"]:
                    if progress["state"] == "Applying":
                        progress["error"] = str(error)
                self._save(record, "Execution interrupted; partial changes require inspection")
                return self._rollback_locked(record, snapshot, automatic=True)

    def assessment(self, transaction_id: str) -> dict:
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            results = []
            for op, progress in zip(snapshot["operations"], record["operations"]):
                handler = self._handler(op["handler"])
                row = {"operation": op["description"] or op["handler"], "target": op["target"],
                       "original": op["original"], "capability": op["capability"], "error": ""}
                try:
                    current = handler.capture(op["target"])
                    row["current"] = current
                    row["already_restored"] = handler.compare_state(current) == handler.compare_state(op["original"])
                    expected = progress.get("after")
                    row["conflict"] = not row["already_restored"] and (expected is None or
                        handler.compare_state(current) != handler.compare_state(expected))
                    row["permissions"] = not op["admin"] or self.is_admin()
                    row["ready"] = row["permissions"] and not row["conflict"] and op["capability"] == Capability.FULL.value
                except Exception as error:
                    row.update(ready=False, conflict=False, error=str(error))
                results.append(row)
            return {"transaction_id": transaction_id, "snapshot_integrity": "Valid", "status": record["status"],
                    "ready": all(row["ready"] for row in results), "operations": results,
                    "notice": "Assessment does not guarantee a subsequent recovery will succeed."}

    def rollback(self, transaction_id: str, *, confirmed=False, force=False) -> Result:
        if not confirmed:
            raise RecoveryError("Explicit confirmation is required before restoration")
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            if record["status"] in {"Prepared", "Cancelled", "Recovered"}:
                raise RecoveryError("This transaction has no outstanding executed changes")
            # Manual recovery remains available in Safe Mode; automatic loops do not.
            return self._rollback_locked(record, snapshot, automatic=False, force=force)

    def _rollback_locked(self, record: dict, snapshot: dict, *, automatic: bool, force=False) -> Result:
        control = self.store.read_signed("control.json")
        if automatic and control.get("safe_mode"):
            record["status"] = "Recovery Required"
            self._save(record, "Automatic recovery disabled by Recovery Safe Mode")
            return Result(record["transaction_id"], record["status"], "Review this transaction in Recovery Centre")
        if any(op["admin"] for op in snapshot["operations"]) and not self.is_admin():
            record["status"] = "Recovery Required"
            self._save(record, "Administrator permission unavailable; recovery not started")
            return Result(record["transaction_id"], record["status"], "Use Elevate to attempt recovery")
        attempt: dict = {"id": identifier("ROLLBACK"), "created": timestamp(), "automatic": automatic,
                   "force_conflicts": force, "operations": []}
        record["attempts"].append(attempt)
        record["status"] = "Rolling Back"
        self._save(record, "Recovery intent persisted")
        for index in reversed(record["order"]):
            op, progress = snapshot["operations"][index], record["operations"][index]
            if progress["state"] == "Prepared":
                continue
            handler = self._handler(op["handler"])
            outcome = {"id": op["id"], "verified": False, "error": ""}
            attempt["operations"].append(outcome)
            try:
                current = handler.capture(op["target"])
                if handler.compare_state(current) == handler.compare_state(op["original"]):
                    outcome["verified"] = True
                else:
                    if op["capability"] in {Capability.NONE.value, Capability.MANUAL.value}:
                        raise RecoveryError("Manual recovery required; this operation has no automatic restoration handler")
                    expected = progress.get("after")
                    # A crash inside apply has no confirmed 'after'. Only the declared
                    # expected properties can establish that this is our own change.
                    owned = (handler.compare_state(current) == handler.compare_state(expected)
                             if expected is not None else handler.owns_partial(current, op["original"], op["desired"]))
                    if not owned and not force:
                        raise ConflictError("External or unverified configuration changes detected; review differences before forcing restoration")
                    outcome["state"] = "Restoring"
                    self._save(record, f"Recovery intent persisted for operation {index + 1}")
                    with _mutation_scope():
                        handler.restore(op["target"], op["original"])
                    restored = handler.capture(op["target"])
                    outcome["actual"] = restored
                    outcome["verified"] = handler.compare_state(restored) == handler.compare_state(op["original"])
                    if not outcome["verified"] or op["capability"] == Capability.PARTIAL.value:
                        raise RecoveryError("Only partial recovery could be verified; manual recovery may still be required")
                progress["state"] = "Recovered"
            except Exception as error:
                outcome["verified"] = False
                outcome["error"] = str(error)
            self._save(record, f"Recovery verification recorded for operation {index + 1}")
        complete = all(row["verified"] for row in attempt["operations"])
        record["status"] = "Recovered" if complete else "Partial Recovery"
        if complete:
            record.pop("connectivity_confirmed", None)
        self._save(record, "Recovery verification completed")
        if complete and any(op["connectivity"] for op in snapshot["operations"]) and hasattr(self.watchdog, "disarm"):
            self.watchdog.disarm(record["transaction_id"])
        failures = sum(not all(row["verified"] for row in old["operations"]) for old in record["attempts"])
        if failures >= 2:
            self._safe_mode_locked("Repeated incomplete recovery attempts; inspect unresolved resources")
        message = "Rollback Successful" if complete else "Partial Rollback Completed; review resources that require attention"
        if record["error"]:
            message += ". Original operation: " + record["error"]
        return Result(record["transaction_id"], record["status"], message, attempt["operations"],
                      operation_failed=automatic)

    def transactions(self, *, include_deleted=False) -> list[dict]:
        with self.store.locked():
            return sorted((record for record in self.store.records().values()
                           if include_deleted or not record.get("deleted")), key=lambda record: record["created"], reverse=True)

    def details(self, transaction_id: str) -> dict:
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            return {"transaction": record, "snapshot": snapshot}

    def interrupted(self) -> list[dict]:
        return [record for record in self.transactions() if unresolved(record)]

    def verify_current(self, transaction_id: str) -> dict:
        assessment = self.assessment(transaction_id)
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            if all(row.get("already_restored") for row in assessment["operations"]):
                record["status"] = "Recovered" if any(op["state"] != "Prepared" for op in record["operations"]) else "Cancelled"
                record.pop("connectivity_confirmed", None)
            elif record["status"] == "Pending Reboot" and snapshot["boot_id"] != self.boot_id() and all(
                    self._handler(op["handler"]).verify(row.get("current", {}), op["desired"])
                    for op, row in zip(snapshot["operations"], assessment["operations"])):
                record["status"] = "Completed"
                for progress in record["operations"]:
                    progress.update(state="Completed", verification=True)
            elif record["status"] in {"Prepared", "Running", "Rolling Back"}:
                record["status"] = "Recovery Required"
            record["last_assessment"] = assessment
            self._save(record, "Current Windows state independently inspected")
        return assessment

    def mark_pending_reboot(self, transaction_id: str) -> None:
        with self.store.locked():
            record, _ = self._record(transaction_id)
            if record["status"] not in {"Completed", "Running"}:
                raise RecoveryError("This transaction cannot wait for reboot")
            record["status"] = "Pending Reboot"
            self._save(record, "Expected post-reboot state preserved")

    def confirm_connectivity(self, transaction_id: str) -> None:
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            if record["status"] != "Completed" or not any(op["connectivity"] for op in snapshot["operations"]):
                raise RecoveryError("No completed network change is awaiting confirmation")
            record["connectivity_confirmed"] = True
            self._save(record, "Connectivity explicitly confirmed by user; configuration verification is separate")
            if hasattr(self.watchdog, "disarm"):
                self.watchdog.disarm(transaction_id)

    def export_record(self, transaction_id: str, destination: Path, *, confirmed_sensitive=False) -> None:
        if not confirmed_sensitive:
            raise RecoveryError("Confirm that this export may contain sensitive system configuration")
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            payload = {"schema": 1, "transaction": record, "snapshot": snapshot}
            # Exports are evidence; they cannot register handlers or execute commands.
            self.store._write(Path(destination), canonical_export(self.store.envelope(payload)), exclusive=True)

    def validate_export(self, path: Path) -> dict:
        if path.stat().st_size > 32 * 1024 * 1024:
            raise IntegrityError("Recovery export exceeds the supported size")
        payload = self.store.unwrap(json.loads(path.read_text(encoding="utf-8")))
        if set(payload) != {"schema", "transaction", "snapshot"} or payload["schema"] != 1:
            raise IntegrityError("Unsupported recovery export")
        snapshot = payload["snapshot"]
        if snapshot["machine"] != self.store.machine or snapshot["user"] != self.store.identity:
            raise IntegrityError("Recovery export belongs to another machine/user")
        for op in snapshot["operations"]:
            self._handler(op["handler"]).validate(op["target"], op["desired"])
        return payload

    def delete_record(self, transaction_id: str, *, confirmed=False) -> None:
        if not confirmed:
            raise RecoveryError("Confirm deletion of the recovery record")
        with self.store.locked():
            record, _ = self._record(transaction_id)
            if unresolved(record):
                raise RecoveryError("Unfinished or unresolved recovery records cannot be deleted")
            record["deleted"] = True
            self._save(record, "Resolved recovery record deleted by explicit user request; audit evidence retained")
            (self.store.snapshots / record["snapshot"]).unlink()

    def retention_candidates(self) -> list[str]:
        limit = datetime.now(timezone.utc) - timedelta(days=self.settings()["retention_days"])
        return [record["transaction_id"] for record in self.transactions()
                if not unresolved(record) and datetime.fromisoformat(record["created"]) < limit]

    def save_profile(self, name: str, transaction_ids: list[str]) -> None:
        if not name.strip() or len(name) > 100:
            raise RecoveryError("Choose a profile name of 1–100 characters")
        with self.store.locked():
            for transaction_id in transaction_ids:
                self._record(transaction_id)
            control = self.store.read_signed("control.json")
            control["profiles"][name] = list(dict.fromkeys(transaction_ids))
            self.store.write_signed("control.json", control)

    def acknowledge_manual_recovery(self, transaction_id: str, note: str, *, confirmed=False) -> Result:
        if not confirmed or not note.strip() or len(note) > 2000:
            raise RecoveryError("Explicit confirmation and a manual recovery note are required")
        with self.store.locked():
            record, snapshot = self._record(transaction_id)
            if record["status"] not in {"Partial Recovery", "Recovery Required", "Completed"}:
                raise RecoveryError("This transaction is not awaiting manual recovery review")
            manual = False
            for op, progress in zip(snapshot["operations"], record["operations"]):
                if op["capability"] != Capability.FULL.value:
                    manual = True
                elif progress["state"] not in {"Prepared", "Recovered"}:
                    handler = self._handler(op["handler"])
                    if handler.compare_state(handler.capture(op["target"])) != handler.compare_state(op["original"]):
                        raise RecoveryError("Automatically recoverable resources must be restored and verified first")
                    progress["state"] = "Recovered"
            if not manual:
                raise RecoveryError("Use state verification or rollback for this fully supported transaction")
            record.update(status="Manual Recovery Acknowledged", manual_resolution={
                "note": note, "user": self.store.identity, "created": timestamp(),
                "verification": "User acknowledgement only; complete restoration was not independently verified"})
            record.pop("connectivity_confirmed", None)
            self._save(record, "Manual recovery acknowledged without claiming verified restoration")
            return Result(transaction_id, record["status"], "Manual recovery acknowledgement recorded; restoration is not marked verified")

    def profile_details(self, name: str) -> dict:
        profiles = self.settings()["profiles"]
        if name not in profiles:
            raise RecoveryError("Recovery profile not found")
        return {"name": name, "records": [self.details(transaction_id) for transaction_id in profiles[name]]}

    def export_profile(self, name: str, destination: Path, *, confirmed_sensitive=False) -> None:
        if not confirmed_sensitive:
            raise RecoveryError("Confirm that this profile contains sensitive recovery configuration")
        payload = self.profile_details(name)
        self.store._write(Path(destination), canonical_export(self.store.envelope(payload)), exclusive=True)

    def monitor(self) -> list[dict]:
        """Read and report drift; never automatically reapply an earlier setting."""
        reports = []
        with self.store.locked():
            candidates = []
            for record in self.store.records().values():
                if record["status"] == "Completed" and not record.get("deleted") and not unresolved(record):
                    snapshot = self.store.load_snapshot(record["snapshot"])
                    candidates.extend((record, op, progress) for op, progress in zip(snapshot["operations"], record["operations"]))
            if not candidates:
                return []
            # At most two resource reads per pass; continue from the last position.
            for step in range(min(2, len(candidates))):
                record, op, progress = candidates[(self._monitor_position + step) % len(candidates)]
                try:
                    handler = self._handler(op["handler"])
                    current = handler.capture(op["target"])
                    expected = progress.get("after", op["desired"])
                    if handler.compare_state(current) != handler.compare_state(expected):
                        report = {"operation_id": op["id"], "original": op["original"],
                                  "last_ghosty_state": expected, "current": current, "created": timestamp()}
                        previous = record.get("last_monitor", {}).get(op["id"], {})
                        if previous.get("current") != current:
                            record.setdefault("last_monitor", {})[op["id"]] = report
                            self._save(record, "External configuration difference detected; no settings reapplied")
                            reports.append({"transaction_id": record["transaction_id"], **report})
                except Exception as error:
                    reports.append({"transaction_id": record["transaction_id"], "error": str(error)})
            self._monitor_position = (self._monitor_position + min(2, len(candidates))) % len(candidates)
        return reports


def canonical_export(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
