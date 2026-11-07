"""Los pesos de carpetas sueltas se calculan aparte: la lista sale de inmediato.

Medido en un equipo real (1668 paquetes, 163 carpetas sueltas): pacman tarda
<0,6 s en total pero dimensionar las carpetas (~/.local, Steam…) sumaba ~6 s
dentro del escaneo, con la lista vacía todo ese tiempo.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

import blip_eraser.utils.apps as apps_mod
from blip_eraser.utils.apps import (
    InstalledApp,
    clear_manual_size_cache,
    fill_manual_sizes,
    list_installed_apps,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_manual_size_cache()
    yield
    clear_manual_size_cache()


@pytest.fixture()
def folder(tmp_path):
    d = tmp_path / "Games" / "foo"
    d.mkdir(parents=True)
    (d / "a.bin").write_bytes(b"x" * 1234)
    return d


def _list(folder, **kw):
    with (
        patch.object(apps_mod, "pacman_installed_info", return_value={}),
        patch.object(apps_mod, "list_explicit_packages", return_value=[]),
        patch.object(apps_mod, "list_dependency_packages", return_value=[]),
        patch.object(apps_mod, "scan_manual_entries", return_value=[folder]),
    ):
        return list_installed_apps(**kw)


def test_deferred_listing_does_not_walk_folders(folder):
    with patch.object(apps_mod, "path_size_for_display", side_effect=AssertionError("recorrió")):
        result = _list(folder, manual_sizes=False)
    assert [a.name for a in result] == ["foo"]
    assert result[0].size_bytes == 0


def test_fill_computes_pending_sizes_in_place(folder):
    result = _list(folder, manual_sizes=False)
    fill_manual_sizes(result)
    assert result[0].size_bytes == 1234


def test_default_listing_still_sizes_folders(folder):
    assert _list(folder)[0].size_bytes == 1234


def test_size_is_cached_so_rescans_are_instant(folder):
    fill_manual_sizes(_list(folder, manual_sizes=False))
    with patch.object(apps_mod, "path_size_for_display", side_effect=AssertionError("sin caché")):
        again = _list(folder, manual_sizes=False)
        assert again[0].size_bytes == 1234  # sale de la caché sin recorrer
        fill_manual_sizes(again)


def test_fill_ignores_pacman_entries_and_known_sizes():
    pkgs = [
        InstalledApp(name="p", source="pacman", detail="1.0"),
        InstalledApp(name="m", source="manual", detail="/nonexistent/x", size_bytes=7),
    ]
    with patch.object(apps_mod, "path_size_for_display", side_effect=AssertionError("no debía")):
        fill_manual_sizes(pkgs)
    assert [a.size_bytes for a in pkgs] == [0, 7]


def test_fill_runs_folders_concurrently():
    items = [InstalledApp(name=f"m{i}", source="manual", detail=f"/x/{i}") for i in range(3)]

    def slow(path: Path) -> int:
        time.sleep(0.3)
        return 5

    with patch.object(apps_mod, "path_size_for_display", slow):
        start = time.perf_counter()
        fill_manual_sizes(items, workers=3)
        elapsed = time.perf_counter() - start
    assert [a.size_bytes for a in items] == [5, 5, 5]
    assert elapsed < 0.8  # en fila serían ~0,9 s


# --- Vista general: las etiquetas se actualizan al llegar los pesos ----------

pytest.importorskip("PyQt6.QtWidgets")
import blip_eraser.pages.overview_page as overview_mod  # noqa: E402
import blip_eraser.utils.log as log_mod  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def page(qapp, tmp_path, monkeypatch):
    import blip_eraser.utils.config as config_mod

    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")
    monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", tmp_path / "diag.log")
    monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
    p = overview_mod.OverviewPage()
    p.refresh = lambda: None
    yield p
    p.close()


def _pump(qapp, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_overview_labels_update_when_sizes_arrive(qapp, page, folder):
    page._apps = _list(folder, manual_sizes=False)
    page._reset_apps_window()
    page._rebuild_apps()
    assert page._sub_labels[0][1].text() == str(folder)  # aún sin peso

    page._start_size_fill(page._apps, page._on_sizes_filled)
    assert _pump(qapp, lambda: "|" in page._sub_labels[0][1].text())
    assert page._sub_labels[0][1].text().startswith(f"{folder}  |  ")


def test_stale_size_result_is_ignored(qapp, page, folder):
    old = _list(folder, manual_sizes=False)
    page._apps = _list(folder, manual_sizes=False)  # lista distinta: escaneo más nuevo
    page._rebuild_apps()
    page._start_size_fill(old, page._on_sizes_filled)
    _pump(qapp, lambda: False, timeout=0.5)
    assert "|" not in page._sub_labels[0][1].text()
