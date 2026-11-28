"""Recovery controls using the application's existing Qt components and theme."""

from datetime import datetime
import json
from pathlib import Path
import threading

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                            QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                            QPushButton, QSpinBox, QTextEdit, QTreeWidget, QTreeWidgetItem,
                            QVBoxLayout)

from src.core.recovery.integration import get_engine, hardening_profiles, set_approval_handler


def formatted(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


class RecoveryTask(QThread):
    outcome = pyqtSignal(object)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.outcome.emit({"value": self.function()})
        except Exception as error:
            self.outcome.emit({"error": str(error)})


class RecoveryController(QObject):
    approval_requested = pyqtSignal(object)

    def __init__(self, window, provider=get_engine):
        super().__init__(window)
        self.window = window
        self.provider = provider
        self.dialog = None
        self.tasks = []
        self.waiters = []
        self.approval_requested.connect(self._receive_approval)
        set_approval_handler(self.approve)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor)
        self.monitor_busy = False
        QTimer.singleShot(750, self.startup_check)

    def submit(self, function, callback=None):
        task = RecoveryTask(function, self)
        self.tasks.append(task)
        task.outcome.connect(callback or self._report)
        task.finished.connect(lambda: self._finished(task))
        task.start()
        return task

    def _finished(self, task):
        if task in self.tasks:
            self.tasks.remove(task)
        task.deleteLater()

    def _report(self, outcome):
        if "error" in outcome:
            self.window.log_signal.emit("Recovery: " + outcome["error"], "error")
            QMessageBox.warning(self.window, "Recovery Centre", outcome["error"])
        else:
            value = outcome.get("value")
            if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], bool):
                success, message = value
            else:
                success = getattr(value, "success", True)
                message = getattr(value, "message", str(value) if value is not None else "Recovery record updated")
            self.window.log_signal.emit(message, "info" if success else "warning")
            if not success:
                QMessageBox.warning(self.window, "Recovery Centre", message)
            if self.dialog is not None:
                self.dialog.refresh()

    def approve(self, payload):
        if QThread.currentThread() == self.thread():
            return self._ask(payload)
        request = {"payload": payload, "event": threading.Event(), "approved": False, "expired": False}
        self.waiters.append(request)
        self.approval_requested.emit(request)
        # No operation starts if the GUI is closed, blocked, or cannot show approval.
        if not request["event"].wait(timeout=300):
            request["expired"] = True
        if request in self.waiters:
            self.waiters.remove(request)
        return request["approved"] and not request["expired"]

    @pyqtSlot(object)
    def _receive_approval(self, request):
        if not request["expired"]:
            request["approved"] = self._ask(request["payload"])
        request["event"].set()

    def _ask(self, payload):
        kind = payload.get("type", "operation")
        if kind == "restore_point_failed":
            return QMessageBox.question(self.window, "Windows System Restore",
                "System recovery point could not be created. Continue anyway?\n\n" + payload["error"] +
                "\n\nThe validated Ghosty Tools recovery snapshot is still available.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
        if kind == "connectivity":
            box = QMessageBox(self.window)
            box.setWindowTitle("Confirm connectivity")
            box.setText(f"Network changes applied.\n\nConfirm connectivity within {payload['seconds']} seconds. "
                        "The independent watchdog will attempt recovery if confirmation is not received.")
            confirm = box.addButton("Connectivity Working", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Attempt Recovery", QMessageBox.ButtonRole.RejectRole)
            timer = QTimer(box)
            timer.setSingleShot(True)
            timer.timeout.connect(box.reject)
            timer.start(payload["seconds"] * 1000)
            box.exec()
            return box.clickedButton() is confirm
        if kind == "rollback":
            return self._show_preview("Review Recovery", payload["assessment"], "Attempt Recovery")
        operations = []
        for operation in payload["operations"]:
            operations.append({"action": operation["description"], "target": operation["target"],
                               "current": operation["original"], "proposed": operation["desired"],
                               "risk": operation["risk"], "recovery": operation["capability"],
                               "administrator_required": operation["admin"]})
        value = {"action": payload["label"], "transaction": payload["transaction_id"],
                 "snapshot": payload["snapshot"], "operations": operations,
                 "notice": "Terminated processes may lose unsaved data. Only captured supported properties can be restored."}
        return self._show_preview("Operation Preview", value, "Confirm Operation")

    def _show_preview(self, title, payload, confirm_text):
        dialog = QDialog(self.window)
        dialog.setWindowTitle(title)
        dialog.resize(780, 560)
        layout = QVBoxLayout(dialog)
        label = QLabel(title)
        label.setObjectName("PageTitle")
        layout.addWidget(label)
        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText(formatted(payload))
        layout.addWidget(details)
        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        confirm = QPushButton(confirm_text)
        confirm.setObjectName("PrimaryBtn")
        cancel.clicked.connect(dialog.reject)
        confirm.clicked.connect(dialog.accept)
        row.addWidget(cancel)
        row.addWidget(confirm)
        layout.addLayout(row)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def show(self):
        if self.dialog is None:
            self.dialog = RecoveryCentre(self)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.refresh()

    def startup_check(self):
        def inspect():
            engine = self.provider()
            return {"health": engine.health(), "interrupted": engine.interrupted(), "settings": engine.settings()}
        self.submit(inspect, self._startup_result)

    def _startup_result(self, outcome):
        if "error" in outcome:
            self.window.log_signal.emit("Recovery health: Fault — " + outcome["error"], "error")
            return
        value = outcome["value"]
        self.window.log_signal.emit("Recovery health: " + value["health"]["status"], "info")
        self.monitor_timer.start(max(10, value["settings"]["monitor_seconds"]) * 1000)
        if value["interrupted"]:
            answer = QMessageBox.question(self.window, "Interrupted system modification",
                "An interrupted system modification was detected. Ghosty Tools has located the associated recovery record.\n\n"
                "Open Recovery Centre to review, verify or attempt recovery? Choosing No leaves the records protected for later.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                self.show()

    def _monitor(self):
        if self.monitor_busy:
            return
        self.monitor_busy = True
        self.submit(lambda: self.provider().monitor(), self._monitor_result)

    def _monitor_result(self, outcome):
        self.monitor_busy = False
        if "error" in outcome:
            self.window.log_signal.emit("Recovery validation: " + outcome["error"], "warning")
        elif outcome.get("value"):
            self.window.log_signal.emit("Recovery validation detected external changes; review Recovery Centre. "
                                        "No settings were reapplied.", "warning")

    def close(self):
        for request in self.waiters[:]:
            request["expired"] = True
            request["event"].set()
        # Application shutdown must not destroy an active QThread mid-journal write.
        if any(task.isRunning() for task in self.tasks):
            return False
        self.monitor_timer.stop()
        return True


class RecoveryCentre(QDialog):
    def __init__(self, controller):
        super().__init__(controller.window)
        self.controller = controller
        self.setWindowTitle("Security · Recovery Centre")
        self.resize(1060, 720)
        layout = QVBoxLayout(self)
        title = QLabel("Recovery Centre")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        self.health_label = QLabel("Checking recovery records…")
        self.health_label.setWordWrap(True)
        layout.addWidget(self.health_label)
        self.history = QTreeWidget()
        self.history.setHeaderLabels(["Date / Time", "Transaction", "Action / Target", "Risk", "Status", "Recovery"])
        self.history.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.history, 1)
        row = QHBoxLayout()
        for label, callback in (("Refresh", self.refresh), ("Roll Back", self.rollback),
                ("View Details", self.details), ("Verify Current State", self.verify),
                ("Compare / Dry Run", self.assess), ("Export", self.export), ("Delete", self.delete),
                ("Cancel Pending", self.cancel_pending)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.profile_box = QComboBox()
        self.profile_box.addItems(hardening_profiles())
        profiles = QHBoxLayout()
        profiles.addWidget(QLabel("Security profile"))
        profiles.addWidget(self.profile_box)
        preview = QPushButton("Select Actions / Preview")
        preview.clicked.connect(self.profile)
        profiles.addWidget(preview)
        save_group = QPushButton("Group Selected Records")
        save_group.clicked.connect(self.group_records)
        profiles.addWidget(save_group)
        layout.addLayout(profiles)
        settings = QHBoxLayout()
        self.restore_points = QCheckBox("Create Windows Restore Point Before Major Changes")
        settings.addWidget(self.restore_points)
        self.watchdog_seconds = QSpinBox()
        self.watchdog_seconds.setRange(10, 600)
        self.watchdog_seconds.setSuffix(" s")
        settings.addWidget(QLabel("Connectivity confirmation"))
        settings.addWidget(self.watchdog_seconds)
        self.retention_days = QSpinBox()
        self.retention_days.setRange(1, 3650)
        self.retention_days.setSuffix(" days")
        settings.addWidget(QLabel("Retention"))
        settings.addWidget(self.retention_days)
        save = QPushButton("Save Settings")
        save.clicked.connect(self.save_settings)
        settings.addWidget(save)
        layout.addLayout(settings)
        mode = QHBoxLayout()
        for label, callback in (("Enable Recovery Safe Mode", self.safe_mode),
                                ("Validate and Leave Safe Mode", self.leave_safe_mode),
                                ("Review Retention Cleanup", self.retention),
                                ("Connectivity Working", self.confirm_connectivity)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            mode.addWidget(button)
        layout.addLayout(mode)
        self.notice = QLabel("Recovery restores captured configuration. Process/session data and irreversible changes may require manual recovery.")
        self.notice.setWordWrap(True)
        self.notice.setObjectName("MutedText")
        layout.addWidget(self.notice)

    def selected(self):
        items = self.history.selectedItems()
        if len(items) != 1:
            QMessageBox.information(self, "Recovery Centre", "Select one transaction first.")
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    def refresh(self):
        def load():
            engine = self.controller.provider()
            records = engine.transactions()
            rows = []
            for record in records:
                try:
                    snapshot = engine.details(record["transaction_id"])["snapshot"]
                    capability = ", ".join(dict.fromkeys(op["capability"] for op in snapshot["operations"]))
                    target = ", ".join(str(op["target"]) for op in snapshot["operations"])
                except Exception as error:
                    capability, target = "Recovery Unavailable", str(error)
                rows.append((record, capability, target))
            return {"health": engine.health(), "rows": rows, "settings": engine.settings(),
                    "bytes": sum(path.stat().st_size for path in engine.store.root.rglob("*") if path.is_file())}
        self.controller.submit(load, self._loaded)

    def _loaded(self, outcome):
        if "error" in outcome:
            self.health_label.setText("Recovery health: Fault — " + outcome["error"])
            return
        data = outcome["value"]
        health = data["health"]
        self.health_label.setText(f"Recovery health: {health['status']} · Storage: {float(data['bytes']) / 1048576:.2f} MB\n" +
                                 "; ".join(health["issues"]))
        self.history.clear()
        for record, capability, target in data["rows"]:
            when = datetime.fromisoformat(record["created"]).astimezone().strftime("%d/%m/%Y %H:%M:%S")
            status = record["status"]
            if record.get("connectivity_confirmed") is False:
                status += " · Awaiting connectivity confirmation"
            item = QTreeWidgetItem([when, record["transaction_id"], record["label"], record["risk"], status, capability])
            item.setData(0, Qt.ItemDataRole.UserRole, record["transaction_id"])
            item.setToolTip(2, target)
            self.history.addTopLevelItem(item)
        self.restore_points.setChecked(data["settings"]["restore_points"])
        self.watchdog_seconds.setValue(data["settings"]["watchdog_seconds"])
        self.retention_days.setValue(data["settings"]["retention_days"])
        for column in (0, 3, 4):
            self.history.resizeColumnToContents(column)

    def show_data(self, title, outcome):
        if "error" in outcome:
            QMessageBox.warning(self, title, outcome["error"])
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(850, 580)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(formatted(outcome["value"]))
        layout.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def details(self):
        transaction = self.selected()
        if transaction:
            self.controller.submit(lambda: self.controller.provider().details(transaction),
                                   lambda result: self.show_data("Transaction details", result))

    def assess(self):
        transaction = self.selected()
        if transaction:
            self.controller.submit(lambda: self.controller.provider().assessment(transaction),
                                   lambda result: self.show_data("Recovery assessment / differences", result))

    def verify(self):
        transaction = self.selected()
        if transaction:
            self.controller.submit(lambda: self.controller.provider().verify_current(transaction),
                                   lambda result: (self.show_data("Verification result", result), self.refresh()))

    def rollback(self):
        transaction = self.selected()
        if transaction:
            self.controller.submit(lambda: self.controller.provider().assessment(transaction),
                                   lambda result: self._review_rollback(transaction, result))

    def _review_rollback(self, transaction, outcome):
        if "error" in outcome:
            self.show_data("Recovery assessment", outcome)
            return
        assessment = outcome["value"]
        force = False
        if any(row.get("conflict") for row in assessment["operations"]):
            self.show_data("External changes — review differences", outcome)
            box = QMessageBox(self)
            box.setWindowTitle("External configuration changes")
            box.setText("External configuration changes have been detected. Restoring this snapshot may overwrite changes made outside Ghosty Tools.")
            force_button = box.addButton("Force Restoration", QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(cancel)
            box.exec()
            force = box.clickedButton() is force_button
            if not force:
                return
        elif not self.controller._show_preview("Review Recovery", assessment, "Attempt Recovery"):
            return
        self.controller.submit(lambda: self.controller.provider().rollback(transaction, confirmed=True, force=force))

    def export(self):
        transaction = self.selected()
        if not transaction:
            return
        if QMessageBox.question(self, "Export recovery data", "Recovery exports may contain usernames, network addresses and file paths. Export this record?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Export recovery record", transaction + ".json", "JSON (*.json)")
        if destination:
            self.controller.submit(lambda: self.controller.provider().export_record(transaction, Path(destination), confirmed_sensitive=True))

    def delete(self):
        transaction = self.selected()
        if transaction and QMessageBox.question(self, "Delete recovery record", "Delete this resolved recovery record? Its audit history is retained. Unfinished records cannot be deleted.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.controller.submit(lambda: self.controller.provider().delete_record(transaction, confirmed=True))

    def cancel_pending(self):
        transaction = self.selected()
        if transaction:
            self.controller.submit(lambda: self.controller.provider().cancel(transaction))

    def group_records(self):
        transactions = [item.data(0, Qt.ItemDataRole.UserRole) for item in self.history.selectedItems()]
        if not transactions:
            return
        name, ok = QInputDialog.getText(self, "Recovery profile", "Name this group of recovery records:")
        if ok and name.strip():
            self.controller.submit(lambda: self.controller.provider().save_profile(name.strip(), transactions))

    def save_settings(self):
        values = {"restore_points": self.restore_points.isChecked(), "retention_days": self.retention_days.value(),
                  "watchdog_seconds": self.watchdog_seconds.value()}
        self.controller.submit(lambda: self.controller.provider().configure(**values))

    def safe_mode(self):
        self.controller.submit(lambda: self.controller.provider().enter_safe_mode("Enabled explicitly from Recovery Centre"))

    def leave_safe_mode(self):
        if QMessageBox.question(self, "Leave Recovery Safe Mode", "Validate all recovery records and return to normal operation? Unresolved faults must be fixed first.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.controller.submit(lambda: self.controller.provider().leave_safe_mode(confirmed=True))

    def retention(self):
        self.controller.submit(lambda: self.controller.provider().retention_candidates(), self._retention_ready)

    def _retention_ready(self, outcome):
        if "error" in outcome:
            self.show_data("Retention review", outcome)
            return
        candidates = outcome["value"]
        if not candidates:
            QMessageBox.information(self, "Retention review", "No resolved records are older than the retention limit.")
        elif QMessageBox.question(self, "Confirm retention cleanup", f"Delete {len(candidates)} resolved recovery records older than the retention limit? Unfinished records are protected.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.controller.submit(lambda: [self.controller.provider().delete_record(value, confirmed=True) for value in candidates])

    def confirm_connectivity(self):
        transaction = self.selected()
        if transaction:
            self.controller.submit(lambda: self.controller.provider().confirm_connectivity(transaction))

    def profile(self):
        name = self.profile_box.currentText()
        operations = hardening_profiles()[name]
        dialog = QDialog(self)
        dialog.setWindowTitle(name + " — select supported actions")
        layout = QVBoxLayout(dialog)
        choices = QListWidget()
        for operation in operations:
            item = QListWidgetItem(operation.description)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            choices.addItem(item)
        layout.addWidget(choices)
        preview = QPushButton("Capture State and Preview")
        preview.clicked.connect(dialog.accept)
        layout.addWidget(preview)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = [operation for index, operation in enumerate(operations)
                        if choices.item(index).checkState() == Qt.CheckState.Checked]
            if selected:
                self.controller.submit(lambda: self.controller.provider().run(name, selected, profile=name))
