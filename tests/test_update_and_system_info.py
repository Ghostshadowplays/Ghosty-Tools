import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core.release_notes import bundled_release_notes
from src.core.system_info import windows_system_details
from src.core.update_handoff import clean_restart_environment, launch_windows_update
from src.core.update_manager import UpdateManager


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"


class UpdateEnvironmentTests(unittest.TestCase):
    def test_restart_discards_stale_runtime_but_keeps_other_paths(self):
        source = {
            "_PYI_APPLICATION_HOME_DIR": r"C:\Temp\_MEI123",
            "_PYI_PARENT_PROCESS_LEVEL": "1",
            "_MEIPASS2": r"C:\Temp\_MEI123",
            "PYTHONHOME": r"C:\Temp\_MEI123",
            "Path": r"C:\Windows;C:\Temp\_MEI123;C:\Temp\_MEI123\bin;C:\Temp\_MEI1234;D:\Tools",
            "APPDATA": r"C:\Users\Someone\AppData\Roaming",
        }
        clean = clean_restart_environment(source, r"c:\temp\_MEI123")
        self.assertEqual(clean["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.assertEqual(clean["Path"], r"C:\Windows;C:\Temp\_MEI1234;D:\Tools")
        self.assertEqual(clean["APPDATA"], source["APPDATA"])
        self.assertFalse(any(key.startswith(("_PYI_", "_MEIPASS")) for key in clean))
        self.assertNotIn("PYTHONHOME", clean)
        self.assertIn("_PYI_APPLICATION_HOME_DIR", source)

    def test_handoff_preserves_paths_as_data_and_leaves_old_binary_until_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "User's tools & utilities!"
            folder.mkdir()
            source = folder / "update.exe"
            target = folder / "Ghosty Tools.exe"
            source.write_bytes(b"MZ" + b"new data")
            target.write_bytes(b"old version")
            with patch("src.core.update_handoff.subprocess.Popen") as launch:
                log = launch_windows_update(source, target, source_pid=123456).log_path
            command = launch.call_args.args[0]
            self.assertEqual(command[0], "powershell.exe")
            manifest = json.loads((log.parent / "update.json").read_text(encoding="utf-8"))
            # Windows may expand an 8.3 TEMP alias when resolving the manifest paths.
            self.assertTrue(source.samefile(manifest["source"]))
            self.assertTrue(target.samefile(manifest["target"]))
            self.assertEqual(manifest["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(target.read_bytes(), b"old version")
            self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
            self.assertNotIn("cmd.exe", command)

    def test_bad_download_never_starts_a_helper_or_replaces_the_app(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "update.exe"
            target = Path(temporary) / "app.exe"
            source.write_bytes(b"<html>Error</html>")
            target.write_bytes(b"old version")
            with patch("src.core.update_handoff.subprocess.Popen") as launch:
                with self.assertRaises(ValueError):
                    launch_windows_update(source, target)
            launch.assert_not_called()
            self.assertEqual(target.read_bytes(), b"old version")

    def test_versioned_notes_are_bundled_and_path_traversal_is_rejected(self):
        self.assertIn("What's New in v8.0.6", bundled_release_notes("v8.0.6"))
        self.assertIn("Your system, in one overview", bundled_release_notes("v8.0.6"))
        self.assertEqual(bundled_release_notes("../version"), "")

    def test_release_notes_use_the_installed_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch("src.core.update_manager.get_config_dir", return_value=temporary):
                manager = UpdateManager()
            with patch("src.core.update_manager.requests.get") as request:
                request.return_value.json.return_value = {"body": "Installed release"}
                manager.get_release_info("v8.0.6")
            self.assertTrue(request.call_args.args[0].endswith("/releases/tags/v8.0.6"))


class SystemInfoTests(unittest.TestCase):
    def test_cim_collects_all_sections_and_escapes_hardware_names(self):
        data = {
            "Computer": {"Manufacturer": "Ghosty", "Model": "Workstation"},
            "OS": [{"Caption": "Windows 11", "OSArchitecture": "64-bit", "BuildNumber": "26200"}],
            "CPU": [{"Name": "Test <CPU>"}],
            "GPU": [{"Name": "Test graphics", "DriverVersion": "123"}],
            "Board": [{"Manufacturer": "Board Maker", "Product": "Main Board"}],
            "BIOS": [{"Manufacturer": "Firmware", "SMBIOSBIOSVersion": "1.2"}],
            "Memory": [{"DeviceLocator": "DIMM 1", "Capacity": 8 * 1024**3, "Speed": 3200}],
            "Disks": [{"Model": "System SSD", "Size": 512 * 1024**3, "InterfaceType": "NVMe"}],
        }
        def command(args, **kwargs):
            self.assertEqual(args[0], "powershell.exe")
            self.assertNotIn("wmic", " ".join(args).lower())
            self.assertEqual(kwargs["timeout"], 45)
            return SimpleNamespace(returncode=0, stdout=json.dumps(data))
        report = windows_system_details(command)
        for expected in ("Workstation", "Windows 11", "Test &lt;CPU&gt;", "Test graphics",
                         "Main Board", "1.2", "8.0 GB", "3200 MHz", "System SSD"):
            self.assertIn(expected, report)
        self.assertNotIn("Test <CPU>", report)

    def test_cim_unavailability_does_not_invent_device_names(self):
        report = windows_system_details(lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""))
        self.assertIn("Not reported by this system", report)
        self.assertIn("Detailed CIM information was unavailable", report)


@unittest.skipUnless(os.name == "nt" and COMPILER.exists(), "Windows .NET compiler required")
class WindowsUpdateIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temporary.name)
        code = cls.folder / "App.cs"
        cls.binary = cls.folder / "fixture.exe"
        code.write_text(
            'using System; using System.IO; using System.Reflection; '
            'class App { static void Main() { '
            'var path = Assembly.GetExecutingAssembly().Location + ".started"; '
            'File.WriteAllText(path, '
            '(Environment.GetEnvironmentVariable("_PYI_APPLICATION_HOME_DIR") ?? "clean") + "|" + '
            'Environment.GetEnvironmentVariable("PYINSTALLER_RESET_ENVIRONMENT")); } }',
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(COMPILER), "/nologo", "/target:winexe", f"/out:{cls.binary}", str(code)],
            capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def fixture(self):
        folder = Path(tempfile.mkdtemp(prefix="Unicode é & user's apps! ", dir=self.folder))
        source = folder / "download.exe"
        target = folder / "Ghosty Tools.exe"
        shutil.copyfile(self.binary, source)
        target.write_bytes(b"previous version")
        return folder, source, target

    def test_native_helper_replaces_and_reopens_without_deleting_other_runtimes(self):
        folder, source, target = self.fixture()
        runtime = folder / "_MEI_other_application"
        runtime.mkdir()
        marker = runtime / "keep.dll"
        marker.write_bytes(b"another running application")
        with patch.dict(os.environ, {"_PYI_APPLICATION_HOME_DIR": str(runtime)}):
            handoff = launch_windows_update(source, target, source_pid=2147483647)
            log = handoff.log_path
        handoff.process.wait(timeout=20)
        started = Path(str(target) + ".started")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if started.exists() and log.exists() and "application launched" in log.read_text(encoding="utf-8-sig"):
                break
            time.sleep(0.1)
        self.assertTrue(started.exists(), log.read_text(encoding="utf-8-sig") if log.exists() else "No helper log")
        self.assertEqual(started.read_text(), "clean|1")
        self.assertEqual(target.read_bytes(), self.binary.read_bytes())
        self.assertEqual(marker.read_bytes(), b"another running application")
        backups = list(folder.glob("*.previous-*.exe"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"previous version")

    def test_changed_download_is_rejected_without_removing_the_old_binary(self):
        folder, source, target = self.fixture()
        with patch("src.core.update_handoff.subprocess.Popen"):
            log = launch_windows_update(source, target, source_pid=2147483647).log_path
        source.write_bytes(b"MZchanged after preparation")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(log.parent / "apply_update.ps1"), "-ManifestPath", str(log.parent / "update.json")],
            capture_output=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(target.read_bytes(), b"previous version")
        self.assertIn("changed before installation", log.read_text(encoding="utf-8-sig"))
