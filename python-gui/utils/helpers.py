import os
import sys
import logging

# Set up logging
logger = logging.getLogger(__name__)

def setup_app_logging():
    """Configure logging to both console (if available) and a file in the user's data directory."""
    try:
        config_dir = get_config_dir()
        log_dir = os.path.join(config_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "app.log")
        
        # Max size 1MB, keep 3 backup files
        from logging.handlers import RotatingFileHandler
        
        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # File handler
        file_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=3)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Stream handler (console)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        
        logging.info(f"Logging initialized. Log file: {log_file}")
    except Exception as e:
        print(f"Failed to initialize logging: {e}", file=sys.stderr)

def get_resource_path(relative_path):
    """Return absolute path to resource, works for dev and PyInstaller."""
    # Ensure relative_path is using correct separators for the OS
    relative_path = relative_path.replace('/', os.sep).replace('\\', os.sep)
    
    # Locations to search
    search_paths = []
    
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller temp folder
        base_path = sys._MEIPASS
        search_paths.append(os.path.join(base_path, relative_path))
        
        # Check if it's flattened
        search_paths.append(os.path.join(base_path, os.path.basename(relative_path)))
        
        # Check for config specifically if it's a config file
        if "config" in relative_path:
            search_paths.append(os.path.join(base_path, "config", os.path.basename(relative_path)))
    else:
        # Development mode - we assume we're in 'python-gui/utils'
        # So we go up two levels to get to the true project root
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        search_paths.append(os.path.join(base_path, relative_path))
        
        # If relative_path starts with python-gui, also try without it
        if relative_path.startswith(f"python-gui{os.sep}"):
            shorter_path = relative_path[len(f"python-gui{os.sep}"):]
            search_paths.append(os.path.join(base_path, shorter_path))
            # Also try from current directory
            search_paths.append(os.path.join(os.getcwd(), relative_path))
            search_paths.append(os.path.join(os.getcwd(), shorter_path))
    
    for path in search_paths:
        if os.path.exists(path):
            logger.debug(f"Resource found: {path}")
            return path
            
    # If not found in any search path, return the first one as a default
    default_path = search_paths[0] if search_paths else os.path.join(os.getcwd(), relative_path)
    logger.warning(f"Resource not found: {relative_path}. Returning default: {default_path}")
    return default_path

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
        # Prepare environment: remove ALL PyInstaller-related variables to ensure the new process 
        # extracts itself correctly instead of trying to use the current process's temporary directory.
        # This prevents "Failed to load Python DLL" errors when relaunching after elevation or update.
        for key in list(os.environ.keys()):
            # _MEIPASS and _MEIPASS2 are critical. Any PYI_* variables should also be cleared.
            if key in ('_MEIPASS', '_MEIPASS2', 'PYI_CHILD_PATH', 'PYTHONHOME', 'PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY') or key.startswith('PYI'):
                del os.environ[key]
        
        # Clean PATH of any _MEI references to prevent loading DLLs from the wrong temp folder
        if 'PATH' in os.environ:
            paths = os.environ['PATH'].split(os.pathsep)
            os.environ['PATH'] = os.pathsep.join([p for p in paths if '_MEI' not in p])
            
        # Using ShellExecuteW with "runas" is the standard way to elevate on Windows.
        # It inherits the current process's modified environment (with PyInstaller variables removed).
        ctypes.windll.shell32.ShellExecuteW(None, "runas", str(executable), str(params), None, 1)
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
