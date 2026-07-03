# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Platform detection
is_windows = sys.platform == 'win32'

added_files = [
    ('config', 'config'),
    ('images', 'images'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=['speedtest'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove vcruntime140.dll from the bundle so Windows loads it from System32.
# Bundling it next to the exe triggers DLL sideloading detections (e.g. Sigma rule
# for APT29/WinELOADER techniques). The system-installed redistributable is always
# present on Windows 10/11 and is the correct source for this DLL.
_vcruntime_dlls = {'vcruntime140.dll', 'vcruntime140_1.dll'}
a.binaries = [b for b in a.binaries if b[0].lower() not in _vcruntime_dlls]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_windows:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='GhostyTools',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=os.environ.get('TARGET_ARCH'),
        codesign_identity=None,
        entitlements_file=None,
        icon=['images/ghosty icon.ico'],
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='GhostyTools',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=os.environ.get('TARGET_ARCH'),
        codesign_identity=None,
        entitlements_file=None,
    )
