"""Tests para utils/theme.py (QSS y fuentes, sin PyQt6)."""

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.theme import (
    THEMES,
    build_qss,
    font_family,
    font_label,
    palette_for,
)


class TestThemes:
    def test_four_themes_present(self):
        assert set(THEMES) == {"red", "blue", "green", "purple"}

    def test_each_theme_has_full_palette(self):
        for key, theme in THEMES.items():
            palette = theme["palette"]
            for field in ("bg", "panel", "sidebar", "text", "subtext", "border", "hover", "icon"):
                assert field in palette, f"{key} falta {field}"
            assert theme["accent"]
            assert theme["label_key"]

    def test_red_and_green_are_dark(self):
        assert THEMES["red"]["is_dark"] is True
        assert THEMES["green"]["is_dark"] is True

    def test_blue_and_purple_are_light(self):
        assert THEMES["blue"]["is_dark"] is False
        assert THEMES["purple"]["is_dark"] is False


class TestBuildQss:
    def test_contains_accent(self):
        qss = build_qss("green")
        assert THEMES["green"]["accent"] in qss

    def test_light_theme_bg_appears(self):
        qss = build_qss("blue")
        assert THEMES["blue"]["palette"]["bg"] in qss

    def test_dark_theme_bg_appears(self):
        qss = build_qss("red")
        assert THEMES["red"]["palette"]["bg"] in qss

    def test_returns_non_empty_string(self):
        assert build_qss("red").strip().startswith("QWidget")

    def test_unknown_theme_falls_back_to_red(self):
        assert build_qss("no-existe") == build_qss("red")

    def test_header_checkbox_has_no_block_background(self):
        for key in THEMES:
            qss = build_qss(key)
            assert "QCheckBox#SelectAllCheck { background: transparent;" in qss
            assert "QHeaderView::section:first { padding: 0; }" in qss
            assert "::indicator:indeterminate" in qss


class TestPalette:
    def test_palette_by_theme(self):
        assert palette_for("blue") == THEMES["blue"]["palette"]
        assert palette_for("no-existe") == THEMES["red"]["palette"]

    def test_dark_and_light_differ(self):
        assert palette_for("red")["bg"] != palette_for("blue")["bg"]


class TestFonts:
    def test_font_family_system_is_none(self):
        assert font_family("system") is None

    def test_font_family_named(self):
        assert font_family("roboto") == "Roboto"

    def test_font_family_unknown_is_none(self):
        assert font_family("no-existe") is None

    def test_font_label_uses_label_key(self):
        assert font_label("system") == tr("font_system")

    def test_font_label_uses_family_when_no_key(self):
        assert font_label("roboto") == "Roboto"

    def test_font_label_unknown_returns_id(self):
        assert font_label("no-existe") == "no-existe"