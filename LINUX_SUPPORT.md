# 🐧 Linux Support for Ghosty Tools

Ghosty Tools is fully cross-platform with native support for Linux desktop environments.

## Status: Stable — v7.3.5

Core features have **platform-specific Linux implementations**. Windows-only features (Debloat, Registry Tweaks, Tidy Desktop, Game Analyzer, Event Viewer) are automatically hidden or replaced with a platform notice when running on Linux.

---

## Supported Features on Linux

| Feature | Status |
|---|---|
| Dashboard — CPU/RAM/Disk monitoring | ✅ Full |
| System Health Score | ✅ Full |
| Live System Alerts | ✅ Full |
| Recent Activity Log | ✅ Full |
| Network Hub (IP, DNS, Port Scan, Speed Test) | ✅ Full |
| Task / Process Manager | ✅ Full |
| Privacy Audit & Browser Cleaner | ✅ Full |
| Secure File Shredder | ✅ Full |
| System Maintenance (apt/dnf/pacman/zypper) | ✅ Package-manager aware |
| Security Scanner (ufw, ssh, sudo, world-writable checks) | ✅ Full (5 checks) |
| Password Generator & ShadowKeys Vault | ✅ Full |
| Hardware Specs (CPU, GPU, RAM, Board) | ✅ Full (via lscpu, lspci, /sys) |
| Linux Autostart Manager | ✅ Full (~/.config/autostart/) |
| Software Installer | ✅ Translated to apt-get |
| App Appearance / Theme | ✅ Full |
| System Tray & Notifications | ✅ Full |
| Debloat / Registry Tweaks | ❌ Windows only (platform notice shown) |
| Tidy Desktop | ❌ Windows only |
| Game Compatibility Analyzer | ❌ Windows only |
| Event Viewer | ❌ Windows only (hidden) |
| LibreHardwareMonitor Sensors | ❌ Windows only |

---

## Config & Data Locations (Linux)

All persistent data is stored safely in the user home directory:

| File | Location |
|---|---|
| App settings | `~/.config/GhostyTools/app_settings.json` |
| Theme config | `~/.config/GhostyTools/theme.json` |
| ShadowKeys vault | `~/.config/GhostyTools/vault.db` |
| Activity log | `~/.config/GhostyTools/activity.json` |
| Speed test history | `~/.config/GhostyTools/speedtest_history.json` |
| Log files | `~/.config/GhostyTools/logs/` |
| Autostart entry | `~/.config/autostart/ghostytools.desktop` |

---

## Package Manager Detection

Ghosty Tools automatically detects your Linux package manager at startup and uses it throughout maintenance and cleanup operations. Supported:

- `apt` (Debian, Ubuntu, Mint)
- `dnf` (Fedora, RHEL)
- `pacman` (Arch, Manjaro)
- `zypper` (openSUSE)
- `emerge` (Gentoo)

---

## Installation (Recommended — Debian/Ubuntu)

The easiest way to install on Debian-based systems is via the official `.deb` package.

1. **Download the package:**
   ```bash
   wget https://github.com/Ghostshadowplays/Ghosty-Tools/releases/latest/download/GhostyTools-Linux-x64.deb
   ```

2. **Install:**
   ```bash
   sudo apt update
   sudo dpkg -i GhostyTools-Linux-x64.deb
   sudo apt install -f  # Fix any missing dependencies
   ```

3. **Run:**
   ```bash
   ghostytools
   ```

---

## Building from Source

1. **Install prerequisites:**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv xclip
   ```

2. **Clone and set up:**
   ```bash
   git clone https://github.com/Ghostshadowplays/Ghosty-Tools.git
   cd Ghosty-Tools
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run from source:**
   ```bash
   python main.py
   ```

4. **Or build a standalone binary:**
   ```bash
   chmod +x build_linux.sh
   ./build_linux.sh
   # Output: dist/GhostyTools
   ```

---

## Requirements

- **Clipboard support:** Install `xclip` or `xsel`
- **GUI:** Requires an X11 or Wayland environment
- **Permissions:** Maintenance and Security features require `sudo` privileges
- **App icon:** Uses `.png` format for better desktop environment integration

---

---

*Ghosty Tools v7.3.5 — We are continuously expanding Linux support. Ideas and contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).*
