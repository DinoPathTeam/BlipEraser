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


class TestFixedPositions:
    SCREEN = (0, 0, 1920, 1080)
    SIZE = (300, 233)

    def test_nine_positions_are_distinct_and_inside(self):
        seen = set()
        for key in logic.FIXED_POSITIONS:
            x, y = logic.fixed_position(key, self.SIZE, self.SCREEN)
            assert 0 <= x <= 1920 - 300 and 0 <= y <= 1080 - 233
            seen.add((x, y))
        assert len(seen) == 9

    def test_corners_edges_and_center(self):
        fp = lambda k: logic.fixed_position(k, self.SIZE, self.SCREEN)  # noqa: E731
        assert fp("top-left") == (16, 16)
        assert fp("bottom-right") == (1920 - 300 - 16, 1080 - 233 - 16)
        assert fp("center") == ((1920 - 300) // 2, (1080 - 233) // 2)
        assert fp("top")[1] == 16 and fp("bottom")[1] == 1080 - 233 - 16
        assert fp("left")[0] == 16 and fp("right")[0] == 1920 - 300 - 16

    def test_second_monitor_offset(self):
        x, y = logic.fixed_position("top-left", self.SIZE, (1920, 0, 1920, 1080))
        assert x == 1920 + 16 and y == 16

    def test_window_bigger_than_screen_does_not_escape(self):
        assert logic.fixed_position("center", (3000, 2000), self.SCREEN) == (0, 0)


class TestResolvePosition:
    SCREEN = (0, 0, 1920, 1080)
    SIZE = (300, 233)
    ANCHOR = (1800, 1060)

    def test_auto_follows_the_icon(self):
        got = logic.resolve_position({}, self.ANCHOR, self.SIZE, self.SCREEN)
        assert got == logic.popup_position(self.ANCHOR, self.SIZE, self.SCREEN)

    def test_fixed_ignores_the_icon(self):
        prefs = {logic.PREF_POSITION: "top-left"}
        assert logic.resolve_position(prefs, self.ANCHOR, self.SIZE, self.SCREEN) == (16, 16)

    def test_custom_uses_saved_position_clamped_to_the_screen(self):
        prefs = {logic.PREF_POSITION: "custom", logic.PREF_CUSTOM: [500, 300]}
        assert logic.resolve_position(prefs, self.ANCHOR, self.SIZE, self.SCREEN) == (500, 300)
        prefs[logic.PREF_CUSTOM] = [9000, -50]  # monitor que ya no existe
        assert logic.resolve_position(prefs, self.ANCHOR, self.SIZE, self.SCREEN) == (1620, 0)

    @pytest.mark.parametrize("bad", [None, "x", [1], [1, 2, 3], ["a", 2], [True, 2]])
    def test_corrupt_custom_or_unknown_key_falls_back_to_icon(self, bad):
        auto = logic.popup_position(self.ANCHOR, self.SIZE, self.SCREEN)
        prefs = {logic.PREF_POSITION: "custom", logic.PREF_CUSTOM: bad}
        assert logic.resolve_position(prefs, self.ANCHOR, self.SIZE, self.SCREEN) == auto
        prefs = {logic.PREF_POSITION: "diagonal"}
        assert logic.resolve_position(prefs, self.ANCHOR, self.SIZE, self.SCREEN) == auto


class TestForceXcb:
    WL = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}

    def test_only_when_a_fixed_or_custom_position_is_chosen(self):
        assert not logic.should_force_xcb(self.WL, {})
        assert not logic.should_force_xcb(self.WL, {logic.PREF_POSITION: "auto"})
        assert logic.should_force_xcb(self.WL, {logic.PREF_POSITION: "top"})
        assert logic.should_force_xcb(self.WL, {logic.PREF_POSITION: "custom"})

    def test_needs_wayland_session_with_xwayland(self):
        prefs = {logic.PREF_POSITION: "top"}
        assert not logic.should_force_xcb({"DISPLAY": ":0"}, prefs)  # ya es X11
        assert not logic.should_force_xcb({"WAYLAND_DISPLAY": "wayland-0"}, prefs)  # sin XWayland

    def test_respects_an_explicit_platform(self):
        env = {**self.WL, "QT_QPA_PLATFORM": "wayland"}
        assert not logic.should_force_xcb(env, {logic.PREF_POSITION: "top"})
