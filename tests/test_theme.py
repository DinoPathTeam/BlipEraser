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


def _relative_luminance(hex_color: str) -> float:
    def channel(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    hex_color = hex_color.lstrip("#")
    r, g, b = (channel(int(hex_color[i : i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class TestContrast:
    """Contraste garantizado de texto e íconos en los 4 temas.

    El porcentaje del gauge "SALUD DEL SISTEMA" se pinta sobre el panel y
    los íconos del sidebar sobre su fondo; ambos usan colores del tema.
    Con este test verificamos que esos pares cumplen WCAG AA (≥3:1 para
    texto/grandes), por lo que ningún tema puede dejar texto fantasma.
    """

    def test_gauge_text_on_panel(self):
        for key, theme in THEMES.items():
            p = theme["palette"]
            ratio = _contrast_ratio(p["text"], p["panel"])
            assert ratio >= 3.0, f"{key}: text sobre panel = {ratio:.2f}"

    def test_sidebar_icon_on_sidebar_bg(self):
        for key, theme in THEMES.items():
            p = theme["palette"]
            ratio = _contrast_ratio(p["icon"], p["sidebar"])
            assert ratio >= 3.0, f"{key}: icon sobre sidebar = {ratio:.2f}"


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