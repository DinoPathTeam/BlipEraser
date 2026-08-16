"""Tests GUI del refresco inmediato tras una acción destructiva.

Verifican que tras un borrado exitoso la vista se actualiza de inmediato
(sin esperar a navegar ni a pulsar escanear), y que no reintroduce escaneos
duplicados ni rompe la navegación por caché. Los escaneos corren ahora en
segundo plano (BackgroundScanMixin), así que los tests bombean el event loop
hasta que el resultado llega al hilo principal. Requieren PyQt6; se reportan
como *skipped* en entornos sin él y corren en CachyOS.
"""

import time

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")

from pathlib import Path

import blip_eraser.pages.cleaner_page as cleaner_mod
import blip_eraser.pages.overview_page as overview_mod


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _pump_until(app, condition, timeout_ms=3000):
    """Bombea el event loop hasta que `condition()` sea verdadera (o timeout)."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    app.processEvents()
    return condition()


class TestCleanerRefreshesAfterDelete:
    def test_delete_selected_retriggers_scan(self, app, monkeypatch):
        """Tras eliminar, delete_selected re-escanea y repinta la tabla."""
        calls = {"scan": 0}
        monkeypatch.setattr(
            cleaner_mod, "run_destructive_action", lambda *a, **k: True
        )
        monkeypatch.setattr(cleaner_mod, "scan_cleanup_items", lambda: [])

        section = cleaner_mod._RecommendedSection()
        section._visible = [
            ("junk", Path("/tmp/x"), 1),
            ("cache", Path("/tmp/y"), 2),
        ]
        for _ in range(2):
            section.table.add_check_row()
        section.table.item(0, 0).setCheckState(QtCore.Qt.CheckState.Checked)
        section.table.item(1, 0).setCheckState(QtCore.Qt.CheckState.Checked)

        orig_scan = section.scan

        def spy_scan():
            calls["scan"] += 1
            return orig_scan()

        section.scan = spy_scan
        section.delete_selected()
        assert calls["scan"] == 1
        _pump_until(app, lambda: not section._scanning)

    def test_delete_selected_repaints_table_rows(self, app, monkeypatch):
        """Tras re-escaneo, la tabla refleja el nuevo resultado (menos filas)."""
        monkeypatch.setattr(cleaner_mod, "run_destructive_action", lambda *a, **k: True)
        monkeypatch.setattr(
            cleaner_mod,
            "scan_cleanup_items",
            lambda *a, **k: [("junk", Path("/tmp/queda"), 3)],
        )

        section = cleaner_mod._RecommendedSection()
        section._visible = [("junk", Path("/tmp/x"), 1)]
        section.table.add_check_row()
        section.table.item(0, 0).setCheckState(QtCore.Qt.CheckState.Checked)

        section.delete_selected()
        # El re-escaneo corre en segundo plano: espera a que llegue el resultado.
        assert _pump_until(app, lambda: section.table.rowCount() == 1)
        assert section.table.rowCount() == 1  # repintado con el resultado nuevo


class TestOverviewRefreshesAfterCleanup:
    def _page(self, monkeypatch):
        """OverviewPage sin SCAN NOW inicial (evita threads de fondo)."""
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        return page

    def test_cleanup_now_updates_metrics_and_summary(self, app, monkeypatch):
        """Tras 'Limpiar ahora' exitoso, resumen Y métricas se repintan."""
        monkeypatch.setattr(overview_mod, "run_destructive_action", lambda *a, **k: True)
        page = self._page(monkeypatch)

        cleanup = {
            "junk_bytes": 1024,
            "pacman_cache_bytes": 2048,
            "logs_bytes": 512,
            "orphan_count": 3,
        }
        page._on_cleanup_summary_ready(cleanup)

        assert page.cleanup_junk_label.text() == f"{overview_mod.tr('cleanup_junk')}: 1.0 KB"
        assert page.metric_junk.text() == f"{overview_mod.tr('metric_junk')}: 1.0 KB"
        assert page.metric_orphans.text() == f"{overview_mod.tr('metric_orphans')}: 3"

    def test_cleanup_now_only_scans_once(self, app, monkeypatch):
        """'Limpiar ahora' recalcula con UNA sola pasada de scan_cleanup()."""
        calls = {"scan_cleanup": 0}
        real_scan = overview_mod.scan_cleanup

        def spy(*a, **k):
            calls["scan_cleanup"] += 1
            return real_scan(*a, **k)

        monkeypatch.setattr(overview_mod, "scan_cleanup", spy)
        monkeypatch.setattr(overview_mod, "run_destructive_action", lambda *a, **k: True)
        page = self._page(monkeypatch)
        # Forzar el hilo de resumen a emitir directo (sin esperar el thread).
        page._refresh_cleanup_summary = lambda: page._on_cleanup_summary_ready(
            spy()
        )

        page._on_cleanup_items_ready([("junk", Path("/tmp/x"), 1)])
        # Una pasada de scan_cleanup alimenta resumen + métricas; sin loop.
        assert calls["scan_cleanup"] == 1


class TestBackgroundScans:
    """Los escaneos corren en segundo plano: el hilo principal no se bloquea."""

    def test_scan_does_not_block_main_thread(self, app, monkeypatch):
        """Un escaneo lento no congela la GUI: se puede seguir procesando."""
        import threading

        started = threading.Event()
        release = threading.Event()

        def slow_scan():
            started.set()
            release.wait(2)
            return []

        monkeypatch.setattr(cleaner_mod, "scan_cleanup_items", slow_scan)
        section = cleaner_mod._RecommendedSection()
        section.scan()

        # El worker arranca en su propio hilo.
        assert _pump_until(app, started.is_set)
        assert section._scanning is True
        assert section.refresh_btn.isEnabled() is False

        # Mientras escanea, el hilo principal sigue procesando eventos.
        got = []
        timer = QtCore.QTimer()
        timer.timeout.connect(lambda: got.append(True))
        timer.start(20)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and not got:
            app.processEvents()
            time.sleep(0.005)
        timer.stop()
        assert got, "el hilo principal se bloqueó durante el escaneo"

        release.set()
        assert _pump_until(app, lambda: not section._scanning)
        assert section.refresh_btn.isEnabled() is True

    def test_stale_result_ignored_when_newer_scan_starts(self, app, monkeypatch):
        """Si se lanza un segundo escaneo, el resultado del primero se descarta."""
        import threading

        started_a = threading.Event()
        release_a = threading.Event()
        a_entries = [("junk", Path("/tmp/a"), 1)]
        b_entries = [("cache", Path("/tmp/b"), 2)]

        def scan_a():
            started_a.set()
            release_a.wait(2)
            return a_entries

        def scan_b():
            return b_entries

        section = cleaner_mod._RecommendedSection()

        # Escaneo A (lento) y luego B antes de que A termine.
        monkeypatch.setattr(cleaner_mod, "scan_cleanup_items", scan_a)
        section.scan()
        assert _pump_until(app, started_a.is_set)

        monkeypatch.setattr(cleaner_mod, "scan_cleanup_items", scan_b)
        section.scan()

        release_a.set()
        # B es el escaneo más reciente: su resultado gana, A se descarta.
        assert _pump_until(app, lambda: not section._scanning)
        assert section._found == b_entries

    def test_uninstaller_load_apps_does_not_block(self, app, monkeypatch):
        """El Desinstalador también escanea en segundo plano (botones fuera)."""
        import blip_eraser.pages.uninstaller_page as uninstaller_mod
        import threading

        from blip_eraser.utils.apps import InstalledApp, KIND_APP

        started = threading.Event()
        release = threading.Event()

        def slow_list():
            started.set()
            release.wait(2)
            return [InstalledApp(name="foo", source="pacman", kind=KIND_APP)]

        monkeypatch.setattr(uninstaller_mod, "list_installed_apps", slow_list)
        page = uninstaller_mod.UninstallerPage()
        page.load_apps()

        assert _pump_until(app, started.is_set)
        assert page._scanning is True
        assert page.refresh_btn.isEnabled() is False
        assert page.uninstall_btn.isEnabled() is False

        release.set()
        assert _pump_until(app, lambda: not page._scanning)
        assert page.refresh_btn.isEnabled() is True
        assert page.table.rowCount() == 1
        assert page.table.item(0, 1).text() == "foo"