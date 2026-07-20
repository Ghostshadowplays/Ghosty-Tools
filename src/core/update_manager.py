import requests
import logging
import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from src.utils.helpers import get_config_dir, get_resource_path, get_logs_dir

logger = logging.getLogger(__name__)

# Use get_resource_path to ensure we read the bundled version.json in frozen EXEs
CURRENT_VERSION = "v8.0.1"
try:
    _version_path = get_resource_path(os.path.join("config", "version.json"))
    if os.path.exists(_version_path):
        with open(_version_path, "r") as _f:
            CURRENT_VERSION = json.load(_f).get("version", "v8.0.1")
except Exception as e:
    logger.error(f"Failed to load version: {e}")

REPO_URL = "https://api.github.com/repos/Ghostshadowplays/Ghosty-Tools/releases/latest"

class UpdateManager:
    def __init__(self):
        self.current_version = CURRENT_VERSION
        self.config_dir = get_config_dir()
        self.version_file = os.path.join(self.config_dir, "version_info.json")

    def check_for_updates(self):
        """Checks GitHub API for the latest release."""
        try:
            headers = {'User-Agent': 'GhostyTools/1.0'}
            response = requests.get(REPO_URL, timeout=10, headers=headers)
            response.raise_for_status()
            data = response.json()
            latest_version = data.get("tag_name", "")
            
            if latest_version and self._is_newer(latest_version, self.current_version):
                return {
                    "available": True,
                    "latest_version": latest_version,
                    "release_notes": data.get("body", ""),
                    "download_url": data.get("html_url", ""),
                    "assets": data.get("assets", [])
                }
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
        
        return {"available": False}

    def _is_newer(self, remote, local):
        """Returns True if remote version is strictly newer than local."""
        def normalize(v):
            if not v: return [0]
            # Remove 'v' and suffixes like '-beta'
            v_clean = v.lower().lstrip('v').split('-')[0]
            return [int(x) for x in v_clean.split('.') if x.isdigit()]
        
        try:
            r_parts = normalize(remote)
            l_parts = normalize(local)
            
            # Compare part by part
            for i in range(max(len(r_parts), len(l_parts))):
                rv = r_parts[i] if i < len(r_parts) else 0
                lv = l_parts[i] if i < len(l_parts) else 0
                if rv > lv: return True
                if rv < lv: return False
            return False
        except Exception:
            # Fallback to simple inequality if parsing fails
            return remote != local

    def backup_current_binary(self):
        """Creates a backup of the current binary in the user config dir, not next to the exe."""
        try:
            current_exe = sys.executable
            exe_name = os.path.basename(current_exe)
            backup_dir = self.config_dir  # %APPDATA%\GhostyTools
            backup_path = os.path.join(backup_dir, exe_name + ".bak")
            shutil.copy2(current_exe, backup_path)
            logger.info(f"Created backup of current binary at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    def rollback(self, backup_path):
        """Restores the backup binary if update fails."""
        try:
            current_exe = sys.executable
            if os.path.exists(backup_path):
                # This might need to be done by the external updater if the main EXE is replaced but corrupted
                # But if it's just a download failure, we still have the original EXE.
                # If we are here, it means the update process (download/prepare) failed.
                logger.warning(f"Update failed. Rollback initiated from {backup_path}")
                log_file = os.path.join(get_logs_dir(), "rollback.log")
                with open(log_file, "a") as f:
                    f.write(f"{datetime.now().isoformat()} - Rollback due to update failure\n")
                return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
        return False

    def get_last_seen_version(self):
        """Returns the version the user last acknowledged."""
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, "r") as f:
                    data = json.load(f)
                    return data.get("last_version", "")
            except Exception as e:
                logger.error(f"Failed to read version file: {e}")
        return ""

    def acknowledge_current_version(self):
        """Saves the current version as acknowledged."""
        try:
            with open(self.version_file, "w") as f:
                json.dump({"last_version": self.current_version}, f)
        except Exception as e:
            logger.error(f"Failed to save version file: {e}")

    def get_release_info(self, version=None):
        """Fetches info for a specific version or latest."""
        try:
            # For simplicity, we usually want the latest info if it matches current_version
            headers = {'User-Agent': 'GhostyTools/1.0'}
            response = requests.get(REPO_URL, timeout=10, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            logger.error(f"Failed to fetch release info: {e}")
            return None

class UpdateWorker(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, download_url, target_path, delta_url=None):
        super().__init__()
        self.download_url = download_url
        self.target_path = target_path
        self.delta_url = delta_url

    def run(self):
        try:
            # Try delta patching first if supported/available
            if self.delta_url:
                self.status.emit("Attempting delta update...")
                if self._apply_delta_update():
                    self.status.emit("Delta update applied successfully.")
                    self.finished.emit(True, self.target_path)
                    return
                else:
                    self.status.emit("Delta update failed. Falling back to full download.")

            self.status.emit("Downloading full update...")
            headers = {
                'User-Agent': 'GhostyTools-Updater/1.0'
            }
            response = requests.get(self.download_url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded = 0
            # Ensure target directory exists
            os.makedirs(os.path.dirname(self.target_path), exist_ok=True)
            
            with open(self.target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self.progress.emit(int(downloaded * 100 / total_size))
            
            self.status.emit("Download complete. Preparing to apply update...")
            self.finished.emit(True, self.target_path)
        except Exception as e:
            logger.error(f"Update download failed: {e}")
            self.status.emit(f"Update failed: {str(e)}")
            self.finished.emit(False, str(e))

    def _apply_delta_update(self):
        """
        Placeholder for delta update logic.
        In a real scenario, this would download a binary diff and apply it to the current EXE.
        """
        # For now, we return False to trigger full download, 
        # as we don't have a delta generation system in place yet.
        return False
