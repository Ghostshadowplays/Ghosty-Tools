"""Validate handler contracts with simulated Windows services and registry APIs."""

import ast
import base64
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core.recovery.engine import SecurityRecoveryEngine
from src.core.recovery.models import Operation, RecoveryError, _mutation_scope
from src.core.recovery.store import RecoveryStore
from src.core.recovery.windows import (HostsHandler, RegistryHandler, ServiceHandler, WindowsBackend)


ROOT = Path(__file__).resolve().parents[1]


class RegistryFixture:
    HKEY_CURRENT_USER = "user"
    HKEY_LOCAL_MACHINE = "machine"
    KEY_READ = 0x20019
    KEY_SET_VALUE = 2
    KEY_WOW64_64KEY = 0x100

    def __init__(self):
        self.keys = {}
        self.access = []

    @contextmanager
    def OpenKey(self, hive, path, reserved=0, access=KEY_READ):
        self.access.append(access)
        identity = (hive, path)
        if identity not in self.keys:
            raise FileNotFoundError(path)
        yield identity

    @contextmanager
    def CreateKeyEx(self, hive, path, reserved=0, access=KEY_SET_VALUE):
        self.access.append(access)
        for index in range(1, len(path.split("\\")) + 1):
            self.keys.setdefault((hive, "\\".join(path.split("\\")[:index])), {})
        yield hive, path

    def QueryValueEx(self, key, name):
        if name not in self.keys[key]:
            raise FileNotFoundError(name)
        return self.keys[key][name]

    def SetValueEx(self, key, name, reserved, kind, value):
        self.keys[key][name] = value, kind

    def DeleteValue(self, key, name):
        if name not in self.keys[key]:
            raise FileNotFoundError(name)
        del self.keys[key][name]

    def QueryInfoKey(self, key):
        hive, path = key
        children = {other[len(path) + 1:].split("\\")[0] for owner, other in self.keys
                    if owner == hive and other.startswith(path + "\\")}
        return len(children), len(self.keys[key]), 0

    def DeleteKeyEx(self, hive, path, access):
        identity = hive, path
        if self.QueryInfoKey(identity)[:2] != (0, 0):
            raise OSError("Key has unrelated content")
        del self.keys[identity]


class ServiceFixture:
    def __init__(self):
        self.services = {name: {"name": name, "running": True, "startup": "Auto", "delayed": True,
                        "dependencies": [], "dependents": [], "executable": f"{name}.exe", "account": "LocalSystem"}
                         for name in ("alpha", "beta")}
        self.calls = []
        self.fail_stop = False

    def service_read(self, name):
        return deepcopy(self.services[name.casefold()])

    def service_write(self, name, desired):
        name = name.casefold()
        self.calls.append(name)
        if "startup" in desired:
            self.services[name]["startup"] = desired["startup"]
        if self.fail_stop and desired.get("running") is False:
            raise RuntimeError("Injected stop failure after changing startup")
        self.services[name].update(desired)


class HandlerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.store = RecoveryStore(self.folder / "recovery", key=b"h" * 32, identity="fixture", secure=False)

    def engine(self, handler, name="registry.value.v1"):
        return SecurityRecoveryEngine(self.store, {name: handler}, is_admin=lambda: True, approve=lambda preview: True)

    def test_registry_original_type_and_binary_data_are_restored_exactly(self):
        registry = RegistryFixture()
        path = r"System\GameConfigStore"
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, path) as key:
            registry.SetValueEx(key, "GameDVR_Enabled", 0, 3, b"\x00\xff\x01")
        before = deepcopy(registry.keys)
        with patch.dict("sys.modules", {"winreg": registry}):
            engine = self.engine(RegistryHandler())
            result = engine.run("Change DVR", [Operation("registry.value.v1", {"id": "game_dvr"},
                                                         {"exists": True, "type": 4, "value": 0})])
            self.assertTrue(result.success)
            self.assertTrue(engine.rollback(result.transaction_id, confirmed=True).success)
        self.assertEqual(registry.keys, before)
        self.assertTrue(all(access & registry.KEY_WOW64_64KEY for access in registry.access[1:]))

    def test_new_registry_values_and_new_empty_keys_are_removed_on_rollback(self):
        registry = RegistryFixture()
        with patch.dict("sys.modules", {"winreg": registry}):
            engine = self.engine(RegistryHandler())
            result = engine.run("Create setting", [Operation("registry.value.v1", {"id": "telemetry"},
                                                            {"exists": True, "type": 4, "value": 0})])
            self.assertTrue(engine.rollback(result.transaction_id, confirmed=True).success)
        self.assertEqual(registry.keys, {})

    def test_registry_rollback_preserves_unrelated_values_created_later(self):
        registry = RegistryFixture()
        with patch.dict("sys.modules", {"winreg": registry}):
            engine = self.engine(RegistryHandler())
            result = engine.run("Create setting", [Operation("registry.value.v1", {"id": "game_dvr"},
                                                            {"exists": True, "type": 4, "value": 0})])
            key = registry.HKEY_CURRENT_USER, r"System\GameConfigStore"
            registry.SetValueEx(key, "UnrelatedUserSetting", 0, 4, 17)
            restored = engine.rollback(result.transaction_id, confirmed=True)
        self.assertEqual(restored.status, "Partial Recovery")
        self.assertEqual(registry.keys[key], {"UnrelatedUserSetting": (17, 4)})

    def test_unknown_registry_locations_and_direct_writes_are_rejected(self):
        handler = RegistryHandler()
        with self.assertRaises(RecoveryError):
            handler.validate({"id": "HKLM\\SAM"}, {"exists": False})
        with self.assertRaises(RecoveryError):
            handler.apply({"id": "game_dvr"}, {"exists": True, "type": 4, "value": 0})
        runner = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="{}", stderr="")
        with self.assertRaises(RecoveryError):
            WindowsBackend(runner).service_write("alpha", {"running": False})

    def test_service_partial_failure_restores_startup_and_running_state(self):
        backend = ServiceFixture()
        backend.fail_stop = True
        original = deepcopy(backend.services)
        engine = self.engine(ServiceHandler(backend), "service.config.v1")
        result = engine.run("Stop service", [Operation("service.config.v1", {"name": "alpha"},
                                                      {"startup": "Disabled", "running": False})])
        self.assertFalse(result.success)
        self.assertEqual(result.status, "Recovered")
        self.assertEqual(backend.services, original)

    def test_service_dependency_order_and_case_insensitive_resource_locking(self):
        backend = ServiceFixture()
        backend.services["alpha"]["dependencies"] = ["beta"]
        engine = self.engine(ServiceHandler(backend), "service.config.v1")
        result = engine.run("Stop dependency group", [
            Operation("service.config.v1", {"name": "beta"}, {"running": False}),
            Operation("service.config.v1", {"name": "alpha"}, {"running": False})])
        self.assertTrue(result.success)
        self.assertEqual(backend.calls, ["alpha", "beta"])
        engine.rollback(result.transaction_id, confirmed=True)
        self.assertEqual(backend.calls[-2:], ["beta", "alpha"])
        preview = engine.prepare("Prepared", [Operation("service.config.v1", {"name": "Alpha"}, {"running": False})])
        with self.assertRaises(RecoveryError):
            engine.prepare("Same resource", [Operation("service.config.v1", {"name": "alpha"}, {"running": False})])
        engine.cancel(preview["transaction_id"])

    def test_critical_services_cannot_be_disabled(self):
        handler = ServiceHandler(ServiceFixture())
        with self.assertRaises(RecoveryError):
            handler.classify({"name": "RpcSs"}, {"running": False})

    def test_hosts_file_round_trip_is_limited_to_the_configured_file(self):
        hosts = self.folder / "fixture-hosts"
        original = b"127.0.0.1 localhost\r\n# Original bytes\r\n"
        hosts.write_bytes(original)
        engine = self.engine(HostsHandler(hosts), "file.hosts.v1")
        encoded = base64.b64encode(b"127.0.0.1 localhost\n0.0.0.0 example.invalid\n").decode("ascii")
        result = engine.run("Edit hosts", [Operation("file.hosts.v1", {"scope": "Windows hosts file"}, {"content_base64": encoded})])
        self.assertTrue(result.success)
        self.assertTrue(engine.rollback(result.transaction_id, confirmed=True).success)
        self.assertEqual(hosts.read_bytes(), original)

    def test_powershell_resource_names_are_passed_as_json_and_never_interpolated(self):
        calls = []
        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            return SimpleNamespace(returncode=0, stdout="{}", stderr="")
        name = "User's service & $(this must stay data)"
        with patch("src.core.recovery.windows.sys.platform", "win32"):
            WindowsBackend(runner).service_read(name)
        arguments, kwargs = calls[0]
        script = base64.b64decode(arguments[-1]).decode("utf-16-le")
        self.assertNotIn(name, script)
        self.assertEqual(json.loads(kwargs["env"]["GHOSTY_RECOVERY_DATA"]), {"name": name})
        self.assertIn("-NonInteractive", arguments)
        self.assertGreater(kwargs["timeout"], 0)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell parser required")
    def test_native_script_syntax_without_executing_any_windows_actions(self):
        tree = ast.parse((ROOT / "src/core/recovery/windows.py").read_text(encoding="utf-8"))
        scripts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "ps" and node.args:
                try:
                    value = ast.literal_eval(node.args[0])
                except (ValueError, TypeError):
                    continue
                if isinstance(value, str):
                    scripts.append(value)
        parser = """
        $ErrorActionPreference='Stop'; $scripts=ConvertFrom-Json $env:GHOSTY_PARSE_ONLY;
        foreach ($script in $scripts) {
          $tokens=$null; $errors=$null;
          [System.Management.Automation.Language.Parser]::ParseInput($script,[ref]$tokens,[ref]$errors) | Out-Null;
          if ($errors.Count) {throw ($errors.Message -join '; ')}
        }
        """
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", parser],
            env={**os.environ, "GHOSTY_PARSE_ONLY": json.dumps(scripts)}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
