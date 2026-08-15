"""Caché del último escaneo por sección — lógica pura, sin PyQt6.

Cada sección de la UI (Desinstalador, Limpiador recomendado, Limpiador
manual) guarda cuándo escaneó por última vez. Al volver a mostrar la
página, se re-escanea solo si el caché está viciado:

- Por tiempo: pasaron `max_age_seconds` (por defecto 300s = 5 min) desde
  el último escaneo.
- Por invalidación: la app marcó la sección como "cambió algo por acción
  propia" (borrado/desinstalación exitosa), así no hay que esperar al
  timeout.

El botón "Actualizar lista" ignora el caché y escanea siempre; eso no
pasa por aquí. Testeable sin GUI y con un reloj inyectable (`_clock`).
"""

from __future__ import annotations

import time

# Claves de sección conocidas (constantes para no esparcir strings sueltos).
SECTION_UNINSTALLER = "uninstaller"
SECTION_CLEANER_RECOMMENDED = "cleaner_recommended"
SECTION_CLEANER_MANUAL = "cleaner_manual"

DEFAULT_MAX_AGE_SECONDS = 300  # 5 minutos

# Reloj inyectable (los tests lo reemplazan para simular el paso del tiempo).
_clock = time.time

# {section_key: {"last_scanned": float | None, "invalidated": bool}}
_STATE: dict[str, dict] = {}


def is_stale(section_key: str, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> bool:
    """True si la sección debe re-escancarse (sin caché válido)."""
    entry = _STATE.get(section_key)
    if entry is None:
        return True
    if entry.get("invalidated"):
        return True
    last_scanned = entry.get("last_scanned")
    if last_scanned is None:
        return True
    return (_clock() - last_scanned) >= max_age_seconds


def mark_scanned(section_key: str) -> None:
    """Registra el escaneo actual de la sección (caché fresco)."""
    _STATE[section_key] = {"last_scanned": _clock(), "invalidated": False}


def invalidate(section_key: str) -> None:
    """Fuerza is_stale a True sin esperar el timeout (acción propia)."""
    _STATE[section_key] = {"last_scanned": None, "invalidated": True}


def clear() -> None:
    """Limpia el caché completo (útil en tests y al arrancar)."""
    _STATE.clear()