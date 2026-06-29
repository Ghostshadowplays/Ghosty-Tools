# 👻 Ghosty Tools
Official Website: [ghostyware.com](https://ghostyware.com)

[🚀 **Download Latest Release**](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)

![Security & Quality Audit](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml/badge.svg)
[![Lint: flake8](https://img.shields.io/badge/lint-flake8-1f6feb?logo=python&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml)
[![Format: black](https://img.shields.io/badge/format-black-000000?logo=python&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml)
[![Types: mypy](https://img.shields.io/badge/types-mypy-2d2d2d?logo=python&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml)
[![Releases](https://img.shields.io/github/v/release/Ghostshadowplays/Ghosty-Tools?label=Latest%20Release&logo=github)](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)

**The Professional All-in-One Cross-Platform Optimization & Security Suite**

Ghosty Tools is a high-performance, modular utility designed to secure and optimize your Windows, Linux, and macOS environments. Built with a focus on **Security First**, it combines system maintenance, security auditing, and professional-grade password management into a single, sleek interface.

## 🆕 What's New in v7.3.5

- 🎮 **Gaming Mode fixed:** `@staticmethod` decorator added to `toggle_gaming_mode` — previously the `enable` parameter defaulted to `True` when called as a class method, meaning "Revert to Defaults" was silently enabling instead of reverting. Both Enable and Revert now work correctly.
- 🧵 **Gaming Mode no longer hangs:** `QTimer.singleShot` callbacks from background threads now use the 3-argument form (`singleShot(0, context, callback)`) to ensure they run on the main thread — eliminating the UI freeze.
- 🗂️ **Log Viewer upgraded:** File selector dropdown to switch between all available log files, Refresh button, line count indicator, and a cleaner styled layout.
- 🧹 **Tidy Desktop enhanced:** Un-recognised files now appear in an "Other / Unrecognised" section (collapsed, unchecked by default). Every category has a tick-box — un-tick to skip the whole category or individual files. Parent-to-child check propagation for one-click category control.
- 🎮 **Steam game detection:** Dropping a game `.exe` now first looks up the Steam `appmanifest_*.acf` file to get the official game title — works for any installed Steam game, not just those in the built-in database.
- 🎨 **Appearance slider fixed:** Background intensity slider no longer chops/stutters on drag — `valueChanged` now only updates the internal value while dragging; the theme rebuild and save happen only once on `sliderReleased`.
- 🔧 **DLL error on update fixed:** Batch updater now cleans **all** `_MEI*` folders in `%TEMP%` (not just one specific path) before relaunching — eliminates "Failed to load Python DLL" errors after self-updates. Wait time before relaunch increased from 3 s to 5 s.

## 🆕 What's New in v7.3.4 (Hotfix)

- 🐧 **Linux sudo fix:** `is_admin()` now uses `os.geteuid()` instead of `os.getuid()` — sudo correctly grants admin mode on Linux (real UID vs effective UID).
- 🎮 **Dedicated Gaming page:** Gaming Mode and Game Compatibility Analyzer moved to their own **Gaming** sidebar page — enable/disable/revert controls and the full inline analyzer all in one place.
- 🖱️ **Drag & drop fixed:** Game `.exe` files now drop correctly onto the Game Analyzer — `QLineEdit` and `QTextEdit` no longer silently intercept drag events; a proper `_DropZoneFrame` with visual hover feedback is used instead.
- 🌐 **All games supported:** When a game is not in the built-in database (50+ titles), a manual requirements form appears — enter RAM, CPU cores, VRAM, and storage yourself, then compare against your detected hardware.
- ↩️ **Revert Gaming Mode:** New "Revert to Defaults" button restores Balanced power plan, re-enables SysMain, Windows Update, and other gaming tweaks back to their original state.

## 🆕 What's New in v7.3.3

- 🗂️ **Tidy Desktop:** New one-click desktop organiser — scans for loose files (images, videos, music, documents, archives, installers) and moves them to the correct library folder. Shortcuts and folders are never touched.
- 🎮 **Game Compatibility Analyzer:** Type a game name or drag & drop its `.exe` to get an instant compatibility score (0–100) against your hardware. Checks RAM, CPU cores, GPU VRAM, and free disk space. Built-in database of 30+ popular titles. Suggests Gaming Mode if your system is below recommended specs.
- 🚀 **Expanded Game Mode:** Gaming Mode now applies 9 comprehensive tweaks — Ultimate Performance power plan, Xbox Game DVR off, Nagle's algorithm disable per interface, GPU high-performance preference, fullscreen optimisations off, SysMain/Superfetch disable, MMCSS priority boost, and Windows Update pause — with a full restore path.
- 🛡️ **Expanded Security Scanner:** Windows checks expanded from 5 to 11 (adds RDP exposure, Windows Update status, autorun entries, BitLocker, Guest account, and open ports). Linux checks expanded from 3 to 5 (adds sudoers NOPASSWD and world-writable files).
- 🔗 **Auto-Update Shortcut:** The updater now automatically recreates the desktop shortcut pointing to the new exe after a successful update, so your shortcut is never left pointing at the old path.
- 🖥️ **Compact Page Startup:** Cleanup, Hardware, Services, and Automation pages now start minimal — data containers are hidden until a scan/refresh is triggered, making the UI feel faster and less cluttered.
- 📺 **Taller Terminal Feed:** Live terminal feed height increased from 150 to 220 px for more visible output.
- 🐧 **Tweaks Page Platform Guard:** System Tweaks page now correctly shows a "not available" notice on Linux and macOS instead of rendering Windows-only registry controls.

## 🆕 What's New in v7.3.2

- 🔧 **Settings Page:** New dedicated Settings page with minimize-to-tray toggle, alert refresh interval, startup page selector, and full Windows/Linux startup manager.
- 🖥️ **Startup Manager:** Register or remove Ghosty Tools from Windows startup (registry) or Linux autostart (`.desktop` file) — one click, no manual steps.
- 📊 **Live Sensor Data:** Hardware tab now integrates with LibreHardwareMonitor — one-click install via `winget`, automatic web server configuration, and minimized background launch.
- 🔔 **Live System Alerts:** Dashboard alerts are now fully dynamic — real-time checks for high memory, low disk space, pending reboots, and available updates.
- 🏆 **Real Health Score:** Multi-factor scoring accounts for CPU, RAM, disk usage, pending reboots, and update availability with colour-coded feedback.
- 📈 **Speed Test History:** Last 3 speed test results are now persisted and shown in the Network page.
- 📋 **Recent Activity Log:** App actions are saved across sessions and shown in the Dashboard activity card.
- 📄 **Export System Report:** Generate a full system snapshot (OS, CPU, RAM, disk, network, speed history, activity) saved to your Desktop.
- 📝 **Built-in Log Viewer:** View today's log file in-app without leaving the window.
- ↔️ **Resizable Sidebar:** Drag the divider between the sidebar and content area to any width you prefer.
- 🎨 **Appearance & Theme Buttons:** Clearly labelled sidebar buttons — `🎨 Appearance` and `🌙 Toggle Theme` — no more mystery icons.
- 🔢 **Version Badge:** Current version shown at the bottom of the sidebar.
- 🃏 **Card Hover Effects:** Dashboard cards highlight their border on hover using the active theme colour.
- 🐧 **Linux Transparency Fix:** Background no longer bleeds through on Linux desktop environments.
- ⚡ **Speed Test Fix:** Speed test now works correctly in the Windows `.exe` (noconsole) build.
- 🖼️ **Sidebar Icons Fix:** Nav icons now render correctly on all Windows systems (font loaded via inline stylesheet).
- 💾 **Config File Locations:** All config files (`theme.json`, activity log, speed history, backup) now stored safely in `%APPDATA%\GhostyTools\` — nothing lands next to the exe.
- 🔄 **Update Reliability:** Batch updater now cleans up the old PyInstaller temp folder before launching the new exe, preventing DLL load errors on restart.
- 🍎 **macOS Branding Fixed:** macOS now shows the correct 🍎 icon instead of the Linux 🐧.
- 🖼️ **PNG Icon on Linux:** App icon uses `.png` on Linux for better desktop environment integration.

## ✨ Features

### 📊 Dashboard & System Overview
- **Live System Usage:** Real-time monitoring of CPU, RAM, and GPU utilisation with colour-coded health indicators.
- **System Health Score:** Multi-factor score (0–100) accounting for CPU, RAM, disk, pending reboots, and available updates.
- **Live System Alerts:** Dynamic alerts for high memory, low disk, pending reboots, and update availability — auto-refreshed every 60 seconds.
- **Recent Activity:** Persistent log of recent app actions shown on the Dashboard.
- **System Specifications:** Detailed hardware information (CPU, GPU, RAM, Motherboard) — cross-platform.
- **Battery & Disk Health:** Real-time health status monitoring for battery and system drives.
- **Quick Actions:** One-click shortcuts for common tasks, platform-aware (Windows Update / macOS Update / APT).

### 🌐 Network Hub
- **Network Speed Test:** Integrated speed test with persistent history of the last 3 results.
- **IP Intelligence:** Display local/public IP, ISP details, and geographic location.
- **DNS Benchmarker:** Compare response times of major DNS providers to find the fastest one.
- **Port Scanner:** Check for open ports to identify potential security exposure.

### 🔧 System Maintenance & Advanced Tools
- **Full Maintenance:** One-click execution of SFC, DISM, GPUpdate, and CHKDSK.
- **Hosts File Editor:** Safe GUI for managing system-level domain mapping and telemetry blocking.
- **DNS Flush & Network Repair:** Quickly clear DNS cache or run a full network repair sequence.
- **Windows Updates:** Check for and initiate Windows Update installations.
- **Restore Points:** Create system restore points before making major changes.

### 🛡️ Privacy & Security
- **Privacy Audit:** Scans for privacy-invasive settings and helps disable them.
- **Browser Privacy Cleaner:** Clear cookies, cache, and history across Chrome, Firefox, Edge, and Safari.
- **Secure File Shredder:** Permanently delete sensitive files by overwriting them multiple times.
- **Vulnerability Scanner:** Checks Windows Defender, Firewall, UAC, SMBv1, RDP exposure, Windows Update status, autorun entries, BitLocker, Guest account, and open ports (11 checks on Windows, 5 on Linux).

### 🖥️ Hardware & Sensors
- **Live Sensor Data:** Real-time CPU/GPU temperatures, fan speeds, and voltages via LibreHardwareMonitor.
- **One-click LHM Setup:** Install LibreHardwareMonitor via `winget`, auto-configure its web server, and launch it minimised — sensors appear automatically.
- **S.M.A.R.T. Diagnostics:** Disk health checks and battery info.

### 🚀 Task & Process Management
- **Resource Hog Detector:** Lists top processes by CPU/RAM with a one-click "Optimize" button.
- **Process Manager:** Real-time process monitoring and management.

### 🗑️ Windows Debloat & Tool Manager
- **System Scan:** Detect installed bloatware across multiple categories (Xbox, Cortana, Bing, etc.).
- **Smart Uninstaller:** Sequences from Winget ID → Name → Specialised PowerShell removal for stubborn apps.
- **App Essentials:** One-click installation for 7-Zip, VLC, Brave, Discord, HWiNFO, and more via Winget.
- **Tidy Desktop:** Automatically organise desktop files into library folders (Pictures, Videos, Music, Documents, Downloads) — shortcuts and folders untouched.
- **Game Compatibility Analyzer:** Check if your system meets the minimum/recommended requirements for 30+ popular games. Drag & drop an exe or type a game name for an instant scored report.

### 🔐 Password Management
- **Password Generator:** Generate cryptographically secure passwords.
- **ShadowKeys Vault:** AES-256 encrypted local password storage with PBKDF2-HMAC key derivation.
- **Clipboard Security:** Copied passwords are automatically cleared after 30 seconds.

### ⚙️ Settings & Startup
- **Settings Page:** Control minimize-to-tray, alert refresh interval, and startup page from within the app.
- **Startup Manager (Windows):** Add/remove Ghosty Tools from the Windows registry Run key.
- **Startup Manager (Linux):** Add/remove a `.desktop` autostart entry for your desktop environment.

### 🔔 Tray & Notifications
- **System Tray Icon:** Always-available tray icon with quick-access menu for common actions.
- **Tray Notifications:** Desktop notifications for completed scans, updates, speed tests, and more.
- **Minimize Behaviour:** By default, minimising keeps the window in the taskbar and Task View. Tray-on-minimize is optional in Settings.

## 🌍 Cross-Platform Support
Ghosty Tools v7.3.5 is fully optimised for **Windows**, **Linux**, and **macOS**.
- **Windows:** Deep system tweaks, Winget integration, registry startup manager, and PowerShell-based maintenance.
- **Linux:** UFW firewall management, package manager detection (apt/dnf/pacman/zypper), autostart `.desktop` management, and native log viewing.
- **macOS:** Homebrew integration, app residue cleaning, and native maintenance scripts.

> **Note for Linux & macOS users:** Core features (Dashboard, Network Hub, Security Scanner, Task Manager, Privacy Audit, Password Vault) are fully functional on all platforms. Some Windows-specific features (Debloat, Registry Tweaks, Tidy Desktop, Game Compatibility Analyzer, Event Viewer) are automatically hidden or replaced with a platform notice on non-Windows systems. macOS support continues to expand — see [LINUX_SUPPORT.md](LINUX_SUPPORT.md) for build instructions and a full feature matrix.

See [LINUX_SUPPORT.md](LINUX_SUPPORT.md) for Linux build instructions.

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (Fully compatible with Python 3.14)
- **Windows 10/11, Linux, or macOS**
- **Administrator Privileges** (optional for launch, required for system modifications)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Ghostshadowplays/Ghosty-Tools.git
   cd Ghosty-Tools
   ```
2. Create and activate a virtual environment (recommended):
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App
```bash
python main.py
```

## 📁 Project Structure
- `src/core/` — Logic engines for scanning, cleaning, updates, and security.
- `src/gui/` — User interface components built with PyQt6.
- `src/utils/` — Helper functions, theme manager, and logging configuration.
- `config/` — JSON configuration files for bloatware definitions and version info.
- `images/` — Brand assets and icons.

## 🔒 Security Policy
- **No Data Collection:** Ghosty Tools operates entirely locally. No passwords or system data are ever transmitted externally.
- **Secure Commands:** All system operations use secure `subprocess` calls without shell execution (where possible) to prevent command injection.
- **Encryption:** ShadowKeys uses industry-standard Fernet (AES) encryption with secure key derivation (PBKDF2-HMAC-SHA256).
- **Key Verification:** The vault includes a verification block to ensure the master password is correct before attempting to decrypt your data.
- **Local Storage:** All config, vault, and log files are stored in platform-specific directories with restricted permissions:
  - **Windows:** `%APPDATA%\GhostyTools\`
  - **Linux/macOS:** `~/.config/GhostyTools/`
- **Clipboard Security:** Copied passwords are automatically cleared from the clipboard after 30 seconds.
- **Least Privilege:** The application launches with standard user privileges. Admin elevation is only requested when performing system-level operations.

## 📝 License
This project is licensed under the **GNU General Public License v3.0**. See the `LICENSE` file for details.

## 🙏 Special Thanks
A big thank you to [haywardgg](https://github.com/haywardgg) — systems admin, vibe coder from Manchester, and founder of a chill coding community where devs share projects, help each other out, and keep it low-pressure. This project would not be as great as it is without him.

Join the communities:
- **GhostyWare Discord:** [discord.gg/YKsAJYx](https://discord.gg/YKsAJYx)
- **haywardgg's Coding Server:** [discord.gg/UUuafBYMdG](https://discord.gg/UUuafBYMdG)

---
**Disclaimer:** *Ghosty Tools provides advanced system modification capabilities. While safety checks are included, use these tools at your own risk. Always back up important data before making system changes.*
