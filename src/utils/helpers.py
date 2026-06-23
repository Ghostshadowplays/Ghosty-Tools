import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """Return absolute path to resource, works for dev and PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # Go up two levels from src/utils/helpers.py to reach project root
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)

def get_config_dir():
    """Get platform-specific configuration directory"""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        path = os.path.join(base, 'GhostyTools')
    else:
        # Linux/macOS
        path = os.path.join(os.path.expanduser('~'), '.config', 'GhostyTools')
    
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        try:
            if sys.platform != 'win32':
                os.chmod(path, 0o700)
        except Exception:
            pass
    return path

def get_logs_dir():
    """Get platform-specific logs directory"""
    config_dir = get_config_dir()
    logs_dir = os.path.join(config_dir, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, exist_ok=True)
    return logs_dir

def get_os_info():
    """Return a dictionary with OS information"""
    import platform
    return {
        "os": sys.platform,
        "platform": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine()
    }

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
        # Prepare environment: remove PyInstaller variables to ensure the new process extracts itself correctly
        # instead of trying to use the current process's temporary directory.
        for key in list(os.environ.keys()):
            if key == '_MEIPASS' or key.startswith('PYI'):
                del os.environ[key]
        
        # Clean PATH of any _MEI references to prevent loading DLLs from the wrong temp folder
        if 'PATH' in os.environ:
            paths = os.environ['PATH'].split(os.pathsep)
            os.environ['PATH'] = os.pathsep.join([p for p in paths if '_MEI' not in p])
            
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

def run_command(cmd, **kwargs):
    """Run a subprocess command with proper encoding and error handling."""
    import subprocess
    
    # Default parameters
    params = {
        'capture_output': True,
        'text': False,  # Capture as bytes to handle encoding manually
    }
    
    # Handle creationflags for Windows to hide console window
    if sys.platform == 'win32':
        if 'creationflags' not in kwargs:
            # CREATE_NO_WINDOW = 0x08000000
            params['creationflags'] = 0x08000000
    
    # Allow overrides
    params.update(kwargs)
    
    try:
        result = subprocess.run(cmd, **params)
        
        def safe_decode(data):
            if not data:
                return ""
            # Try UTF-8 first
            try:
                decoded = data.decode('utf-8')
                # If it's full of null bytes, it's probably UTF-16
                if decoded.count('\x00') > len(decoded) / 3:
                    return data.decode('utf-16', errors='replace')
                return decoded
            except UnicodeDecodeError:
                # Try UTF-16
                try:
                    return data.decode('utf-16', errors='replace')
                except UnicodeDecodeError:
                    # Fallback to system default with replacement
                    return data.decode(sys.getdefaultencoding(), errors='replace')

        stdout_str = safe_decode(result.stdout)
        stderr_str = safe_decode(result.stderr)

        class DecodedProcess:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
        
        return DecodedProcess(result.returncode, stdout_str, stderr_str)

    except Exception as e:
        logger.error(f"Error running command {cmd}: {e}")
        class FailedProcess:
            def __init__(self, error):
                self.returncode = -1
                self.stdout = ""
                self.stderr = str(error)
        return FailedProcess(e)
