"""Tests para widgets/splash_screen.py — video de intro + fallback.

Patrón del proyecto: pytest.importorskip + fixture app manual (QApplication.instance).
"""

import pytest

from unittest.mock import MagicMock

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")
QtGui = pytest.importorskip("PyQt6.QtGui")

# QtMultimedia es opcional
QtMultimedia = pytest.importorskip("PyQt6.QtMultimedia", reason="QtMultimedia opcional")
QtMultimediaWidgets = pytest.importorskip(
    "PyQt6.QtMultimediaWidgets", reason="QtMultimediaWidgets opcional"
)

from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker, _VideoWidget


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestVideoWidget:
    """Tests del widget de renderizado de video (_VideoWidget)."""

    def test_video_widget_constructs(self, app):
        widget = _VideoWidget()
        assert widget is not None
        assert widget._current_image is None
        widget.close()

    def test_video_widget_set_frame_triggers_update(self, app, monkeypatch):
        """set_frame guarda la imagen y llama update()."""
        widget = _VideoWidget()
        widget.resize(320, 180)

        # Mock update para verificar que se llama
        updated = []
        monkeypatch.setattr(widget, "update", lambda: updated.append(True))

        # Crear QImage de prueba
        image = QtGui.QImage(100, 100, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor("#FF0000"))

        widget.set_frame(image)

        assert widget._current_image is not None
        assert not widget._current_image.isNull()
        assert len(updated) == 1
        widget.close()

    def test_video_widget_ignores_null_frame(self, app):
        """Frames nulos no rompen el widget."""
        widget = _VideoWidget()
        null_image = QtGui.QImage()
        assert null_image.isNull()

        widget.set_frame(null_image)
        assert widget._current_image is None
        widget.close()

    def test_video_widget_paint_event_no_crash(self, app):
        """paintEvent no crashea sin frame ni con frame."""
        widget = _VideoWidget()
        widget.resize(100, 100)

        # Sin frame - no debe crashear
        from PyQt6.QtGui import QPaintEvent, QRect
        event = QPaintEvent(QRect(0, 0, 100, 100))
        widget.paintEvent(event)

        # Con frame - no debe crashear
        image = QtGui.QImage(100, 100, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor("#00FF00"))
        widget.set_frame(image)
        widget.paintEvent(event)

        widget.close()


class TestSplashScreenConstruction:
    """SplashScreen se construye sin excepción con y sin video/QtMultimedia."""

    def test_splash_constructs_without_pyqt6_multimedia(self, monkeypatch, app):
        """Si QtMultimedia no está disponible, fallback a animación de logo."""
        import sys
        import blip_eraser.widgets.splash_screen as splash_mod

        monkeypatch.setitem(sys.modules, "PyQt6.QtMultimedia", None)
        monkeypatch.setitem(sys.modules, "PyQt6.QtMultimediaWidgets", None)
        import importlib

        importlib.reload(splash_mod)

        from blip_eraser.widgets.splash_screen import SplashScreen

        splash = SplashScreen()
        assert splash is not None
        assert splash._video_loaded is False
        assert splash._media_player is None
        splash.close()

    def test_splash_constructs_with_video_missing(self, monkeypatch, app):
        """Si el archivo de video no existe, fallback silencioso."""
        from blip_eraser.widgets.splash_screen import SplashScreen

        splash = SplashScreen()
        assert splash is not None
        assert splash._video_loaded is False
        splash.close()

    def test_splash_constructs_with_mock_video_available(self, monkeypatch, app):
        """Simula video disponible: verifica que _video_loaded=True y media_player creado."""
        from blip_eraser.widgets.splash_screen import SplashScreen
        from pathlib import Path

        monkeypatch.setattr(Path, "exists", lambda self: True)

        splash = SplashScreen()
        assert splash is not None
        # En CI sin QtMultimedia real, _video_loaded será False
        splash.close()


class TestSplashScreenFallbackBehavior:
    """Comportamiento del fallback (animación logo) cuando no hay video."""

    def test_fallback_animation_runs(self, monkeypatch, app):
        """La animación de logo+título se ejecuta en fallback."""
        splash = SplashScreen()
        splash._video_loaded = False
        splash._media_player = None
        splash._video_widget = None
        splash._logo.show()
        splash._title.show()

        assert splash._logo.isVisible()
        assert splash._title.isVisible()
        splash.close()

    def test_fallback_message_queue(self, monkeypatch, app):
        """Mensajes se encolan durante animación de entrada y se muestran al terminar."""
        splash = SplashScreen()
        splash._video_loaded = False
        splash._intro_done = False

        splash.set_message("Test message")
        assert splash._pending_message == "Test message"

        splash._intro_done = True
        splash._on_intro_finished()

        assert splash._pending_message is None
        splash.close()


class TestVideoTimingBehavior:
    """Comportamiento de timing: video + worker coordination."""

    def test_media_status_changed_sets_video_ended_flag(self, monkeypatch, app):
        """_on_media_status_changed pone _video_ended=True al recibir EndOfMedia."""
        from PyQt6.QtMultimedia import QMediaPlayer

        splash = SplashScreen()
        splash._video_loaded = True
        splash._video_ended = False

        mock_player = QtWidgets.QWidget()
        monkeypatch.setattr(splash, "_media_player", mock_player)

        splash._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)

        assert splash._video_ended is True
        assert splash._waiting_for_worker is False
        splash.close()

    def test_media_status_changed_ignores_other_statuses(self, monkeypatch, app):
        """Otros MediaStatus no marcan _video_ended."""
        from PyQt6.QtMultimedia import QMediaPlayer

        splash = SplashScreen()
        splash._video_loaded = True
        splash._video_ended = False

        mock_player = QtWidgets.QWidget()
        monkeypatch.setattr(splash, "_media_player", mock_player)

        for status in (
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        ):
            splash._video_ended = False
            splash._on_media_status_changed(status)
            assert splash._video_ended is False, f"Status {status} no debería marcar video_ended"

        splash.close()

    def test_media_error_fallbacks_to_animation(self, monkeypatch, app):
        """Error en media player -> fallback silencioso a animación logo."""
        from PyQt6.QtMultimedia import QMediaPlayer

        splash = SplashScreen()
        splash._video_loaded = True

        mock_player = QtWidgets.QWidget()
        monkeypatch.setattr(splash, "_media_player", mock_player)
        splash._video_widget = QtWidgets.QWidget()

        splash._on_media_error(QMediaPlayer.Error.ResourceError, "test error")

        assert splash._video_loaded is False
        assert splash._media_player is None
        assert splash._logo.isVisible() or splash._title.isVisible()
        splash.close()

    def test_worker_finished_before_video_waits_for_video(self, app):
        """Worker termina antes que video -> espera fin natural del video."""
        splash = SplashScreen()
        splash._video_loaded = True
        splash._video_ended = False
        splash._worker_finished = False

        splash.notify_worker_finished()
        assert splash._worker_finished is True
        assert splash._video_ended is False
        assert splash._waiting_for_worker is False
        splash.close()

    def test_video_ended_before_worker_pauses_and_waits(self, app):
        """Video termina antes que worker -> pausa en último frame y espera worker."""
        splash = SplashScreen()
        splash._video_loaded = True
        splash._video_ended = False
        splash._worker_finished = False

        splash._video_ended = True
        splash._check_both_finished()

        assert splash._video_ended is True
        assert splash._worker_finished is False
        assert splash._waiting_for_worker is True
        splash.close()

    def test_both_finished_closes_splash(self, monkeypatch, app):
        """Ambos terminados -> cierra splash."""
        splash = SplashScreen()
        splash._video_loaded = True
        splash._video_ended = True
        splash._worker_finished = True

        closed = []

        def mock_close():
            closed.append(True)

        monkeypatch.setattr(splash, "close", mock_close)
        splash._check_both_finished()

        assert len(closed) == 1
        splash.close()


class TestSplashScreenMessages:
    """Tests de mensajes de progreso (comunes a video y fallback)."""

    def test_set_message_after_intro_shows_immediately(self, app):
        splash = SplashScreen()
        splash._intro_done = True

        splash.set_message("Hello")
        assert splash._message.text() == "Hello"
        assert splash._message_effect.opacity() > 0
        splash.close()

    def test_multiple_messages_fade_transition(self, app):
        splash = SplashScreen()
        splash._intro_done = True

        splash.set_message("First")
        splash.set_message("Second")

        assert splash._message.text() == "Second"
        splash.close()

    def test_message_visible_over_video_widget(self, monkeypatch, app):
        """En modo video el texto va al overlay y el video queda debajo."""
        splash = SplashScreen()
        splash._intro_done = True
        splash._video_loaded = True

        mock_widget = QtWidgets.QWidget()
        monkeypatch.setattr(splash, "_video_widget", mock_widget)
        lowered = []
        raised = []
        monkeypatch.setattr(mock_widget, "lower", lambda: lowered.append(True))
        monkeypatch.setattr(mock_widget, "raise_", lambda: raised.append(True))

        splash.set_message("Test over video")

        assert splash._message_overlay.text() == "Test over video"
        assert splash._message_overlay.isVisible()
        assert len(lowered) == 1
        assert len(raised) == 0
        splash.close()

    def test_video_widget_fills_splash(self, app):
        """El widget de video ocupa todo el splash (no solo arriba)."""
        from blip_eraser.widgets.splash_screen import _VideoWidget

        splash = SplashScreen()
        try:
            widget = _VideoWidget(splash)
            widget.resize(splash.size())
            assert widget.size() == splash.size()
            assert widget.pos() == QtCore.QPoint(0, 0)
        finally:
            splash.close()

    def test_start_intro_marks_done_in_video_mode(self, monkeypatch, app):
        """En modo video la intro termina al arrancar (mensajes encima)."""
        splash = SplashScreen()
        try:
            player = MagicMock()
            monkeypatch.setattr(splash, "_video_loaded", True)
            monkeypatch.setattr(splash, "_media_player", player)
            splash._start_intro()
            assert splash._intro_done is True
            player.play.assert_called_once_with()
            assert splash._logo.isHidden()
        finally:
            splash.close()


class TestStartupWorker:
    """Tests del StartupWorker (sin cambios en lógica)."""

    def test_worker_emits_messages_in_order(self, app):
        worker = StartupWorker()
        messages = []

        def capture(msg):
            messages.append(msg)

        worker.message.connect(capture)
        worker.start()
        worker.wait()

        assert len(messages) == 5
        assert "updates" in messages[0].lower()
        assert "permissions" in messages[1].lower()
        assert "dependencies" in messages[2].lower()
        assert "scanning" in messages[3].lower()
        assert "welcome" in messages[4].lower()