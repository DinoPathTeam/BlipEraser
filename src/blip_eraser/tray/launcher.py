"""Arranque de la bandeja desde la app principal (Qt).

La bandeja es un proceso aparte con una instancia única (bloqueo de archivo).
Al cerrar la app principal se deja la bandeja en segundo plano: cerrar del todo
es un paso más (Salir en el menú de la bandeja).
"""

from __future__ import annotations

import fcntl
import os
import tempfile
import time
from pathlib import Path

from blip_eraser.tray import logic

LOCK_NAME = "blip-eraser-tray.lock"
PREF_KEEP_RUNNING = "tray_keep_running"


def lock_path() -> str:
    """Ruta del bloqueo de instancia única.

    En Flatpak la app y la bandeja corren en sandboxes distintos (cada uno con su
    propio /tmp): el bloqueo vive en `$XDG_RUNTIME_DIR/app/<app-id>/`, que sí
    comparten todas las instancias de la misma app.
    """
    from blip_eraser.utils.host_cmd import is_flatpak

    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if is_flatpak() and runtime:
        shared = Path(runtime) / "app" / logic.FLATPAK_APP_ID
        try:
            shared.mkdir(parents=True, exist_ok=True)
            return str(shared / LOCK_NAME)
        except OSError:
            pass
    return str(Path(tempfile.gettempdir()) / LOCK_NAME)


class TrayLock:
    """Bloqueo exclusivo con `flock`: lo libera el sistema si el proceso muere.

    A diferencia de `QLockFile`, no depende de comprobar si un PID sigue vivo, que
    no vale entre sandboxes (cada uno tiene su espacio de PIDs).
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path or lock_path()
        self._fd: int | None = None

    def try_lock(self, timeout_ms: int = 0) -> bool:
        if self._fd is not None:
            return True
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        except OSError:
            return False
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fd = fd
                return True
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    return False
                time.sleep(0.05)

    def unlock(self) -> None:
        if self._fd is not None:
            os.close(self._fd)  # cerrar el descriptor suelta el flock
            self._fd = None


def tray_is_running() -> bool:
    """True si ya hay una bandeja activa (su bloqueo está tomado)."""
    lock = TrayLock()
    if lock.try_lock(0):
        lock.unlock()
        return False
    return True


def keep_running_enabled(prefs: dict) -> bool:
    return prefs.get(PREF_KEEP_RUNNING, True) is not False


def ensure_tray_running(prefs: dict) -> bool:
    """Lanza la bandeja si el usuario lo quiere y no hay una activa. True si la lanzó.

    No se lanza si el usuario lo desactivó en Ajustes. En Flatpak se arranca en el
    host (`flatpak-spawn --host`) como instancia independiente: un proceso hijo
    del sandbox moriría junto con la app.
    """
    from PyQt6.QtCore import QProcess

    if not keep_running_enabled(prefs):
        return False
    if tray_is_running():
        return False
    cmd = logic.tray_command()
    return bool(QProcess.startDetached(cmd[0], cmd[1:]))
