"""Tests de GUI para widgets/splash_screen.py (requieren PyQt6).

Se reportan como *skipped* en entornos sin PyQt6 (este Windows); corren
en CachyOS con PyQt6 instalado.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QSignalSpy

from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker


@pytest.fixture(scope="module")
def app():
    """QApplication compartida: necesaria para construir QWidgets."""
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestSplashScreen:
    def test_builds_and_sets_message(self, app):
        splash = SplashScreen()
        splash.set_message("hola")
        assert splash._message.text() == "hola"

    def test_close_emits_closed_signal(self, app):
        splash = SplashScreen()
        spy = QSignalSpy(splash.closed)
        splash.close()
        assert len(spy) == 1

    def test_has_logo_label(self, app):
        splash = SplashScreen()
        assert splash._logo is not None


class TestStartupWorker:
    def test_worker_is_interruptible_before_start(self, app):
        worker = StartupWorker()
        worker.requestInterruption()
        worker.run()
        assert worker.isInterruptionRequested() is True