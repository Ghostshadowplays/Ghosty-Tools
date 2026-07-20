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

## 🆕 What's New in v8.0.1

- 🐛 **Driver list fixed:** System report driver list no longer shows garbled/corrupted characters — switched from `driverquery` (OEM encoding) to `Get-CimInstance Win32_PnPSignedDriver` via PowerShell for clean Unicode output.
- 🔧 **Full System Maintenance expanded:** Phase 1 now includes `DISM /ScanHealth` (corruption detection) and `DISM /StartComponentCleanup /ResetBase` (WinSxS component store cleanup) alongside the existing CheckHealth and RestoreHealth passes.
- 📋 **Export Report auto-fill:** Clicking "Submit to GhostyWare Support" now automatically copies the full report to your clipboard before opening the intake form — paste it directly into the "Reported Issues" field.
- 🎮 **Gaming Mode fully stops Windows Update:** Previously only changed the service startup type (effective on next boot). Now immediately stops `wuauserv`, `UsoSvc`, and `WaaSMedicSvc`, and sets the `NoAutoUpdate` registry policy — updates and restarts are properly suppressed while Gaming Mode is active. Revert restores all three services and clears the policy.

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
Ghosty Tools v8.0.1 is fully optimised for **Windows**, **Linux**, and **macOS**.
- **Windows:** Deep system tweaks, Winget integration, registry startup manager, and PowerShell-based maintenance.
- **Linux:** UFW firewall management, package manager detection (apt/dnf/pacman/zypper), autostart `.desktop` management, and native log viewing.
- **macOS:** Homebrew integration, app residue cleaning, and native maintenance scripts.

> **Note for Linux & macOS users:** Core features (Dashboard, Network Hub, Security Scanner, Task Manager, Privacy Audit, Password Vault) are fully functional on all platforms. Some Windows-specific features (Debloat, Registry Tweaks, Tidy Desktop, Game Compatibility Analyzer, Event Viewer) are automatically hidden or replaced with a platform notice on non-Windows systems. macOS support continues to expand — see [LINUX_SUPPORT.md](LINUX_SUPPORT.md) for build instructions and a full feature matrix.

See [LINUX_SUPPORT.md](LINUX_SUPPORT.md) for Linux build instructions.

## 📦 Install via Winget

You can install Ghosty Tools directly from the Windows Package Manager:

```powershell
winget install ghostytools
```

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
