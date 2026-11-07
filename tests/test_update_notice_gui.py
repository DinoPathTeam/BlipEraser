"""Aviso discreto de versión nueva (barra de estado + comprobación en segundo plano)."""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from blip_eraser.utils import updates  # noqa: E402
from blip_eraser.utils.i18n import set_language  # noqa: E402
from blip_eraser.widgets.status_bar import SystemStatusBar  # noqa: E402
from blip_eraser.widgets.update_notice import UpdateNotifier  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _label(bar):
    return bar.findChild(QLabel, "UpdateNotice")


def test_no_notice_by_default(app):
    bar = SystemStatusBar()
    assert _label(bar) is None or not _label(bar).isVisibleTo(bar)


def test_show_update_available_shows_version_and_releases_link(app):
    set_language("es")
    bar = SystemStatusBar()
    bar.show_update_available("1.2.0")
    label = _label(bar)
    assert label is not None
    assert "1.2.0" in label.text()
    assert "github.com/DinoPathTeam/BlipEraser/releases" in label.text()
    assert label.openExternalLinks() is True
    assert label.isVisibleTo(bar)


def test_notice_is_retranslated(app):
    bar = SystemStatusBar()
    set_language("es")
    bar.show_update_available("1.2.0")
    es = _label(bar).text()
    set_language("en")
    bar.retranslate()
    assert _label(bar).text() != es
    assert "1.2.0" in _label(bar).text()
    set_language("es")


def _wait(signal_emitted, ms=3000):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    signal_emitted.connect(loop.quit)
    loop.exec()


def test_notifier_emits_when_update_found(app, monkeypatch):
    monkeypatch.setattr(
        updates, "check_for_updates", lambda *a, **k: updates.UpdateCheckResult(True, "9.9.9")
    )
    n = UpdateNotifier()
    got = []
    n.update_found.connect(got.append)
    n.start()
    _wait(n.update_found)
    QCoreApplication.processEvents()
    assert got == ["9.9.9"]


def test_notifier_is_silent_without_update(app, monkeypatch):
    monkeypatch.setattr(
        updates, "check_for_updates", lambda *a, **k: updates.UpdateCheckResult(False)
    )
    n = UpdateNotifier()
    got = []
    n.update_found.connect(got.append)
    n.start()
    _wait(n.update_found, ms=300)
    assert got == []


def test_notifier_survives_exceptions(app, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(updates, "check_for_updates", boom)
    n = UpdateNotifier()
    n.start()
    _wait(n.update_found, ms=300)  # no debe lanzar ni colgar


def test_main_window_shows_notice_when_update_found(app, monkeypatch):
    from blip_eraser.renderer import MainWindow

    monkeypatch.setattr(
        updates, "check_for_updates", lambda *a, **k: updates.UpdateCheckResult(True, "9.9.9")
    )
    window = MainWindow()
    try:
        window.start_update_check()
        loop = QEventLoop()
        QTimer.singleShot(3000, loop.quit)
        window._update_notifier.update_found.connect(loop.quit)
        loop.exec()
        QCoreApplication.processEvents()
        assert "9.9.9" in window.statusBar().findChild(QLabel, "UpdateNotice").text()
    finally:
        window.close()


def test_main_window_construction_never_starts_a_network_check(app, monkeypatch):
    from blip_eraser.renderer import MainWindow

    def forbidden(*a, **k):
        raise AssertionError("no debe consultar la red al construir la ventana")

    monkeypatch.setattr(updates, "check_for_updates", forbidden)
    window = MainWindow()
    window.close()
    assert not hasattr(window, "_update_notifier")
