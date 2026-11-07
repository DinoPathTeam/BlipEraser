"""Gauge radial de salud del sistema — dibujado con QPainter.

Dibuja un anillo con barrer rojo (valor) sobre pista oscura, el porcentaje
en el centro (ligeramente por encima) y el estado debajo ("GOOD" en verde).
El valor (0-100) lo proporciona utils.apps.health_score. El título queda en
manos de la página (Overview), no se pinta dentro del círculo.
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
        self._text_color = "#ececef"
        self._track_color = QColor(64, 64, 68)
        self._status_color = QColor(60, 220, 120)
        self.setMinimumSize(240, 210)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, int(value)))
        self.update()

    def set_accent(self, color: str) -> None:
        self._accent = color
        self.update()

    def set_track_color(self, color: str) -> None:
        """Color de la pista del anillo (derivado del tema activo)."""
        self._track_color = QColor(color)
        self.update()

    def set_status_color(self, color: str) -> None:
        """Color del estado (GOOD/FAIR/POOR): más oscuro en temas claros."""
        self._status_color = QColor(color)
        self.update()

    def set_text_color(self, color: str) -> None:
        """Color del texto del porcentaje central.

        Debe derivarse del tema activo (`palette['text']`): un valor fijo
        claro solo es legible sobre fondo oscuro y desaparece en los temas
        Azul/Morado. El estado (GOOD/FAIR/POOR) mantiene su verde propio.
        """
        self._text_color = color
        self.update()

    def set_status(self, status: str) -> None:
        self._status = status
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
        track_pen = QPen(self._track_color, 15)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, _ARC_START * 16, _ARC_SPAN * 16)

        # Anillo de valor, con un halo tenue del mismo color debajo
        span = int(_ARC_SPAN * self._value / 100)
        if span > 0:
            halo = QColor(self._accent)
            halo.setAlpha(45)
            halo_pen = QPen(halo, 25)
            halo_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(halo_pen)
            painter.drawArc(rect, _ARC_START * 16, -span * 16)
        value_pen = QPen(QColor(self._accent), 15)
        value_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(value_pen)
        painter.drawArc(rect, _ARC_START * 16, -span * 16)

        # Porcentaje central (ligeramente por encima del centro)
        painter.setPen(QColor(self._text_color))
        percent_font = QFont(self.font())
        percent_font.setPointSize(28)
        percent_font.setBold(True)
        painter.setFont(percent_font)
        painter.drawText(
            rect.adjusted(0, -20, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._value}%",
        )

        # Estado debajo del porcentaje (separación mínima de ~10px)
        if self._status:
            painter.setPen(self._status_color)
            status_font = QFont(self.font())
            status_font.setPointSize(12)
            status_font.setBold(True)
            painter.setFont(status_font)
            painter.drawText(
                rect.adjusted(0, 38, 0, 0),
                Qt.AlignmentFlag.AlignCenter,
                self._status,
            )