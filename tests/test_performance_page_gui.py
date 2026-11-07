"""Tests de GUI para pages/performance_page.py (requieren PyQt6)."""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.pages import performance_page as pp
from blip_eraser.utils import performance as perf


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def env(monkeypatch):
    """Sistema simulado: sin bloqueos, todo apagado; prefs en memoria."""
    prefs: dict = {}
    states = {k: False for k in perf.TWEAKS}
    monkeypatch.setattr(pp, "load_prefs", lambda: dict(prefs, theme="red"))
    monkeypatch.setattr(pp, "save_prefs", lambda d: prefs.update(d))
    monkeypatch.setattr(pp, "get_all_tweak_states", lambda: dict(states))
    monkeypatch.setattr(pp, "get_tweak_block_reason", lambda k: None)
    return prefs, states


def _row(page, key):
    return next(r for r in page._rows if r["key"] == key)


class TestDriftBanner:
    def test_intent_kept_and_banner_shown_when_system_lost_setting(self, app, env):
        prefs, _ = env
        prefs["perf_zswap"] = True
        page = pp.PerformancePage()
        assert prefs["perf_zswap"] is True           # no se pisa la elección
        assert not page._drift_bar.isHidden()
        assert page._drifted == ["perf_zswap"]
        assert not _row(page, "perf_zswap")["checkbox"].isChecked()

    def test_no_banner_when_in_sync(self, app, env):
        page = pp.PerformancePage()
        assert page._drift_bar.isHidden()

    def test_active_in_system_is_adopted_into_prefs(self, app, env):
        prefs, states = env
        states["perf_trim_mounts"] = True
        pp.PerformancePage()
        assert prefs.get("perf_trim_mounts") is True


class TestBlockedRows:
    def test_blocked_row_disabled_with_tooltip_and_prefs_untouched(self, app, env, monkeypatch):
        prefs, _ = env
        prefs["perf_compress_ram"] = True
        monkeypatch.setattr(
            pp, "get_tweak_block_reason",
            lambda k: perf.TweakBlock("system_zram", "msg") if k == "perf_compress_ram" else None,
        )
        page = pp.PerformancePage()
        box = _row(page, "perf_compress_ram")["checkbox"]
        assert not box.isEnabled() and box.toolTip()
        assert prefs["perf_compress_ram"] is True
        assert page._drifted == []

    def test_enable_only_block_keeps_active_tweak_toggleable(self, app, env, monkeypatch):
        _, states = env
        states["perf_zswap"] = True
        monkeypatch.setattr(
            pp, "get_tweak_block_reason",
            lambda k: perf.TweakBlock("zram_swap", "m", enable_only=True) if k == "perf_zswap" else None,
        )
        page = pp.PerformancePage()
        box = _row(page, "perf_zswap")["checkbox"]
        assert box.isEnabled() and box.isChecked()
