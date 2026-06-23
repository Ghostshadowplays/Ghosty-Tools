# 🐧 Linux Support for Ghosty Tools

Ghosty Tools was originally designed for Windows, but we have added support for Linux systems.

## ⚠️ Status: Beta / Experimental
Most system-level tools (Maintenance, Security) now have **platform-specific implementations for Linux**. Windows-only features like Debloat and Registry Tweaks will be hidden or disabled when running on Linux.

### Supported Features on Linux:
- **Dashboard:** CPU/RAM monitoring, System Specs, and Boot Time.
- **Network Hub:** IP intelligence, DNS benchmarking, and port scanning.
- **Task Manager:** Resource hog detector and process management.
- **Privacy Suite:** Privacy auditing and multi-browser cleaning.
- **Secure Shredder:** Permanent file deletion.
- **System Maintenance:** `apt` updates, upgrades, and system cleanup.
- **Security Scanner:** Linux-specific checks for `ufw`, `ssh`, and root access.
- **Speed Test:** Fully functional.
- **Password Generator:** Fully functional.
- **ShadowKeys Vault:** Fully functional (stored in `~/.config/ghostytools/`).
- **Software Installer:** Automated translation of common tools to `apt-get`.

## 🛠️ Building for Linux
To create a standalone Linux executable (similar to a Windows `.exe`), follow these steps:

1. **Install Prerequisites:**
   You will need Python 3, pip, and system libraries for PyQt6.
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv xclip xsel
   ```

2. **Run the Build Script:**
   We provide a script to automate the build process:
   ```bash
   chmod +x build_linux.sh
   ./build_linux.sh
   ```

3. **Find the Binary:**
   After the script finishes, your standalone executable will be in the `dist/` directory:
   ```bash
   ./dist/GhostyTools
   ```

## 📋 Requirements
- **Clipboard support:** Install `xclip` or `xsel`.
- **GUI:** Requires an X11 or Wayland environment.
- **Python Dependencies:** Automatically handled by the build script.

---
*Note: We are continuously expanding Linux support. If you have ideas for more Linux-specific features, please see our CONTRIBUTING.md!*
