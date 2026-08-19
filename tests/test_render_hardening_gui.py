"""Tests de la defensa dura + instrumentación forense de los renders.

Regresión del crash persistente de CachyOS (3 incidencias tras dos rondas de
fixes): `RuntimeError: wrapped C/C++ object of type QVBoxLayout has been
deleted` en `overview_page._rebuild_apps -> addWidget(row)`. El guard
anterior solo protegía el ENTRADA de la función; el layout puede morir a
MITAD de la reconstrucción (después de limpiar filas viejas, antes/durante
el addWidget de las nuevas).

Estos tests NO pretenden resolver la causa raíz: verifican que la app ya no
se cae (try/except RuntimeError que no relanza), que se deja evidencia
forense en la bitácora de diagnóstico (vida e identidad de los widgets,
filas en curso, hilo), y que el camino feliz no cambia.

Cubre los tres puntos con el patrón de riesgo: Overview (_rebuild_apps),
Desinstalador (_render) y Limpiador (ambas secciones _render).

Requieren PyQt6; se reportan como *skipped* en entornos sin él.
"""

from types import SimpleNamespace

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
    """Contenido de la bitácora forense; "" si aún no se creó."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class TestOverviewRebuildHardening:
    def _page(self, monkeypatch):
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        return page

    def test_layout_dies_mid_rebuild_is_contained(self, app, prefs_tmp, monkeypatch, diag_path):
        """El layout muere DESPUÉS del guard inicial, a mitad de la
        reconstrucción (entre la limpieza de filas viejas y el addWidget de la
        primera fila nueva) -> la app NO se cae, se registra el error y la
        evidencia forense queda en la bitácora."""
        page = self._page(monkeypatch)
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

        page._rebuild_apps()  # no debe crashear

        assert not sip.isdeleted(page)  # la página sigue viva
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED overview_page._rebuild_apps" in content
        assert "apps_layout_alive=False" in content
        assert "apps_widget_alive=False" in content
        assert "rows_cleared=1" in content
        assert "adding_index=0" in content
        assert "apps_total=2" in content
        assert "thread=MainThread" in content

    def test_layout_dead_at_entry_skips_with_diag(self, app, prefs_tmp, monkeypatch, diag_path):
        """Layout ya muerto al entrar: guard descarta y deja evidencia."""
        page = self._page(monkeypatch)
        _destroy_widget(app, page._apps_widget)
        assert not sip.isdeleted(page)
        assert sip.isdeleted(page._apps_layout)

        page._rebuild_apps()  # sin RuntimeError
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "skipped (layout ya muerto al entrar)" in content
        assert "apps_layout_alive=False" in content

    def test_happy_path_unchanged(self, app, prefs_tmp, monkeypatch, diag_path):
        """Camino feliz: 2 apps renderizadas, sin errores en el log de usuario
        ni RENDER_FAILED en la bitácora forense."""
        page = self._page(monkeypatch)
        page._apps = [_fake_app("App A"), _fake_app("App B")]

        page._rebuild_apps()

        assert page._apps_layout.count() == 2
        assert "RENDER_FAILED" not in _diag_text(diag_path)


class TestUninstallerRenderHardening:
    def test_table_dead_is_contained(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.uninstaller_page import UninstallerPage

        page = UninstallerPage()
        page._apps = [_fake_app("App A"), _fake_app("App B")]
        _destroy_widget(app, page.table)
        assert not sip.isdeleted(page)
        assert sip.isdeleted(page.table)

        page._render()  # no debe crashear

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("table_render_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED uninstaller_page._render" in content
        assert "table_alive=False" in content

    def test_happy_path_unchanged(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.uninstaller_page import UninstallerPage

        page = UninstallerPage()
        page._apps = [_fake_app("App A")]
        page._render()
        assert page.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)


class TestCleanerRenderHardening:

    def _cleaner(self):
        from blip_eraser.pages.cleaner_page import CleanerPage

        return CleanerPage()

    def test_recommended_table_dead_is_contained(self, app, prefs_tmp, monkeypatch, diag_path):
        cleaner = self._cleaner()
        section = cleaner.recommended
        section._found = [("junk", Path("/tmp/basura"), 123)]
        _destroy_widget(app, section.table)
        assert not sip.isdeleted(section)
        assert sip.isdeleted(section.table)

        section._render()  # no debe crashear

        assert log_mod.log.latest() == tr("table_render_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED cleaner_recommended._render" in content
        assert "table_alive=False" in content

    def test_manual_table_dead_is_contained(self, app, prefs_tmp, monkeypatch, diag_path):
        cleaner = self._cleaner()
        section = cleaner.manual
        section._found = [Path("/tmp/AppImage")]
        _destroy_widget(app, section.table)
        assert sip.isdeleted(section.table)

        section._render()  # no debe crashear

        assert log_mod.log.latest() == tr("table_render_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED cleaner_manual._render" in content

    def test_happy_path_unchanged(self, app, prefs_tmp, monkeypatch, diag_path):
        cleaner = self._cleaner()
        cleaner.recommended._found = [("junk", Path("/tmp/basura"), 123)]
        cleaner.recommended._render()
        assert cleaner.recommended.table.rowCount() == 1
        cleaner.manual._found = [Path("/tmp/AppImage")]
        cleaner.manual._render()
        assert cleaner.manual.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)


class TestOverviewScanDoneHardening:
    """El handler COMPLETO del resultado (_on_scan_done) queda contenido:
    un widget que muera en cualquier punto de la cadena (aquí, un label de la
    sección de limpieza DESPUÉS de que _rebuild_apps ya corrió bien) no tumba
    la app y deja evidencia con la pila exacta."""

    def _page(self, monkeypatch):
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        page.refresh = lambda: None  # no muestrear stats del sistema en tests
        return page

    def test_cleanup_label_dies_after_rebuild_within_scan_done(self, app, prefs_tmp, monkeypatch, diag_path):
        """El ESCENARIO NUEVO: cleanup_junk_label muere DESPUÉS de que
        _rebuild_apps se ejecutó sin problema, dentro de la misma llamada a
        _on_scan_done -> contenido por el try/except del método completo."""
        page = self._page(monkeypatch)
        page._apps = [_fake_app("App A")]
        real_rebuild = page._rebuild_apps

        def rebuild_then_kill_cleanup_label():
            real_rebuild()
            assert page._apps_layout.count() == 1  # rebuild ya funcionó
            _destroy_widget(app, page.cleanup_junk_label)
            assert sip.isdeleted(page.cleanup_junk_label)

        monkeypatch.setattr(page, "_rebuild_apps", rebuild_then_kill_cleanup_label)

        page._on_scan_done({"apps": [_fake_app("App A")], "cleanup": dict(_CLEANUP)})

        assert not sip.isdeleted(page)  # la app sigue viva
        assert log_mod.log.latest() == tr("overview_rebuild_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED overview_page._on_scan_done" in content
        assert "cleanup_junk_label_alive=False" in content
        assert "TRACEBACK:" in content
        assert "cleanup_junk_label.setText" in content  # la pila revela el widget

    def test_scan_done_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        """Camino feliz de _on_scan_done completo: widgets actualizados, sin
        errores ni evidencia forense de fallo."""
        page = self._page(monkeypatch)
        page._on_scan_done({"apps": [_fake_app("App A"), _fake_app("App B")], "cleanup": dict(_CLEANUP)})

        assert page._apps_layout.count() == 2
        assert page.cleanup_junk_label.text().startswith(tr("cleanup_junk"))
        assert page.metric_junk.text().startswith(tr("metric_junk"))
        assert "RENDER_FAILED" not in _diag_text(diag_path)

    def test_init_writes_created_diagnostic(self, app, prefs_tmp, monkeypatch, diag_path):
        """Tarea 2.4: __init__ registra la construcción (id de la página y de
        los widgets) en la bitácora forense, para comparar contra el id del
        próximo incidente (hipótesis de instancia duplicada)."""
        page = self._page(monkeypatch)
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "OverviewPage CREATED" in content
        assert f"id={id(page)}" in content
        assert f"apps_layout_id={id(page._apps_layout)}" in content
        assert f"cleanup_junk_label_id={id(page.cleanup_junk_label)}" in content


class TestUninstallerHandlerHardening:
    def test_on_apps_loaded_contains_render_failure(self, app, prefs_tmp, monkeypatch, diag_path):
        """El handler COMPLETO (_on_apps_loaded) contiene un fallo de render que
        sucede fuera del try/except interno de _render: si algún widget de la
        página muere en C++ en cualquier punto de la cadena del resultado, el
        except externo lo captura y deja la pila exacta."""
        from blip_eraser.pages.uninstaller_page import UninstallerPage

        page = UninstallerPage()

        def render_raises():
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")

        monkeypatch.setattr(page, "_render", render_raises)

        page._on_apps_loaded([_fake_app("App A")])  # no debe crashear

        assert not sip.isdeleted(page)
        assert log_mod.log.latest() == tr("table_render_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED uninstaller_page._on_apps_loaded" in content
        assert "TRACEBACK:" in content

    def test_on_apps_loaded_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        from blip_eraser.pages.uninstaller_page import UninstallerPage

        page = UninstallerPage()
        page._on_apps_loaded([_fake_app("App A")])
        assert page.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)


class TestCleanerHandlerHardening:
    def _cleaner(self):
        from blip_eraser.pages.cleaner_page import CleanerPage

        return CleanerPage()

    def test_on_scan_ready_recommended_contains_render_failure(self, app, prefs_tmp, monkeypatch, diag_path):
        cleaner = self._cleaner()
        section = cleaner.recommended

        def render_raises():
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")

        monkeypatch.setattr(section, "_render", render_raises)

        section._on_scan_ready([("junk", Path("/tmp/basura"), 123)])  # no crashea

        assert log_mod.log.latest() == tr("table_render_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED cleaner_recommended._on_scan_ready" in content
        assert "TRACEBACK:" in content

    def test_on_scan_ready_manual_contains_render_failure(self, app, prefs_tmp, monkeypatch, diag_path):
        cleaner = self._cleaner()
        section = cleaner.manual

        def render_raises():
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")

        monkeypatch.setattr(section, "_render", render_raises)

        section._on_scan_ready([Path("/tmp/AppImage")])  # no crashea

        assert log_mod.log.latest() == tr("table_render_failed")
        content = Path(diag_path).read_text(encoding="utf-8")
        assert "RENDER_FAILED cleaner_manual._on_scan_ready" in content
        assert "TRACEBACK:" in content

    def test_on_scan_ready_happy_path(self, app, prefs_tmp, monkeypatch, diag_path):
        cleaner = self._cleaner()
        cleaner.recommended._on_scan_ready([("junk", Path("/tmp/basura"), 123)])
        assert cleaner.recommended.table.rowCount() == 1
        cleaner.manual._on_scan_ready([Path("/tmp/AppImage")])
        assert cleaner.manual.table.rowCount() == 1
        assert "RENDER_FAILED" not in _diag_text(diag_path)