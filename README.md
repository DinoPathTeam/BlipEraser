<p align="center">
  <img src="src/blip_eraser/assets/BlipEraserLogo.png" alt="BlipEraser Logo" width="480"/>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://archlinux.org/"><img src="https://img.shields.io/badge/OS-Arch%20Linux%20%7C%20Arch-based-red.svg" alt="Arch Linux / Arch-based"></a>
  <a href="https://riverbankcomputing.com/software/pyqt/"><img src="https://img.shields.io/badge/GUI-PyQt6-informational.svg" alt="PyQt6"></a>
</p>

<p align="center">
  <a href="#-english"><b>English</b></a> · <a href="#-español"><b>Español</b></a>
</p>

---

<a id="-english"></a>
## 🇬🇧 English

# BlipEraser

An app uninstaller and system cleaner for **Arch Linux** (and any Arch-based distro).

BlipEraser exists to fill the gap left by traditional graphical package managers:
apps installed **manually** — AppImages, loose folders from third-party launchers
and unpackaged programs — that **are not tracked by any package
manager** and therefore cannot be detected by the usual "uninstall" tools.

---

## Features

- **Overview**: system health gauge (*GOOD / FAIR / POOR*), live CPU/GPU/RAM/disk stats, and a one-click "Clean now" summary of recommended cleanup.
- **Uninstaller**: a unified list of `pacman` packages and manual folders, with sorting, search filter and **manual per-row selection** (no "select all" header checkbox, to prevent accidental mass uninstalls). Uninstalls run through `pkexec pacman -Rns --noconfirm`.
- **Cleaner**: two independent sections — *recommended cleanup* (junk `~/.cache`, pacman cache `/var/cache/pacman/pkg`, logs `/var/log`) and *manually installed apps* (loose folders and AppImages in the scan paths).
- **Safety confirmation & large-size threshold**: every destructive operation lists exactly what will be removed; selections over **5 GiB** show a **highlighted red/bold warning**. Confirmation is mandatory, no "don't ask again".
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

## Architecture

```
main.py ── PyQt6 check → first-run language → Splash + StartupWorker
  (5 steps: updates stub, permissions, dependencies, reference scan, welcome)
            │
            ▼
renderer.py MainWindow (HeaderBar + Sidebar + QStackedWidget
  + SystemStatusBar + collapsible LogPanel; theme/font/language)
  pages/ ×10 (live for the whole session, never destroyed on navigation)
  ├── overview (health gauge + SYSINFO + apps + "Clean now")
  ├── uninstaller (6-col table: pacman explicit/dependency/manual)
  ├── cleaner (2 independent tabs: recommended + manual)
  ├── performance (fstrim/zram/mirrors, one click)
  └── settings/personalize/tools/help
  widgets/ ×13 (QVideoSink splash, check_table, scan_worker mixin, dialogs)
            │
            ▼
utils/ ×24 PURE modules, no Qt (testable without display)
  scan/apps/pacman (detection) · privileges/validation/dbus_client
  (security) · scan_cache/scan_worker (background thread + generation token)
  i18n/theme/config/log/confirm/table_filters/system_stats...
      │                               │
      ▼                               ▼
D-Bus system bus → root daemon   pkexec fallback
RemovePackages/CleanSystem        pacman -Rns / rm -rf allowlist
Paths/Ping (Type=dbus)            (1 auth prompt per batch)
```

**Stack:** Python ≥3.11 (everything) · PyQt6 + QSS (GUI/themes) ·
D-Bus + `gi` (privileged IPC) · polkit (per-action auth, `wheel` only) ·
systemd (`Type=dbus` root service + hardening) · AppArmor (confinement) ·
pacman/systemd/loginctl/gst-libav (H.264) · Bash (installers/wrappers).

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

**Easiest:** download `BlipEraser-v1.0.0-x86_64.flatpak` from
[Releases](https://github.com/DinoPathTeam/BlipEraser/releases/tag/v1.0.0) and:

```bash
# 1. Privileged daemon on the host (one time only)
./scripts/install-daemon.sh   # or fetch the script from the repo
# 2. Install and run the flatpak
flatpak install --user BlipEraser-v1.0.0-x86_64.flatpak
flatpak run io.github.DinoPathTeam.BlipEraser
```

> The flatpak manages the host via `flatpak-spawn` (needs `--filesystem=host`:
> it is a system tool). Privileged operations use pkexec on the host.

**AUR (Arch Linux):**

```bash
yay -S blip-eraser
# then enable the privileged daemon (needs wheel group):
sudo systemctl enable --now blip-eraser-privileged.service
```

No AUR helper? Build it manually (same files as `packaging/aur/`):

```bash
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser
gh release download v1.0.1 -p "BlipEraser-1.0.1.tar.gz"
mkdir build && cp packaging/aur/PKGBUILD packaging/aur/blip-eraser.install build/
cp BlipEraser-1.0.1.tar.gz build/blip-eraser-1.0.1.tar.gz
cd build && makepkg -si
```

**Recommended (native):** deploy the privileged daemon (code + systemd + D-Bus + polkit) with the installer script — it is idempotent, re-run it after every code change:

```bash
# 1. System dependencies (includes gst-libav for splash screen video intro)
sudo pacman -S python-pyqt6 python-gobject gst-libav

# 2. Deploy daemon (asks for sudo by itself)
./scripts/install-daemon.sh
```

<details>
<summary>Manual install (alternative, same steps the script performs)</summary>

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

</details>

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

## 🗺️ Roadmap

> Rebuilt from scratch: where each piece would sit if planned by versions,
> where we are (~70% functional) and what is missing for production.
> **Flathub paused** (≥1 month, at the creator's decision).

- [x] **v0.1 — Foundation**: `src/blip_eraser/` scaffold, pure logic in
  `utils/` without Qt, pacman reading (`-Qe/-Qd/-Qi`), base window and navigation.
- [x] **v0.2 — Unified uninstaller**: pacman table + manual entries
  (AppImages, `~/Games`, Hydra), manual selection without "select all",
  type/size/date filters.
- [x] **v0.3 — Cleanup and system**: Cleaner (recommended + manual),
  health-gauge Overview, performance tweaks (fstrim/zram/mirrors),
  themes, hot ES/EN switching, scan cache (5 min).
- [x] **v0.4 — Security Phase 1**: path allowlist, symlink rejection,
  package validation, mandatory confirmation, ≥5 GiB warning,
  forensic audit (`diagnostics.log`).
- [x] **v0.5 — Phase 2 privileges + startup**: systemd D-Bus daemon
  (`RemovePackages`/`CleanSystemPaths`/`Ping`) with pkexec fallback,
  video splash, background scans with token, custom app icon.
- [x] **v1.0 — CachyOS stabilization**: hard `sip.isdeleted` defense,
  `BackgroundScanMixin` on all 3 pages, forensic instrumentation.
  **Current state**: code `1.0.0`, functional on Arch/CachyOS.
- [x] **v1.1 — Order and quality (done)**:
  - Green suite (591 passed, 3 skipped) + minimal CI
    (`pytest` + `compileall`) on every push/PR to `main`.
  - Background deletion with progress dialog ("Removing… n/N", auto-close):
    no more "Not responding" freezes; modal with no cancel (a half
    deletion cannot be interrupted safely).
  - Single allowlist/denylist in `utils/validation.py` (daemon, pkexec
    client and GUI share it; `dbus_client` only re-exports).
  - `pyproject.toml` version in sync → `1.0.0`.
  - Clean root (no `Z:/` artifacts, no stray logs).
  - Release extras: real `check_for_updates` (GitHub Releases,
    fail-closed), D-Bus rate limit (10 destructive calls/min per
    sender), tag + GitHub release `v1.0.0` with downloadable Flatpak
    (`io.github.DinoPathTeam.BlipEraser`).
- [x] **v1.2 — AUR packaging (packaged, upload ⏸️)**: `.desktop` with
  `Icon=`, PKGBUILD 1.0.1 + `.SRCINFO` validated with `makepkg`
  (`packaging/aur/`), installer covering polkit + AppArmor, guide
  without `--break-system-packages` (venv `--system-site-packages`).
  > Note: the AUR upload itself is paused — the 3 files in
  > `packaging/aur/` are ready to push when reactivated.
- [x] **v1.3 — Production (done)**: AppArmor enforce verified on a real
  host (systemd `AppArmorProfile=`, evidence-hardened profile, 0 DENIED),
  real `check_for_updates` (GitHub Releases), audit of the daemon's
  fd-atomic `rm -rf`, D-Bus rate limiting, release tags `v1.0.0`/`v1.0.1`.
- [ ] **Future**: migrate i18n to gettext, E2E tests, PyGObject in the
  Flatpak bundle (today pkexec-host fallback), **Flathub ⏸️**.

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

---
---

<a id="-español"></a>
## 🇪🇸 Español

# BlipEraser

Desinstalador de aplicaciones y limpiador del sistema para **Arch Linux** (y cualquier distro basada en Arch).

BlipEraser existe para cubrir el hueco que dejan los gestores gráficos tradicionales:
apps instaladas **manualmente** — AppImages, carpetas sueltas de lanzadores de terceros
y programas sin paquete — que **no quedan registradas en ningún
gestor de paquetes** y que, por tanto, ninguna herramienta tradicional es capaz de detectar.

---

## 🌟 Navegación y Secciones

1. **Vista general (Overview)**: Puntuación de salud radial (*GOOD / FAIR / POOR*), estadísticas de CPU/GPU/RAM/Disco y botón de acción rápida *"Limpiar ahora"*.
2. **Desinstalador**: Lista unificada de paquetes de `pacman` y carpetas manuales, con ordenación, filtro de búsqueda y selección manual por fila (sin checkbox de "seleccionar todo").
3. **Limpiador del sistema**:
   - **Limpieza recomendada**: Basura (`~/.cache`), Caché de pacman (`/var/cache/pacman/pkg`) y Registros (`/var/log`) desglosados ítem por ítem.
   - **Aplicaciones instaladas (manual)**: Carpetas sueltas y AppImages detectados.
4. **Ajustes de rendimiento**: Optimizaciones seguras de Arch Linux (`fstrim`, `zswap`, espejos de pacman por velocidad), cada una con tooltip de mecanismo, consecuencias y beneficio.
5. **Configuración**: Selección de temas cromáticos, fuentes tipográficas y borrado de historial de actividad.

---

## 🛡️ Confirmación de Seguridad y Umbral de Gran Tamaño

- Toda operación destructiva muestra la categorización exacta y el peso total a liberar.
- Si la selección supera el umbral de **5 GiB**, se muestra una **advertencia destacada en rojo y negrita**.
- **Confirmación obligatoria sin excepción**: la app no incluye casillas de *"no volver a preguntar"*.

---

### 🎯 Distribuciones compatibles

BlipEraser funciona en **cualquier distribución basada en Arch Linux** que use `pacman` como gestor de paquetes y `systemd` + D-Bus, incluyendo (pero no limitado a):

- **Arch Linux** (oficial)
- **CachyOS**
- **EndeavourOS**
- **Manjaro**
- **Garuda Linux**
- **ArcoLinux**
- **Artix Linux** (con systemd)
- **Hyperbola** (con systemd)
- **Parabola GNU/Linux-libre**
- **RebornOS**
- **Archcraft**
- **ArchBang**
- **Namib Linux**
- **Obarun** (con systemd)
- **Arch Linux ARM**, y otras derivadas que mantengan compatibilidad con `pacman`, `systemd` y D-Bus

> **Nota**: Si tu distribución usa `pacman`, `systemd` y tiene D-Bus en el bus de sistema, BlipEraser debería funcionar. Si encuentras problemas en una derivada específica, reporta un issue.

---

## Arquitectura

```
main.py ── check PyQt6 → idioma primer arranque → Splash + StartupWorker
  (5 pasos: updates-stub, permisos, dependencias, escaneo referencia, bienvenida)
            │
            ▼
renderer.py MainWindow (HeaderBar + Sidebar + QStackedWidget
  + SystemStatusBar + LogPanel colapsable; tema/fuente/idioma)
  pages/ ×10 (viven toda la sesión, nunca se destruyen al navegar)
  ├── overview (gauge salud + SYSINFO + apps + "Limpiar ahora")
  ├── uninstaller (tabla 6 col: pacman explícito/dependencia/manual)
  ├── cleaner (2 tabs independientes: recomendada + manual)
  ├── performance (fstrim/zram/mirrors, un clic)
  └── settings/personalize/tools/help
  widgets/ ×13 (splash QVideoSink, check_table, scan_worker mixin, diálogos)
            │
            ▼
utils/ ×24 módulos PUROS, sin Qt (testeables sin display)
  scan/apps/pacman (detección) · privileges/validation/dbus_client
  (seguridad) · scan_cache/scan_worker (hilo fondo + token generación)
  i18n/theme/config/log/confirm/table_filters/system_stats...
      │                               │
      ▼                               ▼
D-Bus bus sistema → daemon root   fallback pkexec
RemovePackages/CleanSystem        pacman -Rns / rm -rf allowlist
Paths/Ping (Type=dbus)            (1 auth por lote)
```

**Stack:** Python ≥3.11 (todo) · PyQt6 + QSS (GUI/temas) ·
D-Bus + `gi` (IPC privilegiado) · polkit (auth por acción, solo `wheel`) ·
systemd (servicio `Type=dbus` root + hardening) · AppArmor (confinamiento) ·
pacman/systemd/loginctl/gst-libav (H.264) · Bash (instaladores/wrappers).

---

## 🛠️ Requisitos del sistema

- Cualquier distro basada en Arch (requiere `pacman`, `systemd`, D-Bus).
- Python 3.11+, PyQt6 y **PyGObject** (instalados vía `pacman`).
- **Multimedia**: `gst-libav` (plugin GStreamer para video de intro H.264).
- `pkexec` / polkit para las acciones con privilegios de administrador.
- `systemd` + D-Bus (bus de sistema) para el daemon privilegiado (Fase 2).
- **Seguridad**: AppArmor (perfil incluido en `packaging/apparmor/`).

---

## 📦 Instalación

**Lo más fácil:** descarga `BlipEraser-v1.0.0-x86_64.flatpak` desde
[Releases](https://github.com/DinoPathTeam/BlipEraser/releases/tag/v1.0.0) y:

```bash
# 1. Daemon privilegiado en el host (una sola vez)
./scripts/install-daemon.sh   # o baja el script del repo
# 2. Instalar y lanzar el flatpak
flatpak install --user BlipEraser-v1.0.0-x86_64.flatpak
flatpak run io.github.DinoPathTeam.BlipEraser
```

> El flatpak gestiona el host vía `flatpak-spawn` (pide `--filesystem=host`:
> es una herramienta de sistema). Las operaciones con privilegios usan pkexec en el host.

**AUR (Arch Linux):**

```bash
yay -S blip-eraser
# y habilita el daemon privilegiado (requiere grupo wheel):
sudo systemctl enable --now blip-eraser-privileged.service
```

¿Sin ayudante AUR? Compílalo a mano (mismos archivos de `packaging/aur/`):

```bash
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser
gh release download v1.0.1 -p "BlipEraser-1.0.1.tar.gz"
mkdir build && cp packaging/aur/PKGBUILD packaging/aur/blip-eraser.install build/
cp BlipEraser-1.0.1.tar.gz build/blip-eraser-1.0.1.tar.gz
cd build && makepkg -si
```

**Muy importante:** PyQt6, PyGObject y gst-libav se instalan con el gestor del sistema, **no por pip**.

**Recomendado:** despliega el daemon (código + systemd + D-Bus + polkit) con el script instalador — es idempotente, re-ejecútalo tras cada cambio de código:

```bash
# 1. Dependencias del sistema (incluye gst-libav para video de intro)
sudo pacman -S python-pyqt6 python-gobject gst-libav

# 2. Desplegar daemon (pide sudo solo)
./scripts/install-daemon.sh
```

<details>
<summary>Instalación manual (alternativa: mismos pasos del script)</summary>

El daemon privilegiado (Fase 2) requiere PyGObject para D-Bus y gst-libav para el video de intro H.264.

```bash
# 1. Instalar dependencias del sistema (incluye gst-libav para video de intro)
sudo pacman -S python-pyqt6 python-gobject gst-libav

# 2. Instalar AppArmor profile (para daemon privilegiado Fase 2)
sudo cp packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged /etc/apparmor.d/
sudo apparmor_parser -r /etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged

# 3. Instalar systemd service (para daemon privilegiado Fase 2)
sudo mkdir -p /usr/lib/blip-eraser/
sudo cp packaging/systemd/blip-eraser-privileged.service /usr/lib/systemd/system/
sudo cp packaging/dbus/blip-eraser-privileged.conf /usr/share/dbus-1/system.d/
sudo cp packaging/dbus/com.dinopath.BlipEraser.Privileged.xml /usr/share/dbus-1/interfaces/
sudo cp packaging/scripts/blip-eraser-privileged /usr/lib/blip-eraser/
sudo chmod +x /usr/lib/blip-eraser/blip-eraser-privileged
sudo systemctl daemon-reload
sudo systemctl enable --now blip-eraser-privileged.service
```

</details>

# 4. Clona el repo e instala el proyecto en modo editable
```bash
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser
pip install -e . --break-system-packages
```

Si prefieres aislar dependencias (venv), usa `--system-site-packages` para reutilizar PyQt6 y pytest de pacman en vez de descargarlos de nuevo:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

---

## 🎮 Uso básico

Ejecuta la app con:

```bash
blip-eraser
# también vale (tras la instalación editable):
python -m blip_eraser
```

> Sin instalar, también puedes lanzarla desde la raíz del repo con
> `PYTHONPATH=src python -m blip_eraser`.

---

## Comprobación de dependencias

BlipEraser comprueba sus dependencias en **dos niveles**:

1. **Nivel 1 — antes de abrir ventana:** si falta PyQt6 no se puede dibujar nada, así que la app imprime el comando de instalación en consola y sale con código de error.
2. **Nivel 2 — con la GUI abierta:** comprueba en segundo plano (sin bloquear la UI) si los binarios `pacman` y `pkexec` están disponibles. Si falta alguno, muestra qué es, por qué se necesita y el comando exacto para instalarlo.

**BlipEraser NUNCA instala nada automáticamente.** Solo detecta, informa y guía; cualquier instalación la hace siempre el usuario explícitamente.

---

## 🗺️ Roadmap

> Reconstruido desde cero: dónde estaría cada pieza si se hubiera
> planificado por versiones, dónde estamos (~70% funcional) y qué falta
> para producción. **Flathub en pausa** (≥1 mes, a decisión del creador).

- [x] **v0.1 — Fundación**: scaffold `src/blip_eraser/`, lógica pura en
  `utils/` sin Qt, lectura pacman (`-Qe/-Qd/-Qi`), ventana y navegación base.
- [x] **v0.2 — Desinstalador unificado**: tabla pacman + entradas manuales
  (AppImages, `~/Games`, Hydra), selección manual sin "seleccionar todo",
  filtros por tipo/peso/fecha.
- [x] **v0.3 — Limpieza y sistema**: Limpiador (recomendada + manual),
  Overview con gauge de salud, ajustes de rendimiento (fstrim/zram/mirrors),
  temas, ES/EN en caliente, caché de escaneo (5 min).
- [x] **v0.4 — Seguridad Fase 1**: allowlist de paths, rechazo de symlinks,
  validación de paquetes, confirmación obligatoria, aviso ≥5 GiB,
  auditoría forense (`diagnostics.log`).
- [x] **v0.5 — Privilegios Fase 2 + arranque**: daemon D-Bus systemd
  (`RemovePackages`/`CleanSystemPaths`/`Ping`) con fallback pkexec,
  splash con vídeo, escaneos en segundo plano con token, icono propio.
- [x] **v1.0 — Estabilización CachyOS**: defensa dura `sip.isdeleted`,
  `BackgroundScanMixin` en las 3 páginas, instrumentación forense.
  **Estado actual**: código `1.0.0`, funcional en Arch/CachyOS.
- [x] **v1.1 — Orden y calidad (hecho)**:
  - Suite verde (591 passed, 3 skipped) + CI mínimo
    (`pytest` + `compileall`) en cada push/PR a `main`.
  - Borrado en segundo plano con diálogo de progreso ("Eliminando… n/N",
    se cierra solo): adiós al "No responde"; modal sin cancelar (un
    borrado a medias no se puede interrumpir).
  - Allowlist/denylist única en `utils/validation.py` (daemon, cliente
    pkexec y GUI la comparten; `dbus_client` solo re-exporta).
  - Sincronizar versión `pyproject.toml` → `1.0.0`.
  - Limpieza de raíz (sin artefactos `Z:/`, sin logs sueltos).
  - Extras del release: `check_for_updates` real (GitHub Releases,
    fail-closed), rate-limit D-Bus (10 ops destructivas/min por sender),
    tag + release `v1.0.0` en GitHub con Flatpak descargable
    (`io.github.DinoPathTeam.BlipEraser`).
- [x] **v1.2 — Empaquetado AUR (empaquetado, subida ⏸️)**: `.desktop`
  con `Icon=`, PKGBUILD 1.0.1 + `.SRCINFO` validados con `makepkg`
  (`packaging/aur/`), instalador que cubre polkit + AppArmor, guía sin
  `--break-system-packages` (venv `--system-site-packages`).
  > Nota: la subida a AUR está en pausa — los 3 archivos de
  > `packaging/aur/` están listos para pushear cuando se reactive.
- [x] **v1.3 — Producción (hecho)**: AppArmor en enforce verificado en
  host real (`AppArmorProfile=` en systemd, perfil endurecido con
  evidencia, 0 DENIED), `check_for_updates` real (GitHub Releases),
  auditoría del `rm -rf` fd-atómico, rate-limit D-Bus, tags `v1.0.0`/`v1.0.1`.
- [ ] **Futuro**: migrar i18n a gettext, tests E2E, PyGObject en el bundle
  Flatpak (hoy fallback pkexec-host), **Flathub ⏸️**.

---

## 🧪 Pruebas / Tests

Toda la lógica pura (escaneo, categorización, umbral de confirmación, normalización de fechas de pacman) vive en `src/blip_eraser/utils/` sin dependencia de PyQt6. Esto permite ejecutar la suite de pruebas sin entorno gráfico:

```bash
pytest
```

---

## Seguridad

- Toda operación destructiva (desinstalar paquetes, borrar carpetas) pide **confirmación explícita** antes de ejecutarse, listando exactamente qué se eliminará.
- Los privilegios se piden **por acción** vía `pkexec` (prompt polkit): no hay modo "sudo persistente" con derechos de admin toda la sesión.
- La app nunca instala ni modifica el sistema sin intervención del usuario.

---

## 📄 Licencia

[MIT](LICENSE)
