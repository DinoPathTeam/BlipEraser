"""La lista de apps de la Vista general se renderiza por lotes.

Antes se creaba un widget-fila (≈8 widgets, con estilo QSS y layout con
word-wrap) por CADA app instalada, de golpe y en el hilo de la interfaz:
con ~3000 apps la ventana se quedaba congelada varios segundos tras cada
escaneo (el coste crece más que linealmente). Ahora solo existen las filas
visibles más un margen; el resto se crea al acercarse al final del scroll.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import blip_eraser.pages.overview_page as overview_mod  # noqa: E402
import blip_eraser.utils.log as log_mod  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def page(app, tmp_path, monkeypatch):
    import blip_eraser.utils.config as config_mod

    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")
    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", tmp_path / "diag.log")
    monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
    p = overview_mod.OverviewPage()
    p.refresh = lambda: None
    p.resize(1000, 700)
    p.show()
    app.processEvents()
    yield p
    p.close()


def _apps(n: int):
    return [
        SimpleNamespace(
            name=f"pkg-{i}", detail="/usr/bin/x", size_bytes=4096,
            kind="app", source="pacman", install_date="2024-01-01",
        )
        for i in range(n)
    ]


def _rows(page) -> int:
    return page._apps_layout.count()


def _settle(app, page) -> None:
    """Deja que Qt calcule el layout (el rango del scroll llega en eventos aparte)."""
    for _ in range(10):
        app.processEvents()
        if page._apps_scroll.verticalScrollBar().maximum() > 0:
            break


def test_only_first_batch_is_rendered(page):
    page._apps = _apps(1000)
    page._rebuild_apps()
    assert _rows(page) == overview_mod.APPS_BATCH
    # El contador muestra el TOTAL real, no las filas creadas.
    assert "1000" in page.apps_count.text()


def test_small_lists_render_completely(page):
    page._apps = _apps(7)
    page._rebuild_apps()
    assert _rows(page) == 7


def test_scrolling_near_the_end_loads_next_batch(page, app):
    page._apps = _apps(1000)
    page._rebuild_apps()
    _settle(app, page)
    bar = page._apps_scroll.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum())  # llega al final
    assert _rows(page) == 2 * overview_mod.APPS_BATCH


def test_everything_can_eventually_be_reached(page, app):
    page._apps = _apps(250)
    page._rebuild_apps()
    for _ in range(10):
        _settle(app, page)
        bar = page._apps_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
    assert _rows(page) == 250


def test_new_scan_resets_to_first_batch(page, app):
    page._apps = _apps(1000)
    page._rebuild_apps()
    _settle(app, page)
    bar = page._apps_scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    assert _rows(page) > overview_mod.APPS_BATCH
    page._reset_apps_window()
    page._rebuild_apps()
    assert _rows(page) == overview_mod.APPS_BATCH


def test_retranslate_keeps_what_was_already_loaded(page, app):
    page._apps = _apps(1000)
    page._rebuild_apps()
    _settle(app, page)
    bar = page._apps_scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    loaded = _rows(page)
    assert loaded > overview_mod.APPS_BATCH
    page.retranslate()
    assert _rows(page) == loaded


def test_rebuild_does_not_write_one_diagnostic_per_row(page, tmp_path):
    page._apps = _apps(500)
    page._rebuild_apps()
    diag = tmp_path / "diag.log"
    lines = diag.read_text(encoding="utf-8").splitlines() if diag.exists() else []
    # Antes: ~2 líneas por app (miles de escrituras a disco en el hilo de la UI).
    assert len(lines) < 20
    assert any("PERF overview_rebuild" in ln for ln in lines)


def test_empty_state_still_works(page):
    page._apps = []
    page._rebuild_apps()
    assert _rows(page) == 1  # etiqueta "sin apps"
