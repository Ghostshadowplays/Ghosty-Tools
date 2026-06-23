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

## 📦 Installation (Recommended)
The easiest way to use Ghosty Tools on Debian-based systems (Ubuntu, Mint, etc.) is via the official `.deb` package.

1. **Download the Package:**
   ```bash
   wget https://github.com/Ghostshadowplays/Ghosty-Tools/releases/download/v7.3/GhostyTools-Linux-x64.deb
   ```

2. **Install the Package:**
   ```bash
   sudo apt update
   sudo dpkg -i GhostyTools-Linux-x64.deb
   sudo apt install -f  # Fix any missing dependencies
   ```

3. **Run the Application:**
   You can now launch Ghosty Tools from your application menu or terminal:
   ```bash
   ghostytools
   ```

## 🛠️ Building from Source
If you prefer to build the standalone binary yourself:

1. **Install Prerequisites:**
   Ensure you have Python 3, pip, and venv installed:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv xclip
   ```

2. **Clone and Build:**
   ```bash
   git clone https://github.com/Ghostshadowplays/Ghosty-Tools.git
   cd Ghosty-Tools
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
- **Permissions:** Some features (Maintenance, Security) require `sudo` privileges.

---
*Note: We are continuously expanding Linux support. If you have ideas for more Linux-specific features, please see our CONTRIBUTING.md!*
