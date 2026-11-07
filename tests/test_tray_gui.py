"""Bandeja: ventanita temática, escaneo, limpieza con confirmación y avisos."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import blip_eraser.tray.app as tray_app  # noqa: E402
import blip_eraser.utils.config as config_mod  # noqa: E402
import blip_eraser.utils.log as log_mod  # noqa: E402
import blip_eraser.utils.scan as scan_mod  # noqa: E402
import blip_eraser.widgets.confirm_dialog as confirm_mod  # noqa: E402
from blip_eraser.tray import logic  # noqa: E402
from blip_eraser.utils.i18n import set_language  # noqa: E402

GIB = 1024**3


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def destructive_calls(monkeypatch):
    """Sustituye el flujo destructivo: registra lo que se le pide confirmar."""
    calls: list[dict] = []

    def fake(parent, plan, title, **kw):
        calls.append({"parent": parent, "plan": plan, "title": title, **kw})

    monkeypatch.setattr(confirm_mod, "run_destructive_action", fake)
    return calls


@pytest.fixture()
def ctl(qapp, tmp_path, monkeypatch, destructive_calls):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")
    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", tmp_path / "diag.log")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    set_language("en")
    c = tray_app.build_controller()
    yield c
    c.popup.hide()
    c.menu.close()


def _pump(qapp, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def _fake_stats(monkeypatch, **over):
    data = {"cpu": 12, "ram": 40, "disk": None, "recoverable": 2 * GIB, **over}
    monkeypatch.setattr(tray_app, "gather_stats", lambda: data)


# --- ventanita ---------------------------------------------------------------
def test_popup_starts_empty_and_clean_is_disabled(ctl):
    p = ctl.popup
    assert not p.clean_btn.isEnabled()
    assert p.scan_btn.text() == "Scan" and p.clean_btn.text() == "Clean"
    assert p.open_btn.text() == "Open BlipEraser"


def test_scan_fills_bars_and_enables_clean(qapp, ctl, monkeypatch):
    _fake_stats(monkeypatch)
    ctl.refresh_stats()
    assert ctl.popup.scan_btn.text() == "Scanning…" and not ctl.popup.scan_btn.isEnabled()
    assert _pump(qapp, lambda: not ctl._gathering)
    p = ctl.popup
    assert (p._bars["cpu"].value(), p._bars["ram"].value()) == (12, 40)
    assert p._bars["cpu"].format() == "12%" and p._bars["disk"].format() == "N/D"
    assert p.recoverable_value.text() == "2.0 GB"
    assert p.scan_btn.isEnabled() and p.clean_btn.isEnabled()


def test_clean_stays_disabled_when_nothing_recoverable(qapp, ctl, monkeypatch):
    _fake_stats(monkeypatch, recoverable=0)
    ctl.refresh_stats()
    assert _pump(qapp, lambda: not ctl._gathering)
    assert not ctl.popup.clean_btn.isEnabled()


def test_failed_scan_does_not_break_the_tray(qapp, ctl, monkeypatch):
    def boom():
        raise OSError("sin permisos")

    monkeypatch.setattr(tray_app, "gather_stats", boom)
    ctl.refresh_stats()
    assert _pump(qapp, lambda: not ctl._gathering)
    assert ctl.popup.scan_btn.isEnabled()
    assert ctl.popup.recoverable_value.text() == "N/D"


def test_no_overlapping_scans(ctl, monkeypatch):
    calls = []
    monkeypatch.setattr(tray_app, "gather_stats", lambda: calls.append(1) or {})
    ctl._gathering = True
    ctl.refresh_stats()
    assert calls == []


def test_show_popup_scans_and_stays_on_screen(qapp, ctl, monkeypatch):
    from PyQt6.QtGui import QGuiApplication

    _fake_stats(monkeypatch)
    ctl.show_popup()
    assert ctl.popup.isVisible()
    area = QGuiApplication.primaryScreen().availableGeometry()
    assert area.contains(ctl.popup.geometry().topLeft())
    assert _pump(qapp, lambda: not ctl._gathering)


def test_toggle_closes_and_ignores_the_click_that_just_closed_it(qapp, ctl, monkeypatch):
    _fake_stats(monkeypatch)
    ctl.show_popup()
    ctl.toggle_popup()
    assert not ctl.popup.isVisible()
    ctl.toggle_popup()  # inmediatamente después: es el mismo clic que la cerró
    assert not ctl.popup.isVisible()
    ctl.popup._closed_at = 0.0
    ctl.toggle_popup()
    assert ctl.popup.isVisible()
    _pump(qapp, lambda: not ctl._gathering)


def test_popup_follows_the_theme_chosen_in_the_main_app(ctl):
    from blip_eraser.utils import theme as theme_mod

    config_mod.save_prefs({"theme": "blue"})
    ctl.popup.apply_theme()
    assert theme_mod.THEMES["blue"]["accent"].lower() in ctl.popup.styleSheet().lower()
    config_mod.save_prefs({"theme": "green"})
    ctl.popup.apply_theme()
    assert theme_mod.THEMES["green"]["accent"].lower() in ctl.popup.styleSheet().lower()


def test_unknown_theme_falls_back_to_default(ctl):
    from blip_eraser.utils import theme as theme_mod

    config_mod.save_prefs({"theme": "no-existe"})
    ctl.popup.apply_theme()
    assert theme_mod.THEMES["red"]["accent"].lower() in ctl.popup.styleSheet().lower()


# --- limpieza: siempre por el flujo con confirmación -------------------------
def test_clean_lists_items_and_asks_for_confirmation(qapp, ctl, destructive_calls, monkeypatch):
    entries = [("junk", Path("/home/u/.cache/a"), 10), ("logs", Path("/var/log/b"), 20)]
    monkeypatch.setattr(scan_mod, "scan_cleanup_items", lambda: entries)
    ctl.clean()
    assert _pump(qapp, lambda: bool(destructive_calls))
    call = destructive_calls[0]
    assert call["parent"] is None
    assert [i.paths for i in call["plan"].items] == [[Path("/home/u/.cache/a")], [Path("/var/log/b")]]
    assert call["plan"].total_bytes == 30
    assert callable(call["on_finished"])  # tras limpiar se vuelve a escanear


def test_clean_with_nothing_to_clean_shows_message_and_deletes_nothing(
    qapp, ctl, destructive_calls, monkeypatch
):
    from PyQt6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a: shown.append(a[2])))
    monkeypatch.setattr(scan_mod, "scan_cleanup_items", lambda: [])
    ctl.clean()
    assert _pump(qapp, lambda: bool(shown))
    assert shown == ["There is nothing to clean."]
    assert destructive_calls == []


def test_failed_listing_is_treated_as_nothing_and_never_deletes(
    qapp, ctl, destructive_calls, monkeypatch
):
    from PyQt6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a: shown.append(a)))

    def boom():
        raise OSError("x")

    monkeypatch.setattr(scan_mod, "scan_cleanup_items", boom)
    ctl.clean()
    assert _pump(qapp, lambda: bool(shown))
    assert destructive_calls == []


def test_after_cleaning_it_rescans(qapp, ctl, destructive_calls, monkeypatch):
    monkeypatch.setattr(scan_mod, "scan_cleanup_items", lambda: [("junk", Path("/x"), 1)])
    _fake_stats(monkeypatch, recoverable=0)
    ctl.clean()
    assert _pump(qapp, lambda: bool(destructive_calls))
    destructive_calls[0]["on_finished"](True)
    assert _pump(qapp, lambda: ctl.popup.recoverable_value.text() == "0.0 B")


# --- abrir la app ---------------------------------------------------------------
def test_open_app_launches_detached_and_debounces(ctl, monkeypatch):
    from PyQt6.QtCore import QProcess

    launched = []
    monkeypatch.setattr(
        QProcess, "startDetached", staticmethod(lambda prog, args: launched.append((prog, args)) or True)
    )
    assert ctl.open_app() is True
    assert ctl.open_app() is False  # clic repetido: ignorado
    assert launched == [(launched[0][0], ["-m", "blip_eraser"])]


def test_open_button_hides_popup_and_opens(ctl, monkeypatch):
    opened = []
    monkeypatch.setattr(ctl, "open_app", lambda: opened.append(1))
    ctl.popup.show()
    ctl.popup.open_btn.click()
    assert opened == [1] and not ctl.popup.isVisible()


# --- avisos y ajustes ----------------------------------------------------------------
def test_startup_notice_for_new_version_is_shown_once(ctl, monkeypatch):
    shown = []
    monkeypatch.setattr(ctl.tray, "showMessage", lambda *a: shown.append(a[:2]))
    ctl._on_startup({"update_version": "9.9.9", "recoverable": 0})
    assert shown and "9.9.9" in shown[0][1]
    ctl._on_startup({"update_version": "9.9.9", "recoverable": 0})
    assert len(shown) == 1


def test_junk_notice_click_opens_the_popup(ctl, monkeypatch):
    shown = []
    monkeypatch.setattr(ctl.tray, "showMessage", lambda *a: shown.append(a[:2]))
    popups = []
    monkeypatch.setattr(ctl, "show_popup", lambda: popups.append(1))
    ctl._on_startup({"update_version": None, "recoverable": 8 * GIB})
    assert shown and "8.0 GB" in shown[0][1]
    ctl._on_message_clicked()
    assert popups == [1]


def test_startup_is_silent_when_notifications_disabled(ctl, monkeypatch):
    config_mod.save_prefs({"tray_notifications": False})
    shown = []
    monkeypatch.setattr(ctl.tray, "showMessage", lambda *a: shown.append(a))
    ctl._on_startup({"update_version": "9.9.9", "recoverable": 99 * GIB})
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


# --- Wayland: nada de popups con grab ----------------------------------------------
def test_popup_is_not_a_grabbing_popup(ctl):
    from PyQt6.QtCore import Qt

    assert ctl.popup.windowType() == Qt.WindowType.Tool  # no Qt.Popup
    assert ctl.popup.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_popup_closes_when_it_loses_focus_after_being_active(qapp, ctl, monkeypatch):
    from PyQt6.QtCore import QEvent

    ctl.popup.show()
    event = QEvent(QEvent.Type.ActivationChange)
    monkeypatch.setattr(ctl.popup, "isActiveWindow", lambda: True)
    ctl.popup.changeEvent(event)
    assert ctl.popup._was_active
    monkeypatch.setattr(ctl.popup, "isActiveWindow", lambda: False)
    ctl.popup.changeEvent(event)
    assert _pump(qapp, lambda: not ctl.popup.isVisible())


def test_popup_does_not_close_before_it_was_ever_active(qapp, ctl, monkeypatch):
    from PyQt6.QtCore import QEvent

    ctl.popup.show()
    ctl.popup._was_active = False
    monkeypatch.setattr(ctl.popup, "isActiveWindow", lambda: False)
    ctl.popup.changeEvent(QEvent(QEvent.Type.ActivationChange))
    _pump(qapp, lambda: False, timeout=0.2)
    assert ctl.popup.isVisible()


def test_escape_closes_the_popup(qapp, ctl):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    ctl.popup.show()
    QTest.keyClick(ctl.popup, Qt.Key.Key_Escape)
    assert not ctl.popup.isVisible()
