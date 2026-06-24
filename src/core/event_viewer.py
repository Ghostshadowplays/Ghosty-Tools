import sys
import logging
import csv
import io
from src.utils.helpers import run_command

logger = logging.getLogger(__name__)

class EventViewer:
    @staticmethod
    def get_windows_events(log_name="System", level=None, count=100):
        """Fetch Windows Event Logs."""
        if sys.platform != "win32":
            return []
        
        filter_str = ""
        if level:
            # 1: Critical, 2: Error, 3: Warning, 4: Information
            filter_str = f"| Where-Object {{ $_.Level -eq {level} }}"
            
        cmd = ["powershell", "-Command", f"Get-WinEvent -LogName {log_name} -MaxEvents {count} {filter_str} | Select-Object TimeCreated, LevelDisplayName, ProviderName, Message | ConvertTo-Json"]
        proc = run_command(cmd)
        
        import json
        try:
            return json.loads(proc.stdout)
        except:
            return []

    @staticmethod
    def export_to_csv(events, filename):
        """Export events to CSV."""
        if not events: return False
        try:
            keys = events[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                dict_writer = csv.DictWriter(f, keys)
                dict_writer.writeheader()
                dict_writer.writerows(events)
            return True
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return False

    @staticmethod
    def get_friendly_explanation(event_id):
        """Provide a friendly explanation for common event IDs."""
        # Mapping common Windows event IDs to friendly text
        explanations = {
            6005: "The Event Log service was started. This occurs at boot.",
            6006: "The Event Log service was stopped. This occurs at shutdown.",
            7036: "A service changed its state (e.g., started or stopped).",
            10016: "A DCOM permission error. Usually harmless and common on Windows.",
            41: "The system has rebooted without cleanly shutting down first (Kernel-Power).",
        }
        return explanations.get(event_id, "No specific explanation available for this Event ID.")
