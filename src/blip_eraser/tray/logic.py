"""Lógica de la bandeja — pura, sin PyQt6.

Decide cuándo avisar (versión nueva, mucho espacio recuperable), gestiona el
autoarranque de sesión y construye los comandos para abrir la app principal.
La limpieza destructiva NO se decide aquí: el borrado usa el mismo flujo con
confirmación y autorización de siempre (`run_destructive_action`).
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
FLATPAK_APP_ID = "io.github.DinoPathTeam.BlipEraser"
FLATPAK_TRAY_COMMAND = "blip-eraser-tray"


def _in_flatpak() -> bool:
    from blip_eraser.utils.host_cmd import is_flatpak

    return is_flatpak()


def flatpak_run_command(command: str | None = None) -> list[str]:
    """`flatpak run [--command=X] <app-id>`: como se arranca el Flatpak desde el host."""
    cmd = ["flatpak", "run"]
    if command:
        cmd.append(f"--command={command}")
    cmd.append(FLATPAK_APP_ID)
    return cmd


def _detached_on_host(command: list[str]) -> list[str]:
    # `setsid -f`: la instancia nueva no depende del sandbox que la lanza.
    return ["flatpak-spawn", "--host", "setsid", "-f", *command]


def app_command() -> list[str]:
    """Comando para abrir la app principal (otra instancia del Flatpak, o el mismo intérprete)."""
    if _in_flatpak():
        return _detached_on_host(flatpak_run_command())
    return [sys.executable, "-m", "blip_eraser"]


def tray_command() -> list[str]:
    """Comando para arrancar la propia bandeja."""
    if _in_flatpak():
        return _detached_on_host(flatpak_run_command(FLATPAK_TRAY_COMMAND))
    return [sys.executable, "-m", "blip_eraser.tray"]


def autostart_command() -> list[str]:
    """Exec= del autoarranque: lo ejecuta el host, no el sandbox."""
    if _in_flatpak():
        return flatpak_run_command(FLATPAK_TRAY_COMMAND)
    return tray_command()


def autostart_path() -> Path:
    if _in_flatpak():
        # Dentro del sandbox XDG_CONFIG_HOME apunta a ~/.var/app/…: el autoarranque
        # de sesión se lee del ~/.config real del host.
        from blip_eraser.utils.host_cmd import host_home

        return host_home() / ".config" / "autostart" / AUTOSTART_FILENAME
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
        exec_line = _desktop_exec(command or autostart_command())
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=BlipEraser (tray)\n"
            "Comment=BlipEraser tray icon\n"
            f"Exec={exec_line}\n"
            f"Icon={FLATPAK_APP_ID if _in_flatpak() else 'blip-eraser'}\n"
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


# ---------------------------------------------------------------------------
# Posición de la ventanita
# ---------------------------------------------------------------------------
POPUP_MARGIN = 8


def popup_position(
    anchor: tuple[int, int],
    size: tuple[int, int],
    screen: tuple[int, int, int, int],
) -> tuple[int, int]:
    """Esquina superior izquierda de la ventanita junto al icono de bandeja.

    `anchor` es el centro del icono (o el cursor si el escritorio no da su
    geometría), `size` el tamaño de la ventanita y `screen` el área disponible
    `(x, y, ancho, alto)`. Se abre hacia arriba si el icono está en la mitad
    inferior de la pantalla y hacia abajo si está en la superior, y se recorta
    para que nunca quede fuera.
    """
    ax, ay = anchor
    w, h = size
    sx, sy, sw, sh = screen
    x = ax - w // 2
    y = ay - h - POPUP_MARGIN if ay > sy + sh // 2 else ay + POPUP_MARGIN
    x = max(sx + POPUP_MARGIN, min(x, sx + sw - w - POPUP_MARGIN))
    y = max(sy + POPUP_MARGIN, min(y, sy + sh - h - POPUP_MARGIN))
    return x, y


# ---------------------------------------------------------------------------
# Posición elegida por el usuario
# ---------------------------------------------------------------------------
POS_AUTO = "auto"  # junto al icono de bandeja (por defecto)
POS_CUSTOM = "custom"  # arrastrada por el usuario (solo con plataforma que lo permita)
# Rejilla 3x3: (clave, columna, fila). Las 9 posiciones fijas del selector.
GRID_POSITIONS: tuple[tuple[str, int, int], ...] = (
    ("top-left", 0, 0), ("top", 1, 0), ("top-right", 2, 0),
    ("left", 0, 1), ("center", 1, 1), ("right", 2, 1),
    ("bottom-left", 0, 2), ("bottom", 1, 2), ("bottom-right", 2, 2),
)
FIXED_POSITIONS = tuple(key for key, _c, _r in GRID_POSITIONS)
PREF_POSITION = "tray_popup_position"
PREF_CUSTOM = "tray_popup_custom"
FIXED_MARGIN = 16


def fixed_position(
    key: str,
    size: tuple[int, int],
    screen: tuple[int, int, int, int],
    margin: int = FIXED_MARGIN,
) -> tuple[int, int]:
    """Esquina superior izquierda de la ventanita en una de las 9 posiciones.

    Usa el área disponible de la pantalla (sin paneles). `key` desconocida =
    abajo a la derecha, la zona habitual de la bandeja.
    """
    col, row = next(((c, r) for k, c, r in GRID_POSITIONS if k == key), (2, 2))
    w, h = size
    sx, sy, sw, sh = screen
    x = (sx + margin, sx + (sw - w) // 2, sx + sw - w - margin)[col]
    y = (sy + margin, sy + (sh - h) // 2, sy + sh - h - margin)[row]
    return (
        max(sx, min(x, sx + sw - w)),
        max(sy, min(y, sy + sh - h)),
    )


def _valid_custom(value: object) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    ):
        return int(value[0]), int(value[1])
    return None


def guess_tray_corner(
    geometry: tuple[int, int, int, int], available: tuple[int, int, int, int]
) -> str:
    """Esquina de la pantalla donde suele estar la bandeja, según dónde hay panel.

    Compara la pantalla completa con su área disponible (sin paneles): panel
    arriba → arriba a la derecha; panel en un lateral → abajo en ese lado;
    en cualquier otro caso (panel abajo o sin panel) → abajo a la derecha.
    """
    gx, gy, gw, gh = geometry
    ax, ay, aw, ah = available
    top = ay > gy
    bottom = ay + ah < gy + gh
    left = ax > gx
    right = ax + aw < gx + gw
    if top and not bottom:
        return "top-right"
    if left and not (right or bottom):
        return "bottom-left"
    return "bottom-right"


def resolve_position(
    prefs: dict,
    anchor: tuple[int, int] | None,
    size: tuple[int, int],
    screen: tuple[int, int, int, int],
    tray_corner: str = "bottom-right",
) -> tuple[int, int]:
    """Dónde abrir la ventanita según la preferencia del usuario.

    - posición fija elegida en la app → esa esquina/borde/centro;
    - `custom` → la última posición arrastrada, recortada a la pantalla;
    - `auto` (o valor desconocido/corrupto) → junto al icono si se conoce su
      posición (`anchor`); si no (Wayland no la da), en la esquina donde suele
      estar la bandeja (`tray_corner`, ver `guess_tray_corner`).
    """
    key = prefs.get(PREF_POSITION, POS_AUTO)
    if key in FIXED_POSITIONS:
        return fixed_position(key, size, screen)
    if key == POS_CUSTOM:
        custom = _valid_custom(prefs.get(PREF_CUSTOM))
        if custom is not None:
            sx, sy, sw, sh = screen
            w, h = size
            return (
                max(sx, min(custom[0], sx + sw - w)),
                max(sy, min(custom[1], sy + sh - h)),
            )
    if anchor is None:
        return fixed_position(tray_corner, size, screen, margin=POPUP_MARGIN)
    return popup_position(anchor, size, screen)


def should_force_xcb(env: dict, prefs: dict | None = None) -> bool:
    """True si conviene arrancar la bandeja vía XWayland para poder colocarla.

    En Wayland una aplicación no puede decidir dónde se abre su ventana (ni
    siquiera "junto a la bandeja"); con X11/XWayland sí. Se usa cuando hay
    sesión Wayland con XWayland disponible y el usuario no fijó él mismo
    `QT_QPA_PLATFORM`.
    """
    if env.get("QT_QPA_PLATFORM"):
        return False
    return bool(env.get("WAYLAND_DISPLAY")) and bool(env.get("DISPLAY"))
