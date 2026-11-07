"""Bandeja: menú, relleno de datos al abrirlo, avisos y apertura de la app."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import blip_eraser.tray.app as tray_app  # noqa: E402
import blip_eraser.utils.config as config_mod  # noqa: E402
import blip_eraser.utils.log as log_mod  # noqa: E402
from blip_eraser.tray import logic  # noqa: E402
from blip_eraser.utils.i18n import set_language  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def ctl(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")
    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", tmp_path / "diag.log")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    set_language("en")
    c = tray_app.build_controller()
    yield c
    c.menu.close()


def _pump(qapp, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_menu_shows_placeholders_until_stats_arrive(ctl):
    assert ctl.status_action.text() == "Calculating…"
    assert "Calculating" in ctl.recoverable_action.text()


def test_opening_menu_gathers_stats_in_background(qapp, ctl, monkeypatch):
    monkeypatch.setattr(
        tray_app, "gather_stats",
        lambda: {"cpu": 12, "ram": 40, "disk": None, "recoverable": 2 * 1024**3},
    )
    ctl.refresh_stats()
    assert _pump(qapp, lambda: "CPU 12%" in ctl.status_action.text())
    assert ctl.status_action.text() == "CPU 12% · RAM 40% · Disk N/D"
    assert "2.0 GB" in ctl.recoverable_action.text()
    assert not ctl._gathering


def test_failed_gather_does_not_break_the_tray(qapp, ctl, monkeypatch):
    def boom():
        raise OSError("sin permisos")

    monkeypatch.setattr(tray_app, "gather_stats", boom)
    ctl.refresh_stats()
    assert _pump(qapp, lambda: not ctl._gathering)


def test_no_overlapping_gathers(ctl, monkeypatch):
    calls = []
    monkeypatch.setattr(tray_app, "gather_stats", lambda: calls.append(1) or {})
    ctl._gathering = True
    ctl.refresh_stats()
    assert calls == []


def test_open_app_launches_detached_and_debounces(ctl, monkeypatch):
    from PyQt6.QtCore import QProcess

    launched = []
    monkeypatch.setattr(
        QProcess, "startDetached", staticmethod(lambda prog, args: launched.append((prog, args)) or True)
    )
    assert ctl.open_app() is True
    assert ctl.open_app() is False  # clic repetido: ignorado
    assert len(launched) == 1
    assert launched[0][1] == ["-m", "blip_eraser"]
    ctl._last_open = 0.0
    ctl.open_app([logic.CLEANUP_FLAG])
    assert launched[1][1][-1] == "--cleanup"


def test_startup_notice_for_new_version_is_shown_once(ctl, monkeypatch):
    shown = []
    monkeypatch.setattr(ctl.tray, "showMessage", lambda *a: shown.append(a[:2]))
    ctl._on_startup({"update_version": "9.9.9", "recoverable": 0})
    assert shown and "9.9.9" in shown[0][1]
    ctl._on_startup({"update_version": "9.9.9", "recoverable": 0})
    assert len(shown) == 1


def test_startup_junk_notice_click_opens_cleanup(ctl, monkeypatch):
    shown = []
    monkeypatch.setattr(ctl.tray, "showMessage", lambda *a: shown.append(a[:2]))
    opened = []
    monkeypatch.setattr(ctl, "open_app", lambda extra=None: opened.append(extra))
    ctl._on_startup({"update_version": None, "recoverable": 8 * 1024**3})
    assert shown and "8.0 GB" in shown[0][1]
    ctl._on_message_clicked()
    assert opened == [[logic.CLEANUP_FLAG]]


def test_startup_is_silent_when_notifications_disabled(ctl, monkeypatch):
    config_mod.save_prefs({"tray_notifications": False})
    shown = []
    monkeypatch.setattr(ctl.tray, "showMessage", lambda *a: shown.append(a))
    ctl._on_startup({"update_version": "9.9.9", "recoverable": 99 * 1024**3})
    assert shown == []


def test_autostart_toggle_creates_and_removes_entry(ctl):
    assert not logic.autostart_enabled()
    ctl.autostart_action.setChecked(True)
    assert logic.autostart_enabled()
    ctl.autostart_action.setChecked(False)
    assert not logic.autostart_enabled()


def test_notifications_toggle_persists(ctl):
    ctl.notify_action.setChecked(False)
    assert config_mod.load_prefs()["tray_notifications"] is False


def test_startup_check_combines_update_and_cleanup(monkeypatch):
    import blip_eraser.utils.scan as scan_mod
    import blip_eraser.utils.updates as updates_mod

    monkeypatch.setattr(
        updates_mod, "check_for_updates",
        lambda: updates_mod.UpdateCheckResult(True, "3.0.0"),
    )
    monkeypatch.setattr(
        scan_mod, "scan_cleanup",
        lambda: {"junk_bytes": 1, "pacman_cache_bytes": 2, "logs_bytes": 3, "orphan_count": 0},
    )
    assert tray_app.startup_check() == {"update_version": "3.0.0", "recoverable": 6}
