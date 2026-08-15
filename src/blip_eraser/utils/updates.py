"""Comprobación de actualizaciones — lógica pura, sin PyQt6 ni red.

Por ahora es un stub intencionado: `check_for_updates()` no hace llamadas
de red ni de sistema y siempre devuelve "no hay actualización". El flujo
de arranque (splash) lo usa como paso definido y determinista, sin
depender de conectividad ni latencia.

Cuando se implemente el chequeo real contra GitHub Releases, esta función
es el único punto a tocar: debe seguir devolviendo un `UpdateCheckResult`
para no romper el contrato del splash.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateCheckResult:
    """Resultado de la comprobación de actualizaciones."""

    has_update: bool
    latest_version: str | None = None


def check_for_updates() -> UpdateCheckResult:
    """Comprueba si existe una versión más reciente de BlipEraser.

    Stub: devuelve siempre "sin actualización" y no toca la red.
    """
    # TODO(actualizaciones): consultar el feed de GitHub Releases de
    # DinoPathTeam/BlipEraser y comparar con la versión local. Hasta que
    # exista ese feed, este stub se mantiene sin llamadas de red.
    return UpdateCheckResult(has_update=False, latest_version=None)