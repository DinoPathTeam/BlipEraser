"""Tests para utils/ui_text.py (texto localizado, sin PyQt6).

Se mockea ui_text.check_binary_available y el idioma activo de i18n,
igual que se mockea subprocess.run en test_pacman.py.
"""

import pytest

from blip_eraser.utils import i18n, ui_text
from blip_eraser.utils.i18n import set_language
from blip_eraser.utils.ui_text import (
    localized_missing_banner,
    localized_missing_lines,
    resolve_initial_language,
    should_ask_for_language,
)


@pytest.fixture(autouse=True)
def isolated_i18n(tmp_path, monkeypatch):
    """Cada test: settings en tmp_path y sin idioma previo en memoria."""
    monkeypatch.setattr(i18n, "_current_language", None)
    monkeypatch.setattr(i18n, "SETTINGS_FILE", tmp_path / "settings.json")


def mock_binaries_available(monkeypatch, missing):
    """`missing`: conjunto de binarios que NO estarán disponibles."""
    monkeypatch.setattr(
        ui_text,
        "check_binary_available",
        lambda name: name not in missing,
    )


class TestLocalizedMissingLines:
    def test_all_present_no_lines(self, monkeypatch):
        set_language("es")
        mock_binaries_available(monkeypatch, set())
        assert localized_missing_lines(["pacman", "pkexec"]) == []

    def test_missing_pkexec_spanish_suggests_command(self, monkeypatch):
        set_language("es")
        mock_binaries_available(monkeypatch, {"pkexec"})

        (line,) = localized_missing_lines(["pacman", "pkexec"])
        assert "pkexec" in line
        assert "Instala con: sudo pacman -S polkit" in line
        assert "• pacman" not in line

    def test_missing_pacman_spanish_uses_incompatibility(self, monkeypatch):
        set_language("es")
        mock_binaries_available(monkeypatch, {"pacman"})

        (line,) = localized_missing_lines(["pacman"])
        assert "basadas en Arch" in line
        assert "sudo pacman -S pacman" not in line

    def test_english_uses_english_text(self, monkeypatch):
        set_language("en")
        mock_binaries_available(monkeypatch, {"pkexec"})

        (line,) = localized_missing_lines(["pkexec"])
        assert "Install with: sudo pacman -S polkit" in line


class TestLocalizedMissingBanner:
    def test_none_missing_empty(self, monkeypatch):
        set_language("es")
        mock_binaries_available(monkeypatch, set())
        assert localized_missing_banner(["pacman", "pkexec"]) == ""

    def test_unknown_binary_no_line(self, monkeypatch):
        set_language("es")
        mock_binaries_available(monkeypatch, {"no-existe"})
        assert localized_missing_banner(["no-existe"]) == ""

    def test_language_change_refreshes_text(self, monkeypatch):
        mock_binaries_available(monkeypatch, {"pacman", "pkexec"})

        set_language("es")
        es_banner = localized_missing_banner(["pacman", "pkexec"])
        assert "pacman no encontrado" in es_banner
        assert "pkexec no encontrado" in es_banner
        assert es_banner.count("no encontrado") == 2

        set_language("en")
        en_banner = localized_missing_banner(["pacman", "pkexec"])
        assert "pacman not found" in en_banner
        assert en_banner.count("not found") == 2


class TestFirstRunLanguage:
    def test_should_ask_only_when_no_preference(self):
        assert should_ask_for_language(None) is True
        assert should_ask_for_language("es") is False
        assert should_ask_for_language("en") is False

    def test_resolve_keeps_valid_choice(self):
        assert resolve_initial_language("es") == "es"
        assert resolve_initial_language("en") == "en"

    def test_resolve_none_uses_detection(self, monkeypatch):
        monkeypatch.setattr(ui_text, "detect_system_language", lambda: "es")
        assert resolve_initial_language(None) == "es"

    def test_resolve_unsupported_falls_to_detection(self, monkeypatch):
        monkeypatch.setattr(ui_text, "detect_system_language", lambda: "en")
        assert resolve_initial_language("fr") == "en"