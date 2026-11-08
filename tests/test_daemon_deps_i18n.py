"""El diálogo de dependencias del daemon sale en el idioma activo (ES/EN)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import PyQt6.QtWidgets as qtw  # noqa: E402

import blip_eraser.utils.phase2_installer as p2  # noqa: E402
from blip_eraser.main import _offer_daemon_deps, _show_installed_summary  # noqa: E402
from blip_eraser.utils import dependency_check as dc  # noqa: E402
from blip_eraser.utils import i18n  # noqa: E402

_LANGS = ("es", "en")


class _FakeBox:
    """QMessageBox falso: guarda lo que se muestra y 'pulsa' el primer botón."""

    shown: dict = {}

    class Icon:
        Question = 0

    class ButtonRole:
        AcceptRole = 0
        RejectRole = 1

    def __init__(self, *a, **k):
        self._buttons: list[tuple[str, object]] = []
        type(self).shown = {"buttons": []}

    def setWindowTitle(self, t):
        type(self).shown["title"] = t

    def setText(self, t):
        type(self).shown["text"] = t

    def setIcon(self, *_): ...

    def addButton(self, label, role):
        btn = object()
        self._buttons.append((label, btn))
        type(self).shown["buttons"].append(label)
        return btn

    def exec(self): ...

    def clickedButton(self):
        return self._buttons[0][1]  # "Instalar"

    @staticmethod
    def warning(parent, title, text):
        _FakeBox.shown["warning"] = (title, text)

    @staticmethod
    def information(parent, title, text):
        _FakeBox.shown["information"] = (title, text)


@pytest.fixture
def fake_box(monkeypatch):
    monkeypatch.setattr(qtw, "QMessageBox", _FakeBox)
    return _FakeBox


@pytest.mark.parametrize("lang", _LANGS)
def test_dialogo_de_instalacion_usa_el_idioma_activo(monkeypatch, fake_box, lang):
    monkeypatch.setattr(i18n, "_current_language", lang)
    dep = dc.DAEMON_DEPENDENCIES[0]
    monkeypatch.setattr(p2, "install_daemon_dependency", lambda d: (True, ""))

    _offer_daemon_deps(None, [dep])

    shown = fake_box.shown
    assert shown["title"] == i18n.tr("daemon_deps_title")
    assert shown["buttons"] == [i18n.tr("daemon_deps_install"), i18n.tr("daemon_deps_cancel")]
    assert dep.name in shown["text"]
    expected_status = i18n.tr(
        "daemon_deps_not_installed" if not dep.check_cmd else "daemon_deps_not_active"
    )
    assert expected_status in shown["text"]
    if lang == "en":
        assert shown["buttons"] == ["Install", "Cancel"]
        assert "requires the following" in shown["text"]
    else:
        assert shown["buttons"] == ["Instalar", "Cancelar"]
        assert "requiere las siguientes" in shown["text"]


@pytest.mark.parametrize("lang", _LANGS)
def test_error_de_instalacion_se_muestra_traducido(monkeypatch, fake_box, lang):
    monkeypatch.setattr(i18n, "_current_language", lang)
    dep = dc.DAEMON_DEPENDENCIES[0]
    monkeypatch.setattr(p2, "install_daemon_dependency", lambda d: (False, "boom"))

    assert _offer_daemon_deps(None, [dep]) == (False, [])

    title, text = fake_box.shown["warning"]
    assert title == i18n.tr("daemon_deps_error_title")
    assert dep.name in text and "boom" in text
    assert text.startswith("Error installing" if lang == "en" else "Error instalando")


@pytest.mark.parametrize("lang", _LANGS)
@pytest.mark.parametrize("restart", [False, True])
def test_resumen_de_instaladas(monkeypatch, fake_box, lang, restart):
    monkeypatch.setattr(i18n, "_current_language", lang)

    _show_installed_summary(None, ["apparmor", "polkit"], restart)

    title, text = fake_box.shown["information"]
    assert title == i18n.tr("daemon_deps_done_title")
    assert "• apparmor" in text and "• polkit" in text
    assert (i18n.tr("daemon_deps_restart") in text) is restart


def test_claves_nuevas_existen_en_ambos_idiomas():
    keys = [k for k in i18n.TRANSLATIONS["es"] if k.startswith("daemon_deps_")]
    assert keys, "no se encontraron claves daemon_deps_*"
    for k in keys:
        assert k in i18n.TRANSLATIONS["en"], k
        assert i18n.TRANSLATIONS["en"][k] != i18n.TRANSLATIONS["es"][k] or k == "daemon_deps_error_title"
