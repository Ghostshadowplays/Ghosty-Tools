"""Hardware and operating-system details for the unified overview."""

from datetime import datetime
from html import escape
import json
import platform
import socket

import psutil
from src.core.update_handoff import clean_restart_environment


WINDOWS_QUERY = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
function Read-Cim($Class) {
    @(Get-CimInstance -ClassName $Class -ErrorAction SilentlyContinue)
}
$details = [ordered]@{
    Computer = @(Read-Cim Win32_ComputerSystem | Select-Object Manufacturer, Model)
    OS = @(Read-Cim Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture,
        @{Name='Installed'; Expression={if ($_.InstallDate) {$_.InstallDate.ToString('yyyy-MM-dd')}}})
    CPU = @(Read-Cim Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors)
    GPU = @(Read-Cim Win32_VideoController | Select-Object Name, DriverVersion)
    Board = @(Read-Cim Win32_BaseBoard | Select-Object Manufacturer, Product)
    BIOS = @(Read-Cim Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion)
    Memory = @(Read-Cim Win32_PhysicalMemory | Select-Object DeviceLocator, Capacity, Speed)
    Disks = @(Read-Cim Win32_DiskDrive | Select-Object Model, Size, InterfaceType)
}
$details | ConvertTo-Json -Depth 5 -Compress
"""


def _section(title, lines):
    values = "<br>".join(escape(str(line)) for line in lines if line)
    return f"<p><b>{escape(title)}</b><br>{values or 'Not reported by this system'}</p>"


def common_system_details():
    """Portable readings; optional devices never prevent the rest from loading."""
    sections = []
    memory = psutil.virtual_memory()
    sections.append(_section("Memory", [
        f"{memory.total / 1024**3:.1f} GB total · {memory.available / 1024**3:.1f} GB available",
        f"{psutil.cpu_count(logical=False) or '?'} physical CPU cores · {psutil.cpu_count()} logical processors",
    ]))
    sections.append(_section("System", [
        f"{platform.system()} {platform.release()} · {platform.machine()}",
        f"Computer: {socket.gethostname()}",
        f"Booted: {datetime.fromtimestamp(psutil.boot_time()):%Y-%m-%d %H:%M}",
    ]))
    drives = []
    try:
        partitions = psutil.disk_partitions()
    except (OSError, psutil.Error):
        partitions = []
    for partition in partitions:
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            drives.append(f"{partition.mountpoint} · {partition.fstype} · "
                          f"{usage.total / 1024**3:.1f} GB total · "
                          f"{usage.free / 1024**3:.1f} GB free")
        except (OSError, PermissionError):
            continue
    sections.append(_section("Volumes", drives))
    adapters = []
    try:
        interfaces = psutil.net_if_addrs()
    except (OSError, psutil.Error):
        interfaces = {}
    for name, addresses in interfaces.items():
        ip_addresses = [address.address for address in addresses
                        if address.family in (socket.AF_INET, socket.AF_INET6)]
        if ip_addresses:
            adapters.append(f"{name}: {', '.join(ip_addresses)}")
    sections.append(_section("Network adapters", adapters))
    try:
        battery = psutil.sensors_battery()
    except (OSError, psutil.Error, NotImplementedError, AttributeError):
        battery = None
    sections.append(_section("Power", [
        f"Battery: {battery.percent:.0f}% · {'plugged in' if battery.power_plugged else 'on battery'}"
        if battery else "No battery reported (desktop or unsupported battery interface)",
    ]))
    return "".join(sections)


def windows_system_details(run_command):
    result = run_command(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_QUERY],
        timeout=45, env=clean_restart_environment(),
    )
    try:
        data = json.loads(result.stdout.lstrip("\ufeff")) if result.returncode == 0 else {}
    except (ValueError, AttributeError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    def rows(name):
        value = data.get(name, [])
        if isinstance(value, dict):
            value = [value]
        return [row for row in value if isinstance(row, dict)]

    sections = []
    sections.append(_section("Computer", [
        f"{row.get('Manufacturer', '')} {row.get('Model', '')}".strip()
        for row in rows("Computer")
    ]))
    sections.append(_section("Operating system", [
        f"{row.get('Caption', '')} · {row.get('OSArchitecture', '')} · "
        f"build {row.get('BuildNumber', '')} · installed {row.get('Installed', '')}"
        for row in rows("OS")
    ]))
    for name, title, fields in [
        ("CPU", "Processor", ("Name",)),
        ("GPU", "Graphics adapters", ("Name", "DriverVersion")),
        ("Board", "Motherboard", ("Manufacturer", "Product")),
        ("BIOS", "BIOS", ("Manufacturer", "SMBIOSBIOSVersion")),
    ]:
        sections.append(_section(title, [
            " · ".join(str(row[field]) for field in fields if row.get(field))
            for row in rows(name)
        ]))
    memory_modules = []
    for row in rows("Memory"):
        size = float(row.get("Capacity") or 0) / 1024**3
        memory_modules.append(f"{row.get('DeviceLocator') or 'Memory module'}: "
                              f"{size:.1f} GB · {row.get('Speed') or 'Unknown'} MHz")
    sections.append(_section("Memory modules", memory_modules))
    disks = []
    for row in rows("Disks"):
        size = float(row.get("Size") or 0) / 1024**3
        disks.append(f"{row.get('Model') or 'Disk'} · {size:.1f} GB · "
                     f"{row.get('InterfaceType') or 'Interface not reported'}")
    sections.append(_section("Physical drives", disks))
    if not data:
        sections.append(_section("Hardware collection", [
            "Detailed CIM information was unavailable. Portable system readings follow.",
            platform.processor(),
        ]))
    return "".join(sections)
