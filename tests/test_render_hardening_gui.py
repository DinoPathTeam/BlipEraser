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