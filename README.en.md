🇪🇸 [Leer en español](README.es.md)

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# BlipEraser

An app uninstaller for **CachyOS** (and any Arch-based distro).

BlipEraser exists to fill the gap left by traditional graphical package managers:
apps installed **manually** — AppImages, loose folders from third-party launchers
such as Hydra Launcher, unpackaged programs — that **are not tracked by any package
manager** and therefore cannot be detected by the usual "uninstall" tools.

## System requirements

- CachyOS or any Arch-based distro (requires `pacman`).
- KDE Plasma (recommended, though not strictly required).
- Python 3.11+ and PyQt6 (see installation).
- `pkexec` / polkit for privileged actions.

## Installation

**Important:** PyQt6 must be installed through the system package manager, **not via
pip**. Installing it with pip clashes with your system's Qt libraries:

```bash
sudo pacman -S python-pyqt6 python-pytest
```

Then clone the repository and install the project in editable mode:

```bash
git clone <repository-url>
cd blipEraser
pip install -e . --break-system-packages
```

If you prefer to keep your dependencies isolated (venv), use `--system-site-packages`
so the virtualenv reuses the PyQt6 and pytest packages from pacman instead of
downloading them again:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

## Basic usage

Run the app with:

```bash
blip-eraser
# this also works (after the editable install):
python -m blip_eraser
```

> Without installing, you can also run it straight from the repository root with
> `PYTHONPATH=src python -m blip_eraser`.

The window has two tabs:

- **Packages (pacman):** lists the explicitly installed packages (`pacman -Qe`) and
  lets you select one or more and uninstall them with `pkexec pacman -Rns --noconfirm`.
- **Manual scan:** walks typical locations (`~/.local/share`, `~/Games`,
  `~/Descargas`, `~/Applications`), computes the size of each folder/AppImage and
  lets you delete them with confirmation.

## Dependency checking

BlipEraser checks its dependencies on **two levels**:

1. **Level 1 — before any window opens:** if PyQt6 is missing, no GUI can be drawn at
   all, so the app prints the install command to the console and exits with a
   non-zero error code.
2. **Level 2 — once the GUI is up:** it checks in the background (without blocking the
   UI) whether the external binaries `pacman` and `pkexec` are available. If any is
   missing, it shows what it is, why it's needed and the exact command to install it.

**BlipEraser NEVER installs anything automatically.** Its only job is to detect,
report and guide; any dependency installation is always carried out explicitly by the
user.

## Development / Tests

The business logic (scanning, size calculation, pacman commands, dependency checking)
lives in `src/blip_eraser/utils/` **with no dependency on PyQt6**, precisely so it can
be tested without a graphical environment — even from Windows or any headless Linux.

```bash
pytest tests/ -v
```

Only mocks (of `subprocess`/`shutil.which`) and pytest's `tmp_path` are used: the
suite needs neither PyQt6 installed nor a real Arch system.

## Security

- Every destructive operation (uninstalling packages, deleting folders) asks for
  **explicit confirmation** before running, listing exactly what will be removed.
- Elevated privileges are requested **per action** through `pkexec` (polkit prompt):
  there is no "persistent sudo" mode that keeps administrator rights for the whole
  session.
- The app never performs installations or system modifications without user input.

## License

[MIT](LICENSE)