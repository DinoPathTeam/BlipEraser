"""Escaneo real del sistema para la UI — lógica pura, sin PyQt6.

SQLes solo leen (pacman -Qi/-Qdt, tamaños de carpetas). Se usa para
alimentar el gauge (SYSTEM HEALTH), el botón "SCAN NOW" y el resumen
"SYSTEM CLEANUP RECOMMENDED" con datos reales. Todo es fácilmente
mockeable en tests.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
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


# Con locale C, `pacman -Qi` imprime "Install Date" siempre en inglés y con
# un formato fijo, sin depender del LANG/LC_TIME del usuario.
_C_LOCALE_ENV = {**os.environ, "LANG": "C", "LC_ALL": "C"}


def _run(cmd: list[str], timeout: int = 8, env: dict | None = None) -> str:
    """Ejecuta un comando de solo lectura y devuelve su stdout.

    Nunca lanza: cualquier fallo (comando ausente, timeout, error) se
    traduce en cadena vacía. `env` permite fijar el entorno del proceso
    hijo (por ejemplo, forzar el locale).
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            errors="replace",
            env=env,
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


def normalize_pacman_date(value: str) -> str:
    """Normaliza 'Install Date' (locale C, inglés) a 'YYYY-MM-DD'.

    Con pacman en un locale forzado la fecha sale siempre como
    'Tue 11 Jun 2024 08:15:00 AM UTC'. Si el parseo falla por cualquier
    razón (formato inesperado, valor vacío), devuelve el valor crudo en
    vez de romper.
    """
    if not value:
        return value
    try:
        return datetime.strptime(value, "%a %d %b %Y %I:%M:%S %p %Z").strftime("%Y-%m-%d")
    except ValueError:
        return value


def pacman_installed_info() -> dict[str, dict]:
    """{paquete: {"size": bytes, "date": str}} de todos los instalados.

    Una sola consulta `pacman -Qi`: tamaño instalado y fecha de instalación
    (normalizada a YYYY-MM-DD; valor crudo si no se puede parsear) por
    paquete. Los bloques de paquetes están separados por líneas en blanco.
    """
    out = _run(["pacman", "-Qi"], env=_C_LOCALE_ENV)
    result: dict[str, dict] = {}
    for block in out.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        name: str | None = None
        info = {"size": 0, "date": ""}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "Name":
                name = value
            elif key == "Installed Size":
                size = parse_pacman_size(value)
                if size is not None:
                    info["size"] = size
            elif key == "Install Date":
                info["date"] = normalize_pacman_date(value)
        if name:
            result[name] = info
    return result


def pacman_installed_sizes() -> dict[str, int]:
    """{nombre_paquete: bytes} de todos los paquetes instalados (pacman -Qi)."""
    return {name: info["size"] for name, info in pacman_installed_info().items()}


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