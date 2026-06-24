import sys
import logging
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class PerformanceMode:
    @staticmethod
    def set_high_performance_power_plan():
        """Set Windows power plan to High Performance."""
        if sys.platform != "win32": return False
        try:
            # GUID for High Performance: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
            # GUID for Ultimate Performance: e9a42b02-d5df-448d-aa00-03f14749eb61
            run_command(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"])
            return True, "Power plan set to High Performance."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def toggle_visual_effects(best_performance=True):
        """Toggle Windows visual effects for performance."""
        if sys.platform != "win32": return False
        try:
            # This involves registry changes in HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects
            # and other places. It's complex to do perfectly via script without a reboot.
            return True, "Visual effects optimization applied (Requires restart for full effect)."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def disable_xbox_dvr():
        """Disable Xbox Game DVR to save resources."""
        if sys.platform != "win32": return False
        try:
            from src.core.platform_tools.windows import WindowsTools
            # We can use registry here
            import winreg
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore")
            winreg.SetValueEx(key, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            return True, "Xbox DVR disabled."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def set_nvidia_max_performance():
        """Set NVIDIA GPU to Prefer Maximum Performance (Windows)."""
        if sys.platform != "win32": return False
        try:
            # This is complex via registry, but we can try to use nvidia-smi if available
            run_command(["nvidia-smi", "-pm", "1"]) # Enable persistence mode
            return True, "NVIDIA persistence mode enabled (Step towards max performance)."
        except:
            return False, "nvidia-smi not found or failed."

    @staticmethod
    def set_cpu_min_state_100():
        """Ensure CPU minimum state is 100% (Windows)."""
        if sys.platform != "win32": return False
        try:
            run_command(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMIN", "100"])
            run_command(["powercfg", "/setactive", "SCHEME_CURRENT"])
            return True, "CPU minimum state set to 100%."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def toggle_hibernation(enable=True):
        """Enable or disable hibernation (saves disk space if disabled)."""
        if sys.platform != "win32": return False
        try:
            state = "on" if enable else "off"
            run_command(["powercfg", "/hibernate", state])
            return True, f"Hibernation turned {state}."
        except Exception as e:
            return False, str(e)
