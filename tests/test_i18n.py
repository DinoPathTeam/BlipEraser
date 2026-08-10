"""Tests para el módulo i18n (sin PyQt6, sin tocar ~/.config real).

Se mockea locale.getlocale() y se apunta SETTINGS_FILE a tmp_path para
no tocar la configuración real del usuario durante los tests.
"""

import json
import locale

import pytest

from blip_eraser.utils import i18n
from blip_eraser.utils.i18n import (
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    detect_system_language,
    get_current_language,
    load_saved_language,
    set_language,
    tr,
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Cada test: settings en tmp_path y sin idioma previo en memoria."""
    monkeypatch.setattr(i18n, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(i18n, "_current_language", None)


def mock_lang(monkeypatch, lang_code):
    """Fuerza locale.getlocale() a devolver (lang_code, encoding)."""
    monkeypatch.setattr(
        i18n.locale, "getlocale", lambda: (lang_code, "UTF-8")
    )


class TestDetectSystemLanguage:
    @pytest.mark.parametrize(
        "lang_code", ["es_ES", "es_MX", "es_AR.UTF-8"]
    )
    def test_spanish(self, monkeypatch, lang_code):
        mock_lang(monkeypatch, lang_code)
        assert detect_system_language() == "es"

    @pytest.mark.parametrize("lang_code", ["en_US", "fr_FR", "de_DE", "ja_JP"])
    def test_non_spanish_uses_english(self, monkeypatch, lang_code):
        mock_lang(monkeypatch, lang_code)
        assert detect_system_language() == "en"

    @pytest.mark.parametrize("lang_code", [None, "C", ""])
    def test_no_information_falls_back_to_english(self, monkeypatch, lang_code):
        mock_lang(monkeypatch, lang_code)
        assert detect_system_language() == "en"

    def test_getlocale_raising_falls_back_to_english(self, monkeypatch):
        def boom():
            raise locale.Error("invalid locale")

        monkeypatch.setattr(i18n.locale, "getlocale", boom)
        assert detect_system_language() == "en"


class TestTr:
    def test_spanish_active(self):
        set_language("es")
        assert tr("window_title") == TRANSLATIONS["es"]["window_title"]
        assert tr("refresh_button") == "Actualizar lista"

    def test_changing_language_changes_result(self):
        set_language("es")
        assert tr("refresh_button") == "Actualizar lista"
        set_language("en")
        assert tr("refresh_button") == "Refresh list"

    def test_scan_now_button_is_localized(self):
        # Bug: antes 'overview_erase_button' era "SCAN NOW" en ambos idiomas.
        set_language("es")
        assert tr("overview_erase_button") == "Escanear ahora"
        set_language("en")
        assert tr("overview_erase_button") == "Scan now"

    def test_uninstall_button_count_key(self):
        set_language("es")
        assert (
            tr("uninstall_button_count").format(n=0)
            == "Desinstalar seleccionados (0)"
        )
        assert (
            tr("uninstall_button_count").format(n=3)
            == "Desinstalar seleccionados (3)"
        )
        set_language("en")
        assert (
            tr("uninstall_button_count").format(n=3)
            == "Uninstall selected (3)"
        )

    def test_missing_key_returns_brackets(self):
        set_language("es")
        assert tr("clave_inexistente") == "[clave_inexistente]"

    def test_key_missing_in_active_language_falls_back_to_english(self, monkeypatch):
        set_language("es")
        # Simula una clave que solo existe en inglés: la quita del diccionario 'es'.
        monkeypatch.setitem(TRANSLATIONS["en"], "only_in_en", "English-only text")
        monkeypatch.delitem(TRANSLATIONS["es"], "only_in_en", raising=False)
        assert tr("only_in_en") == "English-only text"

    def test_both_languages_share_same_keys(self):
        assert set(TRANSLATIONS["es"]) == set(TRANSLATIONS["en"])


class TestSetAndLoadSavedLanguage:
    def test_roundtrip(self):
        set_language("es")
        assert get_current_language() == "es"
        assert load_saved_language() == "es"
        data = json.loads(i18n.SETTINGS_FILE.read_text(encoding="utf-8"))
        assert data == {"language": "es"}

    def test_no_file_returns_none(self):
        assert load_saved_language() is None

    def test_corrupt_file_returns_none(self):
        i18n.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        i18n.SETTINGS_FILE.write_text("esto no es json", encoding="utf-8")
        assert load_saved_language() is None

    def test_missing_language_key_returns_none(self):
        i18n.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        i18n.SETTINGS_FILE.write_text('{"other": 1}', encoding="utf-8")
        assert load_saved_language() is None

    def test_invalid_language_falls_back_to_english(self):
        set_language("fr")
        assert get_current_language() == "en"
        assert load_saved_language() == "en"

    def test_saved_preference_wins_over_detection(self, monkeypatch):
        set_language("en")
        # Fuerza un sistema en español para comprobar que manda lo guardado.
        monkeypatch.setattr(i18n, "_current_language", None)
        mock_lang(monkeypatch, "es_ES")
        assert get_current_language() == "en"

    def test_detection_used_when_no_preference(self, monkeypatch):
        mock_lang(monkeypatch, "es_ES")
        assert get_current_language() == "es"

    def test_supported_languages_are_translated(self):
        assert SUPPORTED_LANGUAGES == ("es", "en")
        assert all(lang in TRANSLATIONS for lang in SUPPORTED_LANGUAGES)