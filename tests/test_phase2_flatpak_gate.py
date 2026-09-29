"""Gate de phase2_installer en Flatpak: mensaje accionable, sin efectos.

El instalador GUI copia archivos del sandbox (invisibles al host) a
rutas que no existen en el sandbox: en Flatpak debe negarse con el
mensaje que apunta a install-daemon.sh, sin tocar nada.
"""

from blip_eraser.utils import phase2_installer
from blip_eraser.utils.phase2_installer import (
    FLATPAK_DAEMON_MSG,
    install_all_phase2,
    install_phase2_if_needed,
)


def test_install_all_refuses_inside_flatpak(monkeypatch):
    monkeypatch.setattr(phase2_installer, "is_flatpak", lambda: True)
    ok, msg, restart = install_all_phase2()
    assert ok is False
    assert restart is False
    assert "install-daemon.sh" in msg


def test_install_if_needed_refuses_inside_flatpak(monkeypatch):
    monkeypatch.setattr(phase2_installer, "is_flatpak", lambda: True)
    ok, msg = install_phase2_if_needed()
    assert ok is False
    assert msg == FLATPAK_DAEMON_MSG


def test_no_flatpak_paths_outside_sandbox(monkeypatch):
    monkeypatch.setattr(phase2_installer, "is_flatpak", lambda: False)
    assert "install-daemon.sh" in FLATPAK_DAEMON_MSG
