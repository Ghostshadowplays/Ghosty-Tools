import os
import sys
import logging
import shutil
from src.utils.helpers import run_command, is_admin

logger = logging.getLogger(__name__)

class CleanupEngine:
    def __init__(self):
        self.is_windows = sys.platform == "win32"

    def get_windows_update_cache_size(self):
        if not self.is_windows: return 0
        path = r"C:\Windows\SoftwareDistribution\Download"
        return self._get_dir_size(path)

    def clean_windows_update_cache(self):
        if not self.is_windows: return False, "Only available on Windows."
        if not is_admin(): return False, "Administrator privileges required."
        
        try:
            run_command(["net", "stop", "wuauserv"])
            path = r"C:\Windows\SoftwareDistribution\Download"
            self._empty_dir(path)
            run_command(["net", "start", "wuauserv"])
            return True, "Windows Update cache cleaned."
        except Exception as e:
            return False, str(e)

    def clean_cbs_logs(self):
        if not self.is_windows: return False, "Only available on Windows."
        path = r"C:\Windows\Logs\CBS"
        try:
            self._empty_dir(path)
            return True, "CBS logs cleaned."
        except Exception as e:
            return False, str(e)

    def clean_shader_cache(self):
        if not self.is_windows: return False, "Only available on Windows."
        paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\D3DSCache"),
            os.path.expandvars(r"%LOCALAPPDATA%\NVIDIA\GLCache"),
            os.path.expandvars(r"%LOCALAPPDATA%\AMD\DxCache"),
        ]
        results = []
        for path in paths:
            if os.path.exists(path):
                try:
                    self._empty_dir(path)
                    results.append(f"Cleaned {path}")
                except Exception as e:
                    results.append(f"Failed to clean {path}: {e}")
        return True, "\n".join(results)

    def clean_launcher_caches(self):
        paths = {
            "Steam":       os.path.expandvars(r"%LOCALAPPDATA%\Steam\htmlcache") if self.is_windows else None,
            "Epic Games":  os.path.expandvars(r"%LOCALAPPDATA%\EpicGamesLauncher\Saved\webcache") if self.is_windows else None,
            "Riot Client": os.path.expandvars(r"%LOCALAPPDATA%\Riot Games\Riot Client\UX\Cache") if self.is_windows else None,
            "GOG Galaxy":  os.path.expandvars(r"%LOCALAPPDATA%\GOG.com\Galaxy\webcache") if self.is_windows else None,
            "EA Desktop":  os.path.expandvars(r"%LOCALAPPDATA%\Electronic Arts\EA Desktop\Cache") if self.is_windows else None,
            "Battle.net":  os.path.expandvars(r"%LOCALAPPDATA%\Battle.net\Cache") if self.is_windows else None,
        }
        results = []
        for name, path in paths.items():
            if path and os.path.exists(path):
                try:
                    self._empty_dir(path)
                    results.append(f"Cleaned {name} cache.")
                except Exception as e:
                    results.append(f"Failed to clean {name} cache: {e}")
        return True, "\n".join(results) if results else "No launcher caches found."

    def detect_windows_old(self):
        if not self.is_windows: return None
        path = r"C:\Windows.old"
        if os.path.exists(path):
            size = self._get_dir_size(path)
            return f"Windows.old detected ({size / (1024**3):.2f} GB). Use Disk Cleanup to remove it safely."
        return None

    def find_large_files(self, root_dir, min_size_mb=100):
        large_files = []
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                path = os.path.join(root, file)
                try:
                    size = os.path.getsize(path)
                    if size > min_size_mb * 1024 * 1024:
                        large_files.append((path, size))
                except:
                    continue
        return sorted(large_files, key=lambda x: x[1], reverse=True)

    def clean_broken_shortcuts(self, root_dir):
        if not self.is_windows: return []
        broken = []
        import win32com.client # Requires pywin32
        shell = win32com.client.Dispatch("WScript.Shell")
        
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.endswith(".lnk"):
                    path = os.path.join(root, file)
                    try:
                        shortcut = shell.CreateShortCut(path)
                        target = shortcut.Targetpath
                        if target and not os.path.exists(target):
                            broken.append(path)
                    except:
                        continue
        return broken

    def _get_dir_size(self, path):
        total = 0
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    total += os.path.getsize(fp)
        except:
            pass
        return total

    def _empty_dir(self, path):
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f'Failed to delete {file_path}. Reason: {e}')
