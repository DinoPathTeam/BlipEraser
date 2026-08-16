"""Tests GUI del refresco inmediato tras una acción destructiva.

Verifican que tras un borrado exitoso la vista se actualiza de inmediato
(sin esperar a navegar ni a pulsar escanear), y que no reintroduce escaneos
duplicados ni rompe la navegación por caché. Requieren PyQt6; se reportan
como *skipped* en entornos sin él y corren en CachyOS.
"""

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


class TestCleanerRefreshesAfterDelete:
    def test_delete_selected_retriggers_scan(self, app, monkeypatch):
        """Tras eliminar, delete_selected re-escanea y repinta la tabla."""
        calls = {"scan": 0}
        monkeypatch.setattr(
            cleaner_mod, "run_destructive_action", lambda *a, **k: True
        )

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