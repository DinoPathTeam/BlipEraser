"""Lógica pura de escaneo manual, tamaños y borrado — sin PyQt6.

Todo lo que aquí se define es agnóstico a la GUI y testable con pytest:
no importa PyQt6, no toca pacman, no depende del sistema operativo
(salvo la elección de rutas por defecto, pensadas para Arch/CachyOS).
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from blip_eraser.utils.host_cmd import expanduser as _expand_host

def xdg_downloads_path(user_dirs_file: Path | None = None) -> str:
    """Carpeta de descargas según XDG (`user-dirs.dirs`), en forma `~/...`.

    No depende del idioma del sistema (`Descargas`, `Downloads`, ...). Si el
    archivo falta o el valor no es seguro (relativo, con `..` o el propio
    $HOME) cae a `~/Downloads`.
    """
    fallback = "~/Downloads"
    if user_dirs_file is None:
        user_dirs_file = _expand_host("~/.config/user-dirs.dirs")
    try:
        lines = user_dirs_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fallback
    for line in lines:
        line = line.strip()
        if line.startswith("#") or not line.startswith("XDG_DOWNLOAD_DIR="):
            continue
        value = line.split("=", 1)[1].strip().strip('"')
        if value.startswith("$HOME/"):
            value = "~/" + value[len("$HOME/"):]
        if value in ("", "~/") or ".." in value.split("/"):
            return fallback
        if value.startswith("~/") or value.startswith("/"):
            return value.rstrip("/")
        return fallback
    return fallback


def default_scan_paths() -> tuple[str, ...]:
    # D1: ~/.local/share FUERA por defecto (carteras KDE, Steam, Papelera…:
    # datos, no apps). El usuario puede añadirlo a mano en Ajustes.
    return ("~/Games", xdg_downloads_path(), "~/Applications")


DEFAULT_SCAN_PATHS = default_scan_paths()

DEFAULT_IGNORE_NAMES = {"applications", "icons", "mime", "fonts", "sounds"}


def human_size(num_bytes: int) -> str:
    """Convierte un número de bytes en una cadena legible (B/KB/MB/GB/TB/PB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# Cada cuántas entradas el hilo de escaneo cede el GIL al hilo de la interfaz.
# Un recorrido largo en Python puro mantiene el GIL casi todo el tiempo y la
# ventana se siente colgada aunque el escaneo corra en otro hilo.
_YIELD_EVERY = 1024


def _walk_dir_size(path: Path) -> int:
    """Recorrido iterativo con `os.scandir` (sin crear un `Path` por entrada).

    Cede el GIL periódicamente para no ahogar la interfaz cuando se ejecuta
    en un hilo de fondo.
    """
    total = 0
    seen = 0
    stack = [str(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    seen += 1
                    if seen % _YIELD_EVERY == 0:
                        time.sleep(0.0005)
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def get_dir_size(path: Path) -> int:
    """Suma el tamaño de todos los archivos bajo `path` (no sigue symlinks)."""
    return _walk_dir_size(path)


def path_size_for_display(path: Path) -> int:
    """Tamaño de un Path: suma recursiva si es carpeta, stat si es archivo."""
    if path.is_dir():
        return get_dir_size(path)
    try:
        return path.stat().st_size
    except (OSError, PermissionError):
        return 0


def path_mod_date(path: Path) -> str:
    """Fecha de última modificación (YYYY-MM-DD) de un Path; "" si falla."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except (OSError, PermissionError):
        return ""


def scan_manual_entries(
    scan_paths: tuple[str, ...] = DEFAULT_SCAN_PATHS,
    ignore_names: set[str] | None = None,
) -> list[Path]:
    """Recorre los directorios base y devuelve carpetas/AppImages de nivel superior.

    Ignora los nombres de `ignore_names` (aplicado en minúsculas). Los
    directorios base que no existen o no se pueden leer se omiten
    silenciosamente. No borra nada: solo localiza candidatos.
    """
    if ignore_names is None:
        ignore_names = DEFAULT_IGNORE_NAMES
    found: list[Path] = []
    for base in scan_paths:
        base_path = _expand_host(base)
        if not base_path.exists():
            continue
        try:
            for entry in base_path.iterdir():
                if entry.name.lower() in ignore_names:
                    continue
                if entry.is_dir() or entry.suffix.lower() == ".appimage":
                    found.append(entry)
        except (OSError, PermissionError):
            continue
    return found


def delete_path(path: Path) -> None:
    """Elimina PERMANENTEMENTE un directorio (árbol completo) o archivo.

    Lanza OSError/PermissionError si falla. El llamante decide qué hacer
    con los errores (mostrarlos en la GUI, agruparlos, etc.).
    """
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()