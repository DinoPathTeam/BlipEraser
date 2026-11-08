"""Tests del rediseño de Configuración (Personalización, Tema de color, Ayuda)."""

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


def test_theme_swatches_mirror_the_combo(app, prefs_tmp):
    from blip_eraser.pages.settings_page import SettingsPage

    page = SettingsPage()
    buttons = page.theme_choices.buttons()
    assert len(buttons) == len(theme_mod.THEMES)
    assert page.theme_combo.isHidden()
    # Clic en una muestra -> cambia el combo y emite la señal.
    seen = []
    page.theme_changed.connect(seen.append)
    buttons[2].click()
    assert page.theme_combo.currentIndex() == 2
    assert seen == [list(theme_mod.THEMES)[2]]
    # Cambio por código -> se marca la muestra.
    page.theme_combo.setCurrentIndex(1)
    assert [b.isChecked() for b in buttons] == [False, True, False, False]
    page.close()


def test_font_chips_follow_combo(app, prefs_tmp):
    from blip_eraser.pages.settings_page import SettingsPage

    page = SettingsPage()
    chips = page.font_choices.buttons()
    assert len(chips) == page.font_combo.count()
    page.font_combo.setCurrentIndex(len(chips) - 1)
    assert chips[-1].isChecked() and sum(c.isChecked() for c in chips) == 1
    page.close()


def test_settings_has_two_cards_and_uppercase_titles(app, prefs_tmp):
    from blip_eraser.pages.settings_page import SettingsPage

    page = SettingsPage()
    assert len(page.findChildren(Card)) == 2
    assert page.tray_title.text() == page.tray_title.text().upper()
    assert page.theme_title.text() == page.theme_title.text().upper()
    page.close()


def test_help_sections_are_cards(app, prefs_tmp):
    from blip_eraser.pages.help_page import _SECTIONS, HelpPage

    page = HelpPage()
    assert len(page.findChildren(Card)) == len(_SECTIONS)
    page.close()


def test_personalize_list_is_in_card_with_primary_save(app, prefs_tmp):
    from blip_eraser.pages.personalize_page import PersonalizePage

    page = PersonalizePage()
    assert page.save_btn.objectName() == "PrimaryButton"
    assert page.list_widget.objectName() == "PathList"
    assert len(page.findChildren(Card)) == 1
    page.close()


def test_help_usage_mentions_every_real_section(monkeypatch):
    from blip_eraser.utils import i18n

    # Sin set_language(): persistiría el idioma en el config real del usuario.
    monkeypatch.setattr(i18n, "_current_language", "es")
    body = i18n.tr("help_usage_body")
    for name in ("Vista general", "Desinstalador", "Limpiador del sistema", "Ajustes de rendimiento", "Configuración"):
        assert name in body
