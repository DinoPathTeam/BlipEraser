"""Aplicaciones instaladas y salud del sistema — lógica pura, sin PyQt6.

Combina los paquetes de pacman (explícitos = "aplicaciones", dependencias)
con las entradas de escaneo manual (carpetas sueltas/AppImages) en una lista
única para la interfaz, clasificando cada elemento por tipo. Todo es testable
mockeando las utilidades.
"""

from __future__ import annotations

import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

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


# Los tamaños de carpetas sueltas son lo más caro del escaneo (recorrer miles
# o millones de archivos). Se cachean unos minutos para que un reescaneo o abrir
# otra página no vuelva a pagar ese coste.
_MANUAL_SIZE_TTL = 600.0
_manual_size_cache: dict[str, tuple[float, int]] = {}
_manual_size_lock = threading.Lock()


def clear_manual_size_cache() -> None:
    with _manual_size_lock:
        _manual_size_cache.clear()


def _cached_manual_size(path: Path) -> int | None:
    with _manual_size_lock:
        hit = _manual_size_cache.get(str(path))
    if hit is not None and time.monotonic() - hit[0] < _MANUAL_SIZE_TTL:
        return hit[1]
    return None


def _manual_size(path: Path) -> int:
    cached = _cached_manual_size(path)
    if cached is not None:
        return cached
    size = path_size_for_display(path)
    with _manual_size_lock:
        _manual_size_cache[str(path)] = (time.monotonic(), size)
    return size


def fill_manual_sizes(apps: list[InstalledApp], workers: int = 3) -> None:
    """Calcula (en sitio) el tamaño de las carpetas sueltas que aún no lo tienen.

    Pensada para un hilo de fondo tras `list_installed_apps(manual_sizes=False)`:
    la lista aparece enseguida y los pesos se rellenan cuando están listos.
    """
    pending = [a for a in apps if a.source == "manual" and not a.size_bytes]
    if not pending:
        return
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sizes") as pool:
        futures = [(a, pool.submit(_manual_size, Path(a.detail))) for a in pending]
        for app, fut in futures:
            try:
                app.size_bytes = fut.result()
            except (OSError, PermissionError):
                continue


def list_installed_apps(
    include_sizes: bool = True, manual_sizes: bool = True
) -> list[InstalledApp]:
    """Apps visibles al usuario: explícitas + dependencias + carpetas sueltas.

    Los paquetes explícitos son las "aplicaciones" de pacman; los que se
    instalaron como dependencia se marcan como tales; las entradas manuales
    son las carpetas sueltas/AppImages de los directorios de escaneo.
    Sin privilegios, todas las lecturas son seguras.
    Con `manual_sizes=False` las carpetas sueltas salen con el peso que haya en
    caché (o 0) sin recorrerlas; `fill_manual_sizes` lo completa después.
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
        sizes_f = [
            (path, pool.submit(_manual_size, path) if manual_sizes else None)
            for path in manual_paths
        ]

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
                size = size_fut.result() if size_fut is not None else (
                    _cached_manual_size(path) or 0
                )
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