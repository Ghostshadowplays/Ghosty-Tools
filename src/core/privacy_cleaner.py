import os
import shutil
import logging
import sys

logger = logging.getLogger(__name__)

class PrivacyCleaner:
    @staticmethod
    def get_browser_paths():
        """Get paths to browser profile/cache directories."""
        paths = []
        if sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            appdata = os.environ.get("APPDATA", "")
            
            # Chrome
            paths.append({"name": "Chrome Cache", "path": os.path.join(local_appdata, "Google", "Chrome", "User Data", "Default", "Cache")})
            # Edge
            paths.append({"name": "Edge Cache", "path": os.path.join(local_appdata, "Microsoft", "Edge", "User Data", "Default", "Cache")})
            # Firefox
            firefox_profiles = os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
            if os.path.exists(firefox_profiles):
                for profile in os.listdir(firefox_profiles):
                    paths.append({"name": f"Firefox Cache ({profile})", "path": os.path.join(local_appdata, "Mozilla", "Firefox", "Profiles", profile, "cache2")})
        
        elif sys.platform == "linux":
            home = os.path.expanduser("~")
            # Chrome
            paths.append({"name": "Chrome Cache", "path": os.path.join(home, ".cache", "google-chrome", "Default", "Cache")})
            # Firefox
            firefox_path = os.path.join(home, ".mozilla", "firefox")
            if os.path.exists(firefox_path):
                for item in os.listdir(firefox_path):
                    if os.path.isdir(os.path.join(firefox_path, item)) and "." in item:
                        paths.append({"name": f"Firefox Cache ({item})", "path": os.path.join(home, ".cache", "mozilla", "firefox", item, "cache2")})
        
        elif sys.platform == "darwin":
            home = os.path.expanduser("~")
            # Chrome
            paths.append({"name": "Chrome Cache", "path": os.path.join(home, "Library", "Caches", "Google", "Chrome", "Default", "Cache")})
            # Safari
            paths.append({"name": "Safari Cache", "path": os.path.join(home, "Library", "Caches", "com.apple.Safari", "fsCachedData")})
            
        return [p for p in paths if os.path.exists(p["path"])]

    @staticmethod
    def clean_browser_data(path):
        """Clean data at the specified path."""
        try:
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                    os.makedirs(path)
                return True, f"Cleaned {path}"
        except Exception as e:
            logger.error(f"Error cleaning {path}: {e}")
            return False, str(e)
        return False, "Path does not exist."

    @staticmethod
    def run_privacy_audit():
        """Run a privacy audit checklist."""
        results = []
        if sys.platform == "win32":
            # Check for location services, telemetry, etc. (simplified placeholders)
            results.append({"name": "Location Services", "status": "Enabled", "recommendation": "Disable in Settings > Privacy"})
            results.append({"name": "Telemetry (DiagTrack)", "status": "Running", "recommendation": "Disable in Services.msc"})
            results.append({"name": "Advertising ID", "status": "Enabled", "recommendation": "Disable in Settings > Privacy"})
        
        elif sys.platform == "linux":
            results.append({"name": "Automatic Error Reporting", "status": "Likely Enabled", "recommendation": "Check /etc/default/apport"})
            results.append({"name": "Geo-location", "status": "Check System Settings", "recommendation": "Disable if not needed"})
            
        return results
