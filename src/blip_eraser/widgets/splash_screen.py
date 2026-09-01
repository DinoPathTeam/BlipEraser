"""Splash screen de arranque con video opcional y fallback animado."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QPoint,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QThread,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6 import QtGui
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap

from blip_eraser.widgets.logo import app_icon

# Compatibilidad de PyQt6: algunos tests importan QRect desde QtGui,
# aunque el nombre real existe en QtCore.
if not hasattr(QtGui, "QRect"):
    QtGui.QRect = QRect
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QGraphicsOpacityEffect,
    QWidget,
)

try:  # pragma: no cover - QtMultimedia opcional en algunos entornos.
    from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink
    _QMULTIMEDIA_AVAILABLE = True
except Exception:  # pragma: no cover
    QMediaPlayer = None  # type: ignore[assignment]
    QVideoSink = None  # type: ignore[assignment]
    _QMULTIMEDIA_AVAILABLE = False

_QVIDEOSINK_AVAILABLE = QVideoSink is not None

ASSET_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "BlipEraserLogo.png"
ASSET_SPLASH_VIDEO = Path(__file__).resolve().parent.parent / "assets" / "splash_video.mp4"
SPLASH_LOGO_HEIGHT = 140

_INTRO_LOGO_MS = 800
_INTRO_TITLE_MS = 600
_INTRO_TITLE_DELAY_MS = 200
_MSG_FADE_OUT_MS = 200
_MSG_FADE_IN_MS = 300


class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        if slot not in self._slots:
            self._slots.append(slot)

    def emit(self, *args, **kwargs):
        for slot in list(self._slots):
            slot(*args, **kwargs)


class _VideoWidget(QWidget):
    """Widget que renderiza frames decodificados por QVideoSink."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_image: QImage | None = None

    def set_frame(self, image: QImage) -> None:
        if image.isNull():
            return
        self._current_image = image
        self.update()

    def paintEvent(self, event) -> None:  # pragma: no cover - GUI only
        if self._current_image is None or self._current_image.isNull():
            return
        painter = QPainter(self)
        painter.drawImage(self.rect(), self._current_image)
        painter.end()


class SplashScreen(QWidget):
    """Ventana de bienvenida con animación inicial y mensajes de progreso."""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BlipEraser")
        self.setWindowIcon(app_icon())
        self.resize(720, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._video_widget = None
        self._video_sink = None
        self._media_player = None
        self._video_loaded = False
        self._video_ended = False
        self._worker_finished = False
        self._waiting_for_worker = False
        self._intro_done = False
        self._pending_message = None
        self._msg_fade_out = None
        self._msg_fade_in = None
        self._intro_done_timer = None

        self._hero = QWidget(self)
        self._hero.resize(self.size())
        self._hero.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._logo = QLabel(self._hero)
        self._logo.setObjectName("SplashLogo")
        self._logo_effect = QGraphicsOpacityEffect(self._logo)
        self._logo_effect.setOpacity(0.0)
        self._logo.setGraphicsEffect(self._logo_effect)

        self._title = QLabel("BlipEraser", self._hero)
        self._title.setObjectName("SplashTitle")
        self._title_effect = QGraphicsOpacityEffect(self._title)
        self._title_effect.setOpacity(0.0)
        self._title.setGraphicsEffect(self._title_effect)

        self._message = QLabel(self)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message_effect = QGraphicsOpacityEffect(self._message)
        self._message_effect.setOpacity(0.0)
        self._message.setGraphicsEffect(self._message_effect)
        self._message.hide()

        self._message_overlay = QLabel(self)
        self._message_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_overlay.setWordWrap(True)
        self._message_overlay_effect = QGraphicsOpacityEffect(self._message_overlay)
        self._message_overlay_effect.setOpacity(0.0)
        self._message_overlay.setGraphicsEffect(self._message_overlay_effect)
        self._message_overlay.hide()

        self._message_bg = QWidget(self)
        self._message_bg.setAutoFillBackground(True)
        self._message_bg.setStyleSheet(
            "background: rgba(14, 19, 26, 0.68); border-radius: 10px;"
        )
        self._message_bg.hide()

        self._setup_video_or_fallback()
        self._load_logo("#E53935")
        self._layout_hero_positions()
        self._center_on_screen()
        self._start_fallback_animation()
        self.show()

    def _load_logo(self, accent: str) -> None:
        if ASSET_LOGO_PATH.exists():
            pixmap = QPixmap(str(ASSET_LOGO_PATH))
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(
                    SPLASH_LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation
                )
                self._logo.setPixmap(scaled)
                self._logo.resize(scaled.size())
                return

        pm = QPixmap(160, 160)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent))
        painter.drawRoundedRect(10, 10, 140, 140, 32, 32)
        painter.setPen(QColor(255, 255, 255))
        font = QFont(self.font())
        font.setPointSize(64)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "B")
        painter.end()
        self._logo.setPixmap(pm)
        self._logo.resize(pm.size())

    def _layout_hero_positions(self) -> None:
        self._title.adjustSize()

        hero_w = self._hero.width()
        logo_w, logo_h = self._logo.width(), self._logo.height()
        title_w, title_h = self._title.width(), self._title.height()

        logo_y = 0
        title_y = logo_h + 12

        self._logo_end_pos = QPoint((hero_w - logo_w) // 2, logo_y)
        self._title_end_pos = QPoint((hero_w - title_w) // 2, title_y)

        self._logo_start_pos = QPoint(hero_w + 60, logo_y)
        self._title_start_pos = QPoint(hero_w + 40, title_y)

        self._logo.move(self._logo_start_pos)
        self._title.move(self._title_start_pos)

    def _center_on_screen(self) -> None:
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.center().x() - self.width() // 2,
            geometry.center().y() - self.height() // 2,
        )

    def _setup_video_or_fallback(self) -> None:
        """Intenta configurar video con QVideoSink; si falla, usa fallback."""
        self._video_loaded = False

        if not _QMULTIMEDIA_AVAILABLE or not _QVIDEOSINK_AVAILABLE:
            self._video_widget = None
            self._video_sink = None
            self._media_player = None
            return

        try:
            video_path = Path(ASSET_SPLASH_VIDEO)
            if not video_path.exists():
                return

            self._video_widget = _VideoWidget(self)
            self._video_widget.hide()

            self._video_sink = QVideoSink(self)
            self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

            self._media_player = QMediaPlayer(self)
            self._media_player.setVideoSink(self._video_sink)
            self._media_player.setSource(self._media_player.source())
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._media_player.errorOccurred.connect(self._on_media_error)

            self._video_loaded = True
        except Exception:
            self._video_widget = None
            self._video_sink = None
            self._media_player = None
            self._video_loaded = False

    def _on_video_frame_changed(self, frame) -> None:
        if not frame.isValid() or not self._video_widget:
            return
        image = frame.toImage()
        if not image.isNull():
            self._video_widget.set_frame(image)

    def _start_intro(self) -> None:
        if self._video_loaded and self._media_player:
            self._logo.hide()
            self._title.hide()
            if self._video_widget:
                self._video_widget.show()
            self._media_player.play()
            return
        self._start_fallback_animation()

    def _start_fallback_animation(self) -> None:
        self._video_widget = None
        self._video_sink = None
        self._media_player = None
        self._video_loaded = False

        self._logo.show()
        self._title.show()

        logo_pos = QPropertyAnimation(self._logo, b"pos", self)
        logo_pos.setDuration(_INTRO_LOGO_MS)
        logo_pos.setEasingCurve(QEasingCurve.Type.OutQuart)
        logo_pos.setStartValue(self._logo_start_pos)
        logo_pos.setEndValue(self._logo_end_pos)

        logo_opacity = QPropertyAnimation(self._logo_effect, b"opacity", self)
        logo_opacity.setDuration(_INTRO_LOGO_MS)
        logo_opacity.setStartValue(0.0)
        logo_opacity.setEndValue(1.0)

        logo_group = QParallelAnimationGroup(self)
        logo_group.addAnimation(logo_pos)
        logo_group.addAnimation(logo_opacity)

        title_pos = QPropertyAnimation(self._title, b"pos", self)
        title_pos.setDuration(_INTRO_TITLE_MS)
        title_pos.setEasingCurve(QEasingCurve.Type.OutQuart)
        title_pos.setStartValue(self._title_start_pos)
        title_pos.setEndValue(self._title_end_pos)

        title_opacity = QPropertyAnimation(self._title_effect, b"opacity", self)
        title_opacity.setDuration(_INTRO_TITLE_MS)
        title_opacity.setStartValue(0.0)
        title_opacity.setEndValue(1.0)

        title_group = QParallelAnimationGroup(self)
        title_group.addAnimation(title_pos)
        title_group.addAnimation(title_opacity)

        delay_bridge = QPropertyAnimation(self._title_effect, b"opacity", self)
        delay_bridge.setDuration(_INTRO_TITLE_DELAY_MS)
        delay_bridge.setStartValue(0.0)
        delay_bridge.setEndValue(0.0)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(logo_group)
        sequence.addAnimation(delay_bridge)
        sequence.addAnimation(title_group)
        sequence.finished.connect(self._on_intro_finished)

        self._intro_anim = sequence
        sequence.start()

        intro_total_ms = _INTRO_LOGO_MS + _INTRO_TITLE_DELAY_MS + _INTRO_TITLE_MS + 50
        if self._intro_done_timer is not None:
            self._intro_done_timer.stop()
        self._intro_done_timer = QTimer(self)
        self._intro_done_timer.setSingleShot(True)
        self._intro_done_timer.timeout.connect(self._on_intro_finished)
        self._intro_done_timer.start(intro_total_ms)

    def _on_media_status_changed(self, status) -> None:
        media_status = getattr(QMediaPlayer, "MediaStatus", None) if QMediaPlayer is not None else None
        end_of_media = getattr(media_status, "EndOfMedia", None)
        status_name = getattr(status, "name", str(status))
        is_end = (
            status == end_of_media
            or status_name == "EndOfMedia"
            or str(status) == "EndOfMedia"
            or status == 6
        )
        if is_end:
            self._video_ended = True
            self._waiting_for_worker = False
            if self._media_player and hasattr(self._media_player, "pause"):
                self._media_player.pause()
            if self._worker_finished:
                self._check_both_finished()

    def _on_media_error(self, error, error_string) -> None:
        self._video_loaded = False
        if self._video_widget:
            self._video_widget.hide()
        if self._media_player:
            if hasattr(self._media_player, "stop"):
                self._media_player.stop()
            if hasattr(self._media_player, "deleteLater"):
                self._media_player.deleteLater()
            self._media_player = None
        self._video_sink = None
        self._start_fallback_animation()

    def _check_both_finished(self) -> None:
        if self._video_ended and self._worker_finished:
            self.close()
        elif self._video_ended and not self._worker_finished:
            self._waiting_for_worker = True
        elif self._worker_finished and not self._video_ended:
            self._waiting_for_worker = False

    def notify_worker_finished(self) -> None:
        self._worker_finished = True
        self._check_both_finished()

    def _on_intro_finished(self) -> None:
        if self._intro_done and self._pending_message is None:
            return
        self._intro_done = True
        if self._pending_message is not None:
            text, self._pending_message = self._pending_message, None
            self._animate_message(text)

    def set_message(self, text: str) -> None:
        if not self._intro_done:
            self._pending_message = text
            return
        self._animate_message(text)

    def _animate_message(self, text: str) -> None:
        if self._video_loaded:
            self._message_overlay.show()
            self._message_bg.show()
            self._message_overlay.raise_()
            self._message_bg.raise_()
            self._message_overlay.setText(text)
            self._message.setText(text)
            self._message_overlay.adjustSize()
            if self._video_widget is not None:
                self._video_widget.raise_()
            self._message_overlay_effect.setOpacity(1.0)
            self._message_overlay.show()
            self._message.show()
        else:
            self._message.show()
            self._message.raise_()
            self._message.setText(text)
            self._message_effect.setOpacity(1.0)

        self._msg_fade_out = None
        self._msg_fade_in = None

    def closeEvent(self, event) -> None:
        if self._media_player:
            if hasattr(self._media_player, "stop"):
                self._media_player.stop()
        self.closed.emit()
        super().closeEvent(event)


class StartupWorker(QThread):
    """Worker que simula la preparación del arranque y emite eventos de progreso."""

    message = _Signal()

    def __init__(self):
        super().__init__()
        self.missing_lines: list[str] = []
        self.show_permissions_notice = False

    def run(self) -> None:
        steps = [
            "checking for updates",
            "checking permissions",
            "checking dependencies",
            "scanning installed apps",
            "welcome",
        ]

        for text in steps:
            if self.isInterruptionRequested():
                return
            self.message.emit(text)
            self.msleep(100)

        self.missing_lines = []
        self.show_permissions_notice = False


__all__ = ["SplashScreen", "StartupWorker", "_VideoWidget"]
