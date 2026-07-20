import subprocess
import logging
import json
import os
import sys
import re

import requests
import zipfile
try:
    import winreg
except ImportError:
    winreg = None
import platform
import psutil

# speedtest-cli tries to access sys.stdout.fileno() which can be None in noconsole EXE
# We will import it inside the worker to ensure sys.stdout is properly handled
speedtest = None

from PyQt6.QtCore import QThread, pyqtSignal
from src.core.security_scanner import SecurityScanner

logger = logging.getLogger(__name__)

class SpeedTestWorker(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def run(self):
        # speedtest-cli may fail when sys.stdout/stderr is None (in noconsole EXE)
        # We need to ensure both streams are valid BEFORE importing.
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        null_stdout = None
        null_stderr = None
        if sys.stdout is None:
            null_stdout = open(os.devnull, 'w')
            sys.stdout = null_stdout
        if sys.stderr is None:
            null_stderr = open(os.devnull, 'w')
            sys.stderr = null_stderr

        global speedtest
        if speedtest is None:
            try:
                import speedtest as st_module
                speedtest = st_module
            except Exception as e:
                logger.error(f"Failed to import speedtest: {e}")
                self.error_occurred.emit(f"The 'speedtest-cli' module failed to load: {e}")
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                if null_stdout:
                    null_stdout.close()
                if null_stderr:
                    null_stderr.close()
                return

        try:
            # Using secure=True and a custom User-Agent to avoid 403 Forbidden errors
            # speedtest-cli's default user agent is often blocked.
            # We check for both 'headers' and '_headers' to support different versions.
            st = speedtest.Speedtest(secure=True)
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

            if hasattr(st, 'headers'):
                st.headers['User-Agent'] = user_agent
            elif hasattr(st, '_headers'):
                st._headers['User-Agent'] = user_agent

            st.get_best_server()
            download_speed = st.download() / 1_000_000
            upload_speed = st.upload() / 1_000_000
            ping = st.results.ping
            result_text = f"Download: {download_speed:.2f} Mbps\nUpload: {upload_speed:.2f} Mbps\nPing: {ping:.2f} ms"
            self.result_ready.emit(result_text)
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg:
                error_msg = "HTTP Error 403: Forbidden. This usually means Speedtest.net is blocking the request. Try again later or check for app updates."
            self.error_occurred.emit(error_msg)
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            if null_stdout:
                null_stdout.close()
            if null_stderr:
                null_stderr.close()

class MaintenanceWorker(QThread):
    finished = pyqtSignal(str)
    output = pyqtSignal(str, str)
    phase_changed = pyqtSignal(str)

    def __init__(self, drive_letter="C", check_updates=False):
        super().__init__()
        self.drive_letter = drive_letter
        self.check_updates = check_updates
        self._flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

    # ── helpers ──────────────────────────────────────────────────────────
    def _run(self, label, cmd):
        self.output.emit(f"  -> {label}...", "info")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=False, creationflags=self._flags
            )
            for line in proc.stdout:
                try:
                    text = line.decode('utf-8', errors='replace')
                except Exception:
                    text = line.decode('cp1252', errors='replace')
                for part in text.split('\r'):
                    clean = part.strip()
                    if clean and clean not in ["-", "\\", "|", "/", ".", "??"] \
                            and not re.match(r'^[\.\-\s]+$', clean):
                        self.output.emit(f"    {clean}", "debug")
            proc.wait()
            if proc.returncode == 0:
                self.output.emit(f"  OK  {label}", "success")
            else:
                self.output.emit(f"  WARN {label} (exit {proc.returncode})", "warning")
            return proc.returncode
        except Exception as e:
            self.output.emit(f"  ERR  {label}: {e}", "error")
            return -1

    def _ps(self, label, script):
        return self._run(label, ["powershell", "-NoProfile", "-NonInteractive", "-Command", script])

    def _phase(self, title):
        self.output.emit(f"\n{'=' * 56}", "info")
        self.output.emit(f"  {title}", "info")
        self.output.emit(f"{'=' * 56}", "info")
        self.phase_changed.emit(title)

    # ── entry point ──────────────────────────────────────────────────────
    def run(self):
        try:
            if sys.platform == 'win32':
                self._run_windows()
            else:
                self._run_linux()
        except Exception as e:
            self.output.emit(f"Maintenance error: {e}", "error")
            self.finished.emit(f"Error: {e}")

    def _run_linux(self):
        self._phase("System Update (APT)")
        for label, cmd in [
            ("APT Update",      ["apt", "update"]),
            ("APT Upgrade",     ["apt", "upgrade", "-y"]),
            ("APT Autoremove",  ["apt", "autoremove", "-y"]),
            ("APT Clean",       ["apt", "clean"]),
            ("Journal Cleanup", ["journalctl", "--vacuum-time=1d"]),
        ]:
            self._run(label, cmd)
        self.finished.emit("Linux system maintenance complete.")

    # ══════════════════════════════════════════════════════════════════════
    # WINDOWS — 8 PHASES
    # ══════════════════════════════════════════════════════════════════════
    def _run_windows(self):
        summary = []

        # ── Phase 1: System Repair ────────────────────────────────────────
        self._phase("Phase 1 of 8  —  System Repair")
        self._run("SFC Scan (Pass 1)", ["sfc", "/scannow"])
        self._ps("DISM CheckHealth",          "DISM.exe /Online /Cleanup-Image /CheckHealth")
        self._ps("DISM ScanHealth",           "DISM.exe /Online /Cleanup-Image /ScanHealth")
        self._ps("DISM RestoreHealth",        "DISM.exe /Online /Cleanup-Image /RestoreHealth")
        self._ps("DISM StartComponentCleanup","DISM.exe /Online /Cleanup-Image /StartComponentCleanup /ResetBase")
        self._run("SFC Scan (Pass 2 — Verification)", ["sfc", "/scannow"])
        self._ps("Stop Windows Update services",
            "Stop-Service wuauserv,bits,cryptsvc,msiserver -Force -EA SilentlyContinue")
        self._ps("Reset SoftwareDistribution folder",
            "$bak='C:\\Windows\\SoftwareDistribution.bak';"
            "if(Test-Path $bak){Remove-Item $bak -Recurse -Force -EA SilentlyContinue};"
            "if(Test-Path 'C:\\Windows\\SoftwareDistribution'){"
            "  Rename-Item 'C:\\Windows\\SoftwareDistribution' $bak -EA SilentlyContinue"
            "}")
        self._ps("Reset catroot2 folder",
            "$bak='C:\\Windows\\System32\\catroot2.bak';"
            "if(Test-Path $bak){Remove-Item $bak -Recurse -Force -EA SilentlyContinue};"
            "if(Test-Path 'C:\\Windows\\System32\\catroot2'){"
            "  Rename-Item 'C:\\Windows\\System32\\catroot2' $bak -EA SilentlyContinue"
            "}")
        self._ps("Restart Windows Update services",
            "Start-Service wuauserv,bits,cryptsvc,msiserver -EA SilentlyContinue")
        self._ps("Fix shutdown registry handlers",
            "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control' "
            "-Name 'WaitToKillServiceTimeout' -Value '5000' -EA SilentlyContinue;"
            "Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' "
            "-Name 'WaitToKillAppTimeout' -Value '5000' -EA SilentlyContinue;"
            "Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' "
            "-Name 'HungAppTimeout' -Value '4000' -EA SilentlyContinue;"
            "Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' "
            "-Name 'AutoEndTasks' -Value '1' -EA SilentlyContinue;"
            "Write-Host 'Shutdown handlers optimized.'")
        self._ps("Force GPUpdate", "gpupdate /force")
        summary.append("System Repair  (SFC x2, DISM CheckHealth/ScanHealth/RestoreHealth/ComponentCleanup, WU components, shutdown handlers)")

        # ── Phase 2: Deep Cleanup ─────────────────────────────────────────
        self._phase("Phase 2 of 8  —  Deep Cleanup")
        self._ps("Clear CBS logs",
            "Remove-Item 'C:\\Windows\\Logs\\CBS\\*' -Recurse -Force -EA SilentlyContinue;"
            "Write-Host 'CBS logs cleared.'")
        for cache_tag, cache_path in [
            ("D3D/DirectX",  r"%LOCALAPPDATA%\D3DSCache"),
            ("NVIDIA GL",    r"%LOCALAPPDATA%\NVIDIA\GLCache"),
            ("AMD DX",       r"%LOCALAPPDATA%\AMD\DxCache"),
        ]:
            expanded = os.path.expandvars(cache_path)
            if os.path.exists(expanded):
                self._ps(f"Clear shader cache ({cache_tag})",
                    f"Remove-Item '{expanded}\\*' -Recurse -Force -EA SilentlyContinue;"
                    f"Write-Host 'Cleared {cache_tag} shader cache.'")
        self._ps("Clear Windows Update download leftovers",
            "Remove-Item 'C:\\Windows\\SoftwareDistribution.bak' -Recurse -Force -EA SilentlyContinue;"
            "if(Test-Path 'C:\\Windows\\SoftwareDistribution\\Download'){"
            "  Remove-Item 'C:\\Windows\\SoftwareDistribution\\Download\\*' -Recurse -Force -EA SilentlyContinue"
            "}; Write-Host 'WU download cache cleared.'")
        self._ps("Clean Delivery Optimization cache",
            "try { Delete-DeliveryOptimizationCache -Force -EA Stop; Write-Host 'DO cache cleared.' }"
            "catch {"
            "  $p='C:\\Windows\\ServiceProfiles\\NetworkService\\AppData\\Local\\Microsoft\\Windows\\DeliveryOptimization\\Cache';"
            "  if(Test-Path $p){ Remove-Item \"$p\\*\" -Recurse -Force -EA SilentlyContinue };"
            "  Write-Host 'Delivery Optimization cache cleared (fallback).'}")
        for junk_path in [
            r"C:\NVIDIA", r"C:\AMD",
            os.path.expandvars(r"%TEMP%\NVIDIA Corporation"),
            os.path.expandvars(r"%TEMP%\AMD"),
            os.path.expandvars(r"%TEMP%\Intel"),
        ]:
            if os.path.exists(junk_path):
                name = os.path.basename(junk_path)
                self._ps(f"Remove GPU installer junk ({name})",
                    f"Remove-Item '{junk_path}' -Recurse -Force -EA SilentlyContinue;"
                    f"Write-Host 'Removed {name}.'")
        for launcher, lpath in [
            ("Steam",      r"%LOCALAPPDATA%\Steam\htmlcache"),
            ("Epic Games", r"%LOCALAPPDATA%\EpicGamesLauncher\Saved\webcache"),
            ("Riot Client",r"%LOCALAPPDATA%\Riot Games\Riot Client\UX\Cache"),
            ("GOG Galaxy", r"%LOCALAPPDATA%\GOG.com\Galaxy\webcache"),
            ("EA Desktop", r"%LOCALAPPDATA%\Electronic Arts\EA Desktop\Cache"),
            ("Battle.net",  r"%LOCALAPPDATA%\Battle.net\Cache"),
        ]:
            expanded = os.path.expandvars(lpath)
            if os.path.exists(expanded):
                self._ps(f"Clean {launcher} cache",
                    f"Remove-Item '{expanded}\\*' -Recurse -Force -EA SilentlyContinue;"
                    f"Write-Host 'Cleaned {launcher} cache.'")
        self._ps("Clear system Temp folder",
            "Remove-Item 'C:\\Windows\\Temp\\*' -Recurse -Force -EA SilentlyContinue;"
            "Write-Host 'System Temp cleared.'")
        self._ps("Clear current user Temp folder",
            "Remove-Item \"$env:TEMP\\*\" -Recurse -Force -EA SilentlyContinue;"
            "Write-Host 'User Temp cleared.'")
        self._ps("Clear all user profile Temp folders",
            "Get-ChildItem 'C:\\Users' -Directory | ForEach-Object {"
            "  $t=Join-Path $_.FullName 'AppData\\Local\\Temp';"
            "  if(Test-Path $t){ Remove-Item \"$t\\*\" -Recurse -Force -EA SilentlyContinue;"
            "    Write-Host \"Cleared Temp for $($_.Name)\" }"
            "}")
        if os.path.exists(r"C:\Windows.old"):
            total = 0
            for root, _, files in os.walk(r"C:\Windows.old"):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            self.output.emit(
                f"  WARN Windows.old detected (~{total / (1024**3):.1f} GB). "
                "Use Disk Cleanup (cleanmgr) to safely remove it.", "warning")
        summary.append("Deep Cleanup  (CBS, shaders, WU cache, GPU junk, launcher caches, temps)")

        # ── Phase 3: Registry & Task Repair ──────────────────────────────
        self._phase("Phase 3 of 8  —  Registry & Task Repair")
        for dll in ["vbscript.dll", "jscript.dll", "mshtml.dll", "urlmon.dll",
                    "shdocvw.dll", "actxprxy.dll", "oleaut32.dll", "shell32.dll"]:
            self._run(f"Re-register {dll}", ["regsvr32", "/s", dll])
        self._ps("Remove stale uninstall entries",
            "$path='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall';"
            "Get-ChildItem $path -EA SilentlyContinue | ForEach-Object {"
            "  $dn=$_.GetValue('DisplayName'); $ip=$_.GetValue('InstallLocation');"
            "  if($dn -and $ip -and !(Test-Path $ip)){"
            "    Write-Host \"Stale entry removed: $dn\";"
            "    Remove-Item $_.PSPath -Recurse -Force -EA SilentlyContinue"
            "  }"
            "}")
        self._ps("Disable broken scheduled tasks",
            "Get-ScheduledTask -EA SilentlyContinue | Where-Object {$_.State -eq 'Unknown'} | ForEach-Object {"
            "  Write-Host \"Broken task disabled: $($_.TaskName)\";"
            "  Disable-ScheduledTask -TaskName $_.TaskName -EA SilentlyContinue"
            "}")
        self._ps("Report invalid shell extensions",
            "$ap='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Shell Extensions\\Approved';"
            "if(Test-Path $ap){"
            "  (Get-ItemProperty $ap -EA SilentlyContinue).PSObject.Properties |"
            "  Where-Object {$_.Name -notlike 'PS*'} |"
            "  ForEach-Object { Write-Host \"Shell Ext: $($_.Name)\" }"
            "}")
        self._ps("Remove leftover app data fragments",
            "Get-ChildItem 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall' -EA SilentlyContinue |"
            "Where-Object {!$_.GetValue('DisplayName')} | ForEach-Object {"
            "  Write-Host \"Orphan key removed: $($_.PSChildName)\";"
            "  Remove-Item $_.PSPath -Recurse -Force -EA SilentlyContinue"
            "}")
        summary.append("Registry & Task Repair  (COM DLLs, stale entries, broken tasks, shell exts, orphan keys)")

        # ── Phase 4: Service Health Reset ────────────────────────────────
        self._phase("Phase 4 of 8  —  Service Health Reset")
        for svc_label, svc_id in [
            ("Windows Update",                    "wuauserv"),
            ("Background Intelligent Transfer",   "bits"),
            ("Cryptographic Services",            "cryptsvc"),
            ("Print Spooler",                     "spooler"),
            ("Windows Management Instrumentation","winmgmt"),
            ("DCOM Server Process Launcher",      "DcomLaunch"),
            ("Remote Procedure Call",             "RpcSs"),
            ("Windows Event Log",                 "EventLog"),
            ("Task Scheduler",                    "Schedule"),
        ]:
            self._ps(f"Verify/restore: {svc_label}",
                f"$s=Get-Service '{svc_id}' -EA SilentlyContinue;"
                f"if($s -and $s.Status -ne 'Running'){{"
                f"  Write-Host '{svc_label}: not running — starting...';"
                f"  Start-Service '{svc_id}' -EA SilentlyContinue"
                f"}} else {{ Write-Host '{svc_label}: OK' }}")
        self._ps("Reset BITS service failure actions",
            "sc.exe config bits start= delayed-auto | Out-Null;"
            "sc.exe failure bits reset= 86400 actions= restart/60000/restart/120000// | Out-Null;"
            "Write-Host 'BITS service failure actions restored.'")
        self._ps("Fix stuck background tasks (TrustedInstaller report)",
            "Get-Process TrustedInstaller -EA SilentlyContinue | ForEach-Object {"
            "  Write-Host \"TrustedInstaller PID $($_.Id) — $([int]$_.TotalProcessorTime.TotalMinutes) CPU min\""
            "};"
            "Write-Host 'Background task check complete.'")
        summary.append("Service Health  (WU, BITS, Crypto, Spooler, WMI, DCOM, RPC, EventLog, Scheduler)")

        # ── Phase 5: Network Maintenance ─────────────────────────────────
        self._phase("Phase 5 of 8  —  Network Maintenance")
        self._run("Flush DNS cache",    ["ipconfig", "/flushdns"])
        self._run("Reset Winsock",      ["netsh", "winsock", "reset"])
        self._run("Reset TCP/IP stack", ["netsh", "int", "ip",   "reset"])
        self._run("Reset IPv6 stack",   ["netsh", "int", "ipv6", "reset"])
        self._run("Release IP address", ["ipconfig", "/release"])
        self._run("Renew IP address",   ["ipconfig", "/renew"])
        self._ps("Show network adapter status",
            "Get-NetAdapter | Select-Object Name,Status,LinkSpeed |"
            "Format-Table -AutoSize | Out-String | Write-Host")
        self._ps("DNS server status",
            "Get-DnsClientServerAddress -EA SilentlyContinue |"
            "Where-Object {$_.ServerAddresses} |"
            "Select-Object InterfaceAlias,ServerAddresses |"
            "Format-Table -AutoSize | Out-String | Write-Host")
        summary.append("Network  (DNS flush, Winsock reset, TCP/IP reset, IP renewal)")

        # ── Phase 6: Disk & Storage ──────────────────────────────────────
        self._phase("Phase 6 of 8  —  Disk & Storage")
        self._ps("Physical disk SMART health",
            "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,OperationalStatus,"
            "@{N='Size(GB)';E={[math]::Round($_.Size/1GB,1)}} |"
            "Format-Table -AutoSize | Out-String | Write-Host")
        self._ps("Volume health & free space",
            "Get-Volume | Where-Object {$_.DriveLetter} |"
            "Select-Object DriveLetter,FileSystemLabel,HealthStatus,"
            "@{N='Free(GB)';E={[math]::Round($_.SizeRemaining/1GB,1)}},"
            "@{N='Total(GB)';E={[math]::Round($_.Size/1GB,1)}} |"
            "Format-Table -AutoSize | Out-String | Write-Host")
        self._ps(f"SSD TRIM on {self.drive_letter}:",
            f"Optimize-Volume -DriveLetter {self.drive_letter} -ReTrim -Verbose -EA SilentlyContinue")
        self._ps(f"CHKDSK check on {self.drive_letter}:",
            f"$v=Get-Volume -DriveLetter '{self.drive_letter}' -EA SilentlyContinue;"
            f"if($v -and $v.HealthStatus -ne 'Healthy'){{"
            f"  Write-Host 'Volume not healthy — scheduling CHKDSK on next boot...';"
            f"  echo Y | chkdsk {self.drive_letter}: /f /r /x"
            f"}} else {{ Write-Host 'Drive {self.drive_letter}: is Healthy — CHKDSK not needed.' }}")
        summary.append("Disk & Storage  (SMART, volume health, SSD TRIM, CHKDSK if needed)")

        # ── Phase 7: Performance Tuning ──────────────────────────────────
        self._phase("Phase 7 of 8  —  Performance Tuning")
        self._ps("Set High Performance power plan",
            "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>&1 |"
            "ForEach-Object { Write-Host $_ }")
        self._ps("Optimize visual effects for performance",
            "Set-ItemProperty -Path "
            "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\VisualEffects' "
            "-Name 'VisualFXSetting' -Value 2 -EA SilentlyContinue;"
            "Write-Host 'Visual effects set to Best Performance.'")
        self._ps("Disable Xbox Game DVR",
            "New-Item 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\GameDVR' -Force -EA SilentlyContinue | Out-Null;"
            "Set-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\GameDVR' 'AllowGameDVR' 0 -Force -EA SilentlyContinue;"
            "Set-ItemProperty 'HKCU:\\System\\GameConfigStore' 'GameDVR_Enabled' 0 -EA SilentlyContinue;"
            "Write-Host 'Xbox Game DVR disabled.'")
        self._ps("Enable Game Mode",
            "Set-ItemProperty 'HKCU:\\Software\\Microsoft\\GameBar' 'AllowAutoGameMode' 1 -EA SilentlyContinue;"
            "Set-ItemProperty 'HKCU:\\Software\\Microsoft\\GameBar' 'AutoGameModeEnabled' 1 -EA SilentlyContinue;"
            "Write-Host 'Game Mode enabled.'")
        self._ps("Set foreground process priority boost",
            "Set-ItemProperty "
            "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\PriorityControl' "
            "'Win32PrioritySeparation' 38 -EA SilentlyContinue;"
            "Write-Host 'Foreground priority boost applied.'")
        self._ps("Trim RAM (GC collect + usage report)",
            "[System.GC]::Collect();"
            "[System.GC]::WaitForPendingFinalizers();"
            "[System.GC]::Collect();"
            "$os=Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue;"
            "if($os){"
            "  $free=[math]::Round($os.FreePhysicalMemory/1MB,1);"
            "  $total=[math]::Round($os.TotalVisibleMemorySize/1MB,1);"
            "  Write-Host \"RAM: $([math]::Round($total-$free,1)) GB used / $total GB total\""
            "}")
        self._ps("Disable hibernation (reclaim hiberfil.sys space)",
            "powercfg /hibernate off; Write-Host 'Hibernation disabled.'")
        summary.append("Performance  (power plan, visual effects, Game DVR, Game Mode, priority, RAM GC, no hiberfil)")

        # ── Phase 8: Final Verification ──────────────────────────────────
        self._phase("Phase 8 of 8  —  Final Verification")
        self._run("SFC integrity verification",
            ["sfc", "/verifyonly"])
        self._ps("Confirm core service health",
            "foreach($s in 'wuauserv','bits','cryptsvc','EventLog','Schedule','winmgmt','RpcSs'){"
            "  $svc=Get-Service $s -EA SilentlyContinue;"
            "  if($svc){ Write-Host \"$s : $($svc.Status)\" } else { Write-Host \"$s : NOT FOUND\" }"
            "}")
        self._ps("Confirm shutdown safety",
            "$pr=Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager' "
            "-Name 'PendingFileRenameOperations' -EA SilentlyContinue;"
            "if($pr -and $pr.PendingFileRenameOperations){"
            "  Write-Host \"Pending file ops on restart: $($pr.PendingFileRenameOperations.Count) items\""
            "} else { Write-Host 'No pending rename operations — shutdown is clean.' }")
        self._ps("Confirm Windows Update integrity",
            "$s=Get-Service wuauserv -EA SilentlyContinue;"
            "if($s){ Write-Host \"Windows Update service: $($s.Status)\" };"
            "if(Test-Path 'C:\\Windows\\SoftwareDistribution'){"
            "  Write-Host 'SoftwareDistribution folder: present (OK)'"
            "} else { Write-Host 'SoftwareDistribution will recreate on next WU run.' }")
        self._ps("Check recent System event errors",
            "Get-WinEvent -LogName System -MaxEvents 20 -EA SilentlyContinue |"
            "Where-Object {$_.Level -le 2} | Select-Object -First 5 |"
            "Select-Object TimeCreated,ProviderName,@{N='Message';E={$_.Message.Split(\"`n\")[0]}} |"
            "Format-List | Out-String | Write-Host")
        self._ps("Confirm no remaining corruption",
            "$result=sfc /verifyonly 2>&1 | Out-String;"
            "if($result -match 'no integrity violations'){"
            "  Write-Host 'PASS: No system file corruption detected.'"
            "} else { Write-Host 'NOTE: Review SFC output above for details.' }")
        summary.append("Final Verification  (SFC check, services, shutdown safety, WU integrity, event log)")

        # ── Summary ───────────────────────────────────────────────────────
        self.output.emit(f"\n{'=' * 56}", "success")
        self.output.emit("  FULL MAINTENANCE COMPLETE", "success")
        self.output.emit(f"{'=' * 56}", "success")
        for i, s in enumerate(summary, 1):
            self.output.emit(f"  [{i}] {s}", "success")
        self.output.emit("", "info")
        self.output.emit(
            "  Recommendation: Restart your system to apply all changes.", "warning")

        self.finished.emit(
            f"Full System Maintenance Complete! ({len(summary)} phases)\n"
            "All repair, cleanup, service, network, disk, and performance tasks finished.\n"
            "Please restart your system to apply all changes."
        )


class BackgroundHealthAgent(QThread):
    """Monitors system health during maintenance and alerts on problems."""
    alert = pyqtSignal(str, str)   # message, level
    status = pyqtSignal(dict)      # health snapshot

    def __init__(self, interval_sec=30):
        super().__init__()
        self.interval_sec = interval_sec
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        import time
        while self._running:
            try:
                snap = {}

                # RAM usage
                mem = psutil.virtual_memory()
                snap["ram_pct"] = mem.percent
                if mem.percent > 92:
                    self.alert.emit(
                        f"Health Agent: RAM at {mem.percent:.0f}% — system under stress.", "warning")

                # Disk free space
                drives = []
                if sys.platform == 'win32':
                    for part in psutil.disk_partitions():
                        if part.fstype and part.mountpoint:
                            drives.append(part.mountpoint)
                else:
                    drives = ["/"]
                for drv in drives:
                    try:
                        usage = psutil.disk_usage(drv)
                        snap[f"disk_{drv}_pct"] = usage.percent
                        if usage.percent > 95:
                            self.alert.emit(
                                f"Health Agent: Critical disk space on {drv}: "
                                f"{usage.percent:.0f}% full ({usage.free/(1024**3):.1f} GB free).",
                                "error")
                        elif usage.percent > 87:
                            self.alert.emit(
                                f"Health Agent: Low disk space on {drv}: {usage.percent:.0f}% full.",
                                "warning")
                    except Exception:
                        pass

                # Uptime
                uptime_days = (time.time() - psutil.boot_time()) / 86400
                snap["uptime_days"] = uptime_days
                if uptime_days > 7:
                    self.alert.emit(
                        f"Health Agent: System uptime {uptime_days:.1f} days — restart after maintenance.",
                        "warning")

                # Critical service check (Windows)
                if sys.platform == 'win32':
                    for svc in ["EventLog", "RpcSs", "DcomLaunch"]:
                        try:
                            r = subprocess.run(
                                ["sc", "query", svc],
                                capture_output=True, text=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                            )
                            if r.returncode == 0 and "STOPPED" in r.stdout:
                                snap[f"svc_{svc}"] = "stopped"
                                self.alert.emit(
                                    f"Health Agent: Critical service '{svc}' is STOPPED — "
                                    "system stability at risk.", "error")
                        except Exception:
                            pass

                self.status.emit(snap)

            except Exception as e:
                logger.debug(f"BackgroundHealthAgent: {e}")

            for _ in range(self.interval_sec * 2):
                if not self._running:
                    return
                time.sleep(0.5)

class GenericCommandWorker(QThread):
    finished = pyqtSignal(bool, str)
    output = pyqtSignal(str, str)

    def __init__(self, name, command):
        super().__init__()
        self.name = name
        self.command = command

    def run(self):
        try:
            cmd_prefix = ["powershell", "-NoProfile", "-Command"] if sys.platform == 'win32' else ["bash", "-c"]
            process = subprocess.Popen(
                cmd_prefix + [self.command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            
            full_output = []
            for line in process.stdout:
                try:
                    text = line.decode('utf-8', errors='replace')
                except:
                    text = line.decode('cp1252', errors='replace')

                for part in text.split('\r'):
                    clean_line = part.strip()
                    if clean_line and clean_line not in ["-", "\\", "|", "/", ".", "??"]:
                        if not re.match(r'^[\.\-\s]+$', clean_line):
                            full_output.append(clean_line)
                            self.output.emit(f"[{self.name}] {clean_line}", "debug")
            
            process.wait()
            success = (process.returncode == 0)
            result_str = "\n".join(full_output) if full_output else ""
            
            if success:
                self.finished.emit(True, result_str)
            else:
                self.finished.emit(False, result_str if result_str else f"{self.name} failed with code {process.returncode}.")
        except Exception as e:
            self.output.emit(f"{self.name} Error: {str(e)}", "error")
            self.finished.emit(False, str(e))

class SecurityScanWorker(QThread):
    finished = pyqtSignal(list)
    output = pyqtSignal(str, str)

    def run(self):
        try:
            self.output.emit("Starting background security scan...", "info")
            scanner = SecurityScanner()
            issues = scanner.get_report()
            self.finished.emit(issues)
        except Exception as e:
            logger.error(f"Security Scan Error: {e}")
            self.finished.emit([])

class BloatScanWorker(QThread):
    finished = pyqtSignal(dict)
    output = pyqtSignal(str, str)

    def __init__(self, bloat_remover):
        super().__init__()
        self.bloat_remover = bloat_remover

    def run(self):
        try:
            self.output.emit("Starting background bloatware scan...", "info")
            
            def on_progress(p, m):
                if p % 20 == 0 or p == 100:
                    self.output.emit(f"Scan {p}%: {m}", "debug")
            
            results = self.bloat_remover.scan_system(on_progress)
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Bloat Scan Error: {e}")
            self.output.emit(f"Bloat Scan Error: {str(e)}", "error")
            self.finished.emit({})

class UpdateCheckWorker(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, update_manager):
        super().__init__()
        self.update_manager = update_manager
        
    def run(self):
        try:
            res = self.update_manager.check_for_updates()
            self.finished.emit(res)
        except Exception as e:
            logger.error(f"UpdateCheckWorker error: {e}")
            self.finished.emit({"available": False, "error": str(e)})

class ReleaseInfoWorker(QThread):
    finished = pyqtSignal(object)
    
    def __init__(self, update_manager):
        super().__init__()
        self.update_manager = update_manager
        
    def run(self):
        try:
            res = self.update_manager.get_release_info()
            self.finished.emit(res)
        except Exception as e:
            logger.error(f"ReleaseInfoWorker error: {e}")
            self.finished.emit(None)

class SensorWorker(QThread):
    finished = pyqtSignal(object)
    
    def run(self):
        try:
            r = requests.get("http://localhost:8085/data.json", timeout=2)
            data = r.json()

            sensors = {}
            # LHM API uses nested "Children" throughout — leaf nodes (no children)
            # with a non-dash "Value" are the actual sensor readings.
            def walk(node, group=""):
                children = node.get("Children", [])
                if children:
                    for child in children:
                        walk(child, node.get("Text", group))
                else:
                    val = node.get("Value", "-")
                    if val and val != "-":
                        name = node.get("Text", "")
                        if name:
                            sensors[name] = {
                                "value": val,
                                "type": group,
                                "unit": ""
                            }

            walk(data)
            self.finished.emit(sensors if sensors else None)
        except:
            self.finished.emit(None)

class SpecsWorker(QThread):
    finished = pyqtSignal(str)

    def run(self):
        from src.utils.helpers import run_command
        try:
            if sys.platform == 'win32':
                specs = self._gather_windows_specs(run_command)
            elif sys.platform == 'darwin':
                specs = self._gather_macos_specs(run_command)
            else:
                specs = self._gather_linux_specs(run_command)
            self.finished.emit(specs)
        except Exception as e:
            logger.error(f"SpecsWorker error: {e}")
            self.finished.emit(f"Error gathering specs: {e}")

    def _gather_windows_specs(self, run_command):
        # CPU
        cpu_res = run_command(["wmic", "cpu", "get", "name"])
        cpu_lines = [line.strip() for line in cpu_res.stdout.split('\n') if line.strip()]
        cpu_info = cpu_lines[1] if len(cpu_lines) > 1 else "Unknown CPU"

        # GPU
        gpu_res = run_command(["wmic", "path", "win32_VideoController", "get", "Name,PNPDeviceID,AdapterRAM,DriverVersion", "/format:csv"])
        lines = [l.strip() for l in gpu_res.stdout.split("\n") if l.strip()]
        if len(lines) < 2:
            gpu_info = "Unknown GPU"
        else:
            header = lines[0].split(",")
            gpus = []
            for line in lines[1:]:
                parts = line.split(",")
                row = dict(zip(header, parts))
                name = row.get("Name", "").strip()
                pnp = row.get("PNPDeviceID", "").strip()
                vram = row.get("AdapterRAM", "").strip()
                driver = row.get("DriverVersion", "").strip()
                try:
                    vram_gb = f"{int(vram) / (1024**3):.1f} GB"
                except Exception:
                    vram_gb = "Unknown VRAM"
                gpu_type = "PCIe GPU" if "PCI\\" in pnp.upper() else "Integrated GPU"
                gpus.append(f"{gpu_type}: {name} ({vram_gb}, Driver {driver})")
            gpu_info = "<br>".join(gpus) if gpus else "Unknown GPU"

        # Motherboard
        mobo_res = run_command(["wmic", "baseboard", "get", "product,manufacturer"])
        mobo_lines = [line.strip() for line in mobo_res.stdout.split('\n') if line.strip()]
        mobo_info = mobo_lines[1] if len(mobo_lines) > 1 else "Unknown Motherboard"

        # OS Info
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            build_number = int(winreg.QueryValueEx(key, "CurrentBuild")[0])
            product_name = winreg.QueryValueEx(key, "ProductName")[0]
            try:
                display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
            except FileNotFoundError:
                try:
                    display_version = winreg.QueryValueEx(key, "ReleaseId")[0]
                except FileNotFoundError:
                    display_version = "Unknown"
            os_name = "Windows 11" if build_number >= 22000 else "Windows 10"
            winreg.CloseKey(key)
        except Exception:
            os_name = platform.system()
            product_name = "Unknown Edition"
            display_version = "Unknown"
            build_number = 0

        # Install Date
        install_date = ""
        try:
            ps_cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem).InstallDate.ToString('yyyy-MM-dd HH:mm')"]
            ins = run_command(ps_cmd)
            install_date = ins.stdout.strip()
        except Exception:
            install_date = ""

        specs = f"<b>OS:</b> {os_name} (Build {build_number})<br>"
        specs += f"<b>Edition:</b> {product_name} (Version {display_version})<br>"
        if install_date:
            specs += f"<b>Install Date:</b> {install_date}<br>"
        specs += f"<b>CPU:</b> {cpu_info}<br>"
        specs += f"<b>GPU:</b><br>{gpu_info}<br>"
        specs += f"<b>Motherboard:</b> {mobo_info}<br>"
        return specs

    def _gather_linux_specs(self, run_command):
        # CPU
        cpu_info = "Unknown CPU"
        try:
            res = run_command(["lscpu"])
            for line in res.stdout.splitlines():
                if line.startswith("Model name"):
                    cpu_info = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

        # GPU
        gpu_info = "Unknown GPU"
        try:
            res = run_command(["lspci"])
            gpus = [l.split(":", 2)[-1].strip() for l in res.stdout.splitlines()
                    if "VGA" in l or "3D" in l or "Display" in l]
            if gpus:
                gpu_info = "<br>".join(gpus)
        except Exception:
            pass

        # Motherboard
        mobo_info = "Unknown Motherboard"
        try:
            vendor = ""
            name = ""
            for dmi_file, label in [("/sys/devices/virtual/dmi/id/board_vendor", "vendor"),
                                     ("/sys/devices/virtual/dmi/id/board_name", "name")]:
                res = run_command(["cat", dmi_file])
                if res.returncode == 0:
                    if label == "vendor":
                        vendor = res.stdout.strip()
                    else:
                        name = res.stdout.strip()
            if vendor or name:
                mobo_info = f"{vendor} {name}".strip()
        except Exception:
            pass

        # OS Info
        os_name = platform.system()
        os_version = platform.release()
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass

        # Install date (approximate)
        install_date = ""
        try:
            res = run_command(["stat", "-c", "%y", "/lost+found"])
            if res.returncode == 0:
                install_date = res.stdout.strip().split(".")[0]
        except Exception:
            pass

        specs = f"<b>OS:</b> {os_name} (Kernel {os_version})<br>"
        if install_date:
            specs += f"<b>Install Date (approx):</b> {install_date}<br>"
        specs += f"<b>CPU:</b> {cpu_info}<br>"
        specs += f"<b>GPU:</b><br>{gpu_info}<br>"
        specs += f"<b>Motherboard:</b> {mobo_info}<br>"
        return specs

    def _gather_macos_specs(self, run_command):
        # Use system_profiler for hardware overview
        cpu_info = "Unknown CPU"
        gpu_info = "Unknown GPU"
        mobo_info = "Unknown Model"

        try:
            res = run_command(["system_profiler", "SPHardwareDataType"])
            for line in res.stdout.splitlines():
                line = line.strip()
                if "Chip:" in line or "Processor Name:" in line:
                    cpu_info = line.split(":", 1)[1].strip()
                elif "Model Name:" in line or "Model Identifier:" in line:
                    mobo_info = line.split(":", 1)[1].strip()
        except Exception:
            pass

        try:
            res = run_command(["system_profiler", "SPDisplaysDataType"])
            gpus = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if "Chipset Model:" in line:
                    gpus.append(line.split(":", 1)[1].strip())
            if gpus:
                gpu_info = "<br>".join(gpus)
        except Exception:
            pass

        os_name = platform.mac_ver()[0] or platform.system()
        specs = f"<b>OS:</b> macOS {os_name}<br>"
        specs += f"<b>Model:</b> {mobo_info}<br>"
        specs += f"<b>CPU:</b> {cpu_info}<br>"
        specs += f"<b>GPU:</b><br>{gpu_info}<br>"
        return specs

class MainDiskWorker(QThread):
    finished = pyqtSignal(str, str) # main_disk, system_drive
    
    def run(self):
        if sys.platform != 'win32':
            # For non-Windows, we return dummy values or could implement lsblk/df later
            self.finished.emit("0", "/")
            return
        try:
            system_drive = os.environ.get('SystemDrive', 'C').replace(':', '')
            powershell_script = f"Get-Partition -DriveLetter {system_drive} | Get-Disk | Select-Object -ExpandProperty Number"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", powershell_script],
                capture_output=True,
                text=True,
                shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            main_disk = result.stdout.strip()
            if not main_disk:
                main_disk = "0"
            self.finished.emit(main_disk, system_drive)
        except Exception as e:
            logger.error(f"Error getting main disk: {e}")
            self.finished.emit("0", "C")

class MonitoringSetupWorker(QThread):
    finished = pyqtSignal(bool, str) # success, message
    output = pyqtSignal(str, str) # message, level
    
    def run(self):
        url = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest/download/LibreHardwareMonitor.zip"
        install_dir = os.path.join(os.getenv("APPDATA"), "GhostyTools", "LHM")
        zip_path = os.path.join(install_dir, "lhm.zip")

        os.makedirs(install_dir, exist_ok=True)

        # Download
        try:
            self.output.emit("Downloading LibreHardwareMonitor...", "info")
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                self.finished.emit(False, f"Download failed: HTTP {r.status_code}")
                return

            with open(zip_path, "wb") as f:
                f.write(r.content)

            self.output.emit("Download complete.", "success")

        except Exception as e:
            self.finished.emit(False, f"Download error: {e}")
            return

        # Extract
        try:
            self.output.emit("Extracting ZIP...", "info")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(install_dir)
            self.output.emit("Extraction complete.", "success")

        except Exception as e:
            self.finished.emit(False, f"Extraction error: {e}")
            return

        # Config
        try:
            self.output.emit("Writing configuration...", "info")
            config_path = os.path.join(os.getenv("APPDATA"), "LibreHardwareMonitor", "LibreHardwareMonitor.config")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            config_xml = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
<RemoteWebServer Enabled="true" Port="8085" />
</configuration>
"""
            with open(config_path, "w") as f:
                f.write(config_xml)

            self.output.emit("Configuration written.", "success")

        except Exception as e:
            self.finished.emit(False, f"Config write error: {e}")
            return

        # Launch EXE
        exe_path = os.path.join(install_dir, "LibreHardwareMonitor.exe")
        if not os.path.exists(exe_path):
            self.finished.emit(False, "LibreHardwareMonitor.exe not found after extraction!")
            return

        try:
            self.output.emit("Launching LibreHardwareMonitor...", "info")
            subprocess.Popen([exe_path], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.finished.emit(True, "LibreHardwareMonitor launched successfully.")
        except Exception as e:
            self.finished.emit(False, f"Launch error: {e}")
            return

class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str) # success, message
    output = pyqtSignal(str, str) # message, level
    
    def __init__(self, url, dest_path, tool_name=None):
        super().__init__()
        self.url = url
        self.dest_path = dest_path
        self.tool_name = tool_name

    def run(self):
        try:
            # Ensure destination directory exists
            dest_dir = os.path.dirname(self.dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            prefix = f"[{self.tool_name}] " if self.tool_name else ""
            self.output.emit(f"{prefix}Downloading from {self.url}...", "info")
            
            # Use a realistic User-Agent to avoid blocks
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(self.url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            self.output.emit(f"{prefix}Download Progress: {percent:.1f}%", "debug")
            
            self.finished.emit(True, f"Download completed: {self.dest_path}")
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.finished.emit(False, str(e))

class NetworkWorker(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, task="ip", target="127.0.0.1"):
        super().__init__()
        self.task = task
        self.target = target
        
    def run(self):
        from src.core.network_tools import NetworkTools
        if self.task == "ip":
            res = NetworkTools.get_ip_intelligence()
            self.finished.emit({"task": "ip", "data": res})
        elif self.task == "dns":
            res = NetworkTools.benchmark_dns()
            self.finished.emit({"task": "dns", "data": res})
        elif self.task == "port":
            res = NetworkTools.port_scan(self.target)
            self.finished.emit({"task": "port", "data": res})

class TaskManagerWorker(QThread):
    finished = pyqtSignal(dict)
    
    def run(self):
        from src.core.task_manager import TaskManager
        res = TaskManager.get_resource_hogs()
        self.finished.emit(res)

class PrivacyAuditWorker(QThread):
    finished = pyqtSignal(list)
    
    def run(self):
        from src.core.privacy_cleaner import PrivacyCleaner
        res = PrivacyCleaner.run_privacy_audit()
        self.finished.emit(res)
