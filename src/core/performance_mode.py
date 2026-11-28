import sys
import logging

logger = logging.getLogger(__name__)

class PerformanceMode:
    @staticmethod
    def set_high_performance_power_plan():
        if sys.platform != "win32":
            return False, "Only supported on Windows."
        from src.core.recovery.integration import run_operations
        from src.core.recovery.models import Operation
        return run_operations("Activate High Performance power plan", [Operation("power.active.v1",
            {"scope": "Active power plan"}, {"scheme": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"}, "Change active power plan")])

    @staticmethod
    def toggle_visual_effects(best_performance=True):
        return False, "No verified visual-effects handler is available; no settings were changed."

    @staticmethod
    def disable_xbox_dvr():
        if sys.platform != "win32":
            return False, "Only supported on Windows."
        from src.core.recovery.integration import registry_operation, run_operations
        return run_operations("Disable Xbox Game DVR", [registry_operation("game_dvr", 0)])

    @staticmethod
    def set_nvidia_max_performance():
        return False, "NVIDIA persistence-mode changes require a validated Windows driver handler; no settings were changed."

    @staticmethod
    def set_cpu_min_state_100():
        if sys.platform != "win32":
            return False, "Only supported on Windows."
        from src.core.recovery.integration import get_engine, run_operations
        from src.core.recovery.models import Operation
        try:
            scheme = get_engine().handlers["power.active.v1"].backend.power_read()["scheme"]
            return run_operations("Set AC CPU minimum state", [Operation("power.cpu_min.v1",
                {"scheme": scheme, "setting": "cpu_min"}, {"ac": 100}, "Set AC CPU minimum state to 100 percent")])
        except Exception as error:
            return False, str(error)

    @staticmethod
    def toggle_hibernation(enable=True):
        if sys.platform != "win32":
            return False, "Only supported on Windows."
        from src.core.recovery.integration import run_operations
        from src.core.recovery.models import Operation
        return run_operations("Change Windows hibernation", [Operation("power.hibernate.v1",
            {"scope": "Windows hibernation"}, {"enabled": bool(enable)},
            "Change hibernation configuration; a previous hibernation image cannot be recovered")])
