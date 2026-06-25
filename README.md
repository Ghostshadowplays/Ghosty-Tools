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
- **Vulnerability Scanner:** Checks for Windows Defender status, Firewall, UAC, and SMBv1 risks.

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
Ghosty Tools v7.3.2 is fully optimised for **Windows**, **Linux**, and **macOS**.
- **Windows:** Deep system tweaks, Winget integration, registry startup manager, and PowerShell-based maintenance.
- **Linux:** UFW firewall management, package manager detection (apt/dnf/pacman/zypper), autostart `.desktop` management, and native log viewing.
- **macOS:** Homebrew integration, app residue cleaning, and native maintenance scripts.

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
