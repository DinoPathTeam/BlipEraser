"""Logo del encabezado: imagen PNG de la marca o emblema vector de fallback.

Sustituye al texto "BlipEraser - vX.Y.Z" de la barra superior. Si existe
`src/blip_eraser/assets/BlipEraserLogo.png`, carga la imagen de la marca; de lo
contrario, genera el emblema dinámico con QPainter.
"""

from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

ASSET_LOGO_PATH = Path(__file__).parent.parent / "assets" / "BlipEraserLogo.png"


class AppLogo(QWidget):
    def __init__(self, accent: str = "#E53935", parent=None):
        super().__init__(parent)
        self._accent = QColor(accent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mark = QLabel()
        layout.addWidget(self._mark)

        self._wordmark = QLabel("BlipEraser")
        self._wordmark.setObjectName("AppTitle")
        layout.addWidget(self._wordmark)

        self._rebuild_mark()

    def _rebuild_mark(self) -> None:
        if ASSET_LOGO_PATH.exists():
            pixmap = QPixmap(str(ASSET_LOGO_PATH))
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(
                    36, Qt.TransformationMode.SmoothTransformation
                )
                self._mark.setPixmap(scaled)
                self._wordmark.hide()
                return

        self._wordmark.show()
        self._mark.setFixedSize(32, 32)
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