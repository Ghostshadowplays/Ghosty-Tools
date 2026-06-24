import sys
from src.core.platform_tools.windows import WindowsTools
from src.core.platform_tools.linux import LinuxTools
from src.core.platform_tools.macos import MacOSTools

def get_platform_tools():
    if sys.platform == "win32":
        return WindowsTools()
    elif sys.platform == "linux":
        return LinuxTools()
    elif sys.platform == "darwin":
        return MacOSTools()
    else:
        raise NotImplementedError(f"Platform {sys.platform} is not supported.")
