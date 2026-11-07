"""Lógica de la bandeja — pura, sin PyQt6.

Decide cuándo avisar (versión nueva, mucho espacio recuperable), gestiona el
autoarranque de sesión y construye los comandos para abrir la app principal.
La limpieza destructiva NO vive aquí: la bandeja solo abre la app con
`--cleanup` y allí se usa el mismo flujo de confirmación de siempre.
"""

from __future__ import annotations

import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

# Espacio recuperable (basura + caché de pacman + registros) a partir del cual
# se avisa, y tiempo mínimo entre avisos de este tipo.
JUNK_NOTIFY_BYTES = 5 * 1024**3
JUNK_NOTIFY_INTERVAL = 24 * 60 * 60

CLEANUP_FLAG = "--cleanup"
AUTOSTART_FILENAME = "blip-eraser-tray.desktop"

KIND_UPDATE = "update"
KIND_JUNK = "junk"


@dataclass(frozen=True)
class Notice:
    """Un aviso a mostrar: `kind` decide la acción al pulsarlo."""

    kind: str
    value: str  # versión nueva (update) o bytes como texto (junk)


def recoverable_bytes(cleanup: dict[str, int]) -> int:
    """Total recuperable de un resultado de `scan_cleanup()`."""
    return sum(
        int(cleanup.get(key, 0) or 0)
        for key in ("junk_bytes", "pacman_cache_bytes", "logs_bytes")
    )


def status_values(
    cpu: int | None, ram: int | None, disk: int | None, na: str
) -> tuple[str, str, str]:
    """Porcentajes como texto ('N/D' si no hay dato)."""
    fmt = lambda v: f"{v}%" if v is not None else na
    return fmt(cpu), fmt(ram), fmt(disk)


def decide_notices(
    prefs: dict,
    *,
    update_version: str | None,
    recoverable: int,
    now: float,
) -> tuple[list[Notice], dict]:
    """Qué avisos mostrar y qué preferencias persistir para no repetirlos.

    - Versión nueva: una vez por versión (`tray_notified_version`).
    - Espacio recuperable: si supera el umbral y pasaron 24 h desde el último
      aviso de este tipo (`tray_junk_notified_at`); un reloj que retrocede
      cuenta como "ya pasó el intervalo" solo si la marca es corrupta.
    - Con `tray_notifications: false` no se avisa de nada.
    """
    if prefs.get("tray_notifications", True) is False:
        return [], {}

    notices: list[Notice] = []
    updates: dict = {}

    if update_version and prefs.get("tray_notified_version") != update_version:
        notices.append(Notice(KIND_UPDATE, update_version))
        updates["tray_notified_version"] = update_version

    if recoverable >= JUNK_NOTIFY_BYTES:
        last = prefs.get("tray_junk_notified_at")
        valid = isinstance(last, (int, float)) and not isinstance(last, bool)
        if not valid or not (0 <= now - last < JUNK_NOTIFY_INTERVAL):
            notices.append(Notice(KIND_JUNK, str(recoverable)))
            updates["tray_junk_notified_at"] = now

    return notices, updates


# ---------------------------------------------------------------------------
# Comandos y autoarranque
# ---------------------------------------------------------------------------
def app_command(extra_args: list[str] | None = None) -> list[str]:
    """Comando para abrir la app principal con el mismo intérprete."""
    return [sys.executable, "-m", "blip_eraser", *(extra_args or [])]


def tray_command() -> list[str]:
    """Comando para arrancar la propia bandeja."""
    return [sys.executable, "-m", "blip_eraser.tray"]


def autostart_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / AUTOSTART_FILENAME


def _desktop_exec(command: list[str]) -> str:
    """Línea Exec= de un .desktop: argumentos con espacios entre comillas."""
    parts = []
    for part in command:
        if any(c in part for c in ' \t"\\$`'):
            part = '"' + part.replace("\\", "\\\\").replace('"', '\\"') + '"'
        parts.append(part)
    return " ".join(parts)


def autostart_enabled() -> bool:
    return autostart_path().is_file()


def set_autostart(enabled: bool, command: list[str] | None = None) -> bool:
    """Crea o borra la entrada de autoarranque de sesión. True si se aplicó."""
    path = autostart_path()
    try:
        if not enabled:
            path.unlink(missing_ok=True)
            return True
        path.parent.mkdir(parents=True, exist_ok=True)
        exec_line = _desktop_exec(command or tray_command())
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=BlipEraser (tray)\n"
            "Comment=BlipEraser tray icon\n"
            f"Exec={exec_line}\n"
            "Icon=blip-eraser\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def shell_preview(command: list[str]) -> str:
    """Comando legible (para registros y mensajes de error)."""
    return shlex.join(command)
