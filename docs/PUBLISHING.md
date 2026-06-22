# Publishing Ghosty Tools

This guide explains how to use the provided manifest files to publish Ghosty Tools to Windows (WinGet) and Linux (Snap Store).

---

## 🪟 Windows (WinGet)

Ghosty Tools can be submitted to the Windows Package Manager (WinGet) using the manifest in `manifests/g/Ghostshadowplays/GhostyTools/7.0/`.

### 1. Prepare the Release
Before submitting, you must have a public release on GitHub (or another host) with the `.exe` file.

### 2. Update the Manifest
1. Download your latest `GhostyTools.exe`.
2. Open PowerShell and calculate the SHA256 hash:
   ```powershell
   Get-FileHash .\GhostyTools.exe
   ```
3. Open `manifests\g\Ghostshadowplays\GhostyTools\7.0\Ghostshadowplays.GhostyTools.yaml` in this repository.
4. Replace the `InstallerSha256` value with the hash you generated.
5. Ensure `PackageLocale` is set (e.g., `en-US`).
6. Ensure `PackageVersion` and `InstallerUrl` match your latest release.

### 3. Test Locally
You can test the installation on your machine before submitting:
```powershell
winget validate manifests\g\Ghostshadowplays\GhostyTools\7.0\Ghostshadowplays.GhostyTools.yaml
winget install --manifest manifests\g\Ghostshadowplays\GhostyTools\7.0\Ghostshadowplays.GhostyTools.yaml
```

### 4. Submit to WinGet
The easiest way to submit is using the **WinGet Create** tool:
1. Install it: `winget install Microsoft.WingetCreate`
2. Run: `wingetcreate submit manifests\g\Ghostshadowplays\GhostyTools\7.0\Ghostshadowplays.GhostyTools.yaml`
Alternatively, you can manually fork [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) and submit a Pull Request with your manifest.

**Important:** If submitting manually, ensure you follow the strict folder structure:
`manifests/g/Ghostshadowplays/GhostyTools/7.0/Ghostshadowplays.GhostyTools.yaml`

**Troubleshooting:** If your submission fails validation, see [WINGET_TROUBLESHOOTING.md](WINGET_TROUBLESHOOTING.md).

---

## 🐧 Linux (Snap Store)

Ghosty Tools can be published as a Snap package using `snapcraft.yaml`.

### 1. Install Snapcraft
On a Linux system (Ubuntu is recommended):
```bash
sudo snap install snapcraft --classic
```

### 2. Build the Snap
Run the following command in the root of the project:
```bash
snapcraft
```
This will create a `.snap` file (e.g., `ghosty-tools_7.0_amd64.snap`).
*Note: If you are not on Linux, you can use Multipass or LXD which Snapcraft will automatically try to use.*

### 3. Test the Snap
Install the generated snap locally to verify it works:
```bash
sudo snap install --dangerous ghosty-tools_*.snap
```

### 4. Publish to the Store
1. Log in to your developer account:
   ```bash
   snapcraft login
   ```
2. Register the name (if not already done):
   ```bash
   snapcraft register ghosty-tools
   ```
3. Upload and release:
   ```bash
   snapcraft upload --release=stable ghosty-tools_*.snap
   ```

---

## 🛠️ Maintenance
Every time you release a new version:
- **WinGet:** Update `PackageVersion`, `InstallerUrl`, and `InstallerSha256` in the manifest under `manifests/g/Ghostshadowplays/GhostyTools/`.
- **Snap:** Update `version` in `snapcraft.yaml` and rebuild/upload.
