"""Headless checks for the workspace shell and its live-data widgets."""

import json
import os
import sys
import traceback
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QThread, QTimer, Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtTest import QTest, QSignalSpy
from PyQt6.QtWidgets import QApplication

from src.core.update_manager import UpdateManager
from src.gui.dashboard import MonitorCard
from src.gui.main_window import GhostyTool
from src.utils.theme_manager import ThemeManager


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if os.name == "nt":
            # The offscreen Qt plugin does not enumerate Windows system fonts.
            fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
                QFontDatabase.addApplicationFont(str(fonts / name))
        cls.temp = tempfile.TemporaryDirectory()
        cls.environment = patch.dict(os.environ, {"APPDATA": cls.temp.name})
        cls.environment.start()
        cls.paint_errors = []
        cls.old_exception_hook = sys.excepthook
        def capture_exception(kind, value, tb):
            message = "".join(traceback.format_exception(kind, value, tb))
            cls.paint_errors.append(message)
            print(message, file=sys.stderr, flush=True)
        sys.excepthook = capture_exception
        # Build the actual pages without starting background tasks or prompts.
        with (
            patch.object(QThread, "start"),
            patch.object(QTimer, "start"),
            patch.object(QTimer, "singleShot"),
            patch.object(GhostyTool, "init_tray"),
            patch.object(GhostyTool, "refresh_disk_list"),
            patch.object(GhostyTool, "_apply_windows_startup"),
            patch.object(GhostyTool, "_refresh_win_startup_status"),
        ):
            cls.window = GhostyTool()
        cls.window.resize(1240, 840)
        cls.window.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.window._app_settings["minimize_to_tray"] = False
        cls.window.close()
        cls.window.deleteLater()
        cls.app.processEvents()
        cls.environment.stop()
        cls.temp.cleanup()
        sys.excepthook = cls.old_exception_hook
        if cls.paint_errors:
            raise AssertionError("\n".join(cls.paint_errors))

    def setUp(self):
        self.window.tool_search.clear()
        self.window._filter_navigation("")
        self.window.log_toggle.setChecked(False)

    def test_navigation_keeps_all_page_routes(self):
        self.assertEqual(len(self.window.nav_buttons), 19)
        self.assertEqual(self.window.content_stack.count(), 19)
        with (
            patch.object(self.window, "check_tools_status") as apps,
            patch.object(self.window, "scan_bloatware") as debloat,
        ):
            self.window._bloat_ever_scanned = False
            for index, button in enumerate(self.window.nav_buttons):
                button.click()
                self.assertEqual(self.window.content_stack.currentIndex(), index)
                self.assertEqual(self.window.page_title.text(), button.text())
            apps.assert_called_once()
            debloat.assert_called_once()

    def test_search_finds_tools_by_description(self):
        self.window.tool_search.setText("DNS")
        visible = [i for i, button in enumerate(self.window.nav_buttons) if not button.isHidden()]
        self.assertEqual(visible, [3])

    def test_empty_search_result_is_explained(self):
        self.window.tool_search.setText("there-is-no-such-tool")
        self.assertTrue(all(button.isHidden() for button in self.window.nav_buttons))
        self.assertFalse(self.window.no_tools_label.isHidden())
        self.window.tool_search.clear()
        self.assertTrue(self.window.no_tools_label.isHidden())

    def test_search_does_not_restore_unsupported_tools(self):
        old = self.window._unavailable_nav
        try:
            self.window._unavailable_nav = {6, 11}
            self.window._filter_navigation("Windows")
            self.window._filter_navigation("")
            self.assertTrue(self.window.nav_buttons[6].isHidden())
            self.assertTrue(self.window.nav_buttons[11].isHidden())
        finally:
            self.window._unavailable_nav = old
            self.window._filter_navigation("")

    def test_enter_opens_matching_tool_without_a_bloat_scan(self):
        with patch.object(self.window, "scan_bloatware") as scan:
            self.window.tool_search.setText("DNS")
            QTest.keyClick(self.window.tool_search, Qt.Key.Key_Return)
            self.assertEqual(self.window.content_stack.currentIndex(), 3)
            scan.assert_not_called()

    def test_log_collapse_keeps_progress_visible(self):
        self.window.progress_bar.show()
        self.window.log_toggle.setChecked(True)
        self.assertFalse(self.window.terminal_container.isHidden())
        self.window.log_toggle.setChecked(False)
        self.assertTrue(self.window.terminal_container.isHidden())
        self.assertTrue(self.window.progress_bar.isVisible())
        self.window.progress_bar.hide()

    def test_keyboard_shortcut_focuses_tool_search(self):
        self.window.activateWindow()
        self.window.log_toggle.setFocus()
        self.app.processEvents()
        QTest.keyClick(self.window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self.window.tool_search.hasFocus())

    def test_system_overview_updates_and_copies_details(self):
        self.window._on_specs_ready("<b>Processor</b><br>Test CPU<br><b>Graphics adapters</b><br>Test GPU")
        details = self.window.dashboard.system_details
        self.assertIn("Test CPU", details.toPlainText())
        self.assertIn("Test GPU", details.toPlainText())
        self.window.dashboard.system_details_toggle.setChecked(True)
        self.assertFalse(details.isHidden())
        self.window.dashboard.system_copy_btn.click()
        self.assertIn("Test CPU", self.app.clipboard().text())
        self.window.dashboard.system_details_toggle.setChecked(False)

    def test_bundled_whats_new_is_shown_once_per_revision(self):
        # Monthly releases can bump the app version without adding bundled notes.
        # Supply our own notes and acknowledgement file for a future version.
        manager: UpdateManager = self.window.update_manager
        version = "v99.0.0"
        with tempfile.TemporaryDirectory() as directory:
            notes = Path(directory) / f"{version}.md"
            notes.write_text("# What's New\nFirst revision.", encoding="utf-8")
            with (
                patch.object(manager, "current_version", version),
                patch.object(manager, "version_file", str(Path(directory) / "version_info.json")),
                patch("src.core.release_notes.get_resource_path", return_value=str(notes)),
                patch("src.gui.main_window.ReleaseInfoWorker") as remote_notes,
                patch("src.gui.main_window.QDialog.exec", return_value=0) as popup,
            ):
                self.window.check_for_whats_new()
                self.window.check_for_whats_new()
                popup.assert_called_once()
                self.assertEqual(manager.get_last_seen_version(), version)
                first_revision = manager.get_last_seen_notes_revision()
                self.assertTrue(first_revision)

                notes.write_text("# What's New\nUpdated revision.", encoding="utf-8")
                self.window.check_for_whats_new()
                self.window.check_for_whats_new()
                self.assertEqual(popup.call_count, 2)
                self.assertNotEqual(manager.get_last_seen_notes_revision(), first_revision)
                remote_notes.assert_not_called()

    def test_dashboard_fits_a_smaller_workspace(self):
        self.window.switch_page(0)
        self.window.resize(960, 640)
        self.app.processEvents()
        self.assertLessEqual(
            self.window.content_stack.width(),
            self.window.content_scroll.viewport().width(),
        )
        self.window.resize(1240, 840)

    def test_startup_status_refresh_does_not_apply_settings(self):
        if not hasattr(self.window, "_s_start_windows"):
            self.skipTest("Windows startup UI only")
        checkbox = self.window._s_start_windows
        blocked = checkbox.blockSignals(True)
        checkbox.setChecked(False)
        checkbox.blockSignals(blocked)
        changes = QSignalSpy(checkbox.stateChanged)
        with (
            patch("src.gui.main_window.winreg.OpenKey", return_value=object()),
            patch("src.gui.main_window.winreg.CloseKey"),
            patch("src.gui.main_window.winreg.QueryValueEx", return_value=("fixture.exe", 1)),
        ):
            self.window._refresh_win_startup_status()
        self.assertTrue(checkbox.isChecked())
        self.assertEqual(len(changes), 0)

    def test_monitor_samples_are_bounded_and_keep_details(self):
        card = MonitorCard("Test")
        for value in range(40):
            card.set_reading(value, "Live sample")
        self.assertEqual(len(card.sparkline.samples), 32)
        self.assertEqual(card.sparkline.samples[0], 8)
        card.set_reading(150)
        self.assertEqual(card.bar.value(), 100)
        self.assertEqual(card.details_label.text(), "Live sample")
        card.set_reading(-5)
        self.assertEqual(card.value_label.text(), "0%")
        card.resize(260, 180)
        card.show()
        self.app.processEvents()
        self.assertFalse(card.grab().isNull())
        card.close()
        card.deleteLater()

    def test_new_theme_default_and_saved_custom_colours(self):
        settings = Path(self.temp.name) / "theme-test.json"
        manager = ThemeManager(str(settings))
        self.assertEqual(manager.current_theme, "Ghost Mint")
        settings.write_text(json.dumps({
            "current_theme": "Custom", "bg_intensity": 63,
            "custom_colors": {"primary": "#780099"},
        }), encoding="utf-8")
        manager.load_settings()
        self.assertEqual(manager.current_theme, "Custom")
        self.assertEqual(manager.get_theme_colors()["primary"], "#780099")
        self.assertIn("background", manager.get_theme_colors())
        for name in manager.DEFAULT_THEMES:
            manager.current_theme = name
            self.assertIn("QFrame#DashboardHero", manager.get_stylesheet())

    def test_zz_preview_export(self):
        output = os.environ.get("GHOSTY_PREVIEW_PATH")
        if not output:
            self.skipTest("Set GHOSTY_PREVIEW_PATH to export a UI preview")
        self.window.switch_page(0)
        self.window.theme_manager.current_theme = "Ghost Mint"
        self.window.theme_manager.bg_intensity = 50
        self.window.apply_current_theme()
        self.window.resize(1240, 940)
        self.window.refresh_system_alerts()
        self.window.update_specs()
        self.assertTrue(self.window.specs_worker.wait(50000), "System detail worker timed out")
        self.app.processEvents()
        for _ in range(3):
            self.window.update_system_usage()
            QTest.qWait(2000)
        self.app.processEvents()
        self.assertTrue(self.window.grab().save(output))
        self.window.dashboard.system_details_toggle.setChecked(True)
        self.window.dashboard.system_details.verticalScrollBar().setValue(0)
        self.app.processEvents()
        system_preview = Path(output).with_stem(Path(output).stem + "-system")
        self.assertTrue(self.window.grab().save(str(system_preview)))


if __name__ == "__main__":
    unittest.main()
