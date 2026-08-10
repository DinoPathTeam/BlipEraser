"""Gauge radial de salud del sistema — dibujado con QPainter.

Dibuja un anillo con barrer rojo (valor) sobre pista oscura, el porcentaje
en el centro, y encima un título ("SYSTEM HEALTH:") y debajo el estado
("GOOD" en verde). El valor (0-100) lo proporciona utils.apps.health_score.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

_ARC_START = 135  # grados
_ARC_SPAN = 270


class HealthGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._status = "—"
        self._accent = "#E53935"
        self._title = ""
        self.setMinimumSize(240, 210)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, int(value)))
        self.update()

    def set_accent(self, color: str) -> None:
        self._accent = color
        self.update()

    def set_status(self, status: str) -> None:
        self._status = status
        self.update()

    def set_title(self, title: str) -> None:
        self._title = title
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 40
        rect = QRectF(
            (self.width() - side) / 2,
            (self.height() - side) / 2 - 10,
            side,
            side,
        )

        # Anillo de fondo
        track_pen = QPen(QColor(64, 64, 68), 15)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, _ARC_START * 16, _ARC_SPAN * 16)

        # Anillo de valor
        value_pen = QPen(QColor(self._accent), 15)
        value_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(value_pen)
        span = int(_ARC_SPAN * self._value / 100)
        painter.drawArc(rect, _ARC_START * 16, -span * 16)

        # Título
        if self._title:
            painter.setPen(QColor(235, 235, 235))
            title_font = QFont(self.font())
            title_font.setPointSize(10)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.drawText(
                rect.adjusted(0, -28, 0, 0),
                Qt.AlignmentFlag.AlignCenter,
                self._title,
            )

        # Porcentaje central
        painter.setPen(QColor(245, 245, 245))
        percent_font = QFont(self.font())
        percent_font.setPointSize(30)
        percent_font.setBold(True)
        painter.setFont(percent_font)
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{self._value}%",
        )

        # Estado debajo del porcentaje
        if self._status:
            painter.setPen(QColor(60, 220, 120))
            status_font = QFont(self.font())
            status_font.setPointSize(12)
            status_font.setBold(True)
            painter.setFont(status_font)
            painter.drawText(
                rect.adjusted(0, 34, 0, 0),
                Qt.AlignmentFlag.AlignCenter,
                self._status,
            )