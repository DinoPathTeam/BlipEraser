"""Tests de GUI del rediseño: tarjeta con sombra, encabezado y barra lateral."""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.utils import theme as theme_mod
from blip_eraser.utils.i18n import tr
from blip_eraser.widgets.card import SHADOW_BLUR, Card


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def prefs_tmp(tmp_path, monkeypatch):
    import blip_eraser.utils.config as config_mod

    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")
    return tmp_path / "prefs.json"


class TestCard:
    def test_reserves_room_for_shadow(self, app):
        card = Card(padding=10)
        margins = card.contentsMargins()
        assert margins.left() == SHADOW_BLUR + 10
        assert margins.right() == SHADOW_BLUR + 10

    def test_paints_panel_color_inside_and_shadow_outside(self, app):
        card = Card(padding=10)
        card.set_theme("#ffffff", "#d5dce8", dark=False)
        card.resize(200, 120)
        image = card.grab().toImage()
        center = image.pixelColor(100, 60)
        assert center.name() == "#ffffff"
        # Justo fuera del borde, dentro del margen de la sombra, hay píxeles
        # oscurecidos respecto al fondo del widget (que es transparente).
        outside = image.pixelColor(SHADOW_BLUR - 3, 60)
        assert outside.alpha() > 0

    def test_dark_theme_card_uses_dark_panel(self, app):
        card = Card()
        card.set_theme("#151518", "#2a2a30", dark=True)
        card.resize(160, 100)
        assert card.grab().toImage().pixelColor(80, 50).name() == "#151518"


class TestHeaderAndSidebar:
    def test_header_title_follows_section(self, app, prefs_tmp):
        from blip_eraser.renderer import MainWindow

        window = MainWindow()
        assert window.page_title.text() == tr("nav_overview")
        window.sidebar.setCurrentRow(2)
        assert window.page_title.text() == tr("nav_system_cleaner")
        window.sidebar.setCurrentRow(4)
        assert window.page_title.text() == tr("nav_tools")
        window.close()

    def test_inner_page_titles_are_hidden(self, app, prefs_tmp):
        from PyQt6.QtWidgets import QLabel

        from blip_eraser.renderer import MainWindow

        window = MainWindow()
        for page in window._pages.values():
            for label in page.findChildren(QLabel, "PageTitle"):
                assert label.isHidden()
        window.close()

    def test_logo_lives_in_sidebar_not_header(self, app, prefs_tmp):
        from blip_eraser.renderer import MainWindow

        window = MainWindow()
        header = window.findChild(type(window.centralWidget()), "HeaderBar")
        assert window.app_logo.parent() is not header
        assert window.sidebar_activity.parent() is window.app_logo.parent()
        window.close()

    def test_cards_receive_theme_colors(self, app, prefs_tmp):
        from blip_eraser.renderer import MainWindow

        window = MainWindow()
        window._on_theme_changed("blue")
        panel = theme_mod.THEMES["blue"]["palette"]["panel"]
        cards = window.findChildren(Card)
        assert cards
        assert all(c._panel.name().lower() == panel.lower() for c in cards)
        window.close()


class TestGaugeStatusColor:
    def test_light_themes_use_darker_status(self, app, prefs_tmp):
        from blip_eraser.renderer import MainWindow

        window = MainWindow()
        window._on_theme_changed("purple")
        assert window._overview.gauge._status_color.name().lower() == "#1b7f45"
        window._on_theme_changed("green")
        assert window._overview.gauge._status_color.name().lower() == "#3cdc78"
        window.close()
