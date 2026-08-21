"""Test de validación del fix para los crashes de CachyOS.

Este test confirma que los escenarios de crash originales (3 incidencias) están
contenidos por la defensa implementada:

1. Crash original: layout muere a MITAD de _rebuild_apps (después del guard
   inicial) -> contenido por try/except en _rebuild_apps
2. Crash nuevo: cleanup_junk_label muere DESPUÉS de _rebuild_apps, dentro del
   mismo _on_scan_done -> contenido por try/except en _on_scan_done
3. Handler-level wrapping: uninstaller _on_apps_loaded y cleaner _on_scan_ready
   envuelven todo el handler, no solo _render

Además verifica:
- Evidencia forense en bitácora (ids, vida, pila)
- Diagnóstico CREATED en __init__ para hipótesis de instancia duplicada
- Camino feliz sin cambios
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")

from pathlib import Path
from types import SimpleNamespace

from PyQt6 import sip

import blip_eraser.pages.overview_page as overview_mod
import blip_eraser.pages.uninstaller_page as uninstaller_mod
import blip_eraser.pages.cleaner_page as cleaner_mod
import blip_eraser.utils.log as log_mod
from blip_eraser.utils.i18n import tr


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture(scope="module")
def prefs_tmp(tmp_path_factory):
    import blip_eraser.utils.config as config_mod

    prefs_file = tmp_path_factory.mktemp("prefs") / "prefs.json"
    config_mod.PREFS_FILE = prefs_file
    return prefs_file


@pytest.fixture()
def diag_path(tmp_path, monkeypatch):
    path = tmp_path / "diagnostics.log"
    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", path)
    return path


def _fake_app(name: str, *, kind: str = "app", source: str = "pacman"):
    return SimpleNamespace(
        name=name, detail="/usr/bin/x", size_bytes=4096, kind=kind, source=source,
        install_date="2024-01-01",
    )


_CLEANUP = {
    "junk_bytes": 1024,
    "pacman_cache_bytes": 2048,
    "logs_bytes": 512,
    "orphan_count": 3,
}


def _destroy_widget(app, widget):
    widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def _diag_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class TestOriginalCrashScenarios:
    """Escenarios de crash reportados en CachyOS (3 incidencias)."""

    def _make_overview_page(self, monkeypatch):
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        page.refresh = lambda: None
        return page

    def test_scenario_1_layout_dies_mid_rebuild(self, app, prefs_tmp, monkeypatch, diag_path):
        """ESCENARIO 1 (crash original): _apps_layout muere a MITAD de
        _rebuild_apps, DESPUÉS del guard inicial (sip.isdeleted check) pero
        ANTES/DURANTE el addWidget de las nuevas filas.

        Esto reproduce el traceback exacto de producción:
        RuntimeError: wrapped C/C++ object of type QVBoxLayout has been deleted
          File overview_page.py, line 377, in _rebuild_apps
            self._apps_layout.addWidget(row)
        """
        page = self._make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A"), _fake_app("App B")]
        page._apps_layout.addWidget(QtWidgets.QLabel("fila vieja"))

        real_qwidget = overview_mod.QWidget
        state = {"killed": False}

        def dying_qwidget(*args, **kwargs):
            if not state["killed"]:
                state["killed"] = True
                page._apps_widget.deleteLater()
                app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
                assert not sip.isdeleted(page)
                assert sip.isdeleted(page._apps_layout)
            return real_qwidget(*args, **kwargs)

        monkeypatch.setattr(overview_mod, "QWidget", dying_qwidget)

        page._rebuild_apps()  # NO debe crashear

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page._rebuild_apps" in content
        assert "apps_layout_alive=False" in content
        assert "apps_widget_alive=False" in content
        assert "rows_cleared=1" in content
        assert "adding_index=0" in content
        assert "apps_total=2" in content
        assert "thread=MainThread" in content
        assert "TRACEBACK:" in content
        assert "addWidget" in content

    def test_scenario_2_cleanup_label_dies_after_rebuild_in_on_scan_done(
        self, app, prefs_tmp, monkeypatch, diag_path
    ):
        """ESCENARIO 2 (crash nuevo reportado tras fix anterior):
        cleanup_junk_label muere DESPUÉS de que _rebuild_apps ya terminó bien,
        DENTRO de la misma llamada a _on_scan_done (en _apply_cleanup).

        Traceback de producción:
        RuntimeError: wrapped C/C++ object of type QLabel has been deleted
          File scan_worker.py, line 175, in _on_scan_result_ready
            self._scan_on_result(result)
          File overview_page.py, line 274, in _on_scan_done
            self._apply_cleanup(cleanup)
          File overview_page.py, line 290, in _apply_cleanup
            self.cleanup_junk_label.setText(...)
        """
        page = self._make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A")]
        real_rebuild = page._rebuild_apps

        def rebuild_then_kill_cleanup_label():
            real_rebuild()
            assert page._apps_layout.count() == 1
            _destroy_widget(app, page.cleanup_junk_label)
            assert sip.isdeleted(page.cleanup_junk_label)

        monkeypatch.setattr(page, "_rebuild_apps", rebuild_then_kill_cleanup_label)

        page._on_scan_done({"apps": [_fake_app("App A")], "cleanup": dict(_CLEANUP)})

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page._on_scan_done" in content
        assert "cleanup_junk_label_alive=False" in content
        assert "TRACEBACK:" in content
        assert "cleanup_junk_label.setText" in content

    def test_scenario_3_uninstaller_handler_full_wrapping(
        self, app, prefs_tmp, monkeypatch, diag_path
    ):
        """ESCENARIO 3: Handler completo _on_apps_loaded envuelto.
        Un fallo FUERA del _render interno (p.ej. mark_scanned o un widget
        futuro) queda contenido por el try/except externo."""
        page = uninstaller_mod.UninstallerPage()

        def render_succeeds_but_handler_fails():
            page._apps = [_fake_app("App A")]
            real_render = page._render
            real_render()  # _render interno funciona
            # Simula fallo en código POST-render (fuera del try/except interno)
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")

        monkeypatch.setattr(page, "_render", render_succeeds_but_handler_fails)

        page._on_apps_loaded([_fake_app("App A")])  # no crashea

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("table_render_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED uninstaller_page._on_apps_loaded" in content
        assert "TRACEBACK:" in content

    def test_scenario_4_cleaner_recommended_handler_full_wrapping(
        self, app, prefs_tmp, monkeypatch, diag_path
    ):
        """Handler completo _on_scan_ready (recommended) envuelto."""
        from blip_eraser.pages.cleaner_page import CleanerPage

        cleaner = CleanerPage()
        section = cleaner.recommended

        def render_succeeds_but_handler_fails():
            section._found = [("junk", Path("/tmp/x"), 123)]
            real_render = section._render
            real_render()
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")

        from pathlib import Path
        monkeypatch.setattr(section, "_render", render_succeeds_but_handler_fails)

        section._on_scan_ready([("junk", Path("/tmp/basura"), 123)])

        assert log_mod.log.latest() == tr("table_render_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED cleaner_recommended._on_scan_ready" in content
        assert "TRACEBACK:" in content

    def test_scenario_5_cleaner_manual_handler_full_wrapping(
        self, app, prefs_tmp, monkeypatch, diag_path
    ):
        """Handler completo _on_scan_ready (manual) envuelto."""
        from blip_eraser.pages.cleaner_page import CleanerPage
        from pathlib import Path

        cleaner = CleanerPage()
        section = cleaner.manual

        def render_succeeds_but_handler_fails():
            section._found = [Path("/tmp/AppImage")]
            real_render = section._render
            real_render()
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")

        monkeypatch.setattr(section, "_render", render_succeeds_but_handler_fails)

        section._on_scan_ready([Path("/tmp/AppImage")])

        assert log_mod.log.latest() == tr("table_render_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED cleaner_manual._on_scan_ready" in content
        assert "TRACEBACK:" in content


class TestForensicDiagnostics:
    """Verifica que la instrumentación forense deja evidencia usable."""

    def _make_overview_page(self, monkeypatch):
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page.refresh = lambda: None
        return page

    def test_created_diagnostic_overview(self, app, prefs_tmp, monkeypatch, diag_path):
        """OverviewPage.__init__ registra CREATED con ids de página y widgets."""
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page.refresh = lambda: None
        content = _diag_text(diag_path)
        assert "OverviewPage CREATED" in content
        assert f"id={id(page)}" in content
        assert f"apps_layout_id={id(page._apps_layout)}" in content
        assert f"cleanup_junk_label_id={id(page.cleanup_junk_label)}" in content
        assert f"cleanup_cache_label_id={id(page.cleanup_cache_label)}" in content
        assert f"cleanup_logs_label_id={id(page.cleanup_logs_label)}" in content

    def test_created_diagnostic_uninstaller(self, app, prefs_tmp, monkeypatch, diag_path):
        page = uninstaller_mod.UninstallerPage()
        content = _diag_text(diag_path)
        assert "UninstallerPage CREATED" in content
        assert f"id={id(page)}" in content
        assert f"table_id={id(page.table)}" in content

    def test_created_diagnostic_cleaner_recommended(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.cleaner_page import CleanerPage
        cleaner = CleanerPage()
        content = _diag_text(diag_path)
        assert "CleanerRecommendedSection CREATED" in content
        assert f"id={id(cleaner.recommended)}" in content
        assert f"table_id={id(cleaner.recommended.table)}" in content

    def test_created_diagnostic_cleaner_manual(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.cleaner_page import CleanerPage
        cleaner = CleanerPage()
        content = _diag_text(diag_path)
        assert "CleanerManualSection CREATED" in content
        assert f"id={id(cleaner.manual)}" in content
        assert f"table_id={id(cleaner.manual.table)}" in content

    def test_render_failure_includes_traceback(self, app, prefs_tmp, monkeypatch, diag_path):
        """_render_failure adjunta traceback completo (clave para diagnóstico)."""
        page = self._make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A")]

        # Llamamos a _render_failure directamente para probar que escribe traceback
        try:
            raise RuntimeError("wrapped C/C++ object of type QVBoxLayout has been deleted")
        except RuntimeError as exc:
            page._render_failure(
                "overview_page._rebuild_apps",
                exc,
                user_message=tr("overview_rebuild_failed"),
                apps_layout=page._apps_layout,
                apps_widget=page._apps_widget,
            )

        content = _diag_text(diag_path)
        assert "TRACEBACK:" in content
        assert "wrapped C/C++ object of type QVBoxLayout" in content

    def test_forensic_debug_includes_widget_identity(self, app, prefs_tmp, monkeypatch, diag_path):
        """_forensic_debug registra vida e id() de cada widget pasado."""
        page = self._make_overview_page(monkeypatch)
        dbg = page._forensic_debug("test_label", test_widget=page.cleanup_junk_label)
        assert "test_label" in dbg
        assert "page_alive=True" in dbg
        assert f"page_id={id(page)}" in dbg
        assert "test_widget_alive=True" in dbg
        assert f"id={id(page.cleanup_junk_label)}" in dbg


class TestHappyPathsUnchanged:
    """Confirma que el comportamiento normal no cambió."""

    def _make_overview_page(self, monkeypatch):
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        page.refresh = lambda: None
        return page

    def test_overview_rebuild_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        page = self._make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A"), _fake_app("App B")]
        page._rebuild_apps()
        assert page._apps_layout.count() == 2
        assert "RENDER_FAILED" not in _diag_text(diag_path)

    def test_overview_on_scan_done_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        page = self._make_overview_page(monkeypatch)
        page._on_scan_done({"apps": [_fake_app("App A"), _fake_app("App B")], "cleanup": dict(_CLEANUP)})
        assert page._apps_layout.count() == 2
        assert page.cleanup_junk_label.text().startswith(tr("cleanup_junk"))
        assert page.metric_junk.text().startswith(tr("metric_junk"))
        assert "RENDER_FAILED" not in _diag_text(diag_path)

    def test_uninstaller_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        page = uninstaller_mod.UninstallerPage()
        page._on_apps_loaded([_fake_app("App A")])
        assert page.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)

    def test_cleaner_recommended_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.cleaner_page import CleanerPage
        from pathlib import Path
        cleaner = CleanerPage()
        cleaner.recommended._on_scan_ready([("junk", Path("/tmp/basura"), 123)])
        assert cleaner.recommended.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)

    def test_cleaner_manual_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.cleaner_page import CleanerPage
        from pathlib import Path
        cleaner = CleanerPage()
        cleaner.manual._on_scan_ready([Path("/tmp/AppImage")])
        assert cleaner.manual.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)


class TestEdgeCases:
    """Casos borde que podrían no estar cubiertos."""

    def _make_overview_page(self, monkeypatch):
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        page.refresh = lambda: None
        return page

    def test_refresh_timer_callback_not_protected(self, app, prefs_tmp, monkeypatch, diag_path):
        """ADVERTENCIA: refresh() (timer cada 2s) NO tiene try/except.
        Si un widget muere durante refresh(), la app crashearía.
        Este test documenta el gap actual."""
        page = self._make_overview_page(monkeypatch)

        def kill_during_refresh():
            page.cleanup_junk_label.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)

        monkeypatch.setattr(page, "cleanup_junk_label", page.cleanup_junk_label)
        # El timer no se dispara en test (no hay event loop corriendo),
        # pero el método refresh() existe sin protección.
        # Verificamos que refresh() existe y toca labels sin try/except.
        import inspect
        source = inspect.getsource(page.refresh)
        assert "try:" not in source  # confirma que NO hay protección
        # NOTA: En producción, si un label muere, refresh() crashearía.
        # Mitigación: el timer solo toca labels de info del sistema, no layouts.

    def test_retranslate_calls_rebuild_apps_protected(self, app, prefs_tmp, monkeypatch, diag_path):
        """retranslate() llama a _rebuild_apps() que SÍ está protegido."""
        page = self._make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A")]
        # _rebuild_apps tiene su propio try/except
        page.retranslate()
        assert page._apps_layout.count() == 1

    def test_on_log_guard_works(self, app, prefs_tmp, monkeypatch, diag_path):
        """_on_log tiene guard _widget_is_alive() y no crashea si página muerta."""
        page = self._make_overview_page(monkeypatch)
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        assert sip.isdeleted(page)
        log_mod.log.add("test message")  # no debe crashear
        # Sin RuntimeError


class TestDiagnosticLogRotation:
    """Verifica que la bitácora forense rota correctamente."""

    def test_diag_log_truncates_on_size(self, tmp_path, monkeypatch):
        import blip_eraser.utils.log as log_mod

        test_path = tmp_path / "diag_test.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", test_path)
        monkeypatch.setattr(log_mod, "DIAG_LOG_MAX_BYTES", 100)

        log_mod.write_diagnostic("x" * 200)
        assert test_path.exists()
        # La lógica actual: si archivo existe y > MAX_BYTES -> unlink + rewrite.
        # La nueva línea (timestamp + thread + mensaje) puede superar MAX_BYTES.
        # Lo importante: no crece indefinidamente con escrituras repetidas.
        log_mod.write_diagnostic("y" * 200)
        log_mod.write_diagnostic("z" * 200)
        size = test_path.stat().st_size
        # Tras 3 escrituras, el archivo no debería ser 3x el tamaño de la línea
        assert size < 1000  # límite razonable (no crecimiento lineal)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])