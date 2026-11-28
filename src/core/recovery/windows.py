"""Allowlisted Windows handlers. PowerShell receives values as JSON data only."""

import base64
from copy import deepcopy
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from src.utils.helpers import get_resource_path
from .models import Capability, Handler, RecoveryError, Risk, matches, require_transaction


# Supported registry VALUES, not an unrestricted registry editing interface.
REGISTRY = {
    "uac": ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA", 4),
    "rdp": ("HKLM", r"SYSTEM\CurrentControlSet\Control\Terminal Server", "fDenyTSConnections", 4),
    "startup": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "GhostyTools", 1),
    "telemetry": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 4),
    "activity_history": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", 4),
    "game_dvr": ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 4),
    "game_dvr_policy": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", 4),
    "game_capture": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 4),
    "game_mode": ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", 4),
    "auto_game_mode": ("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 4),
    "game_panel": ("HKCU", r"Software\Microsoft\GameBar", "ShowStartupPanel", 4),
    "game_nexus": ("HKCU", r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", 4),
    "gpu_preference": ("HKCU", r"Software\Microsoft\DirectX\UserGpuPreferences", "DirectXUserGlobalSettings", 1),
    "fullscreen_mode": ("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", 4),
    "fullscreen_honor": ("HKCU", r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", 4),
    "fullscreen_behavior": ("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehavior", 4),
    "update_policy": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoUpdate", 4),
    "mmcss_gpu": ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "GPU Priority", 4),
    "mmcss_priority": ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Priority", 4),
    "mmcss_category": ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Scheduling Category", 1),
    "homegroup": ("HKLM", r"SOFTWARE\Classes\CLSID\{B4FB3F98-C1EA-428d-A78A-D1F5659CBA93}\ShellFolder", "Attributes", 4),
    "ipv4_preference": ("HKLM", r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents", 4),
    "location": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors", "DisableLocation", 4),
    "storage_sense": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy", "01", 4),
    "wifi_sense": ("HKLM", r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config", "AutoConnectAllowedOEM", 4),
    "end_task": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarEndTask", 4),
    "bing_search": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", 4),
    "cortana": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "CortanaConsent", 4),
    "search_suggestions": ("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 4),
    "classic_menu": ("HKCU", r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32", "", 1),
    "advertising_id": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 4),
    "spotlight": ("HKCU", r"Software\Policies\Microsoft\Windows\CloudContent", "DisableWindowsSpotlightFeatures", 4),
    "copilot_policy": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 4),
    "copilot_button": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowCopilotButton", 4),
    "news_policy": ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Feeds", "EnableFeeds", 4),
    "news_button": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Feeds", "ShellFeedsTaskbarViewMode", 4),
    "file_extensions": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "HideFileExt", 4),
    "hidden_files": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden", 4),
    "system_files": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowSuperHidden", 4),
    "background_apps": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", 4),
    "background_search": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle", 4),
    "fast_startup": ("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", 4),
    "apps_light_theme": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 4),
    "system_light_theme": ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "SystemUsesLightTheme", 4),
}


def text(value, maximum=512):
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise RecoveryError("Invalid Windows resource identifier")
    return value


def policy() -> dict:
    data = json.loads(Path(get_resource_path("config/recovery_policy.json")).read_text(encoding="utf-8"))
    if data.get("version") != 1 or any(not isinstance(data.get(key), list) for key in
                                       ("critical_services", "blocked_service_stop", "protected_processes")):
        raise RecoveryError("Recovery protection policy is missing or unsupported")
    return data


class WindowsBackend:
    def __init__(self, runner=subprocess.run):
        self.runner = runner

    def ps(self, script: str, data=None, timeout=45, *, mutating=False):
        if mutating:
            require_transaction()
        if sys.platform != "win32":
            raise RecoveryError("This recovery handler requires Windows")
        preamble = "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
        preamble += "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); $OutputEncoding=[Console]::OutputEncoding; "
        preamble += "$p=ConvertFrom-Json $env:GHOSTY_RECOVERY_DATA; "
        encoded = base64.b64encode((preamble + script).encode("utf-16-le")).decode("ascii")
        result = self.runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            env={**os.environ, "GHOSTY_RECOVERY_DATA": json.dumps(data or {})},
            capture_output=True, text=True, encoding="utf-8", timeout=timeout, creationflags=0x08000000,
        )
        if result.returncode:
            raise RecoveryError(result.stderr.strip() or f"Windows operation failed with exit {result.returncode}")
        output = result.stdout.strip()
        return json.loads(output) if output else None

    def service_read(self, name):
        return self.ps(r"""
        $s=Get-CimInstance Win32_Service | Where-Object Name -eq $p.name;
        if (!$s) { throw 'Service is unavailable' };
        $r=Get-Service -Name $p.name;
        $delay=Get-ItemPropertyValue -LiteralPath ('HKLM:\SYSTEM\CurrentControlSet\Services\'+$p.name) -Name DelayedAutoStart -ErrorAction SilentlyContinue;
        $binary=if ($s.PathName -match '^"?(.+?\.exe)"?(?:\s|$)') {$Matches[1]} else {'[Executable path unavailable]'};
        $hash=[System.Security.Cryptography.SHA256]::Create();
        try {$argumentsHash=[Convert]::ToBase64String($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes([string]$s.PathName)))}
        finally {$hash.Dispose()};
        [ordered]@{name=$s.Name; display_name=$s.DisplayName; running=($s.State -eq 'Running');
          startup=$s.StartMode; delayed=($delay -eq 1); executable=$binary; configuration_sha256=$argumentsHash; account=$s.StartName;
          dependencies=@($r.ServicesDependedOn | ForEach-Object {$_.Name});
          dependents=@($r.DependentServices | ForEach-Object {$_.Name})} | ConvertTo-Json -Depth 6 -Compress
        """, {"name": name})

    def service_write(self, name, desired):
        require_transaction()
        self.ps("""
        if ($null -ne $p.state.startup) {
          $mode=@{Auto='Automatic';Manual='Manual';Disabled='Disabled'}[$p.state.startup];
          if (!$mode) {throw 'Unsupported service startup mode'};
          Set-Service -Name $p.name -StartupType $mode;
          if ($p.state.startup -eq 'Auto') {
            $start=if ($p.state.delayed) {'delayed-auto'} else {'auto'};
            & sc.exe config $p.name 'start=' $start | Out-Null;
            if ($LASTEXITCODE -ne 0) {throw 'Delayed startup configuration failed'}
          }
        };
        if ($null -ne $p.state.running) {
          if ($p.state.running) {Start-Service -Name $p.name} else {Stop-Service -Name $p.name};
          $service=Get-Service -Name $p.name;
          $wanted=if ($p.state.running) {'Running'} else {'Stopped'};
          $service.WaitForStatus($wanted,[TimeSpan]::FromSeconds(20))
        }
        """, {"name": name, "state": desired})

    def adapters(self):
        result = self.ps("@(Get-NetAdapter | Where-Object Status -eq 'Up' | ForEach-Object {"
                         "@{guid=$_.InterfaceGuid.ToString();name=$_.Name}}) | ConvertTo-Json -Compress")
        return result if isinstance(result, list) else [result] if result else []

    def dns_read(self, interface):
        return self.ps(r"""
        $a=Get-NetAdapter | Where-Object {$_.InterfaceGuid.ToString() -eq $p.interface};
        if (!$a) {throw 'Network interface is unavailable'};
        $v4=Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4;
        $v6=Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv6;
        $base='HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{'+$p.interface+'}';
        $static=Get-ItemPropertyValue -LiteralPath $base -Name NameServer -ErrorAction SilentlyContinue;
        @{servers=@($v4.ServerAddresses);source=$(if ($static) {'static'} else {'dhcp'});
          ipv6=@($v6.ServerAddresses);interface=$p.interface} | ConvertTo-Json -Depth 5 -Compress
        """, {"interface": interface})

    def dns_write(self, interface, desired):
        require_transaction()
        self.ps("""
        $a=Get-NetAdapter | Where-Object {$_.InterfaceGuid.ToString() -eq $p.interface};
        if (!$a) {throw 'Network interface is unavailable'};
        $client=Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4;
        if ($p.state.source -eq 'dhcp') {$client | Set-DnsClientServerAddress -ResetServerAddresses}
        else {$client | Set-DnsClientServerAddress -ServerAddresses @($p.state.servers)}
        """, {"interface": interface, "state": desired})

    def firewall_profiles_read(self):
        return self.ps("$value=@{}; Get-NetFirewallProfile | ForEach-Object {$value[$_.Name]=[bool]$_.Enabled};"
                       "$value | ConvertTo-Json -Compress")

    def firewall_profiles_write(self, desired):
        require_transaction()
        self.ps("$p.state.PSObject.Properties | ForEach-Object {"
                "Set-NetFirewallProfile -Profile $_.Name -Enabled $_.Value}", {"state": desired})

    def firewall_rule_read(self, name):
        return self.ps("""
        $r=Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object Name -eq $p.name;
        if (!$r) {@{exists=$false} | ConvertTo-Json -Compress; exit};
        if (@($r).Count -ne 1 -or $r.PolicyStoreSourceType -eq 'GroupPolicy') {throw 'Unsupported firewall policy source'};
        $port=$r | Get-NetFirewallPortFilter; $addr=$r | Get-NetFirewallAddressFilter;
        $app=$r | Get-NetFirewallApplicationFilter; $svc=$r | Get-NetFirewallServiceFilter;
        $security=$r | Get-NetFirewallSecurityFilter;
        if (($app.Package -and $app.Package -ne 'Any') -or ($security.Authentication -and $security.Authentication -ne 'NotRequired')) {throw 'This specialised firewall rule is not supported for exact recovery'};
        @{exists=$true;rule=@{DisplayName=$r.DisplayName;Description=$r.Description;Enabled=$r.Enabled.ToString();
          Direction=$r.Direction.ToString();Action=$r.Action.ToString();Profile=$r.Profile.ToString();
          EdgeTraversalPolicy=$r.EdgeTraversalPolicy.ToString();Protocol=$port.Protocol;LocalPort=@($port.LocalPort);
          RemotePort=@($port.RemotePort);LocalAddress=@($addr.LocalAddress);RemoteAddress=@($addr.RemoteAddress);
          Program=$app.Program;Service=$svc.Service}} | ConvertTo-Json -Depth 7 -Compress
        """, {"name": name})

    def firewall_rule_write(self, name, desired):
        require_transaction()
        self.ps("""
        $existing=Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object Name -eq $p.name;
        if ($existing) {$existing | Remove-NetFirewallRule};
        if ($p.state.exists) {
          $args=@{Name=$p.name;PolicyStore='PersistentStore'};
          $p.state.rule.PSObject.Properties | ForEach-Object {$args[$_.Name]=$_.Value};
          New-NetFirewallRule @args | Out-Null
        }
        """, {"name": name, "state": desired})

    def power_read(self):
        return self.ps(r"$s=Get-CimInstance -Namespace root\cimv2\power -ClassName Win32_PowerPlan | Where-Object IsActive;"
                       "@{scheme=($s.InstanceID -replace '^.*{','' -replace '}.*$','')} | ConvertTo-Json -Compress")

    def power_write(self, scheme):
        require_transaction()
        self.ps("& powercfg.exe /setactive $p.scheme | Out-Null;"
                "if ($LASTEXITCODE -ne 0) {throw 'Power plan activation failed'}", {"scheme": scheme})

    def restore_point(self):
        require_transaction()
        self.ps("Checkpoint-Computer -Description 'Ghosty Tools protected change' -RestorePointType MODIFY_SETTINGS", timeout=120)


class RegistryHandler(Handler):
    def requires_reboot(self, target):
        return target["id"] in {"uac", "ipv4_preference"}

    def validate(self, target, desired):
        if set(target) != {"id"} or target["id"] not in REGISTRY:
            raise RecoveryError("Registry target is not in the approved recovery catalog")
        if set(desired) - {"exists", "value", "type"} or not isinstance(desired.get("exists"), bool):
            raise RecoveryError("Invalid registry value request")
        if desired["exists"]:
            expected_type = REGISTRY[target["id"]][3]
            if desired.get("type") != expected_type:
                raise RecoveryError("Unexpected registry value type")
            value = desired.get("value")
            if expected_type == 4 and (not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xffffffff):
                raise RecoveryError("Registry DWORD value is invalid")
            if expected_type == 1 and (not isinstance(value, str) or len(value) > 4096 or "\0" in value):
                raise RecoveryError("Registry string value is invalid")

    def classify(self, target, desired):
        risk = Risk.HIGH if target["id"] in {"uac", "rdp", "ipv4_preference", "update_policy"} else Risk.MEDIUM
        return risk, Capability.FULL, REGISTRY[target["id"]][0] == "HKLM"

    @staticmethod
    def _location(target):
        import winreg
        hive, path, name, _ = REGISTRY[target["id"]]
        return winreg, winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER, path, name

    def capture(self, target):
        reg, hive, path, name = self._location(target)
        missing = []
        for index in range(1, len(path.split("\\")) + 1):
            ancestor = "\\".join(path.split("\\")[:index])
            try:
                with reg.OpenKey(hive, ancestor, 0, reg.KEY_READ | reg.KEY_WOW64_64KEY):
                    pass
            except FileNotFoundError:
                missing.append(ancestor)
        if missing:
            return {"exists": False, "key_exists": False, "missing_keys": missing}
        with reg.OpenKey(hive, path, 0, reg.KEY_READ | reg.KEY_WOW64_64KEY) as key:
            try:
                value, kind = reg.QueryValueEx(key, name)
                if isinstance(value, bytes):
                    value = {"base64": base64.b64encode(value).decode("ascii")}
                return {"exists": True, "key_exists": True, "type": kind, "value": value, "missing_keys": []}
            except FileNotFoundError:
                return {"exists": False, "key_exists": True, "missing_keys": []}

    def apply(self, target, desired):
        require_transaction()
        reg, hive, path, name = self._location(target)
        if desired["exists"]:
            with reg.CreateKeyEx(hive, path, 0, reg.KEY_SET_VALUE | reg.KEY_WOW64_64KEY) as key:
                reg.SetValueEx(key, name, 0, desired["type"], desired["value"])
        else:
            try:
                with reg.OpenKey(hive, path, 0, reg.KEY_SET_VALUE | reg.KEY_WOW64_64KEY) as key:
                    reg.DeleteValue(key, name)
            except FileNotFoundError:
                pass

    def restore(self, target, original):
        reg, hive, path, name = self._location(target)
        state = deepcopy(original)
        if state.get("exists") and isinstance(state.get("value"), dict):
            state["value"] = base64.b64decode(state["value"]["base64"], validate=True)
        # Original type can differ from the requested value type. Restore it exactly.
        self.apply(target, state)
        for ancestor in reversed(original["missing_keys"]):
            try:
                with reg.OpenKey(hive, ancestor, 0, reg.KEY_READ | reg.KEY_WOW64_64KEY) as key:
                    children, values, _ = reg.QueryInfoKey(key)
                if children or values:
                    break
                reg.DeleteKeyEx(hive, ancestor, reg.KEY_WOW64_64KEY)
            except FileNotFoundError:
                pass

    def verify(self, current, expected):
        if not expected["exists"]:
            return not current["exists"]
        return matches(current, {key: expected[key] for key in ("exists", "type", "value")})

    def owns_partial(self, current, original, proposed):
        return self.verify(current, proposed) or current == original


class ServiceHandler(Handler):
    def __init__(self, backend):
        self.backend = backend

    def resource_identity(self, target):
        return {"name": target["name"].casefold()}

    def validate(self, target, desired):
        if set(target) != {"name"}:
            raise RecoveryError("Invalid service target")
        name = text(target["name"], 256)
        if not desired or set(desired) - {"running", "startup", "delayed"}:
            raise RecoveryError("Unsupported service configuration change")
        if "running" in desired and not isinstance(desired["running"], bool):
            raise RecoveryError("Invalid service state")
        if "startup" in desired and desired["startup"] not in {"Auto", "Manual", "Disabled"}:
            raise RecoveryError("Unsupported service startup type")
        if "delayed" in desired and not isinstance(desired["delayed"], bool):
            raise RecoveryError("Invalid delayed startup value")
    def classify(self, target, desired):
        protected = {value.casefold() for value in policy()["blocked_service_stop"]}
        if target["name"].casefold() in protected and (desired.get("running") is False or desired.get("startup") == "Disabled"):
            raise RecoveryError("This critical Windows service is protected against stopping/disabling")
        critical = target["name"].casefold() in {value.casefold() for value in policy()["critical_services"]}
        return Risk.HIGH if critical else Risk.MEDIUM, Capability.FULL, True

    def capture(self, target):
        return self.backend.service_read(target["name"])

    def apply(self, target, desired):
        self.backend.service_write(target["name"], desired)

    def restore(self, target, original):
        self.backend.service_write(target["name"], {key: original[key] for key in ("startup", "delayed", "running")})


class DNSHandler(Handler):
    risk = Risk.HIGH
    connectivity = True

    def __init__(self, backend):
        self.backend = backend

    def resource_identity(self, target):
        return {"interface": str(uuid.UUID(target["interface"]))}

    def validate(self, target, desired):
        if set(target) != {"interface"}:
            raise RecoveryError("Choose one specific network interface")
        try:
            uuid.UUID(target["interface"])
        except (ValueError, TypeError, AttributeError) as error:
            raise RecoveryError("Invalid network interface identity") from error
        if set(desired) != {"source", "servers"} or desired["source"] not in {"dhcp", "static"}:
            raise RecoveryError("Unsupported DNS request")
        if not isinstance(desired["servers"], list) or len(desired["servers"]) > 8:
            raise RecoveryError("Invalid DNS server list")
        if desired["source"] == "static" and not desired["servers"]:
            raise RecoveryError("At least one DNS server is required")
        for address in desired["servers"]:
            if ipaddress.ip_address(address).version != 4:
                raise RecoveryError("This handler supports IPv4 DNS; IPv6 settings are preserved")

    def capture(self, target):
        return self.backend.dns_read(target["interface"])

    def apply(self, target, desired):
        self.backend.dns_write(target["interface"], desired)

    def restore(self, target, original):
        self.backend.dns_write(target["interface"], original)

    def verify(self, current, expected):
        return current["source"] == expected["source"] and (expected["source"] == "dhcp" or current["servers"] == expected["servers"])

    def compare_state(self, state):
        # DHCP leases can legitimately provide a new address while restoring auto DNS.
        return {"source": state["source"], "servers": state["servers"] if state["source"] == "static" else [],
                "ipv6": state["ipv6"], "interface": state["interface"]}


class FirewallProfilesHandler(Handler):
    risk = Risk.HIGH
    connectivity = True

    def __init__(self, backend):
        self.backend = backend

    def validate(self, target, desired):
        if target != {"scope": "Windows Firewall"} or not desired or set(desired) - {"Domain", "Private", "Public"}:
            raise RecoveryError("Unsupported firewall profile request")
        if any(not isinstance(value, bool) for value in desired.values()):
            raise RecoveryError("Invalid firewall profile state")
        if any(value is False for value in desired.values()):
            raise RecoveryError("Disabling Windows Firewall protection is blocked")

    def capture(self, target):
        return self.backend.firewall_profiles_read()

    def apply(self, target, desired):
        self.backend.firewall_profiles_write(desired)

    def restore(self, target, original):
        self.backend.firewall_profiles_write(original)


class FirewallRuleHandler(Handler):
    risk = Risk.HIGH
    connectivity = True
    resource_group = "firewall.rule"
    FIELDS = {"DisplayName", "Description", "Enabled", "Direction", "Action", "Profile", "EdgeTraversalPolicy",
              "Protocol", "LocalPort", "RemotePort", "LocalAddress", "RemoteAddress", "Program", "Service"}

    def __init__(self, backend):
        self.backend = backend

    def resource_identity(self, target):
        return {"name": target["name"].casefold()}

    def validate(self, target, desired):
        if set(target) != {"name"}:
            raise RecoveryError("Invalid firewall rule target")
        text(target["name"])
        if not isinstance(desired.get("exists"), bool) or set(desired) - {"exists", "rule"}:
            raise RecoveryError("Invalid firewall rule request")
        if desired["exists"]:
            rule = desired.get("rule")
            if not isinstance(rule, dict) or set(rule) != self.FIELDS:
                raise RecoveryError("An exact supported firewall rule definition is required")
            if rule["Direction"] not in {"Inbound", "Outbound"} or rule["Action"] not in {"Allow", "Block"}:
                raise RecoveryError("Invalid firewall direction/action")
            if any(not isinstance(value, (str, list)) for value in rule.values()):
                raise RecoveryError("Invalid firewall rule property")

    def capture(self, target):
        return self.backend.firewall_rule_read(target["name"])

    def apply(self, target, desired):
        self.backend.firewall_rule_write(target["name"], desired)

    def restore(self, target, original):
        self.backend.firewall_rule_write(target["name"], original)


class PowerPlanHandler(Handler):
    def __init__(self, backend):
        self.backend = backend

    def validate(self, target, desired):
        if target != {"scope": "Active power plan"} or set(desired) != {"scheme"}:
            raise RecoveryError("Unsupported power configuration")
        try:
            uuid.UUID(desired["scheme"])
        except (ValueError, TypeError, AttributeError) as error:
            raise RecoveryError("Invalid power plan identity") from error

    def capture(self, target):
        return self.backend.power_read()

    def apply(self, target, desired):
        self.backend.power_write(desired["scheme"])

    def restore(self, target, original):
        self.backend.power_write(original["scheme"])


class HostsHandler(Handler):
    risk = Risk.HIGH

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/drivers/etc/hosts"

    def validate(self, target, desired):
        if target != {"scope": "Windows hosts file"} or set(desired) != {"content_base64"}:
            raise RecoveryError("Unsupported hosts file request")
        try:
            contents = base64.b64decode(desired["content_base64"], validate=True)
        except (ValueError, TypeError) as error:
            raise RecoveryError("Invalid hosts file content") from error
        if len(contents) > 2 * 1024 * 1024 or b"\x00" in contents:
            raise RecoveryError("Hosts content exceeds the supported size/format")

    def capture(self, target):
        from .store import reject_link
        reject_link(self.path)
        return {"exists": self.path.exists(), "content_base64": base64.b64encode(self.path.read_bytes()).decode("ascii")
                if self.path.exists() else ""}

    def apply(self, target, desired):
        require_transaction()
        self.path.write_bytes(base64.b64decode(desired["content_base64"], validate=True))

    def restore(self, target, original):
        require_transaction()
        if original["exists"]:
            self.path.write_bytes(base64.b64decode(original["content_base64"], validate=True))
        else:
            self.path.unlink(missing_ok=True)


class PowerSettingHandler(Handler):
    def __init__(self, backend):
        self.backend = backend

    def validate(self, target, desired):
        if set(target) != {"scheme", "setting"} or target["setting"] != "cpu_min":
            raise RecoveryError("Unsupported power setting")
        try:
            uuid.UUID(target["scheme"])
        except (ValueError, TypeError, AttributeError) as error:
            raise RecoveryError("Invalid power plan identity") from error
        if not desired or set(desired) - {"ac", "dc"} or any(not isinstance(value, int) or not 0 <= value <= 100 for value in desired.values()):
            raise RecoveryError("CPU power setting must be between 0 and 100 percent")

    def capture(self, target):
        return self.backend.ps(r"""
        $all=Get-CimInstance -Namespace root\cimv2\power -ClassName Win32_PowerSettingDataIndex;
        $values=@($all | Where-Object {$_.InstanceID -like ('*{'+$p.scheme+'}*{893dee8e-2bef-41e0-89c6-b55d0929964c}')});
        $ac=@($values | Where-Object InstanceID -like '*\AC\*');
        $dc=@($values | Where-Object InstanceID -like '*\DC\*');
        if ($ac.Count -ne 1 -or $dc.Count -ne 1) {throw 'Exact CPU power indexes are unavailable'};
        @{ac=[int]$ac[0].SettingIndexValue;dc=[int]$dc[0].SettingIndexValue} | ConvertTo-Json -Compress
        """, target)

    def apply(self, target, desired):
        require_transaction()
        self.backend.ps("""
        if ($null -ne $p.state.ac) {
          & powercfg.exe /setacvalueindex $p.scheme SUB_PROCESSOR PROCTHROTTLEMIN $p.state.ac | Out-Null;
          if ($LASTEXITCODE -ne 0) {throw 'AC CPU power update failed'}
        };
        if ($null -ne $p.state.dc) {
          & powercfg.exe /setdcvalueindex $p.scheme SUB_PROCESSOR PROCTHROTTLEMIN $p.state.dc | Out-Null;
          if ($LASTEXITCODE -ne 0) {throw 'DC CPU power update failed'}
        }
        """, {"scheme": target["scheme"], "state": desired})

    def restore(self, target, original):
        self.apply(target, original)


class HibernationHandler(Handler):
    risk = Risk.HIGH
    capability = Capability.PARTIAL

    def __init__(self, backend):
        self.backend = backend

    def validate(self, target, desired):
        if target != {"scope": "Windows hibernation"} or set(desired) != {"enabled"} or not isinstance(desired["enabled"], bool):
            raise RecoveryError("Unsupported hibernation request")

    def capture(self, target):
        return self.backend.ps(r"""
        $v=Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Power';
        @{enabled=($v.HibernateEnabled -eq 1);kind=$v.HiberFileType;size_percent=$v.HiberFileSizePercent} | ConvertTo-Json -Compress
        """)

    def apply(self, target, desired):
        require_transaction()
        self.backend.ps("$state=if ($p.enabled) {'on'} else {'off'}; & powercfg.exe /hibernate $state | Out-Null;"
                        "if ($LASTEXITCODE -ne 0) {throw 'Hibernation setting failed'}", desired)

    def restore(self, target, original):
        self.apply(target, original)
        # A previous hibernation image/session is never recreated or claimed recovered.
        if original["enabled"] and original.get("size_percent"):
            self.backend.ps("& powercfg.exe /hibernate /size $p.percent | Out-Null;"
                            "if ($LASTEXITCODE -ne 0) {throw 'Original hibernation size could not be restored'}",
                            {"percent": original["size_percent"]})


class ProcessHandler(Handler):
    risk = Risk.HIGH
    capability = Capability.MANUAL

    def __init__(self, backend):
        self.backend = backend

    def validate(self, target, desired):
        if set(target) != {"pid", "started"} or not isinstance(target["pid"], int) or target["pid"] <= 4:
            raise RecoveryError("Invalid or protected process identity")
        if not isinstance(target["started"], (int, float)) or target["started"] <= 0 or desired != {"running": False}:
            raise RecoveryError("Process recovery requires the exact process start time")

    def capture(self, target):
        import psutil
        try:
            process = psutil.Process(target["pid"])
            if process.create_time() != target["started"]:
                return {"running": False, **target}
            services = []
            if sys.platform == "win32":
                for service in psutil.win_service_iter():
                    info = service.as_dict()
                    if info.get("pid") == target["pid"]:
                        services.append(self.backend.service_read(info["name"]))
            return {"running": process.is_running(), **target, "name": process.name(), "executable": process.exe(),
                    "user": process.username(), "parent": process.ppid(), "publisher": None, "services": services}
        except psutil.NoSuchProcess:
            return {"running": False, **target}

    def classify(self, target, desired):
        import psutil
        state = self.capture(target)
        if state.get("name", "").casefold() in {name.casefold() for name in policy()["protected_processes"]}:
            raise RecoveryError("This critical Windows process is protected")
        protected = {name.casefold() for name in policy()["blocked_service_stop"]}
        if any(service["name"].casefold() in protected for service in state.get("services", [])):
            raise RecoveryError("This process hosts a protected Windows service")
        admin = state.get("user", psutil.Process().username()) != psutil.Process().username()
        return self.risk, Capability.PARTIAL if state.get("services") else Capability.MANUAL, admin

    def apply(self, target, desired):
        require_transaction()
        import psutil
        self.classify(target, desired)
        process = psutil.Process(target["pid"])
        if process.create_time() != target["started"]:
            raise RecoveryError("Process identity changed; the replacement process was not terminated")
        process.terminate()
        process.wait(timeout=15)

    def restore(self, target, original):
        require_transaction()
        if not original.get("services"):
            raise RecoveryError("This process cannot be automatically restored. Manual restart may be required. Any unsaved data may be permanently lost.")
        for service in original["services"]:
            self.backend.service_write(service["name"], {"startup": service["startup"], "delayed": service["delayed"],
                                                          "running": service["running"]})
        raise RecoveryError("Associated services restarted; original process/session state requires manual verification")


class FirewallEnabledHandler(FirewallRuleHandler):
    def validate(self, target, desired):
        if set(target) != {"name"} or set(desired) != {"enabled"} or not isinstance(desired["enabled"], bool):
            raise RecoveryError("Invalid firewall rule enable/disable request")
        text(target["name"])

    def apply(self, target, desired):
        require_transaction()
        self.backend.ps("Set-NetFirewallRule -PolicyStore PersistentStore -Name $p.name -Enabled $p.enabled",
                        {"name": target["name"], "enabled": desired["enabled"]})

    def restore(self, target, original):
        if not original["exists"]:
            raise RecoveryError("Original rule was unavailable; manual recovery required")
        self.apply(target, {"enabled": str(original["rule"]["Enabled"]).lower() == "true"})

    def verify(self, current, expected):
        return current["exists"] and (str(current["rule"]["Enabled"]).lower() == "true") == expected["enabled"]


class SecuritySettingHandler(Handler):
    risk = Risk.HIGH

    def __init__(self, backend):
        self.backend = backend

    def validate(self, target, desired):
        supported = {"defender": {"enabled": True}, "guest": {"enabled": False}, "smbv1": {"state": "Disabled"}}
        if set(target) != {"id"} or target["id"] not in supported or desired != supported[target["id"]]:
            raise RecoveryError("Unsupported security setting; weakening protection is not an available action")

    def classify(self, target, desired):
        return self.risk, Capability.PARTIAL if target["id"] == "smbv1" else Capability.FULL, True

    def capture(self, target):
        if target["id"] == "defender":
            return self.backend.ps("@{enabled=[bool](Get-MpComputerStatus).RealTimeProtectionEnabled;"
                                   "disabled_preference=[bool](Get-MpPreference).DisableRealtimeMonitoring} | ConvertTo-Json -Compress")
        if target["id"] == "guest":
            return self.backend.ps("$u=Get-LocalUser | Where-Object {$_.SID.Value -match '-501$'};"
                                   "if (!$u) {throw 'Guest account is unavailable'};"
                                   "@{enabled=[bool]$u.Enabled;sid=$u.SID.Value} | ConvertTo-Json -Compress")
        return self.backend.ps("@{state=(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State.ToString()} | ConvertTo-Json -Compress")

    def apply(self, target, desired):
        require_transaction()
        if target["id"] == "defender":
            self.backend.ps("Set-MpPreference -DisableRealtimeMonitoring $p.disabled", {"disabled": not desired["enabled"]})
        elif target["id"] == "guest":
            self.backend.ps("$u=Get-LocalUser | Where-Object {$_.SID.Value -match '-501$'};"
                            "if ($p.enabled) {$u | Enable-LocalUser} else {$u | Disable-LocalUser}", desired)
        elif desired["state"] == "Enabled":
            self.backend.ps("Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart | Out-Null", timeout=120)
        else:
            self.backend.ps("Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart | Out-Null", timeout=120)

    def restore(self, target, original):
        require_transaction()
        if target["id"] == "defender":
            self.backend.ps("Set-MpPreference -DisableRealtimeMonitoring $p.disabled", {"disabled": original["disabled_preference"]})
        else:
            self.apply(target, original)

    def pending_reboot(self, current, expected):
        return current.get("state") in {"EnablePending", "DisablePending"}


def handlers(backend=None):
    backend = backend or WindowsBackend()
    return {"registry.value.v1": RegistryHandler(), "service.config.v1": ServiceHandler(backend),
            "network.dns.v1": DNSHandler(backend), "firewall.profiles.v1": FirewallProfilesHandler(backend),
            "firewall.rule.v1": FirewallRuleHandler(backend), "power.active.v1": PowerPlanHandler(backend),
            "file.hosts.v1": HostsHandler(), "process.stop.v1": ProcessHandler(backend),
            "firewall.enabled.v1": FirewallEnabledHandler(backend), "security.setting.v1": SecuritySettingHandler(backend),
            "power.cpu_min.v1": PowerSettingHandler(backend), "power.hibernate.v1": HibernationHandler(backend)}
