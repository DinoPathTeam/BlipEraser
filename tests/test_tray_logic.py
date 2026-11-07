"""Lógica pura de la bandeja: avisos, autoarranque y comandos."""

from __future__ import annotations

import sys

import pytest

from blip_eraser.tray import logic
from blip_eraser.tray.logic import (
    JUNK_NOTIFY_BYTES,
    JUNK_NOTIFY_INTERVAL,
    KIND_JUNK,
    KIND_UPDATE,
    decide_notices,
    recoverable_bytes,
    status_values,
)

NOW = 1_000_000.0
BIG = JUNK_NOTIFY_BYTES + 1


def test_recoverable_sums_three_categories_and_ignores_orphans():
    cleanup = {"junk_bytes": 1, "pacman_cache_bytes": 2, "logs_bytes": 3, "orphan_count": 99}
    assert recoverable_bytes(cleanup) == 6
    assert recoverable_bytes({}) == 0


def test_status_values_uses_na_for_missing():
    assert status_values(10, None, 55, "N/D") == ("10%", "N/D", "55%")


class TestDecideNotices:
    def test_nothing_to_report(self):
        assert decide_notices({}, update_version=None, recoverable=0, now=NOW) == ([], {})

    def test_new_version_notifies_once_per_version(self):
        notices, upd = decide_notices({}, update_version="1.2.0", recoverable=0, now=NOW)
        assert [(n.kind, n.value) for n in notices] == [(KIND_UPDATE, "1.2.0")]
        assert upd == {"tray_notified_version": "1.2.0"}
        again, _ = decide_notices(
            {"tray_notified_version": "1.2.0"}, update_version="1.2.0", recoverable=0, now=NOW
        )
        assert again == []
        newer, _ = decide_notices(
            {"tray_notified_version": "1.2.0"}, update_version="1.3.0", recoverable=0, now=NOW
        )
        assert [n.value for n in newer] == ["1.3.0"]

    def test_junk_below_threshold_is_silent(self):
        assert decide_notices({}, update_version=None, recoverable=BIG - 2, now=NOW)[0] == []

    def test_junk_notifies_then_waits_24h(self):
        notices, upd = decide_notices({}, update_version=None, recoverable=BIG, now=NOW)
        assert [n.kind for n in notices] == [KIND_JUNK]
        assert upd == {"tray_junk_notified_at": NOW}
        prefs = {"tray_junk_notified_at": NOW}
        soon = NOW + JUNK_NOTIFY_INTERVAL - 1
        assert decide_notices(prefs, update_version=None, recoverable=BIG, now=soon)[0] == []
        later = NOW + JUNK_NOTIFY_INTERVAL
        assert [n.kind for n in decide_notices(prefs, update_version=None, recoverable=BIG, now=later)[0]] == [KIND_JUNK]

    @pytest.mark.parametrize("bad", ["x", None, True, NOW + 500])
    def test_corrupt_or_future_timestamp_does_not_silence_forever(self, bad):
        prefs = {"tray_junk_notified_at": bad}
        notices, _ = decide_notices(prefs, update_version=None, recoverable=BIG, now=NOW)
        assert [n.kind for n in notices] == [KIND_JUNK]

    def test_disabled_notifications(self):
        prefs = {"tray_notifications": False}
        assert decide_notices(prefs, update_version="9.9.9", recoverable=BIG, now=NOW) == ([], {})

    def test_update_comes_first_when_both(self):
        notices, upd = decide_notices({}, update_version="2.0.0", recoverable=BIG, now=NOW)
        assert [n.kind for n in notices] == [KIND_UPDATE, KIND_JUNK]
        assert set(upd) == {"tray_notified_version", "tray_junk_notified_at"}


class TestAutostart:
    @pytest.fixture(autouse=True)
    def _xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def test_enable_writes_desktop_entry_with_tray_command(self, tmp_path):
        assert not logic.autostart_enabled()
        assert logic.set_autostart(True, ["/opt/my python/bin/python", "-m", "blip_eraser.tray"])
        path = tmp_path / "autostart" / "blip-eraser-tray.desktop"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("[Desktop Entry]\n")
        assert 'Exec="/opt/my python/bin/python" -m blip_eraser.tray\n' in text
        assert logic.autostart_enabled()

    def test_disable_removes_and_is_idempotent(self):
        logic.set_autostart(True)
        assert logic.set_autostart(False)
        assert not logic.autostart_enabled()
        assert logic.set_autostart(False)

    def test_unwritable_location_reports_failure(self, tmp_path, monkeypatch):
        blocker = tmp_path / "file"
        blocker.write_text("x")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(blocker))
        assert logic.set_autostart(True) is False


def test_commands_use_current_interpreter():
    assert logic.app_command() == [sys.executable, "-m", "blip_eraser"]
    assert logic.tray_command() == [sys.executable, "-m", "blip_eraser.tray"]


class TestPopupPosition:
    SCREEN = (0, 0, 1920, 1080)
    SIZE = (300, 260)

    def test_opens_upwards_when_icon_is_in_bottom_half(self):
        x, y = logic.popup_position((1800, 1060), self.SIZE, self.SCREEN)
        assert y == 1060 - 260 - logic.POPUP_MARGIN
        assert x == 1920 - 300 - logic.POPUP_MARGIN  # recortado al borde derecho

    def test_opens_downwards_when_icon_is_in_top_half(self):
        _, y = logic.popup_position((900, 20), self.SIZE, self.SCREEN)
        assert y == 20 + logic.POPUP_MARGIN

    def test_always_stays_inside_the_screen(self):
        for anchor in ((0, 0), (1919, 1079), (-50, 500), (5000, 5000)):
            x, y = logic.popup_position(anchor, self.SIZE, self.SCREEN)
            assert 0 <= x <= 1920 - 300 and 0 <= y <= 1080 - 260

    def test_respects_screen_offset(self):
        x, y = logic.popup_position((2000, 100), self.SIZE, (1920, 0, 1920, 1080))
        assert x >= 1920 and y >= 0
