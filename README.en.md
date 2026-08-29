🇪🇸 [Leer en español](README.es.md)

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# BlipEraser

An app uninstaller for **Arch Linux** (and any Arch-based distro).

BlipEraser exists to fill the gap left by traditional graphical package managers:
apps installed **manually** — AppImages, loose folders from third-party launchers
such as Hydra Launcher, unpackaged programs — that **are not tracked by any package
manager** and therefore cannot be detected by the usual "uninstall" tools.

---

## Features

- **Overview**: system health gauge (*GOOD / FAIR / POOR*), live CPU/GPU/RAM/disk stats, and a one-click "Clean now" summary of recommended cleanup.
- **Uninstaller**: a unified list of `pacman` packages and manual folders, with sorting, search filter and **manual per-row selection** (no "select all" header checkbox, to prevent accidental mass uninstalls). Uninstalls run through `pkexec pacman -Rns --noconfirm`.
- **Cleaner**: two independent sections — *recommended cleanup* (junk `~/.cache`, pacman cache `/var/cache/pacman/pkg`, logs `/var/log`) and *manually installed apps* (loose folders and AppImages in the scan paths).
- **Performance tweaks**: one-click optimizations for Arch Linux — `fstrim` (SSD), `zswap` (RAM compression) and pacman mirrors sorted by speed, each with a detailed tooltip (mechanism, consequences, benefit).
- **Settings**: theme, fonts, language and activity log management.

---

### 🎯 Supported Distributions

BlipEraser works on **any Arch Linux-based distribution** that uses `pacman` as package manager and `systemd` + D-Bus, including (but not limited to):

- **Arch Linux** (official)
- **CachyOS**
- **EndeavourOS**
- **Manjaro**
- **Garuda Linux**
- **ArcoLinux**
- **Artix Linux** (with systemd)
- **Hyperbola** (with systemd)
- **Parabola GNU/Linux-libre**
- **RebornOS**
- **Archcraft**
- **ArchBang**
- **Namib Linux**
- **Obarun** (with systemd)
- **Arch Linux ARM**, and other derivatives maintaining compatibility with `pacman`, `systemd`, and D-Bus

> **Note**: If your distribution uses `pacman`, `systemd`, and has D-Bus on the system bus, BlipEraser should work. If you encounter issues on a specific derivative, please open an issue.

---

## System Requirements

- Any Arch Linux-based distro (requires `pacman`, `systemd`, D-Bus).
- Python 3.11+, PyQt6 and **PyGObject** (see installation).
- **Multimedia**: `gst-libav` (GStreamer plugin for H.264 video intro).
- `pkexec` / polkit for privileged actions.
- `systemd` + D-Bus (system bus) for privileged daemon (Phase 2).
- **Security**: AppArmor (profile included in `packaging/apparmor/`).

---

## Installation

**Important:** PyQt6 and PyGObject must be installed through the system package manager, **not via pip**. Installing them with pip clashes with your system's libraries:

```bash
# 1. Install system dependencies (includes gst-libav for splash screen video intro)
sudo pacman -S python-pyqt6 python-gobject gst-libav

# 2. Install AppArmor profile (for privileged daemon Phase 2)
sudo cp packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged /etc/apparmor.d/
sudo apparmor_parser -r /etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged

# 3. Install systemd service and D-Bus configuration (for privileged daemon Phase 2)
sudo mkdir -p /usr/lib/blip-eraser/
sudo cp packaging/systemd/blip-eraser-privileged.service /usr/lib/systemd/system/
sudo cp packaging/dbus/blip-eraser-privileged.conf /usr/share/dbus-1/system.d/
sudo cp packaging/dbus/com.dinopath.BlipEraser.Privileged.xml /usr/share/dbus-1/interfaces/
sudo cp packaging/scripts/blip-eraser-privileged /usr/lib/blip-eraser/
sudo chmod +x /usr/lib/blip-eraser/blip-eraser-privileged
sudo systemctl daemon-reload
sudo systemctl enable --now blip-eraser-privileged.service
```

Then clone the repository and install the project in editable mode:

```bash
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser
pip install -e . --break-system-packages
```

If you prefer to keep your dependencies isolated (venv), use `--system-site-packages` so the virtualenv reuses the PyQt6 and pytest packages from pacman instead of downloading them again:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

---

## Basic Usage

Run the app with:

```bash
blip-eraser
# this also works (after the editable install):
python -m blip_eraser
```

> Without installing, you can also run it straight from the repository root with
> `PYTHONPATH=src python -m blip_eraser`.

---

## Dependency Checking

BlipEraser checks its dependencies on **two levels**:

1. **Level 1 — before any window opens:** if PyQt6 is missing, no GUI can be drawn at all, so the app prints the install command to the console and exits with a non-zero error code.
2. **Level 2 — once the GUI is up:** it checks in the background (without blocking the UI) whether the external binaries `pacman` and `pkexec` are available. If any is missing, it shows what it is, why it's needed and the exact command to install it.

**BlipEraser NEVER installs anything automatically.** Its only job is to detect, report and guide; any dependency installation is always carried out explicitly by the user.

---

## Development / Tests

The business logic (scanning, size calculation, pacman commands, dependency checking) lives in `src/blip_eraser/utils/` **with no dependency on PyQt6**, precisely so it can be tested without a graphical environment — even from Windows or any headless Linux.

```bash
pytest tests/ -v
```

Only mocks (of `subprocess`/`shutil.which`) and pytest's `tmp_path` are used: the suite needs neither PyQt6 installed nor a real Arch system.

---

## Security

- Every destructive operation (uninstalling packages, deleting folders) asks for **explicit confirmation** before running, listing exactly what will be removed.
- Elevated privileges are requested **per action** through `pkexec` (polkit prompt): there is no "persistent sudo" mode that keeps administrator rights for the whole session.
- The app never performs installations or system modifications without user input.

---

## License

[MIT](LICENSE)