"""Tests GUI de fluidez: sin hilos duplicados, render por lotes, headers visibles.

Requieren PyQt6 (offscreen vale).
"""

import time

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

import blip_eraser.pages.cleaner_page as cleaner_mod
import blip_eraser.pages.uninstaller_page as uninstaller_mod
from blip_eraser.utils.apps import InstalledApp


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture(autouse=True)
def diag_redirect(tmp_path, monkeypatch):
    import blip_eraser.utils.log as log_mod

    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", tmp_path / "diagnostics.log")


def _pump_until(app, condition, timeout_ms=3000):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    app.processEvents()
    return condition()


def _fake_apps(n):
    return [
        InstalledApp(
            name=f"app-{i:04d}",
            source="pacman",
            detail=f"detail-{i}",
            size_bytes=1024 * i,
            kind="app",
            install_date="2024-01-01",
        )
        for i in range(n)
    ]


class TestNoDuplicateScans:
    """Volver a la pestaña con el escaneo en vuelo no apila otro hilo.

    El guard vive en showEvent (la ruta del rebote): los escaneos
    explícitos (botón Actualizar, tras borrar) siempre corren, y el
    token del mixin sigue descartando resultados obsoletos.
    """

    def test_uninstaller_show_skips_when_in_flight(self, app, monkeypatch):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QShowEvent

        page = uninstaller_mod.UninstallerPage()
        try:
            scheduled = []
            monkeypatch.setattr(
                QTimer, "singleShot", lambda ms, fn: scheduled.append(fn)
            )
            page._scanning = True
            page.showEvent(QShowEvent())
            app.processEvents()
            assert scheduled == []
        finally:
            page.close()

    def test_uninstaller_show_scans_when_idle_and_stale(self, app, monkeypatch):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QShowEvent
        from blip_eraser.utils import scan_cache

        page = uninstaller_mod.UninstallerPage()
        try:
            scheduled = []
            monkeypatch.setattr(
                QTimer, "singleShot", lambda ms, fn: scheduled.append(fn)
            )
            monkeypatch.setattr(scan_cache, "_STATE", {})
            page._scanning = False
            page.showEvent(QShowEvent())
            app.processEvents()
            assert len(scheduled) == 1
        finally:
            page.close()

    def test_cleaner_show_skips_when_in_flight(self, app, monkeypatch):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QShowEvent

        section = cleaner_mod._RecommendedSection()
        try:
            scheduled = []
            monkeypatch.setattr(
                QTimer, "singleShot", lambda ms, fn: scheduled.append(fn)
            )
            section._scanning = True
            section.showEvent(QShowEvent())
            app.processEvents()
            assert scheduled == []
        finally:
            section.close()


class TestBatchedRender:
    def test_uninstaller_refreshes_header_once(self, app, monkeypatch):
        page = uninstaller_mod.UninstallerPage()
        try:
            page._apps = _fake_apps(200)
            count = []
            orig = page.table.refresh_header_state
            monkeypatch.setattr(
                page.table, "refresh_header_state",
                lambda: (count.append(1), orig()),
            )
            page._render()
            assert page.table.rowCount() == 200
            assert len(count) == 1
        finally:
            page.close()


class TestHeadersVisible:
    def test_uninstaller_columns_share_width(self, app):
        from PyQt6.QtWidgets import QHeaderView

        page = uninstaller_mod.UninstallerPage()
        try:
            page.resize(900, 600)
            page.show()
            app.processEvents()
            header = page.table.horizontalHeader()
            assert header.minimumSectionSize() >= 60
            for col in range(1, 6):
                assert header.sectionResizeMode(col) == QHeaderView.ResizeMode.Stretch
                assert header.sectionSize(col) >= 60
        finally:
            page.close()

    def test_cleaner_columns_share_width(self, app):
        from PyQt6.QtWidgets import QHeaderView

        section = cleaner_mod._RecommendedSection()
        try:
            section.resize(900, 600)
            section.show()
            app.processEvents()
            header = section.table.horizontalHeader()
            for col in range(1, section._columns):
                assert header.sectionResizeMode(col) == QHeaderView.ResizeMode.Stretch
                assert header.sectionSize(col) >= 60
        finally:
            section.close()
