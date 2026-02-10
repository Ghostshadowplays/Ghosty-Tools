import os
import sys
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

def get_config_dir():
    """Get platform-specific configuration directory"""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        path = os.path.join(base, 'GhostyTools')
    else:
        path = os.path.join(os.path.expanduser('~'), '.config', 'ghostytools')
    
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        try:
            if sys.platform != 'win32':
                os.chmod(path, 0o700)
        except Exception:
            pass
    return path

def is_admin():
    """Check if the script is running with administrator/root privileges"""
    if sys.platform == 'win32':
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception as e:
            logger.error(f"Error checking admin privileges: {e}")
            return False
    else:
        # Linux/Mac
        try:
            return os.getuid() == 0
        except AttributeError:
            return False

def elevate_privileges():
    """Attempt to elevate privileges. Only implemented for Windows."""
    if sys.platform != 'win32':
        logger.warning("Elevation not implemented for this platform.")
        return

    import ctypes
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        executable = sys.executable
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    else:
        # Running as Python script
        executable = sys.executable
        # Re-run the current script
        params = ' '.join([f'"{sys.argv[0]}"'] + [f'"{arg}"' for arg in sys.argv[1:]])

    try:
        # Prepare environment: remove _MEIPASS so the elevated process extracts itself properly
        # instead of trying to use the current process's temporary directory.
        if '_MEIPASS' in os.environ:
            del os.environ['_MEIPASS']
            
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    except Exception as e:
        logger.error(f"Failed to elevate privileges: {e}")
    sys.exit()

def ensure_private_file(path: str):
    """Best-effort to restrict file visibility/permissions for sensitive files.
    - On Linux/Mac: chmod 600
    - On Windows: set Hidden attribute (does not enforce ACL, but reduces visibility)
    """
    try:
        if sys.platform == 'win32':
            try:
                import ctypes
                FILE_ATTRIBUTE_HIDDEN = 0x2
                ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
            except Exception:
                pass
        else:
            os.chmod(path, 0o600)
    except Exception:
        # Best-effort; ignore failures
        pass
