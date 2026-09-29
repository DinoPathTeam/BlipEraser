"""Comprobación de actualizaciones — lógica pura, sin PyQt6.

`check_for_updates()` consulta el último release de GitHub con la stdlib
(`urllib`, timeout corto) y compara con `__version__`. Ante cualquier
fallo (sin red, API caída, tag ilegible) devuelve "sin actualización":
fail-closed para no bloquear el arranque.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from blip_eraser import __version__

API_URL = "https://api.github.com/repos/DinoPathTeam/BlipEraser/releases/latest"
TIMEOUT = 5


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


def check_for_updates(current_version: str = __version__) -> UpdateCheckResult:
    """Devuelve si existe un release más reciente que `current_version`.

    Sin red o con respuesta inesperada → `has_update=False`.
    """
    try:
        req = Request(API_URL, headers={"Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=TIMEOUT) as resp:  # ponytail: sin caché; un GET/arranque es despreciable
            tag = json.load(resp).get("tag_name", "")
        latest = tag.lstrip("v").strip()
        if latest and _is_newer(latest, current_version):
            return UpdateCheckResult(has_update=True, latest_version=latest)
    except Exception:
        pass
    return UpdateCheckResult(has_update=False, latest_version=None)