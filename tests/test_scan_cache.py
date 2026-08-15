"""Tests para utils/scan_cache.py (lógica pura, sin PyQt6)."""

import time

import pytest

from blip_eraser.utils import scan_cache


@pytest.fixture(autouse=True)
def _clean_cache():
    scan_cache.clear()
    yield
    scan_cache.clear()


class TestScanCache:
    def test_unknown_section_is_stale(self):
        assert scan_cache.is_stale("no-existe") is True

    def test_mark_scanned_makes_fresh(self):
        scan_cache.mark_scanned("uninstaller")
        assert scan_cache.is_stale("uninstaller") is False

    def test_invalidate_forces_stale(self):
        scan_cache.mark_scanned("uninstaller")
        scan_cache.invalidate("uninstaller")
        assert scan_cache.is_stale("uninstaller") is True

    def test_sections_are_independent(self):
        scan_cache.mark_scanned("uninstaller")
        assert scan_cache.is_stale("cleaner_recommended") is True
        assert scan_cache.is_stale("uninstaller") is False

    def test_timeout_makes_stale(self, monkeypatch):
        fake_time = [1000.0]
        monkeypatch.setattr(scan_cache, "_clock", lambda: fake_time[0])
        scan_cache.mark_scanned("cleaner_manual")
        assert scan_cache.is_stale("cleaner_manual") is False
        fake_time[0] += 299
        assert scan_cache.is_stale("cleaner_manual") is False
        fake_time[0] += 1  # 300s: justo en el umbral
        assert scan_cache.is_stale("cleaner_manual") is True

    def test_custom_max_age(self, monkeypatch):
        fake_time = [500.0]
        monkeypatch.setattr(scan_cache, "_clock", lambda: fake_time[0])
        scan_cache.mark_scanned("uninstaller")
        assert scan_cache.is_stale("uninstaller", max_age_seconds=1) is False
        fake_time[0] += 1.0
        assert scan_cache.is_stale("uninstaller", max_age_seconds=1) is True

    def test_clear_resets_all(self):
        scan_cache.mark_scanned("uninstaller")
        scan_cache.clear()
        assert scan_cache.is_stale("uninstaller") is True

    def test_section_constants_exist(self):
        assert scan_cache.SECTION_UNINSTALLER == "uninstaller"
        assert scan_cache.SECTION_CLEANER_RECOMMENDED == "cleaner_recommended"
        assert scan_cache.SECTION_CLEANER_MANUAL == "cleaner_manual"
        assert scan_cache.DEFAULT_MAX_AGE_SECONDS == 300