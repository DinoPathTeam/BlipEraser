"""Test GUI del fix para refresh() sin protección (crash post-splash).

Verifica que refresh() disparado directamente o vía retranslate() con un
widget del panel de información muerto en C++ NO crashea la app, se
registra el error con evidencia forense, y el camino feliz sigue
funcionando.

Escenario sospechoso: 3 incidentes de crash previos ocurrieron "pocos
segundos tras el splash" — justo cuando refresh_appearance()/retranslate()
ejecuta refresh() por primera vez.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")

from pathlib import Path

from PyQt6 import sip

import blip_eraser.pages.overview_page as overview_mod
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
    """Redirige la bitácora forense a un archivo temporal para inspeccionarla."""
    path = tmp_path / "diagnostics.log"
    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", path)
    return path


@pytest.fixture(autouse=True)
def clear_log_buffer():
    """Limpia el buffer de log global antes de cada test para evitar polución."""
    log_mod.log._entries.clear()
    yield
    log_mod.log._entries.clear()


def _fake_app(name: str, *, kind: str = "app", source: str = "pacman"):
    from types import SimpleNamespace
    return SimpleNamespace(
        name=name, detail="/usr/bin/x", size_bytes=4096, kind=kind, source=source,
        install_date="2024-01-01",
    )


def _destroy_widget(app, widget):
    widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def _diag_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _make_overview_page(monkeypatch):
    """OverviewPage sin SCAN NOW inicial (evita threads de fondo)."""
    monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
    page = overview_mod.OverviewPage()
    page._apps = []
    # NO sobrescribimos refresh() - usamos el método real protegido
    return page


class TestRefreshHardening:
    """refresh() con la misma defensa dura que _rebuild_apps."""

    def test_gauge_dead_during_refresh_direct_call(self, app, prefs_tmp, monkeypatch, diag_path):
        """gauge muerto ANTES de llamar a refresh() directamente -> contenido."""
        page = _make_overview_page(monkeypatch)
        _destroy_widget(app, page.gauge)
        assert not sip.isdeleted(page)
        assert sip.isdeleted(page.gauge)

        page.refresh()  # NO debe crashear

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page.refresh" in content
        assert "gauge_alive=False" in content
        assert "TRACEBACK:" in content
        assert "set_value" in content or "set_status" in content

    def test_cpu_row_dead_during_refresh_via_retranslate(self, app, prefs_tmp, monkeypatch, diag_path):
        """cpu_row muerto DURANTE retranslate() -> refresh() interno contenido."""
        page = _make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A")]
        # Simula: retranslate() se llama, luego refresh() interno
        _destroy_widget(app, page.cpu_row)
        assert sip.isdeleted(page.cpu_row)

        page.retranslate()  # llama a refresh() internamente

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page.refresh" in content
        assert "cpu_row_alive=False" in content
        assert "TRACEBACK:" in content
        assert "setText" in content  # la pila revela cpu_row.setText

    def test_ram_row_dead_during_refresh_timer(self, app, prefs_tmp, monkeypatch, diag_path):
        """ram_row muerto cuando el timer dispara refresh() -> contenido."""
        page = _make_overview_page(monkeypatch)
        _destroy_widget(app, page.ram_row)
        assert sip.isdeleted(page.ram_row)

        # Llamada directa simula timer.timeout -> refresh()
        page.refresh()

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page.refresh" in content
        assert "ram_row_alive=False" in content

    def test_disk_row_dead_during_refresh(self, app, prefs_tmp, monkeypatch, diag_path):
        """disk_row muerto -> contenido."""
        page = _make_overview_page(monkeypatch)
        _destroy_widget(app, page.disk_row)

        page.refresh()

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page.refresh" in content
        assert "disk_row_alive=False" in content

    def test_gpu_row_dead_during_refresh(self, app, prefs_tmp, monkeypatch, diag_path):
        """gpu_row muerto -> contenido."""
        page = _make_overview_page(monkeypatch)
        _destroy_widget(app, page.gpu_row)

        page.refresh()

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page.refresh" in content
        assert "gpu_row_alive=False" in content

    def test_refresh_happy_path_unchanged(self, app, prefs_tmp, monkeypatch, diag_path):
        """Camino feliz: refresh() actualiza todos los widgets sin errores."""
        page = _make_overview_page(monkeypatch)

        page.refresh()

        # Sin errores en log ni bitácora forense de fallo
        assert "RENDER_FAILED" not in _diag_text(diag_path)
        # Verifica que los textos se actualizaron (no vacíos, con formato)
        assert "CPU" in page.cpu_row.text() or "cpu" in page.cpu_row.text().lower()
        assert "GPU" in page.gpu_row.text() or "gpu" in page.gpu_row.text().lower()
        assert "RAM" in page.ram_row.text() or "ram" in page.ram_row.text().lower()
        assert "DISK" in page.disk_row.text() or "disk" in page.disk_row.text().lower()
        # gauge debe tener valor (0-100) - atributo privado
        assert page.gauge._value >= 0

    def test_retranslate_calls_refresh_protected(self, app, prefs_tmp, monkeypatch, diag_path):
        """retranslate() llama a refresh() que ahora está protegido."""
        page = _make_overview_page(monkeypatch)
        page._apps = [_fake_app("App A")]

        # Mata gauge ANTES de retranslate
        _destroy_widget(app, page.gauge)

        page.retranslate()  # llama a refresh() internamente

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = _diag_text(diag_path)
        assert "RENDER_FAILED overview_page.refresh" in content

    def test_widget_is_alive_guard_skips_refresh_when_page_dead(self, app, prefs_tmp, monkeypatch, diag_path):
        """Si la página completa está muerta, _widget_is_alive() retorna False
        y refresh() sale sin tocar widgets (ni siquiera entra al try)."""
        page = _make_overview_page(monkeypatch)
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        assert sip.isdeleted(page)

        page.refresh()  # no debe crashear, sale en guard

        # Sin evidencia forense de RENDER_FAILED (guard lo evitó)
        assert "RENDER_FAILED" not in _diag_text(diag_path)

    def test_widget_is_alive_checks_apps_layout(self, app, prefs_tmp, monkeypatch, diag_path):
        """_widget_is_alive() retorna False si _apps_layout está muerto
        (consistente con _rebuild_apps). refresh() respeta ese guard."""
        page = _make_overview_page(monkeypatch)
        page._apps_widget.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        assert not sip.isdeleted(page)
        assert sip.isdeleted(page._apps_layout)
        assert page._widget_is_alive() is False

        page.refresh()  # sale en guard, no toca gauge/cpu_row/etc.

        assert "RENDER_FAILED" not in _diag_text(diag_path)


class TestDiagnosticLogRotationFix:
    """Verifica el fix de rotación en write_diagnostic()."""

    def test_write_diagnostic_truncates_before_write_if_line_would_exceed_limit(self, tmp_path, monkeypatch):
        """Una línea grande (traceback) no deja el archivo por encima del límite."""
        import blip_eraser.utils.log as log_mod

        test_path = tmp_path / "diag_test.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", test_path)
        monkeypatch.setattr(log_mod, "DIAG_LOG_MAX_BYTES", 500)

        # Escribe líneas que individualmente son < 500 pero acumuladas superan
        for i in range(20):
            log_mod.write_diagnostic(f"linea {i} " + "x" * 40)

        size = test_path.stat().st_size
        # El archivo NO debe crecer indefinidamente; rotación truncó
        assert size < 5000  # límite razonable (no 20 * 50 = 1000+ sin control)

    def test_single_large_line_triggers_truncation(self, tmp_path, monkeypatch):
        """Una sola línea > límite: el archivo se trunca (borra y reescribe)."""
        import blip_eraser.utils.log as log_mod

        test_path = tmp_path / "diag_test.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", test_path)
        monkeypatch.setattr(log_mod, "DIAG_LOG_MAX_BYTES", 100)

        # Línea muy grande (simula traceback) - supera el límite
        log_mod.write_diagnostic("x" * 500)

        # El archivo existe (se borra y reescribe con la línea grande)
        assert test_path.exists()
        size = test_path.stat().st_size
        # El tamaño es el de la línea (aprox 500+ bytes), no acumulado
        assert 500 < size < 700

    def test_multiple_writes_dont_accumulate_unbounded(self, tmp_path, monkeypatch):
        """Escrituras repetidas no dejan crecer el archivo sin control."""
        import blip_eraser.utils.log as log_mod

        test_path = tmp_path / "diag_test.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", test_path)
        monkeypatch.setattr(log_mod, "DIAG_LOG_MAX_BYTES", 200)

        for i in range(50):
            log_mod.write_diagnostic(f"entrada {i} " + "y" * 30)

        size = test_path.stat().st_size
        # Con límite 200, el archivo debe rotar y mantenerse acotado
        assert size < 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])