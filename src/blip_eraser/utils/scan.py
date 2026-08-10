"""Escaneo real del sistema para la UI — lógica pura, sin PyQt6.

SQLes solo leen (pacman -Qi/-Qdt, tamaños de carpetas). Se usa para
alimentar el gauge (SYSTEM HEALTH), el botón "SCAN NOW" y el resumen
"SYSTEM CLEANUP RECOMMENDED" con datos reales. Todo es fácilmente
mockeable en tests.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from blip_eraser.utils.file_utils import get_dir_size

_CACHE_DIR = Path("~").expanduser() / ".cache"
_PACMAN_CACHE = Path("/var/cache/pacman/pkg")
_LOG_DIR = Path("/var/log")

_SIZE_UNITS = {
    "B": 1,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
    "TIB": 1024**4,
}


def _run(cmd: list[str], timeout: int = 8) -> str:
    """Ejecuta un comando de solo lectura y devuelve su stdout.

    Nunca lanza: cualquier fallo (comando ausente, timeout, error) se
    traduce en cadena vacía.
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            errors="replace",
        )
        return proc.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_pacman_size(text: str) -> int | None:
    """Convierte 'Installed Size : 543.21 MiB' en bytes.

    Entiende B/KiB/MiB/GiB/TiB en mayúsculas o minúsculas. None si no
    encuentra un tamaño válido.
    """
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)", (text or "").strip())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    multiplier = _SIZE_UNITS.get(unit)
    if multiplier is None:
        return None
    return max(0, int(round(value * multiplier)))


def pacman_installed_sizes() -> dict[str, int]:
    """{nombre_paquete: bytes} de todos los paquetes instalados (pacman -Qi)."""
    out = _run(["pacman", "-Qi"])
    result: dict[str, int] = {}
    current_name: str | None = None
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Name"):
            current_name = stripped.split(":", 1)[-1].strip()
        elif stripped.startswith("Installed Size"):
            if current_name:
                size = parse_pacman_size(stripped.split(":", 1)[-1])
                if size is not None:
                    result[current_name] = size
            current_name = None
    return result


def orphan_packages() -> list[str]:
    """Paquetes huérfanos (instalados como dependencia y ya no necesarios).

    `pacman -Qdt` devuelve líneas "nombre versión", igual que `-Qe`.
    Aquí se extrae solo el nombre para que el resultado pueda pasarse
    directamente a comandos como `pacman -Rns`.
    """
    out = _run(["pacman", "-Qdt"])
    names = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        names.append(stripped.split(None, 1)[0])
    return names


def best_effort_dir_size(path: Path) -> int:
    """Tamaño de una carpeta sin lanzar errores; 0 si no se puede leer."""
    if not path.exists():
        return 0
    try:
        return get_dir_size(path)
    except (OSError, PermissionError):
        return 0


def scan_cleanup() -> dict:
    """Espacio recuperable por categoría (junk/cache/logs) + huérfanos."""
    return {
        "junk_bytes": best_effort_dir_size(_CACHE_DIR),
        "pacman_cache_bytes": best_effort_dir_size(_PACMAN_CACHE),
        "logs_bytes": best_effort_dir_size(_LOG_DIR),
        "orphan_count": len(orphan_packages()),
    }


def total_disk_space(path: str = "/") -> int | None:
    """Capacidad total del disco en bytes."""
    try:
        return shutil.disk_usage(path).total
    except (OSError, PermissionError):
        return None