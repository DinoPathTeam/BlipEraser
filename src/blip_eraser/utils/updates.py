"""Comprobación de actualizaciones — lógica pura, sin PyQt6.

`check_for_updates()` consulta el último release de GitHub con la stdlib
(`urllib`, timeout corto) y compara con `__version__`. Ante cualquier
fallo (sin red, API caída, tag ilegible) devuelve "sin actualización":
fail-closed para no bloquear el arranque.

Como máximo UNA consulta cada 24 h: el último tag y la hora se guardan en
prefs.json (`update_latest`, `update_checked_at`). Un fallo de red no se
cachea (el siguiente arranque reintenta). Se desactiva por completo con la
preferencia `check_updates: false`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen

from blip_eraser import __version__
from blip_eraser.utils.config import load_prefs, save_prefs

API_URL = "https://api.github.com/repos/DinoPathTeam/BlipEraser/releases/latest"
TIMEOUT = 5
CACHE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class UpdateCheckResult:
    """Resultado de la comprobación de actualizaciones."""

    has_update: bool
    latest_version: str | None = None


def _is_newer(latest: str, current: str) -> bool:
    """True si `latest` (tag sin 'v') es mayor que `current`. Fail-closed."""
    try:
        parse = lambda v: tuple(int(p) for p in v.split("."))
        return parse(latest) > parse(current)
    except (ValueError, AttributeError):
        return False


def _cached_latest(prefs: dict, now: float) -> str | None:
    """Último tag cacheado si la consulta tiene menos de 24 h; si no, None.

    Un reloj que retrocede (edad negativa) o valores corruptos invalidan la caché.
    """
    checked_at, latest = prefs.get("update_checked_at"), prefs.get("update_latest")
    if isinstance(checked_at, bool) or not isinstance(checked_at, (int, float)):
        return None
    if not isinstance(latest, str) or not latest:
        return None
    if 0 <= now - checked_at < CACHE_SECONDS:
        return latest
    return None


def _result_for(latest: str, current_version: str) -> UpdateCheckResult:
    if latest and _is_newer(latest, current_version):
        return UpdateCheckResult(has_update=True, latest_version=latest)
    return UpdateCheckResult(has_update=False, latest_version=None)


def check_for_updates(
    current_version: str = __version__, *, now: float | None = None
) -> UpdateCheckResult:
    """Devuelve si existe un release más reciente que `current_version`.

    Sin red, con respuesta inesperada o con `check_updates: false` →
    `has_update=False`. Consulta GitHub como máximo una vez cada 24 h.
    """
    try:
        prefs = load_prefs()
        if prefs.get("check_updates", True) is False:
            return UpdateCheckResult(has_update=False, latest_version=None)
        now = time.time() if now is None else now
        cached = _cached_latest(prefs, now)
        if cached is not None:
            return _result_for(cached, current_version)

        req = Request(API_URL, headers={"Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            tag = json.load(resp).get("tag_name", "")
        latest = tag.lstrip("v").strip()
        if latest:
            save_prefs({"update_checked_at": now, "update_latest": latest})
            return _result_for(latest, current_version)
    except Exception:
        pass
    return UpdateCheckResult(has_update=False, latest_version=None)
