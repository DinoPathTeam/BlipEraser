"""Tests de GUI para widgets/splash_screen.py (requieren PyQt6).

Se reportan como *skipped* en entornos sin PyQt6 (este Windows); corren
en CachyOS con PyQt6 instalado.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtTest = pytest.importorskip("PyQt6.QtTest")

from PyQt6.QtTest import QSignalSpy

from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker

# Duración total de la animación de entrada:
#   logo (800) + delay (200) + título (600) = 1600 ms.
_INTRO_TOTAL_MS = 800 + 200 + 600
# Tras la intro, el mensaje encolado hace fade-out (200) + fade-in (300).
_MSG_FADE_TOTAL_MS = 200 + 300


@pytest.fixture(scope="module")
def app():
    """QApplication compartida: necesaria para construir QWidgets."""
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestSplashScreen:
    def test_builds_and_sets_message_after_intro(self, app):
        splash = SplashScreen()
        # Durante la intro el mensaje se encola, no se pinta de inmediato.
        splash.set_message("hola")
        assert splash._pending_message == "hola"
        assert splash._message.text() == ""
        # Cuando termina la intro, el mensaje encolado se muestra tras su
        # propia cadena fade-out + fade-in.
        QtTest.QTest.qWait(_INTRO_TOTAL_MS + _MSG_FADE_TOTAL_MS + 200)
        assert splash._intro_done is True
        assert splash._message.text() == "hola"

    def test_message_queued_during_intro(self, app):
        splash = SplashScreen()
        splash.set_message("primero")
        splash.set_message("segundo")
        # El último mensaje gana: solo se conserva el más reciente.
        assert splash._pending_message == "segundo"
        assert splash._message.text() == ""

    def test_message_after_intro_applies_after_fade(self, app):
        splash = SplashScreen()
        QtTest.QTest.qWait(_INTRO_TOTAL_MS + 100)
        assert splash._intro_done is True
        splash.set_message("fuera")
        # El texto nuevo se escribe tras el fade-out del anterior.
        QtTest.QTest.qWait(_MSG_FADE_TOTAL_MS + 100)
        assert splash._message.text() == "fuera"

    def test_close_emits_closed_signal(self, app):
        splash = SplashScreen()
        spy = QSignalSpy(splash.closed)
        splash.close()
        assert len(spy) == 1

    def test_has_logo_label(self, app):
        splash = SplashScreen()
        assert splash._logo is not None


class TestStartupWorker:
    def test_worker_is_interruptible_while_running(self, app):
        import time

        # requestInterruption() solo marca el flag mientras el thread corre;
        # isInterruptionRequested() devuelve False una vez finalizado.
        worker = StartupWorker()
        worker.start()
        for _ in range(200):
            if worker.isRunning():
                break
            app.processEvents()
            time.sleep(0.01)
        assert worker.isRunning()
        worker.requestInterruption()
        assert worker.isInterruptionRequested() is True
        assert worker.wait(5000) is True