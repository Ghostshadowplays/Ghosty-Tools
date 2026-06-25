# Contributing to Ghosty Tools

Thanks for your interest in contributing! Keep things clean, focused, and tested.

---

## Before You Start

- Keep PRs focused — one feature or fix at a time
- Don't reformat the whole codebase in a single PR
- Explain what you changed and why
- Test your changes on the target platform before submitting

---

## Workflow

### 1. Fork the repo
Fork [Ghosty-Tools](https://github.com/Ghostshadowplays/Ghosty-Tools) to your own GitHub account.

### 2. Clone your fork
```bash
git clone https://github.com/YOUR_USERNAME/Ghosty-Tools.git
cd Ghosty-Tools
```

### 3. Set up your environment
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Create a branch
Never work directly on `main`.
```bash
git checkout -b feature/my-feature-name
# or
git checkout -b fix/bug-description
```

### 5. Make your changes
- Keep changes small and focused
- Follow existing code style (no global reformatting)
- Platform-specific code should be gated: `if sys.platform == 'win32':` etc.
- All config/data files must use `get_config_dir()` from `src/utils/helpers.py` — never write files next to the exe or in the project root

### 6. Test your changes
Run Ghosty Tools locally and verify:
- App launches without errors
- Your feature works as expected
- Nothing else is broken

Test on Windows if possible. If your change is Linux/macOS-specific, note that in the PR.

### 7. Commit and push
```bash
git add <specific files>
git commit -m "Short description of the change"
git push origin feature/my-feature-name
```

### 8. Open a Pull Request
On GitHub, open a PR against `main` and include:
- What you changed
- Why you changed it
- Platform(s) tested on

---

## Project Structure

```
src/
  core/       # Backend logic (workers, scanners, managers)
  gui/        # PyQt6 UI pages and components
  utils/      # Helpers, theme manager, logging
config/       # JSON configs (version, bloatware definitions)
images/       # App icons and assets
docs/         # Extra documentation
```

---

## Key Conventions

| Convention | Detail |
|---|---|
| Config storage | Always use `get_config_dir()` — resolves to `%APPDATA%\GhostyTools\` on Windows, `~/.config/GhostyTools/` on Linux/macOS |
| Background work | Use `QThread` workers — never block the main thread |
| Terminal output | Use `self.log_signal.emit(message, level)` — never `print()` |
| Platform checks | `sys.platform == 'win32'`, `sys.platform == 'darwin'`, else Linux |
| Icons | Use Segoe MDL2 Assets on Windows via **inline stylesheet** (not `setFont`) to avoid global stylesheet cascade override |

---

## Need Help?

- Join the **GhostyWare Discord:** [discord.gg/YKsAJYx](https://discord.gg/YKsAJYx)
- Join **haywardgg's Coding Server:** [discord.gg/UUuafBYMdG](https://discord.gg/UUuafBYMdG)
