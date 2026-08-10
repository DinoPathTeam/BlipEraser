"""Logo del encabezado: emblema pintado + wordmark 'BlipEraser'.

Sustituye al texto "BlipEraser - vX.Y.Z" de la barra superior. El emblema
se genera con QPainter (cuadro redondeado con acento, banda inferior y
letra 'B'); la versión pasa a mostrarse en la barra de título y en la
sección 'Acerca de' de la página de Ayuda.
"""

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class AppLogo(QWidget):
    def __init__(self, accent: str = "#E53935", parent=None):
        super().__init__(parent)
        self._accent = QColor(accent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mark = QLabel()
        self._mark.setFixedSize(32, 32)
        layout.addWidget(self._mark)

        self._wordmark = QLabel("BlipEraser")
        self._wordmark.setObjectName("AppTitle")
        layout.addWidget(self._wordmark)

        self._rebuild_mark()

    def _rebuild_mark(self) -> None:
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._accent)
        painter.drawRoundedRect(QRect(4, 4, 56, 56), 14, 14)

        painter.setBrush(self._accent.darker(150))
        painter.drawRoundedRect(QRect(8, 46, 48, 10), 5, 5)

        painter.setPen(QColor(255, 255, 255))
        font = QFont(self.font())
        font.setPointSize(30)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "B")
        painter.end()

        self._mark.setPixmap(
            pm.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def set_accent(self, accent: str) -> None:
        self._accent = QColor(accent)
        self._rebuild_mark()
        self.update()