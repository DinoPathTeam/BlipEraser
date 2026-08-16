"""Pantalla de arranque (splash): logo animado + mensaje de progreso.

Animación de entrada: el logo y el título "BLIPERASER" se deslizan desde
la derecha con fade-in. Los mensajes de progreso del StartupWorker se
encolan mientras la animación de entrada corre y se muestran (con su
propio fade) apenas esta termina, para no competir visualmente con ella.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QRect,
    QSequentialAnimationGroup,
    QThread,
    Qt,
    pyqtSignal,
)
from PyQt6.QtCore import QPropertyAnimation
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.theme import THEMES, palette_for
from blip_eraser.widgets.logo import ASSET_LOGO_PATH

SPLASH_WIDTH = 560
SPLASH_HEIGHT = 360
SPLASH_LOGO_HEIGHT = 150

# Altura del área donde viven logo + título, animados a mano (sin layout).
_HERO_HEIGHT = 210

_STEP_PAUSE_MS = 400
_FINAL_PAUSE_MS = 600

_INTRO_LOGO_MS = 800
_INTRO_TITLE_MS = 600
_INTRO_TITLE_DELAY_MS = 200

_MSG_FADE_OUT_MS = 200
_MSG_FADE_IN_MS = 300


class SplashScreen(QWidget):
    """Ventana sin marco: logo+título animados de entrada, mensaje debajo."""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(SPLASH_WIDTH, SPLASH_HEIGHT)
        self.setObjectName("Splash")

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

        # Área "hero" (logo + título) SIN layout: los widgets hijos se
        # posicionan a mano con setGeometry/move, porque un QVBoxLayout
        # activo pelearía contra cualquier QPropertyAnimation sobre `pos`
        # (el layout reimpone su propia posición en cada recálculo).
        self._hero = QWidget()
        self._hero.setFixedSize(SPLASH_WIDTH - 64, _HERO_HEIGHT)
        outer.addWidget(self._hero)

        self._logo = QLabel(self._hero)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel("BLIPERASER", self._hero)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color: {accent}; font-size: 32px; font-weight: bold; "
            "letter-spacing: 2px;"
        )

        self._message = QLabel("")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setStyleSheet(
            f"color: {accent}; font-size: 15px; font-weight: bold;"
        )
        outer.addWidget(self._message)

        # Opacidad animable para logo, título y mensaje.
        self._logo_effect = QGraphicsOpacityEffect(self._logo)
        self._logo.setGraphicsEffect(self._logo_effect)
        self._logo_effect.setOpacity(0.0)

        self._title_effect = QGraphicsOpacityEffect(self._title)
        self._title.setGraphicsEffect(self._title_effect)
        self._title_effect.setOpacity(0.0)

        self._message_effect = QGraphicsOpacityEffect(self._message)
        self._message.setGraphicsEffect(self._message_effect)
        self._message_effect.setOpacity(0.0)

        self._load_logo(accent)
        self._center_on_screen()

        # Referencias vivas: sin esto, el GC de Python puede destruir las
        # QPropertyAnimation a mitad de vuelo y la animación se corta.
        self._intro_anim: QSequentialAnimationGroup | None = None
        self._msg_fade_out: QPropertyAnimation | None = None
        self._msg_fade_in: QPropertyAnimation | None = None

        # Mientras la animación de entrada corre, cualquier set_message()
        # que llegue del StartupWorker se guarda aquí en vez de mostrarse
        # de inmediato, para no competir visualmente con la entrada.
        self._intro_done = False
        self._pending_message: str | None = None

        self._layout_hero_positions()
        self._start_intro_animation()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
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
        """Coloca logo y título en sus posiciones FINALES (centradas).

        Usa sizeHint()/resize() en vez de width()/height() leídos antes de
        mostrar el widget: para un QLabel con pixmap o texto ya asignado,
        el tamaño de contenido está disponible de inmediato, sin depender
        de que la ventana se haya pintado (a diferencia de leer width() de
        un widget recién construido, que devuelve el tamaño por defecto).
        """
        self._title.adjustSize()

        hero_w = self._hero.width()
        logo_w, logo_h = self._logo.width(), self._logo.height()
        title_w, title_h = self._title.width(), self._title.height()

        logo_y = 0
        title_y = logo_h + 12

        self._logo_end_pos = QPoint((hero_w - logo_w) // 2, logo_y)
        self._title_end_pos = QPoint((hero_w - title_w) // 2, title_y)

        # Posición de arranque: fuera del hero, a la derecha.
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

    # ------------------------------------------------------------------
    # Animación de entrada
    # ------------------------------------------------------------------
    def _start_intro_animation(self) -> None:
        """Logo desde la derecha (800ms), luego título (600ms, +200ms delay)."""
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

        # Secuencial real (no QTimer suelto): logo primero, título después,
        # con un pequeño respiro entre ambos vía una animación "puente" de
        # opacidad nula sobre el propio efecto del título (duración = delay).
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

    def _on_intro_finished(self) -> None:
        self._intro_done = True
        if self._pending_message is not None:
            text, self._pending_message = self._pending_message, None
            self._animate_message(text)

    # ------------------------------------------------------------------
    # Mensajes de progreso
    # ------------------------------------------------------------------
    def set_message(self, text: str) -> None:
        """Actualiza el mensaje de progreso.

        Si la animación de entrada todavía está corriendo, el mensaje se
        guarda y se muestra apenas termine (no se pisan las dos animaciones
        a la vez). Una vez terminada la entrada, cada mensaje nuevo hace
        fade-out del anterior y fade-in del nuevo.
        """
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
        self.closed.emit()
        super().closeEvent(event)


class StartupWorker(QThread):
    """Ejecuta los pasos de arranque y emite el mensaje de cada uno.

    Los resultados de los chequeos se guardan como atributos para que
    `main` los consuma sin repetir el trabajo.
    """

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

        # 1. Actualizaciones: stub sin red, avanza casi de inmediato.
        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_check_updates"))
        check_for_updates()
        QThread.msleep(_STEP_PAUSE_MS)

        # 2. Permisos: se comprueba, pero el diálogo se muestra al final.
        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_check_permissions"))
        self.show_permissions_notice = should_show_permissions_notice()
        QThread.msleep(_STEP_PAUSE_MS)

        # 3. Dependencias: el chequeo de binarios vive aquí (no se duplica
        #    en MainWindow); el aviso se muestra cuando la ventana esté lista.
        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_check_dependencies"))
        check_pyqt6_available()
        self.missing_lines = localized_missing_lines(["pacman", "pkexec"])
        QThread.msleep(_STEP_PAUSE_MS)

        # 4. Escaneo de referencia: trabajo real, resultado descartado.
        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_scanning"))
        list_installed_apps()
        QThread.msleep(_STEP_PAUSE_MS)

        # 5. Bienvenida.
        if self.isInterruptionRequested():
            return
        self.message.emit(tr("splash_welcome"))
        QThread.msleep(_FINAL_PAUSE_MS)