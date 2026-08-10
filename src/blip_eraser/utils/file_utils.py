"""Lógica pura de escaneo manual, tamaños y borrado — sin PyQt6.

Todo lo que aquí se define es agnóstico a la GUI y testable con pytest:
no importa PyQt6, no toca pacman, no depende del sistema operativo
(salvo la elección de rutas por defecto, pensadas para Arch/CachyOS).
"""

from __future__ import annotations

import shutil
from pathlib import Path

DEFAULT_SCAN_PATHS = (
    "~/.local/share",
    "~/Games",
    "~/Descargas",
    "~/Applications",
)

DEFAULT_IGNORE_NAMES = {"applications", "icons", "mime", "fonts", "sounds"}


def human_size(num_bytes: int) -> str:
    """Convierte un número de bytes en una cadena legible (B/KB/MB/GB/TB/PB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def get_dir_size(path: Path) -> int:
    """Suma el tamaño de todos los archivos bajo `path` (no sigue symlinks)."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass
    return total


def path_size_for_display(path: Path) -> int:
    """Tamaño de un Path: suma recursiva si es carpeta, stat si es archivo."""
    if path.is_dir():
        return get_dir_size(path)
    try:
        return path.stat().st_size
    except (OSError, PermissionError):
        return 0


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
        base_path = Path(base).expanduser()
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