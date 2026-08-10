"""Aplicaciones instaladas y salud del sistema — lógica pura, sin PyQt6.

Combina los paquetes explícitos de pacman con las entradas de escaneo
manual (AppImages, carpetas sueltas) en una lista única de "aplicaciones
instaladas" para la interfaz. Todo es testable mockeando las utilidades.
"""

from __future__ import annotations

from dataclasses import dataclass

from blip_eraser.utils.config import get_scan_ignore, get_scan_paths
from blip_eraser.utils.file_utils import (
    path_size_for_display,
    scan_manual_entries,
)
from blip_eraser.utils.pacman import list_explicit_packages
from blip_eraser.utils.scan import pacman_installed_sizes


@dataclass
class InstalledApp:
    name: str
    source: str  # "pacman" | "manual"
    detail: str = ""
    size_bytes: int = 0


def list_installed_apps(include_sizes: bool = True) -> list[InstalledApp]:
    """Apps visibles al usuario: paquetes explícitos + AppImages/carpetas.

    Los paquetes explícitos son las "aplicaciones" de pacman; las entradas
    manuales son las carpetas sueltas/AppImages de los directorios de
    escaneo configurados. Sin privilegios, ambas lecturas son seguras.
    Si `include_sizes` es True se añade el tamaño instalado de cada paquete
    (una sola consulta `pacman -Qi`).
    """
    apps: list[InstalledApp] = []
    seen: set[str] = set()

    sizes = pacman_installed_sizes() if include_sizes else {}

    try:
        for name, version in list_explicit_packages():
            apps.append(
                InstalledApp(
                    name=name,
                    source="pacman",
                    detail=version,
                    size_bytes=sizes.get(name, 0),
                )
            )
            seen.add(name.lower())
    except (FileNotFoundError, OSError):
        pass  # pacman ausente: solo contribuye el escaneo manual

    try:
        for path in scan_manual_entries(
            tuple(get_scan_paths()), set(get_scan_ignore())
        ):
            low = path.name.lower()
            if low in seen:
                continue

            apps.append(
                InstalledApp(
                    name=path.name,
                    source="manual",
                    detail=str(path),
                    size_bytes=path_size_for_display(path),
                )
            )
            seen.add(low)
    except (OSError, PermissionError):
        pass

    return apps


def health_score(
    cpu_usage: int | None,
    ram_usage: int | None,
    disk_usage: int | None,
) -> int | None:
    """Puntuación de salud 0-100 a partir de tres porcentajes de uso.

    Combina solo los valores disponibles; si no hay ninguno, devuelve
    None (el gauge mostrará "N/D"). A mayor uso, peor salud.
    [max_health] = 100, se resta la media de los usos.
    """
    samples = [v for v in (cpu_usage, ram_usage, disk_usage) if v is not None]
    if not samples:
        return None
    avg = sum(samples) / len(samples)
    return max(0, min(100, 100 - round(avg)))