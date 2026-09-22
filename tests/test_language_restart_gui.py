"""Tests GUI del cambio de idioma con reinicio (sin cambio en caliente).

Antes: _switch_language llamaba a retranslate() en cascada (reconstruía
todas las tablas en plena sesión: tirones, UI mixta, RuntimeErrors).
Ahora: guarda la preferencia y pide reiniciar; la sesión actual no se
retraduce. Requieren PyQt6; skipped sin él.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.utils import i18n as i18n_mod


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture
def lang_env(app, tmp_path, monkeypatch):
    """Settings i18n a tmp + idioma inicial 'es'; restaura al terminar."""
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(i18n_mod, "SETTINGS_FILE", settings)
    old = i18n_mod._current_language
    i18n_mod.set_language("es")
    yield settings
    i18n_mod._current_language = old


class _FakeButton:
    pass


class _FakeBox:
    """QMessageBox falso: elige qué botón se 'pulsa'."""

    Icon = type("Icon", (), {"Information": 1})
    ButtonRole = type("ButtonRole", (), {"AcceptRole": 1, "RejectRole": 2})

    clicked_as: str = "later"

    def __init__(self, *args, **kwargs):
        self.restart_btn = _FakeButton()
        self.later_btn = _FakeButton()

    def setWindowTitle(self, *a):
        pass

    def setText(self, *a):
        pass

    def setIcon(self, *a):
        pass

    def addButton(self, text, role):
        return self.restart_btn if role == 1 else self.later_btn

    def exec(self):
        return 0

    def clickedButton(self):
        return self.restart_btn if self.clicked_as == "now" else self.later_btn


@pytest.fixture
def window(app, lang_env, monkeypatch):
    """MainWindow real con scans mockeados (rápida, sin pacman real)."""
    import blip_eraser.pages.overview_page as overview_mod
    import blip_eraser.pages.uninstaller_page as uninstaller_mod
    import blip_eraser.pages.cleaner_page as cleaner_mod
    from blip_eraser.renderer import MainWindow
    from blip_eraser.utils.log import log as log_buffer

    monkeypatch.setattr(overview_mod, "list_installed_apps", lambda *a, **k: [])
    monkeypatch.setattr(uninstaller_mod, "list_installed_apps", lambda *a, **k: [])
    monkeypatch.setattr(cleaner_mod, "scan_cleanup_items", lambda *a, **k: [])
    w = MainWindow()
    w.show()
    app.processEvents()
    log_buffer._listeners.clear()
    yield w
    w.close()
    app.processEvents()


def _patch_box(monkeypatch, clicked):
    import blip_eraser.renderer as renderer_mod

    _FakeBox.clicked_as = clicked
    monkeypatch.setattr(renderer_mod, "QMessageBox", _FakeBox)


class TestLanguageRestart:
    def test_switch_saves_without_retranslating(self, window, lang_env, monkeypatch):
        """Elegir idioma lo persiste pero NO re-traduce la sesión actual."""
        _patch_box(monkeypatch, "later")
        calls = []
        for page in window._pages.values():
            if hasattr(page, "retranslate"):
                orig = page.retranslate
                monkeypatch.setattr(
                    page, "retranslate", lambda *a, _o=orig: calls.append(1)
                )
        i18n_mod.set_language("es")
        window._switch_language("en")
        assert i18n_mod.get_current_language() == "en"
        import json

        assert json.loads(lang_env.read_text(encoding="utf-8"))["language"] == "en"
        assert calls == []
        i18n_mod.set_language("es")

    def test_switch_same_language_is_noop(self, window, monkeypatch):
        """Elegir el idioma activo no hace nada (ni diálogo)."""
        i18n_mod.set_language("es")
        _patch_box(monkeypatch, "now")
        created = []
        import blip_eraser.renderer as renderer_mod

        orig_box = renderer_mod.QMessageBox

        class _SpyBox(_FakeBox):
            def __init__(self, *a, **k):
                created.append(1)
                super().__init__(*a, **k)

        monkeypatch.setattr(renderer_mod, "QMessageBox", _SpyBox)
        window._switch_language("es")
        assert created == []
        assert orig_box is not None

    def test_restart_now_quits(self, window, monkeypatch):
        """'Reiniciar ahora' cierra la app para aplicar el idioma."""
        import blip_eraser.renderer as renderer_mod
        from unittest.mock import MagicMock

        _patch_box(monkeypatch, "now")
        quit_mock = MagicMock()
        fake_app = MagicMock()
        fake_app.quit = quit_mock
        fake_qt = MagicMock()
        fake_qt.instance.return_value = fake_app
        monkeypatch.setattr(renderer_mod, "QApplication", fake_qt)
        i18n_mod.set_language("es")
        window._switch_language("en")
        quit_mock.assert_called_once_with()
        i18n_mod.set_language("es")
