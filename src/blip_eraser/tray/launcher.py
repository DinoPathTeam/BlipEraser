"""Arranque de la bandeja desde la app principal (Qt).

La bandeja es un proceso aparte con una instancia única (bloqueo de archivo).
Al cerrar la app principal se deja la bandeja en segundo plano: cerrar del todo
es un paso más (Salir en el menú de la bandeja).
"""

from __future__ import annotations

from blip_eraser.tray import logic

LOCK_NAME = "blip-eraser-tray.lock"
PREF_KEEP_RUNNING = "tray_keep_running"


def lock_path() -> str:
    from PyQt6.QtCore import QDir

    return QDir.tempPath() + "/" + LOCK_NAME


def tray_is_running() -> bool:
    """True si ya hay una bandeja activa (su bloqueo está tomado)."""
    from PyQt6.QtCore import QLockFile

    lock = QLockFile(lock_path())
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        lock.unlock()
        return False
    return True


def keep_running_enabled(prefs: dict) -> bool:
    return prefs.get(PREF_KEEP_RUNNING, True) is not False


def ensure_tray_running(prefs: dict) -> bool:
    """Lanza la bandeja si el usuario lo quiere y no hay una activa. True si la lanzó.

    No se lanza dentro de Flatpak (no incluye la bandeja) ni si el usuario lo
    desactivó en Ajustes.
    """
    from PyQt6.QtCore import QProcess

    from blip_eraser.utils.host_cmd import FLATPAK_INFO

    if not keep_running_enabled(prefs) or FLATPAK_INFO.exists():
        return False
    if tray_is_running():
        return False
    cmd = logic.tray_command()
    return bool(QProcess.startDetached(cmd[0], cmd[1:]))
