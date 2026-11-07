"""Tests del rediseño de Ajustes de rendimiento."""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.utils import theme as theme_mod
from blip_eraser.widgets.card import Card


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def prefs_tmp(tmp_path, monkeypatch):
    import blip_eraser.utils.config as config_mod

    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_switch_icons_are_generated_for_all_states():
    paths = theme_mod.switch_icon_paths(theme_mod.THEMES["red"])
    assert set(paths) == {"off", "on", "off_disabled", "on_disabled"}
    for path in paths.values():
        assert "\\" not in path
        assert "<svg" in open(path, encoding="utf-8").read()


def test_switch_icons_differ_between_themes():
    red = theme_mod.switch_icon_paths(theme_mod.THEMES["red"])
    blue = theme_mod.switch_icon_paths(theme_mod.THEMES["blue"])
    assert red["on"] != blue["on"]


def test_qss_has_switch_and_banner_rules():
    qss = theme_mod.build_qss("green")
    assert "QCheckBox#TweakSwitch::indicator:checked" in qss
    assert "QLabel#RebootBanner" in qss


def test_each_tweak_lives_in_a_card_with_switch(app, prefs_tmp):
    from blip_eraser.pages.performance_page import PerformancePage

    page = PerformancePage()
    cards = page.findChildren(Card)
    assert len(cards) == len(page._rows)
    for row in page._rows:
        assert row["checkbox"].objectName() == "TweakSwitch"
    page.close()


def test_set_accent_recolors_previews(app, prefs_tmp):
    from blip_eraser.pages.performance_page import PerformancePage

    page = PerformancePage()
    theme = theme_mod.THEMES["purple"]
    page.set_accent(theme["accent"], theme)
    preview = page._rows[0]["preview"]
    assert preview._accent.name().lower() == theme["accent"].lower()
    assert preview._fill_top.name().lower() == theme["fill_top"].lower()
    page.close()
