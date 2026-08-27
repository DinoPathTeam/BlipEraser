"""Pantalla de arranque (splash): video de intro + mensaje de progreso.

- Reproduce un video de introducción (splash-intro.mp4) si QtMultimedia
  está disponible y el archivo existe.
- Fallback silencioso a animación original (logo + fade) si falta
  QtMultimedia, el video no carga, o cualquier error en la reproducción.
- Comportamiento de timing:
  * El video se reproduce UNA vez a su duración natural.
  * El StartupWorker corre en paralelo.
  * Si el worker termina ANTES que el video: el video sigue hasta su fin.
  * Si el video termina ANTES que el worker: se PAUSA en el último frame
    (no loop, no negro) y espera al worker.
  * Los mensajes de progreso se superponen en la parte inferior con fade.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QThread,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.theme import THEMES, palette_for
from blip_eraser.widgets.logo import ASSET_LOGO_PATH, app_icon

SPLASH_WIDTH = 560
SPLASH_HEIGHT = 360
SPLASH_LOGO_HEIGHT = 150
_HERO_HEIGHT = 210

_STEP_PAUSE_MS = 400
_FINAL_PAUSE_MS = 600

_INTRO_LOGO_MS = 800
_INTRO_TITLE_MS = 600
_INTRO_TITLE_DELAY_MS = 200

_MSG_FADE_OUT_MS = 200
_MSG_FADE_IN_MS = 300

ASSET_SPLASH_VIDEO = (
    __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]
) + "/../assets/splash-intro.mp4"

_QMULTIMEDIA_AVAILABLE = False
try:
    from PyQt6.QtMultimedia import QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget

    _QMULTIMEDIA_AVAILABLE = True
except ImportError:
    QMediaPlayer = None
    QVideoWidget = None


class SplashScreen(QWidget):
    """Ventana sin marco: video de intro (o logo animado) + mensaje debajo."""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(SPLASH_WIDTH, SPLASH_HEIGHT)
        self.setObjectName("Splash")
        self.setWindowIcon(app_icon())

        theme_key = load_prefs().get("theme", "red")
        palette = palette_for(theme_key)
        accent = THEMES.get(theme_key, THEMES["red"])["accent"]

        self.setStyleSheet(
            f"QWidget#Splash {{ background-color: {palette['panel']}; "
            f"border: 1px solid {palette['border']}; border-radius: 12px; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 36, 32, 28)
        outer.setSpacing(20)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Área "hero" donde va el video o el logo animado
        self._hero = QWidget()
        self._hero.setFixedSize(SPLASH_WIDTH - 64, _HERO_HEIGHT)
        outer.addWidget(self._hero)

        # Componentes de fallback (logo animado original)
        self._logo = QLabel(self._hero)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel("BLIPERASER", self._hero)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color: {accent}; font-size: 32px; font-weight: bold; "
            "letter-spacing: 2px;"
        )

        # Componentes de video
        self._video_widget: QVideoWidget | None = None
        self._media_player: QMediaPlayer | None = None
        self._video_loaded = False
        self._video_ended = False
        self._worker_finished = False
        self._waiting_for_worker = False

        # Mensaje de progreso (común a ambos modos)
        self._message = QLabel("")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setStyleSheet(
            f"color: {accent}; font-size: 15px; font-weight: bold;"
        )
        outer.addWidget(self._message)

        self._message_effect = QGraphicsOpacityEffect(self._message)
        self._message.setGraphicsEffect(self._message_effect)
        self._message_effect.setOpacity(0.0)

        self._load_logo(accent)
        self._center_on_screen()

        self._logo_effect = QGraphicsOpacityEffect(self._logo)
        self._logo.setGraphicsEffect(self._logo_effect)
        self._logo_effect.setOpacity(0.0)

        self._title_effect = QGraphicsOpacityEffect(self._title)
        self._title.setGraphicsEffect(self._title_effect)
        self._title_effect.setOpacity(0.0)

        self._intro_anim: QSequentialAnimationGroup | None = None
        self._msg_fade_out: QPropertyAnimation | None = None
        self._msg_fade_in: QPropertyAnimation | None = None

        self._intro_done = False
        self._pending_message: str | None = None

        self._layout_hero_positions()
        self._setup_video_or_fallback()
        self._start_intro()

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
        painter.drawRoundedRect(QRect(10, 10, 140, 140), 32, 32)
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
        """Intenta configurar video; si falla, usa fallback de logo animado."""
        self._video_loaded = False

        if not _QMULTIMEDIA_AVAILABLE:
            self._video_widget = None
            self._media_player = None
            return

        try:
            from pathlib import Path

            video_path = Path(ASSET_SPLASH_VIDEO)
            if not video_path.exists():
                return

            self._video_widget = QVideoWidget(self._hero)
            self._video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._video_widget.setFixedSize(self._hero.size())
            self._video_widget.setStyleSheet("background: transparent;")
            self._video_widget.hide()

            self._media_player = QMediaPlayer(self)
            self._media_player.setVideoOutput(self._video_widget)
            self._media_player.setSource(QUrl.fromLocalFile(str(video_path)))
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._media_player.errorOccurred.connect(self._on_media_error)

            self._video_loaded = True

        except Exception:
            self._video_widget = None
            self._media_player = None
            self._video_loaded = False

    def _start_intro(self) -> None:
        if self._video_loaded and self._media_player and self._video_widget:
            self._logo.hide()
            self._title.hide()
            self._video_widget.show()
            self._media_player.play()
        else:
            self._start_fallback_animation()

    def _start_fallback_animation(self) -> None:
        """Animación original: logo+título deslizándose desde la derecha."""
        self._video_widget = None
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

    def _on_media_status_changed(self, status) -> None:
        if not self._media_player:
            return

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._video_ended = True
            # Pausar en último frame (no detener)
            self._media_player.pause()
            self._check_both_finished()

    def _on_media_error(self, error, error_string) -> None:
        # Fallback silencioso a animación original
        self._video_loaded = False
        if self._video_widget:
            self._video_widget.hide()
        if self._media_player:
            self._media_player.stop()
            self._media_player.deleteLater()
            self._media_player = None
        self._start_fallback_animation()

    def _check_both_finished(self) -> None:
        """Verifica si ambos (video + worker) han terminado para cerrar."""
        if self._video_ended and self._worker_finished:
            self.close()
        elif self._video_ended and not self._worker_finished:
            self._waiting_for_worker = True
        elif self._worker_finished and not self._video_ended:
            self._waiting_for_worker = False
            # El video sigue reproduciéndose; se cerrará en _on_media_status_changed

    def notify_worker_finished(self) -> None:
        """Llamado desde main cuando StartupWorker termina."""
        self._worker_finished = True
        self._check_both_finished()

    def _on_intro_finished(self) -> None:
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
        if self._msg_fade_out is not None:
            self._msg_fade_out.stop()
        if self._msg_fade_in is not None:
            self._msg_fade_in.stop()

        fade_out = QPropertyAnimation(self._message_effect, b"opacity", self)
        fade_out.setDuration(_MSG_FADE_OUT_MS)
        fade_out.setStartValue(self._message_effect.opacity())
        fade_out.setEndValue(0.0)

        def _swap_and_fade_in() -> None:
            self._message.setText(text)
            fade_in = QPropertyAnimation(self._message_effect, b"opacity", self)
            fade_in.setDuration(_MSG_FADE_IN_MS)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            self._msg_fade_in = fade_in
            fade_in.start()

        fade_out.finished.connect(_swap_and_fade_in)
        self._msg_fade_out = fade_out
        fade_out.start()

    def closeEvent(self, event) -> None:
        if self._media_player:
            self._media_player.stop()
        self.closed.emit()
        super().closeEvent(event)


class StartupWorker(QThread):
    message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_permissions_notice = False
        self.missing_lines: list[str] = []

    def run(self) -> None:
        from blip_eraser.utils.apps import list_installed_apps
        from blip_eraser.utils.dependency_check import check_pyqt6_available
        from blip_eraser.utils.permissions import should_show_permissions_notice
        from blip_eraser.utils.ui_text import localized_missing_lines
        from blip_eraser.utils.updates import check_for_updates

        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_check_updates"))
        check_for_updates()
        QThread.msleep(_STEP_PAUSE_MS)

        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_check_permissions"))
        self.show_permissions_notice = should_show_permissions_notice()
        QThread.msleep(_STEP_PAUSE_MS)

        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_check_dependencies"))
        check_pyqt6_available()
        self.missing_lines = localized_missing_lines(["pacman", "pkexec"])
        QThread.msleep(_STEP_PAUSE_MS)

        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_scanning"))
        list_installed_apps()
        QThread.msleep(_STEP_PAUSE_MS)

        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_welcome"))
        QThread.msleep(_FINAL_PAUSE_MS)