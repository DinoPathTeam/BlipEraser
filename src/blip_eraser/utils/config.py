"""Configuración de la app (temas, fuentes, rutas de escaneo) — sin PyQt6.

Archivo independiente de i18n (~/.config/blip-eraser/prefs.json) para no
tocar el archivo de idioma y sus tests. Toda lectura/escritura es
best-effort y se puede redirigir a tmp_path en tests vía PREFS_FILE.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "blip-eraser"
PREFS_FILE = CONFIG_DIR / "prefs.json"

PREFS_DEFAULTS: dict = {
    "theme": "red",
    "font": "system",
    "scan_paths": [
        "~/.local/share",
        "~/Games",
        "~/Descargas",
        "~/Applications",
    ],
    "scan_ignore": ["applications", "icons", "mime", "fonts", "sounds"],
}


def _read_raw() -> dict:
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def load_prefs() -> dict:
    """Preferencias completas (por defecto + lo persistido)."""
    merged = dict(PREFS_DEFAULTS)
    merged.update(_read_raw())
    return merged


def save_prefs(patch: dict) -> None:
    """Fusiona `patch` sobre las preferencias actuales y persiste.

    Best-effort: un fallo de escritura no rompe la app.
    """
    try:
        current = load_prefs()
        current.update(patch)
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def get_scan_paths() -> list[str]:
    return list(load_prefs().get("scan_paths", PREFS_DEFAULTS["scan_paths"]))


def set_scan_paths(paths: list[str]) -> None:
    save_prefs({"scan_paths": paths})