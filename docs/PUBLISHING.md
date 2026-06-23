# Publishing Ghosty Tools (Linux)

This guide explains how to publish and distribute Ghosty Tools for Linux systems.

---

## 🐧 Linux (Debian/Ubuntu)

Ghosty Tools is automatically built as a `.deb` package via GitHub Actions whenever a new release is published.

### 1. Automated Build
The `.github/workflows/release.yml` workflow handles the creation of the package:
- It bundles the Linux binary.
- It generates the Debian `control` file with the correct version.
- It uploads `ghostytools_amd64.deb` directly to the GitHub Release assets.

### 2. Manual Installation
Users can download the `.deb` file and install it using:
```bash
sudo dpkg -i ghostytools_amd64.deb
sudo apt-get install -f  # To resolve any missing dependencies
```

---

## 📦 Linux (Snap Store)

Ghosty Tools can also be published as a Snap package if a `snapcraft.yaml` is present.

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
This will create a `.snap` file (e.g., `ghosty-tools_7.1_amd64.snap`).

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
- **DEB:** The version is updated in `release.yml`.
- **Snap:** Update `version` in `snapcraft.yaml` (if used).
