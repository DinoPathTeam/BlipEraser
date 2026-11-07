"""Aplicaciones instaladas y salud del sistema — lógica pura, sin PyQt6.

Combina los paquetes de pacman (explícitos = "aplicaciones", dependencias)
con las entradas de escaneo manual (carpetas sueltas/AppImages) en una lista
única para la interfaz, clasificando cada elemento por tipo. Todo es testable
mockeando las utilidades.
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from blip_eraser.utils.config import get_scan_ignore, get_scan_paths
from blip_eraser.utils.file_utils import (
    path_mod_date,
    path_size_for_display,
    scan_manual_entries,
)
from blip_eraser.utils.pacman import (
    list_dependency_packages,
    list_explicit_packages,
)
from blip_eraser.utils.scan import pacman_installed_info

# Tipos de aplicación visibles en la UI.
KIND_APP = "app"          # paquete explícito de pacman
KIND_DEPENDENCY = "dependency"  # paquete instalado como dependencia
KIND_FOLDER = "folder"    # carpeta suelta / AppImage del escaneo manual

_KIND_TO_KEY = {
    KIND_APP: "kind_app",
    KIND_DEPENDENCY: "kind_dependency",
    KIND_FOLDER: "kind_folder",
}


def kind_label_key(kind: str) -> str:
    """Clave i18n de la etiqueta de un tipo (para usar con tr())."""
    return _KIND_TO_KEY.get(kind, _KIND_TO_KEY[KIND_FOLDER])


@dataclass
class InstalledApp:
    name: str
    source: str  # "pacman" | "manual"
    detail: str = ""
    size_bytes: int = 0
    kind: str = KIND_FOLDER  # "app" | "dependency" | "folder"
    install_date: str = ""


def list_installed_apps(include_sizes: bool = True) -> list[InstalledApp]:
    """Apps visibles al usuario: explícitas + dependencias + carpetas sueltas.

    Los paquetes explícitos son las "aplicaciones" de pacman; los que se
    instalaron como dependencia se marcan como tales; las entradas manuales
    son las carpetas sueltas/AppImages de los directorios de escaneo.
    Sin privilegios, todas las lecturas son seguras.
    Si `include_sizes` es True se añade el tamaño instalado y la fecha de
    instalación de cada paquete (una sola consulta `pacman -Qi`).
    """
    apps: list[InstalledApp] = []
    seen: set[str] = set()

    # Las consultas a pacman y el cálculo de tamaños de carpetas manuales son
    # independientes y casi todo su tiempo es esperar (subprocesos / E/S): se
    # lanzan a la vez en lugar de una detrás de otra.
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="apps-scan") as pool:
        info_f = pool.submit(pacman_installed_info) if include_sizes else None
        explicit_f = pool.submit(list_explicit_packages)
        deps_f = pool.submit(list_dependency_packages)

        manual_paths: list = []
        try:
            manual_paths = scan_manual_entries(
                tuple(get_scan_paths()), set(get_scan_ignore())
            )
        except (OSError, PermissionError):
            pass
        sizes_f = [(path, pool.submit(path_size_for_display, path)) for path in manual_paths]

        pacman_info = info_f.result() if info_f is not None else {}

        def _size(name: str) -> int:
            return pacman_info.get(name, {}).get("size", 0) or 0

        def _date(name: str) -> str:
            return pacman_info.get(name, {}).get("date", "") or ""

        for fut, kind in ((explicit_f, KIND_APP), (deps_f, KIND_DEPENDENCY)):
            try:
                for name, version in fut.result():
                    low = name.lower()
                    if low in seen:
                        continue
                    apps.append(
                        InstalledApp(
                            name=name,
                            source="pacman",
                            detail=version,
                            size_bytes=_size(name),
                            kind=kind,
                            install_date=_date(name),
                        )
                    )
                    seen.add(low)
            except (FileNotFoundError, OSError, subprocess.CalledProcessError):
                pass  # pacman ausente o falló: se muestran el resto de orígenes

        for path, size_fut in sizes_f:
            low = path.name.lower()
            if low in seen:
                continue
            try:
                size = size_fut.result()
                mod_date = path_mod_date(path)
            except (OSError, PermissionError):
                continue
            apps.append(
                InstalledApp(
                    name=path.name,
                    source="manual",
                    detail=str(path),
                    size_bytes=size,
                    kind=KIND_FOLDER,
                    install_date=mod_date,
                )
            )
            seen.add(low)

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