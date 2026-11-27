"""Prepare a Windows update outside the running PyInstaller bundle."""

import ctypes
from dataclasses import dataclass
import hashlib
import json
import ntpath
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from src.utils.helpers import get_resource_path


@dataclass
class UpdateHandoff:
    process: subprocess.Popen
    log_path: Path


def clean_restart_environment(environ=None, runtime_dir=None):
    """Make the replacement EXE unpack a fresh runtime instead of reusing ours."""
    original = os.environ if environ is None else environ
    clean = {
        key: value for key, value in original.items()
        if not key.upper().startswith(("_PYI_", "_MEIPASS"))
        and key.upper() not in {"PYTHONHOME", "PYTHONPATH", "PSMODULEPATH", "PYINSTALLER_RESET_ENVIRONMENT"}
    }
    clean["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    runtime = runtime_dir if runtime_dir is not None else getattr(sys, "_MEIPASS", "")
    if runtime:
        root = ntpath.normcase(ntpath.normpath(runtime))
        for key in list(clean):
            if key.upper() == "PATH":
                entries = []
                for entry in clean[key].split(";"):
                    candidate = ntpath.normcase(ntpath.normpath(entry.strip('"')))
                    if candidate != root and not candidate.startswith(root + "\\"):
                        entries.append(entry)
                clean[key] = ";".join(entries)
    return clean


def launch_windows_update(new_file, current_file, source_pid=None):
    """Stage an external helper before the app exits; keep the old EXE on failure."""
    source = Path(new_file).resolve(strict=True)
    target = Path(current_file).resolve(strict=True)
    if source == target or source.suffix.lower() != ".exe":
        raise ValueError("The update must be a separate Windows executable.")
    with source.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("The downloaded file is not a Windows executable.")
        stream.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    directory = Path(tempfile.mkdtemp(prefix="handoff-", dir=str(source.parent)))
    script = directory / "apply_update.ps1"
    shutil.copyfile(get_resource_path("config/windows_update.ps1"), script)
    manifest = directory / "update.json"
    manifest.write_text(json.dumps({
        "source": str(source),
        "target": str(target),
        "source_pid": os.getpid() if source_pid is None else source_pid,
        "sha256": digest.hexdigest(),
        "log": str(directory / "update.log"),
    }, ensure_ascii=False), encoding="utf-8")
    environment = clean_restart_environment()
    runtime = getattr(sys, "_MEIPASS", None)
    # PyInstaller also changes Windows' DLL search directory for child processes.
    kernel = ctypes.windll.kernel32 if sys.platform == "win32" and runtime else None
    if kernel:
        kernel.SetDllDirectoryW(None)
    try:
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-File", str(script), "-ManifestPath", str(manifest)],
            cwd=str(directory), env=environment, close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        if kernel:
            kernel.SetDllDirectoryW(ctypes.c_wchar_p(runtime))
    return UpdateHandoff(process, directory / "update.log")
