"""Application entry points share one engine and one set of approved handlers."""

from functools import wraps
from pathlib import Path
import sys
import threading

from src.utils.helpers import get_config_dir, is_admin
from .engine import SecurityRecoveryEngine
from .models import Operation, RecoveryError
from .store import RecoveryStore
from .windows import REGISTRY, WindowsBackend, handlers


_engine: SecurityRecoveryEngine | None = None
_factory_lock = threading.Lock()
_approval = None


def get_engine() -> SecurityRecoveryEngine:
    global _engine
    with _factory_lock:
        root = Path(get_config_dir()) / "Security" / "Recovery"
        if _engine is None or _engine.store.root != root:
            from src.core.update_manager import CURRENT_VERSION
            from .watchdog import ConnectivityWatchdog
            backend = WindowsBackend()
            store = RecoveryStore(root)
            _engine = SecurityRecoveryEngine(store, handlers(backend), app_version=CURRENT_VERSION,
                is_admin=is_admin, approve=_approval, watchdog=ConnectivityWatchdog(store),
                restore_point=backend.restore_point)
        return _engine


def set_approval_handler(callback) -> None:
    global _approval
    _approval = callback
    if _engine is not None:
        _engine.approve = callback


def registry_operation(name, value=None, *, exists=True):
    if name not in REGISTRY:
        raise RecoveryError("Unsupported registry setting")
    desired = {"exists": exists}
    if exists:
        desired.update(value=value, type=REGISTRY[name][3])
    return Operation("registry.value.v1", {"id": name}, desired, name.replace("_", " "))


def service_operation(name, **desired):
    return Operation("service.config.v1", {"name": name}, desired, f"Configure service {name}")


def run_operations(label: str, operations: list[Operation], *, profile="") -> tuple[bool, str]:
    try:
        result = get_engine().run(label, operations, profile=profile)
        return result.success, f"{result.message}\nTransaction: {result.transaction_id}"
    except Exception as error:
        return False, f"System change was not completed: {error}. Review Recovery Centre before retrying."


def require_success(result):
    success, message = result
    if not success:
        raise RecoveryError(message)
    return message


def restore_profile(profile: str) -> tuple[bool, str]:
    try:
        engine = get_engine()
        record = next((record for record in engine.transactions()
                       if record.get("profile") == profile and record["status"] == "Completed"), None)
        if record is None:
            raise RecoveryError("No captured configuration exists for this profile; assumed defaults will not be applied")
        assessment = engine.assessment(record["transaction_id"])
        if not engine.approve or not engine.approve({"type": "rollback", "assessment": assessment}):
            return False, "Recovery cancelled; current configuration was retained"
        result = engine.rollback(record["transaction_id"], confirmed=True)
        return result.success, f"{result.message}\nTransaction: {result.transaction_id}"
    except Exception as error:
        return False, str(error)


def windows_only_plan(builder):
    """Keep the old public method signature while centralising Windows writes."""
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            if sys.platform != "win32":
                return function(*args, **kwargs)
            return builder(*args, **kwargs)
        guarded.recovery_managed = True
        return guarded
    return decorate


def gaming_operations() -> list[Operation]:
    changes = {"game_capture": 0, "game_dvr": 0, "game_dvr_policy": 0, "auto_game_mode": 1,
               "game_panel": 0, "game_nexus": 0, "gpu_preference": "SwapEffectUpgradeEnable=1;",
               "fullscreen_mode": 2, "fullscreen_honor": 1, "fullscreen_behavior": 2,
               "update_policy": 1, "mmcss_gpu": 8, "mmcss_priority": 6, "mmcss_category": "High"}
    operations = [registry_operation(name, value) for name, value in changes.items()]
    operations.extend(service_operation(name, startup="Disabled", running=False)
                      for name in ("SysMain", "wuauserv", "UsoSvc", "WaaSMedicSvc"))
    operations.append(Operation("power.active.v1", {"scope": "Active power plan"},
                                {"scheme": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"}, "Activate High Performance power plan"))
    return operations


TWEAKS = {
    "disable_telemetry": {"telemetry": 0}, "disable_activity": {"activity_history": 0},
    "disable_gamedvr": {"game_dvr": 0, "game_dvr_policy": 0},
    "disable_homegroup": {"homegroup": 0xb094010c}, "prefer_ipv4": {"ipv4_preference": 0x20},
    "disable_location": {"location": 1}, "disable_storage_sense": {"storage_sense": 0},
    "disable_wifi_sense": {"wifi_sense": 0}, "enable_end_task": {"end_task": 1},
    "disable_web_search": {"bing_search": 0, "cortana": 0, "search_suggestions": 1},
    "classic_context_menu": {"classic_menu": ""}, "disable_ad_id": {"advertising_id": 0},
    "disable_spotlight": {"spotlight": 1}, "disable_copilot": {"copilot_policy": 1, "copilot_button": 0},
    "disable_news": {"news_policy": 0, "news_button": 2}, "show_file_ext": {"file_extensions": 0},
    "show_hidden": {"hidden_files": 1, "system_files": 1}, "disable_game_mode": {"game_mode": 0},
    "disable_background_apps": {"background_apps": 1, "background_search": 0},
    "disable_fast_startup": {"fast_startup": 0},
}


def tweak_operations(selected: list[str]) -> list[Operation]:
    values = {}
    services = {}
    extras = []
    for name in selected:
        if name in TWEAKS:
            values.update(TWEAKS[name])
        elif name == "disable_search_indexing":
            services["WSearch"] = {"startup": "Disabled", "running": False}
        elif name == "disable_sysmain":
            services["SysMain"] = {"startup": "Disabled", "running": False}
        elif name == "set_services_manual":
            services.update({service: {"startup": "Manual"} for service in ("DiagTrack", "dmwappushservice", "RemoteRegistry")})
        elif name == "ultimate_performance":
            extras.append(Operation("power.active.v1", {"scope": "Active power plan"},
                                    {"scheme": "e9a42b02-d5df-448d-aa00-03f14749eb61"}, "Activate installed Ultimate Performance plan"))
        elif name == "disable_hibernation":
            extras.append(Operation("power.hibernate.v1", {"scope": "Windows hibernation"}, {"enabled": False},
                                    "Disable hibernation; existing hibernation image cannot be recovered"))
        else:
            raise RecoveryError(f"{name} does not yet have a validated recovery handler; no selected changes were started")
    return ([registry_operation(name, value) for name, value in values.items()] +
            [service_operation(name, **desired) for name, desired in services.items()] + extras)


def hardening_profiles() -> dict[str, list[Operation]]:
    firewall = Operation("firewall.profiles.v1", {"scope": "Windows Firewall"},
                         {"Domain": True, "Private": True, "Public": True}, "Enable Windows Firewall protection")
    return {
        "Home User": [firewall],
        "Gamer": [registry_operation("auto_game_mode", 1), registry_operation("game_dvr", 0)],
        "Home Lab": [firewall],
        "Security Hardened": [firewall, registry_operation("telemetry", 0), registry_operation("activity_history", 0)],
        "Custom": [firewall, *[registry_operation(name, value) for name, value in
                              {"auto_game_mode": 1, "game_dvr": 0, "telemetry": 0, "activity_history": 0}.items()]],
    }


def security_operations(action_key: str) -> list[Operation]:
    if action_key == "enable_firewall":
        return hardening_profiles()["Home User"]
    if action_key == "enable_uac":
        return [registry_operation("uac", 1)]
    if action_key == "enable_windows_update":
        return [registry_operation("update_policy", exists=False)]
    if action_key in {"enable_defender_rt", "disable_guest", "disable_smbv1"}:
        name, desired = {"enable_defender_rt": ("defender", {"enabled": True}),
                         "disable_guest": ("guest", {"enabled": False}),
                         "disable_smbv1": ("smbv1", {"state": "Disabled"})}[action_key]
        return [Operation("security.setting.v1", {"id": name}, desired, action_key.replace("_", " "))]
    if action_key in {"enable_rdp", "disable_rdp"}:
        enabled = action_key == "enable_rdp"
        engine = get_engine()
        names = engine.handlers["firewall.enabled.v1"].backend.ps(
            "@(Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object Name -like 'RemoteDesktop*' | "
            "ForEach-Object {$_.Name}) | ConvertTo-Json -Compress")
        if isinstance(names, str):
            names = [names]
        if not names:
            raise RecoveryError("Remote Desktop firewall rules are unavailable; no configuration was changed")
        return [registry_operation("rdp", 0 if enabled else 1)] + [
            Operation("firewall.enabled.v1", {"name": name}, {"enabled": enabled}, "Configure Remote Desktop firewall access")
            for name in names]
    raise RecoveryError("No validated recovery plan exists for this security action")
