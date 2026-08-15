"""Pantalla de arranque (splash): logo centrado + mensaje de progreso.

Se muestra ANTES de construir MainWindow. `StartupWorker` (QThread) ejecuta
los pasos de preparación (actualizaciones, permisos, dependencias y un
escaneo de referencia) en un hilo separado y va emitiendo mensajes que el
splash pinta entre paso y paso; al terminar, `main` construye y muestra la
ventana principal y cierra el splash.

Ningún paso toca widgets: solo lógica pura (subprocess / lectura de
archivos), por lo que el QThread no arriesga carreras con la GUI.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.theme import THEMES, palette_for
from blip_eraser.widgets.logo import ASSET_LOGO_PATH

SPLASH_WIDTH = 560
SPLASH_HEIGHT = 360
SPLASH_LOGO_HEIGHT = 150

# Pausa entre pasos (en el hilo de trabajo, NO bloquea la GUI): da tiempo
# al event loop a pintar cada mensaje antes de que llegue el siguiente.
_STEP_PAUSE_MS = 400
_FINAL_PAUSE_MS = 600


class SplashScreen(QWidget):
    """Ventana sin marco con el logo y un QLabel de mensaje actualizable."""

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 36, 32, 28)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._logo = QLabel()
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._logo)

        self._message = QLabel("")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setStyleSheet(f"color: {accent}; font-size: 15px; font-weight: bold;")
        layout.addWidget(self._message)

        self._load_logo(accent)
        self._center_on_screen()

    def _load_logo(self, accent: str) -> None:
        if ASSET_LOGO_PATH.exists():
            pixmap = QPixmap(str(ASSET_LOGO_PATH))
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(
                    SPLASH_LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation
                )
                self._logo.setPixmap(scaled)
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

    def set_message(self, text: str) -> None:
        """Actualiza el mensaje de progreso que se muestra bajo el logo."""
        self._message.setText(text)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class StartupWorker(QThread):
    """Ejecuta los pasos de arranque y emite el mensaje de cada uno.

    Los resultados de los chequeos se guardan como atributos para que
    `main` los consuma sin repetir el trabajo (y sin duplicar el chequeo
    de binarios que antes corría en MainWindow).
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