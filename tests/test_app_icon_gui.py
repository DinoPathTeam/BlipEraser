"""Tests GUI del ícono de la aplicación (requieren PyQt6).

Verifican el fallback silencioso del asset del ícono:
  - app_icon() devuelve un QIcon no nulo si el asset existe.
  - app_icon() devuelve un QIcon() vacío (isNull True) si el asset NO
    existe, sin lanzar excepción.
  - MainWindow y SplashScreen se construyen sin excepción en AMBOS casos
    (asset presente y asset ausente), igual que ya hace ASSET_LOGO_PATH.

Requieren PyQt6; se reportan como *skipped* en entornos sin él y corren
en CachyOS.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtGui = pytest.importorskip("PyQt6.QtGui")
QtTest = pytest.importorskip("PyQt6.QtTest")

from pathlib import Path

from blip_eraser.widgets import logo as logo_mod
from blip_eraser.widgets.logo import app_icon

# Duración total de la animación de entrada del splash:
#   logo (800) + delay (200) + título (600) = 1600 ms.
_INTRO_TOTAL_MS = 800 + 200 + 600


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture(scope="module")
def prefs_tmp(tmp_path_factory):
    """Redirige PREFS_FILE a un tmp para no tocar la config real."""
    import blip_eraser.utils.config as config_mod

    prefs_file = tmp_path_factory.mktemp("prefs") / "prefs.json"
    config_mod.PREFS_FILE = prefs_file
    return prefs_file


_KEEP_ALIVE: list = []


def _wait_scans_done(app, window, timeout_ms=15000):
    """Bombea el event loop hasta que los escaneos de fondo terminen.

    Overview/Desinstalador/Limpiador lanzan hilos daemon al construirse; si
    la ventana (y sus hilos) sobrevive al módulo, un hilo aún vivo puede
    interferir con los monkeypatch de módulos de test posteriores. Esperamos
    a que todas las páginas dejen de escanear antes de devolver el control.
    """
    import time

    pages = list(window._pages.values())
    sections = []
    for p in pages:
        if hasattr(p, "recommended"):
            sections.append(p.recommended)
        if hasattr(p, "manual"):
            sections.append(p.manual)

    def scanning() -> bool:
        for obj in pages + sections:
            if getattr(obj, "_scanning", False):
                return True
        return False

    deadline = time.monotonic() + timeout_ms / 1000
    while scanning() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def _build_mainwindow(app, prefs_tmp):
    """Construye una MainWindow y deja el estado de hilos/listeners limpio."""
    from blip_eraser.renderer import MainWindow
    from blip_eraser.utils.log import log as log_buffer

    w = MainWindow()
    w.show()
    app.processEvents()
    _wait_scans_done(app, w)
    log_buffer._listeners.clear()
    _KEEP_ALIVE.append(w)
    return w


class TestAppIcon:
    def test_app_icon_exists(self, app):
        """Con el asset presente, app_icon() devuelve un QIcon no nulo."""
        assert logo_mod.ASSET_ICON_PATH.exists()
        assert app_icon().isNull() is False

    def test_app_icon_missing_fallback(self, app, monkeypatch):
        """Si el asset no existe, app_icon() devuelve un QIcon() vacío."""
        monkeypatch.setattr(
            logo_mod,
            "ASSET_ICON_PATH",
            Path("C:/no_existe/desktopiconBlip.png"),
        )
        assert app_icon().isNull() is True

    def test_windows_build_with_icon(self, app, prefs_tmp):
        """MainWindow y SplashScreen se construyen sin excepción con el
        ícono presente, y sus windowIcon() no son nulos."""
        from PyQt6.QtTest import QTest

        from blip_eraser.widgets.splash_screen import SplashScreen

        window = _build_mainwindow(app, prefs_tmp)
        splash = SplashScreen()
        _KEEP_ALIVE.append(splash)

        assert window.windowIcon().isNull() is False
        assert splash.windowIcon().isNull() is False

        # Construir un SplashScreen arranca su intro (QPropertyAnimation)
        # sobre el driver global de animación. Dejarla terminar aquí para
        # no dejar el driver colgado cuando corran los tests del splash
        # después de este módulo.
        QTest.qWait(_INTRO_TOTAL_MS + 300)

    def test_windows_build_without_icon(self, app, prefs_tmp, monkeypatch):
        """Si el asset NO existe, MainWindow y SplashScreen igualmente se
        construyen sin excepción (fallback silencioso a QIcon() vacío)."""
        from PyQt6.QtTest import QTest

        from blip_eraser.widgets.splash_screen import SplashScreen

        monkeypatch.setattr(
            logo_mod,
            "ASSET_ICON_PATH",
            Path("C:/no_existe/desktopiconBlip.png"),
        )

        window = _build_mainwindow(app, prefs_tmp)
        splash = SplashScreen()
        _KEEP_ALIVE.append(splash)

        assert window.windowIcon().isNull() is True
        assert splash.windowIcon().isNull() is True

        QTest.qWait(_INTRO_TOTAL_MS + 300)