import os
import sys
import ctypes
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        logger.error(f"Error checking admin privileges: {e}")
        return False

def elevate_privileges():
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        executable = sys.executable
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    else:
        # Running as Python script
        executable = sys.executable
        params = ' '.join([f'"{arg}"' for arg in sys.argv])

    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    except Exception as e:
        logger.error(f"Failed to elevate privileges: {e}")
    sys.exit()
