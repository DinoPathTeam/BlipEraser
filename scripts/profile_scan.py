"""Mide en qué se va el tiempo del escaneo (sin GUI). Uso:

    PYTHONPATH=src python scripts/profile_scan.py
"""

from __future__ import annotations

import time
from pathlib import Path

from blip_eraser.utils.apps import list_installed_apps
from blip_eraser.utils.config import get_scan_ignore, get_scan_paths
from blip_eraser.utils.file_utils import get_dir_size, scan_manual_entries
from blip_eraser.utils.pacman import list_dependency_packages, list_explicit_packages
from blip_eraser.utils.scan import (
    _LOG_DIR,
    _PACMAN_CACHE,
    _cache_dir,
    orphan_packages,
    pacman_installed_info,
    scan_cleanup,
)


def timed(label: str, fn, *args):
    start = time.perf_counter()
    try:
        result = fn(*args)
    except (OSError, RuntimeError) as exc:
        print(f"{'fallo':>8}     {label}: {exc}")
        return None
    print(f"{(time.perf_counter() - start) * 1000:8.0f} ms  {label}")
    return result


def main() -> None:
    print("--- pacman ---")
    timed("pacman -Qe", list_explicit_packages)
    timed("pacman -Qd", list_dependency_packages)
    timed("pacman -Qi (parseado)", pacman_installed_info)
    timed("pacman -Qdt (huérfanos)", orphan_packages)

    print("--- carpetas manuales (las 8 más lentas) ---")
    paths = scan_manual_entries(tuple(get_scan_paths()), set(get_scan_ignore()))
    rows = []
    for path in paths:
        start = time.perf_counter()
        size = get_dir_size(path) if path.is_dir() else 0
        rows.append(((time.perf_counter() - start) * 1000, path, size))
    print(f"{len(paths)} entradas, {sum(r[0] for r in rows):.0f} ms en total")
    for ms, path, size in sorted(rows, reverse=True)[:8]:
        print(f"{ms:8.0f} ms  {size / 1e6:9.1f} MB  {path}")

    print("--- limpieza ---")
    for label, base in (("~/.cache", _cache_dir()), ("caché pacman", Path(_PACMAN_CACHE)), ("/var/log", Path(_LOG_DIR))):
        timed(label, get_dir_size, base)

    print("--- totales ---")
    timed("scan_cleanup()", scan_cleanup)
    timed("list_installed_apps()", list_installed_apps)


if __name__ == "__main__":
    main()
