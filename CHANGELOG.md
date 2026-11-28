# Changelog

Release notes are preserved here as the README moves to each new version.

## v8.0.9

### Changes

- chore: prepare release v8.0.9 (#63) (e815fc1)
- Archive monthly release notes (523f747)
- Improve appearance customization and theming (3db0716)

**Full Changelog**: https://github.com/Ghostshadowplays/Ghosty-Tools/compare/v8.0.8...v8.0.9

[GitHub release](https://github.com/Ghostshadowplays/Ghosty-Tools/releases/tag/v8.0.9)

## v8.0.8

### What's Changed
* Update README.md by @RickyRichards in https://github.com/Ghostshadowplays/Ghosty-Tools/pull/61
* Release v8.0.8 by @Ghostshadowplays in https://github.com/Ghostshadowplays/Ghosty-Tools/pull/62

### New Contributors
* @RickyRichards made their first contribution in https://github.com/Ghostshadowplays/Ghosty-Tools/pull/61

**Full Changelog**: https://github.com/Ghostshadowplays/Ghosty-Tools/compare/v8.0.7...v8.0.8

[GitHub release](https://github.com/Ghostshadowplays/Ghosty-Tools/releases/tag/v8.0.8)

## v8.0.7

- 📅 **Monthly release preparation:** Scheduled version-bump pull requests with SSH-signed commits and checks for CI, security audits, and CodeQL.
- 🚀 **Release publishing:** Added workflows to create release tags and publish GitHub Releases after a release pull request is merged.
- 📦 **Package verification:** Added SHA256 checksum generation for Windows EXE and Linux DEB packages, plus a software bill of materials (SBOM), to the release pipeline.
- 🔄 **Maintenance updates:** Daily dependency checks, GitHub Actions dependency updates, and expanded security audit workflows.

[GitHub release](https://github.com/Ghostshadowplays/Ghosty-Tools/releases/tag/v8.0.7)

## v8.0.6

### A workspace that feels like Ghosty

- A new control room with GhostyWare branding and the Ghosty mascot.
- Grouped navigation and tool search. Press **Ctrl+K** to find a tool, then
  **Enter** to open it.
- The new **Ghost Mint** palette, sharper icons and more space for your tools.
- An activity log you can open when needed, with progress visible in the footer.

### Your system, in one overview

- CPU, graphics, motherboard, BIOS, memory, operating system, storage and
  network details together on the dashboard.
- Hardware details load in the background and can be refreshed or copied.
- Live CPU and memory graphs, storage usage and GPU load when a supported
  sensor is available.
- Modern Windows hardware detection using CIM, including systems without WMIC.

### Smoother updates

- Updated Windows builds reopen with a fresh runtime after installation.
- The updater keeps the previous executable during replacement and records
  failures in an update log.
- Clearer release notes, available in the app even when you're offline.

### Small fixes

- Corrected automatic checks when opening Apps, Network and Debloat.
- Refreshing Windows startup status no longer applies startup settings.
- Better layout behaviour on smaller windows and clearer missing-sensor states.

[GitHub release](https://github.com/Ghostshadowplays/Ghosty-Tools/releases/tag/v8.0.6)

## v8.0.4

- 🐛 **Driver list fixed:** System report driver list no longer shows garbled/corrupted characters — switched from `driverquery` (OEM encoding) to `Get-CimInstance Win32_PnPSignedDriver` via PowerShell for clean Unicode output.
- 🔧 **Full System Maintenance expanded:** Phase 1 now includes `DISM /ScanHealth` (corruption detection) and `DISM /StartComponentCleanup /ResetBase` (WinSxS component store cleanup) alongside the existing CheckHealth and RestoreHealth passes.
- 📋 **Export Report auto-fill:** Clicking "Submit to GhostyWare Support" now automatically copies the full report to your clipboard before opening the intake form — paste it directly into the "Reported Issues" field.
- 🎮 **Gaming Mode fully stops Windows Update:** Previously only changed the service startup type (effective on next boot). Now immediately stops `wuauserv`, `UsoSvc`, and `WaaSMedicSvc`, and sets the `NoAutoUpdate` registry policy — updates and restarts are properly suppressed while Gaming Mode is active. Revert restores all three services and clears the policy.

[GitHub release](https://github.com/Ghostshadowplays/Ghosty-Tools/releases/tag/v8.0.4)
