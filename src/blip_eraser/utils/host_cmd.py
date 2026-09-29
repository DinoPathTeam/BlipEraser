"""Comandos del host cuando la app corre dentro de un Flatpak.

BlipEraser gestiona el sistema anfitrión (pacman, systemctl, pkexec…),
binarios que no existen dentro del sandbox. Cuando se detecta
`/.flatpak-info`, los comandos se prefijan con `flatpak-spawn --host`
para ejecutarlos fuera del sandbox.

Fuera de Flatpak este módulo es transparente: devuelve los comandos
tal cual. Sin dependencias nuevas (stdlib).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

#: Marcador que solo existe dentro del sandbox de Flatpak.
FLATPAK_INFO = Path("/.flatpak-info")

#: Binario puente hacia el host (solo existe dentro del sandbox).
SPAWN = "flatpak-spawn"

_host_home: str | None = None


def is_flatpak() -> bool:
    """True si la app corre dentro de un sandbox Flatpak."""
    return FLATPAK_INFO.exists()


def host_home() -> Path:
    """$HOME del host (en Flatpak, `~` a secas es el home del sandbox).

    Fuera de Flatpak equivale a `Path("~").expanduser()`. Se cachea:
    el home no cambia en una sesión.
    """
    global _host_home
    if not is_flatpak():
        return Path.home()
    if _host_home is None:
        try:
            proc = subprocess.run(
                [SPAWN, "--host", "sh", "-c", "printf %s \"$HOME\""],
                capture_output=True,
                text=True,
                timeout=8,
            )
            _host_home = (proc.stdout or "").strip() or str(Path.home())
        except (OSError, subprocess.SubprocessError):
            _host_home = str(Path.home())
    return Path(_host_home)


def expanduser(path: str | Path) -> Path:
    """Como `Path.expanduser()`, pero contra el home del host en Flatpak."""
    p = Path(path)
    if not is_flatpak():
        return p.expanduser()
    try:
        return Path(str(p).replace("~", str(host_home()), 1)) if str(p).startswith("~") else p
    except (OSError, RuntimeError):
        return p.expanduser()


def host_cmd(cmd: list[str]) -> list[str]:
    """Prefija `cmd` con `flatpak-spawn --host` dentro de Flatpak.

    Fuera de Flatpak devuelve `cmd` sin tocar.
    """
    if is_flatpak():
        return [SPAWN, "--host", *cmd]
    return cmd


def host_shell(cmd: str) -> str | list[str]:
    """Envuelve un comando shell para correrlo en el host en Flatpak.

    Fuera de Flatpak devuelve el string tal cual (para `shell=True`).
    Dentro devuelve lista `flatpak-spawn --host sh -c …` (para `shell=False`).
    """
    if is_flatpak():
        return [SPAWN, "--host", "sh", "-c", cmd]
    return cmd


def host_which(binary: str) -> str | None:
    """Equivalente a `shutil.which` pero contra el PATH del host en Flatpak."""
    if not is_flatpak():
        return shutil.which(binary)
    try:
        proc = subprocess.run(
            [SPAWN, "--host", "sh", "-c", f"command -v {binary}"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        found = (proc.stdout or "").strip().splitlines()
        return found[0] if proc.returncode == 0 and found else None
    except (OSError, subprocess.SubprocessError):
        return None
