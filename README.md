# 👻 Ghosty Tools v5.0.9

[🚀 **Download Latest Release**](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)

![Security & Quality Audit](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml/badge.svg)
[![Lint: flake8](https://img.shields.io/badge/lint-flake8-1f6feb?style=flat-square&logo=python&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml)
[![Format: black](https://img.shields.io/badge/format-black-000000?style=flat-square&logo=python&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml)
[![Types: mypy](https://img.shields.io/badge/types-mypy-2d2d2d?style=flat-square&logo=python&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/actions/workflows/security-audit.yml)
[![Releases](https://img.shields.io/github/v/release/Ghostshadowplays/Ghosty-Tools?label=Latest%20Release&style=flat-square&logo=github)](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)
![GitHub Repo stars](https://img.shields.io/github/stars/Ghostshadowplays/Ghosty-Tools?style=flat-square)
[![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)
[![Linux](https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black)](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)
[![macOS](https://img.shields.io/badge/macOS-000000?style=flat-square&logo=apple&logoColor=white)](https://github.com/Ghostshadowplays/Ghosty-Tools/releases)

**The Professional All-in-One Windows Optimization & Security Suite**

Ghosty Tools is a high-performance, modular utility designed to secure and optimize your Windows environment. Built with a focus on **Security First**, it combines system maintenance, bloatware removal, and professional-grade password management into a single, sleek interface.

## ✨ Features

### 📊 Dashboard & Monitoring
- **Live System Usage:** Real-time monitoring of CPU and RAM utilization.
- **System Specifications:** Detailed hardware information (CPU, GPU, RAM, Motherboard).
- **Battery Health:** Check charge levels and power status.
- **Disk Health:** Real-time health status monitoring for your system drive.
- **Network Speed Test:** Integrated speed test to verify your connection.

### 🔧 System Maintenance
- **Full Maintenance:** One-click execution of SFC, DISM, GPUpdate, and CHKDSK.
- **DNS Flush:** Quickly clear your DNS resolver cache.
- **Disk Cleanup:** Launch the Windows Disk Cleanup utility.
- **Windows Updates:** Check for and initiate Windows Update installations.
- **Restore Points:** Create system restore points before making major changes.
- **Advanced Disk Tools:** MBR to GPT conversion utility (MBR2GPT) with safety validation.

### 🛡️ Security Assessment
- **Vulnerability Scanner:** Checks for Windows Defender status, Firewall configuration, UAC settings, SMBv1 risks, and active network shares.
- **Live Feedback:** Instant reporting of security findings with severity levels.

### 🗑️ Windows Debloat
- **System Scan:** Detect installed bloatware across multiple categories (Xbox, Cortana, Bing, etc.).
- **Safe Removal:** Categorized removal of pre-installed apps and unnecessary Windows components.
- **Restore Integration:** Links directly to restore point creation for maximum safety.

### 📦 System Tools Installer
- **Winget-Powered:** Easily install essential developer tools like WSL, Git, Python, VS Code, Docker, and more.
- **Status Detection:** Automatically detects if tools are already installed.
- **Now includes Essentials & Hardware Tools:** 7-Zip, VLC, Brave, Discord, HWiNFO, CPU-Z.

### 🔐 Password Management
- **Password Generator:** Generate cryptographically secure passwords with customizable length and complexity.
- **ShadowKeys Vault:** Robust SQLite-backed local password storage with AES-256 encryption, PBKDF2-HMAC key derivation, and automated legacy migration. Now stores data in secure, platform-specific config directories with encryption verification.

### ⚙️ System Tweaks
- **Performance & Privacy:** Categorized registry optimizations for Telemetry, Activity History, GameDVR, and more.
- **Bulk Application:** Select multiple tweaks and apply them all at once.
- **New in this build:** Disable Windows Copilot, disable News & Interests, and quickly show file extensions and hidden files.

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
Launch using the wrapper:
```bash
python "Ghosty Tools.py"
```
Or directly:
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
