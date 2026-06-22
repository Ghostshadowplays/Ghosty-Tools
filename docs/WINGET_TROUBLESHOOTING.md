# WinGet Troubleshooting Guide for Ghosty Tools

If your WinGet submission is failing validation on the [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) repository, follow this guide to identify and fix the issue.

## 1. Check the Bot's Feedback
Go to your Pull Request on GitHub. Look for comments from the **WinGet Bot** or **Microsoft Maintainers**. Common labels include:
- `Manifest-Validation-Error`: There is a technical error in your manifest file.
- `Binary-Analysis-Error`: The bot found issues while scanning the `.exe`.
- `Needs-Author-Feedback`: A human or bot needs you to clarify something.

## 2. Common Errors and Fixes

### A. SHA256 Hash Mismatch
**Error:** `The hash provided in the manifest does not match the hash of the downloaded file.`
**Fix:** 
1. Re-download your `.exe` from the GitHub release.
2. Run `Get-FileHash .\GhostyTools.exe` in PowerShell.
3. Update `InstallerSha256` in the manifest file.
4. *Note: Ghosty Tools hash was verified as `D7E40050621824C5A1A1BA056E53EA3DC11C15A70C8BA35EEEFDFBEB16D43FA3` for v7.0.*

### B. License Issues
**Error:** `License URL is not reachable` or `License name is not recognized.`
**Fix:** 
- Use the **Raw** URL for the license (e.g., `https://raw.githubusercontent.com/.../LICENSE`).
- Ensure `License` is a valid identifier (e.g., `GPL-3.0`).

### C. Portable App Requirements
**Error:** `Manifest validation failed` (without specific details).
**Fix:** 
- Portable apps often require a `Commands` list so WinGet can create a shortcut. We have added `GhostyTools` to the commands.
- Ensure `ElevationRequirement` is set if the app needs Admin rights. We have set this to `elevatesSelf`.

### D. SmartScreen / Malware Flags
**Error:** `Binary analysis failed` or `Scan failed.`
**Fix:**
- This often happens with new tools or those that perform system optimizations (like registry tweaks).
- **What to do:** Respond to the PR comment stating that the tool is open-source and performs system maintenance. Provide a link to the source code.

## 3. How to Update Your Submission
If you used `wingetcreate`:
1. Update your local manifest with the latest fixes.
2. Run: `wingetcreate submit manifests\g\Ghostshadowplays\GhostyTools\7.0\Ghostshadowplays.GhostyTools.yaml` again.

If you submitted manually:
1. Update the file in your fork.
2. Push the changes to your branch; the PR will update automatically.

## 4. Manifest Validation Guide
If you see a link to the "Validation Guide" in the PR, it usually refers to this: [WinGet Manifest Validation Guide](https://github.com/microsoft/winget-pkgs/blob/master/doc/validation.md).

### Important: Folder Structure & Case Sensitivity
The WinGet bot is extremely strict about the folder structure in the `microsoft/winget-pkgs` repository. Your manifest MUST be placed in exactly this path:

`manifests/g/Ghostshadowplays/GhostyTools/7.0/Ghostshadowplays.GhostyTools.yaml`

**Common Mistakes:**
1. **Wrong Folder Name:** The folder must be `GhostyTools` (no hyphen, matching the ID).
2. **Case Sensitivity:** `Ghostshadowplays` and `GhostyTools` must have the exact same casing as the `PackageIdentifier`.
3. **Wrong File Name:** The file must be named `Ghostshadowplays.GhostyTools.yaml`, not `manifest.yml`.
4. **Wrong Partition:** The `g` folder is correct because the publisher starts with `G`.

### Manifest Version
Ensure you are using `ManifestVersion: 1.12.0` (or newer) as required by the latest WinGet validation pipelines.
