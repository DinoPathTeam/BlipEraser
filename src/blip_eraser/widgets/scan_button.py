"""Botón pastilla 'SCAN NOW' con resplandor rojo e icono en badge.

Widget autocontenido: dibuja una cápsula con el acento del tema, texto
principal (SCAN NOW) + subtítulo centrados, y una badge circular con
icono de lupa a la derecha. Emite `clicked` (QPushButton).
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PyQt6.QtWidgets import QPushButton


class ScanNowButton(QPushButton):
    def __init__(self, title: str, subtitle: str, icon_name: str = "system-search", parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon = QIcon.fromTheme(icon_name)
        self._accent = QColor("#E53935")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(240, 64)

    def set_texts(self, title: str, subtitle: str):
        self._title = title
        self._subtitle = subtitle
        self.update()

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        disabled = not self.isEnabled()

        # Resplandor: varios trazos con alpha decreciente (usa el acento
        # del tema activo, nunca un color fijo).
        if not disabled:
            for i, alpha in enumerate((40, 70, 110)):
                glow_color = QColor(self._accent)
                glow_color.setAlpha(alpha)
                glow_pen = QPen(glow_color)
                glow_pen.setWidth(6 + i * 3)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-i - 2, -i - 2, i + 2, i + 2), 34, 34)

        # Relleno de la cápsula
        fill = QColor(self._accent)
        if disabled:
            fill.setAlpha(120)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 34, 34)

        # Texto central
        painter.setPen(QColor(255, 255, 255) if not disabled else QColor(255, 255, 255, 160))
        title_font = QFont(self.font())
        title_font.setPointSize(13)
        title_font.setBold(True)
        painter.setFont(title_font)
        text_center = rect.center()
        painter.drawText(
            QRectF(rect.left(), text_center.y() - 22, rect.width() - 52, 22),
            Qt.AlignmentFlag.AlignCenter,
            self._title,
        )
        sub_font = QFont(self.font())
        sub_font.setPointSize(8)
        painter.setFont(sub_font)
        painter.drawText(
            QRectF(rect.left(), text_center.y(), rect.width() - 52, 18),
            Qt.AlignmentFlag.AlignCenter,
            self._subtitle,
        )

        # Badge circular con icono a la derecha
        badge_x = rect.right() - 26
        badge_center = (badge_x, rect.center().y())
        badge_rect = QRectF(badge_center[0] - 18, badge_center[1] - 18, 36, 36)
        painter.setBrush(QColor(255, 255, 255, 40))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(badge_rect)
        if not self._icon.isNull():
            pixmap = self._icon.pixmap(20, 20)
            painter.drawPixmap(
                int(badge_center[0] - 10),
                int(badge_center[1] - 10),
                pixmap,
            )
        painter.end()