"""Recovery fault injection uses simulated resources, never live Windows settings."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.core.recovery.engine import SecurityRecoveryEngine
from src.core.recovery.models import Capability, ConflictError, Handler, IntegrityError, Operation, RecoveryError, Risk
from src.core.recovery.store import RecoveryStore


class MemoryHandler(Handler):
    requires_admin = False

    def __init__(self):
        self.values = {"a": 1, "b": 2, "c": 3}
        self.calls = []
        self.fail_apply = ""
        self.fail_restore = False

    def validate(self, target, desired):
        if set(target) != {"name"} or target["name"] not in self.values or set(desired) != {"value"}:
            raise RecoveryError("Unapproved target or request")

    def capture(self, target):
        return {"value": self.values[target["name"]]}

    def apply(self, target, desired):
        self.calls.append(("apply", target["name"]))
        self.values[target["name"]] = desired["value"]
        if self.fail_apply == target["name"]:
            raise RuntimeError("Injected crash after a partial operation")

    def restore(self, target, original):
        self.calls.append(("restore", target["name"]))
        if not self.fail_restore:
            self.values[target["name"]] = original["value"]


class RecoveryEngineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "Recovery"
        self.key = b"f" * 32
        self.store = RecoveryStore(self.root, key=self.key, identity="fixture-user", secure=False)
        self.handler = MemoryHandler()
        self.boot = [1]
        self.engine = self.reopen()

    def reopen(self):
        return SecurityRecoveryEngine(self.store, {"fixture.v1": self.handler}, app_version="v99.0.0",
                                      is_admin=lambda: True, approve=lambda preview: True, boot_id=lambda: self.boot[0])

    @staticmethod
    def operation(name="a", value=9, dependencies=()):
        return Operation("fixture.v1", {"name": name}, {"value": value}, "Change " + name, dependencies)

    def test_prepare_persists_authenticated_snapshot_before_any_modification(self):
        preview = self.engine.prepare("One change", [self.operation()])
        self.assertEqual(self.handler.calls, [])
        detail = self.engine.details(preview["transaction_id"])
        self.assertEqual(detail["snapshot"]["operations"][0]["original"], {"value": 1})
        self.assertEqual(detail["transaction"]["status"], "Prepared")
        self.assertEqual(self.engine.health()["status"], "Warning")

    def test_verified_rollback_restores_actual_prior_value_and_keeps_snapshot_immutable(self):
        result = self.engine.run("One change", [self.operation()])
        snapshot = self.root / "snapshots" / self.engine.details(result.transaction_id)["transaction"]["snapshot"]
        original_bytes = snapshot.read_bytes()
        self.assertTrue(result.success)
        self.assertEqual(self.handler.values["a"], 9)
        restored = self.engine.rollback(result.transaction_id, confirmed=True)
        self.assertTrue(restored.success)
        self.assertEqual(self.handler.values["a"], 1)
        self.assertEqual(snapshot.read_bytes(), original_bytes)
        self.assertEqual(len(self.engine.details(result.transaction_id)["transaction"]["attempts"]), 1)

    def test_failed_bulk_operation_includes_partial_step_and_recovers_in_reverse_order(self):
        self.handler.fail_apply = "b"
        result = self.engine.run("Bulk", [self.operation("a", 10), self.operation("b", 20), self.operation("c", 30)])
        self.assertFalse(result.success)
        self.assertEqual(result.status, "Recovered")
        self.assertEqual(self.handler.values, {"a": 1, "b": 2, "c": 3})
        self.assertEqual(self.handler.calls, [("apply", "a"), ("apply", "b"), ("restore", "b"), ("restore", "a")])

    def test_intent_is_durable_before_the_handler_runs(self):
        original_apply = self.handler.apply
        def observe(target, desired):
            records = self.store.records()
            latest = next(iter(records.values()))
            self.assertEqual(latest["status"], "Running")
            self.assertEqual(latest["operations"][0]["state"], "Applying")
            original_apply(target, desired)
        self.handler.apply = observe
        self.assertTrue(self.engine.run("Recorded first", [self.operation()]).success)

    def test_dry_run_changes_neither_resources_nor_journal(self):
        result = self.engine.run("One change", [self.operation()])
        before = self.store.records()
        calls = self.handler.calls[:]
        report = self.engine.assessment(result.transaction_id)
        self.assertTrue(report["ready"])
        self.assertEqual(calls, self.handler.calls)
        self.assertEqual(before, self.store.records())

    def test_external_change_is_reported_and_not_silently_overwritten(self):
        result = self.engine.run("One change", [self.operation()])
        self.handler.values["a"] = 42
        self.assertTrue(self.engine.assessment(result.transaction_id)["operations"][0]["conflict"])
        rollback = self.engine.rollback(result.transaction_id, confirmed=True)
        self.assertEqual(rollback.status, "Partial Recovery")
        self.assertEqual(self.handler.values["a"], 42)
        forced = self.engine.rollback(result.transaction_id, confirmed=True, force=True)
        self.assertEqual(forced.status, "Recovered")
        self.assertEqual(self.handler.values["a"], 1)

    def test_a_change_after_preview_requires_a_new_preview(self):
        preview = self.engine.prepare("One change", [self.operation()])
        self.handler.values["a"] = 7
        with self.assertRaises(ConflictError):
            self.engine.execute(preview["transaction_id"], preview["plan_digest"], confirmed=True)
        self.assertEqual(self.handler.calls, [])

    def test_modified_snapshot_is_rejected_even_during_forced_recovery(self):
        result = self.engine.run("One change", [self.operation()])
        path = self.store.snapshots / self.engine.details(result.transaction_id)["transaction"]["snapshot"]
        data = json.loads(path.read_text(encoding="utf-8"))
        data["payload"]["operations"][0]["original"] = {"value": 666}
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(IntegrityError):
            self.engine.rollback(result.transaction_id, confirmed=True, force=True)
        self.assertEqual(self.handler.values["a"], 9)
        self.assertEqual(self.engine.health()["status"], "Fault")

    def test_modified_journal_and_missing_snapshot_are_detected(self):
        result = self.engine.run("One change", [self.operation()])
        detail = self.engine.details(result.transaction_id)
        with closing(sqlite3.connect(self.store.database)) as connection:
            connection.execute("UPDATE events SET payload='{}' WHERE sequence=(SELECT max(sequence) FROM events)")
            connection.commit()
        with self.assertRaises(IntegrityError):
            self.engine.transactions()
        self.assertEqual(self.engine.health()["status"], "Fault")
        self.assertTrue((self.store.snapshots / detail["transaction"]["snapshot"]).exists())

    def test_missing_snapshot_blocks_new_modifications(self):
        result = self.engine.run("One change", [self.operation()])
        snapshot = self.engine.details(result.transaction_id)["transaction"]["snapshot"]
        (self.store.snapshots / snapshot).unlink()
        with self.assertRaises(RecoveryError):
            self.engine.run("Another change", [self.operation("b")])
        self.assertEqual(self.handler.values["b"], 2)

    def test_insufficient_permissions_and_space_do_not_apply_changes(self):
        self.handler.requires_admin = True
        self.engine.is_admin = lambda: False
        with self.assertRaises(RecoveryError):
            self.engine.run("Denied", [self.operation()])
        self.assertEqual(self.handler.calls, [])
        self.engine.is_admin = lambda: True
        with patch.object(self.store, "check_space", side_effect=RecoveryError("Disk full")):
            with self.assertRaises(RecoveryError):
                self.engine.run("Denied", [self.operation()])
        self.assertEqual(self.handler.calls, [])

    def test_cancel_before_execution_and_changed_plan_never_apply(self):
        self.engine.approve = lambda preview: False
        result = self.engine.run("Cancelled", [self.operation()])
        self.assertEqual(result.status, "Cancelled")
        self.assertEqual(self.handler.calls, [])
        preview = self.engine.prepare("Prepared", [self.operation()])
        with self.assertRaises(RecoveryError):
            self.engine.execute(preview["transaction_id"], "wrong-plan", confirmed=True)
        self.assertEqual(self.handler.calls, [])

    def test_unfinished_and_duplicate_resources_are_protected(self):
        preview = self.engine.prepare("Pending", [self.operation()])
        with self.assertRaises(RecoveryError):
            self.engine.prepare("Overlap", [self.operation()])
        with self.assertRaises(RecoveryError):
            self.engine.delete_record(preview["transaction_id"], confirmed=True)
        self.engine.cancel(preview["transaction_id"])
        with self.assertRaises(RecoveryError):
            self.engine.prepare("Duplicate", [self.operation(), self.operation()])

    def test_dependency_order_and_cycles_are_validated(self):
        result = self.engine.run("Ordered", [self.operation("a", dependencies=(1,)), self.operation("b")])
        self.assertEqual(self.handler.calls[:2], [("apply", "b"), ("apply", "a")])
        self.engine.rollback(result.transaction_id, confirmed=True)
        with self.assertRaises(RecoveryError):
            self.engine.prepare("Cycle", [self.operation("a", dependencies=(1,)), self.operation("b", dependencies=(0,))])

    def test_crash_reopen_exposes_interrupted_record_and_recovers_known_state(self):
        preview = self.engine.prepare("Interrupted", [self.operation()])
        with self.store.locked():
            record, _ = self.engine._record(preview["transaction_id"])
            record["status"] = "Running"
            record["operations"][0]["state"] = "Applying"
            self.engine._save(record, "Simulated durable intent before power interruption")
        self.handler.values["a"] = 9
        reopened = self.reopen()
        self.assertEqual(reopened.interrupted()[0]["transaction_id"], preview["transaction_id"])
        result = reopened.rollback(preview["transaction_id"], confirmed=True)
        self.assertEqual(result.status, "Recovered")

    def test_failed_verification_never_reports_complete_recovery(self):
        result = self.engine.run("One change", [self.operation()])
        self.handler.fail_restore = True
        restored = self.engine.rollback(result.transaction_id, confirmed=True)
        self.assertFalse(restored.success)
        self.assertEqual(restored.status, "Partial Recovery")
        self.assertFalse(restored.details[0]["verified"])
        self.engine.rollback(result.transaction_id, confirmed=True)
        self.assertEqual(self.reopen().health()["status"], "Fault")

    def test_safe_mode_survives_reopen_and_needs_explicit_validation(self):
        self.engine.enter_safe_mode("Fixture corruption investigation")
        engine = self.reopen()
        self.assertEqual(engine.health()["status"], "Fault")
        with self.assertRaises(RecoveryError):
            engine.run("Blocked", [self.operation()])
        with self.assertRaises(RecoveryError):
            engine.leave_safe_mode()
        self.assertEqual(engine.leave_safe_mode(confirmed=True)["status"], "Healthy")

    def test_pending_reboot_is_not_claimed_complete_until_a_new_boot_is_verified(self):
        self.handler.requires_reboot = lambda target: True
        result = self.engine.run("Requires restart", [self.operation()])
        self.assertEqual(result.status, "Pending Reboot")
        self.engine.verify_current(result.transaction_id)
        self.assertEqual(self.engine.details(result.transaction_id)["transaction"]["status"], "Pending Reboot")
        self.boot[0] += 1
        self.engine.verify_current(result.transaction_id)
        self.assertEqual(self.engine.details(result.transaction_id)["transaction"]["status"], "Completed")

    def test_unrecoverable_action_preserves_manual_recovery_information(self):
        self.handler.capability = Capability.MANUAL
        result = self.engine.run("Manual", [self.operation()])
        restored = self.engine.rollback(result.transaction_id, confirmed=True)
        self.assertEqual(restored.status, "Partial Recovery")
        self.assertEqual(self.handler.values["a"], 9)
        self.assertIn("Manual recovery", restored.details[0]["error"])

    def test_export_authentication_and_resolved_record_deletion(self):
        result = self.engine.run("One change", [self.operation()])
        export = self.root.parent / "record.json"
        with self.assertRaises(RecoveryError):
            self.engine.export_record(result.transaction_id, export)
        self.engine.export_record(result.transaction_id, export, confirmed_sensitive=True)
        self.assertEqual(self.engine.validate_export(export)["snapshot"]["transaction_id"], result.transaction_id)
        data = json.loads(export.read_text(encoding="utf-8"))
        data["payload"]["snapshot"]["machine"] = "other"
        export.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(IntegrityError):
            self.engine.validate_export(export)
        self.engine.delete_record(result.transaction_id, confirmed=True)
        self.assertEqual(self.engine.transactions(), [])
        self.assertEqual(self.engine.health()["status"], "Healthy")

    def test_prepared_ids_and_snapshots_do_not_collide_within_a_second(self):
        first = self.engine.prepare("First", [self.operation("a")])
        second = self.engine.prepare("Second", [self.operation("b")])
        self.assertNotEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual(len(list(self.store.snapshots.iterdir())), 2)

    def test_missing_control_record_does_not_reset_safe_mode(self):
        self.engine.enter_safe_mode("Preserve evidence")
        (self.root / "control.json").unlink()
        with self.assertRaises(IntegrityError):
            RecoveryStore(self.root, key=self.key, identity="fixture-user", secure=False)


if __name__ == "__main__":
    unittest.main()
