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

## 🆕 What's New in v7.3.1
- 🎨 **GUI Overhaul:** Complete modernization of all pages with a professional dark-modern aesthetic and card-based layout.
- 🚀 **Smart Update System:** New branded notification banner and detailed update dialog for a seamless upgrade experience.
- 📊 **Dynamic Dashboard:** Real-time system health scoring, interactive resource monitors, and proactive system alerts.
- 🤖 **Automation Reports:** Integrated system reporting directly within the application's Automation page.
- 📋 **Enhanced Management:** Modernized Event Viewer, Services Manager, and Advanced System Tools for better usability.
- 🔐 **ShadowKeys v2:** Redesigned vault and generator interface with improved security and clipboard management.
- 📐 **Responsive Design:** Optimized window dimensions and added global scrolling to support a wider range of screen resolutions.
- 🚀 **Stability Fixes:** Resolved several critical runtime exceptions and improved cross-platform compatibility.

## ✨ Features

### 📊 Dashboard & System Overview
- **Live System Usage:** Real-time monitoring of CPU and RAM utilization.
- **System Specifications:** Detailed hardware information (CPU, GPU, RAM, Motherboard).
- **System Overview:** View boot time, OS build, and detailed hardware models at a glance.
- **Battery & Disk Health:** Real-time health status monitoring for your battery and system drive.
- **Network Speed Test:** Integrated speed test to verify your connection.

### 🌐 Network Hub
- **IP Intelligence:** Display local/public IP, ISP details, and geographic location.
- **DNS Benchmarker:** Compare response times of major DNS providers to find the fastest one.
- **Port Scanner:** Check for open ports on the local machine to identify potential security holes.

### 🔧 System Maintenance & Advanced Tools
- **Full Maintenance:** One-click execution of SFC, DISM, GPUpdate, and CHKDSK.
- **Hosts File Editor:** Safe GUI for managing system-level domain mapping and telemetry blocking.
- **Service Management:** Reset Print Spooler and other essential system services.
- **DNS Flush:** Quickly clear your DNS resolver cache.
- **Windows Updates:** Check for and initiate Windows Update installations.
- **Restore Points:** Create system restore points before making major changes.

### 🛡️ Privacy & Security
- **Privacy Audit:** Scans for privacy-invasive settings and helps disable them.
- **Browser Privacy Cleaner:** Clear cookies, cache, and history across Chrome, Firefox, Edge, and Safari.
- **Secure File Shredder:** Permanently delete sensitive files by overwriting them multiple times.
- **Vulnerability Scanner:** Checks for Windows Defender status, Firewall, UAC, and SMBv1 risks.

### 🚀 Task & Process Management
- **Resource Hog Detector:** Lists top processes using CPU/RAM with a one-click "Optimize" button.
- **Process Manager:** Real-time process monitoring and management.

### 🗑️ Windows Debloat & Tool Manager
- **System Scan:** Detect installed bloatware across multiple categories (Xbox, Cortana, Bing, etc.).
- **Smart Uninstaller:** Sequences from Winget ID -> Name -> Specialized PowerShell removal for stubborn apps.
- **App Essentials:** One-click installation for 7-Zip, VLC, Brave, Discord, HWiNFO, and more via Winget.

### 🔐 Password Management
- **Password Generator:** Generate cryptographically secure passwords.
- **ShadowKeys Vault:** AES-256 encrypted local password storage with PBKDF2-HMAC key derivation.
- **System Tray Integration:** Minimize to tray with quick-access buttons for "Quick Clean" or "Speed Test".

## 🌍 Cross-Platform Support
Ghosty Tools v7.3.1 is fully optimized for **Windows**, **Linux**, and **macOS**.
- **Windows:** Deep system tweaks, Winget integration, and PowerShell-based maintenance.
- **Linux:** UFW firewall management, PPA/Repository management, and native log viewing.
- **macOS:** Homebrew integration, app residue cleaning, and native maintenance scripts.

See [LINUX_SUPPORT.md](LINUX_SUPPORT.md) for build instructions.

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (Fully compatible with Python 3.14)
- **Windows 10 or 11**
- **Administrator Privileges** (optional for launch, required for system modifications)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Ghostshadowplays/Ghosty-Tools.git
   cd Ghosty-Tools
   ```
2. Create and activate a virtual environment (Recommended):
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
Launch directly:
```bash
python main.py
```

## 📁 Project Structure
- `src/core/`: Logic engines for scanning, cleaning, and security.
- `src/gui/`: User interface components built with PyQt6.
- `src/utils/`: Helper functions and logging configurations.
- `config/`: JSON configuration files for bloatware and tools.
- `images/`: Brand assets and icons.

## 🔒 Security Policy
- **No Data Collection:** Ghosty Tools operates entirely locally. No passwords or system data are ever transmitted externally.
- **Secure Commands:** All system operations use secure `subprocess` calls without shell execution (where possible) to prevent command injection.
- **Encryption:** ShadowKeys uses industry-standard Fernet (AES) encryption with secure key derivation (PBKDF2-HMAC-SHA256).
- **Key Verification:** The vault includes a verification block to ensure the master password is correct before attempting to decrypt your data.
- **Local Storage:** Salt and Vault files are stored in platform-specific configuration directories with restricted file permissions:
  - **Windows:** `%APPDATA%\GhostyTools\`
  - **Linux/macOS:** `~/.config/ghostytools/`
- **Clipboard Security:** Copied passwords are automatically cleared from the clipboard after 30 seconds to prevent accidental exposure.
- **Least Privilege:** The application launches with standard user privileges. Admin elevation is only requested when performing system-level maintenance or tweaks.

## 📝 License
This project is licensed under the **GNU General Public License v3.0**. See the `LICENSE` file for details.

## 🙏 Special Thanks
A big thank you to [haywardgg](https://github.com/haywardgg) for pushing me on my project and inspiring me with new ideas. This project would not be as great as it is without him.

---
**Disclaimer:** *Ghosty Tools provides advanced system modification capabilities. While safety checks are included, use these tools at your own risk. Always back up important data.*
