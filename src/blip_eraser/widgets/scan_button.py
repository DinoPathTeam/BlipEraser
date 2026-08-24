"""Botón pastilla 'SCAN NOW' con resplandor rojo e icono de lupa.

Widget autocontenido: dibuja una cápsula con el acento del tema, texto
principal (SCAN NOW) + subtítulo centrados, y una badge circular con
icono de lupa DEBAJO del texto (no a la derecha).
Emite `clicked` (QPushButton).
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
        # Altura mínima aumentada para acomodar título + subtítulo + ícono debajo
        self.setMinimumSize(240, 96)

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

        # Texto centrado en la parte superior (título + subtítulo)
        painter.setPen(QColor(255, 255, 255) if not disabled else QColor(255, 255, 255, 160))

        # Título
        title_font = QFont(self.font())
        title_font.setPointSize(13)
        title_font.setBold(True)
        painter.setFont(title_font)
        # Área superior para título + subtítulo (aprox. 60% de la altura)
        text_top_rect = QRectF(rect.left(), rect.top() + 8, rect.width(), rect.height() * 0.55)
        title_rect = QRectF(text_top_rect.left(), text_top_rect.top(), text_top_rect.width(), 26)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._title,
        )

        # Subtítulo
        sub_font = QFont(self.font())
        sub_font.setPointSize(8)
        painter.setFont(sub_font)
        sub_rect = QRectF(text_top_rect.left(), title_rect.bottom() + 2, text_top_rect.width(), 20)
        painter.drawText(
            sub_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._subtitle,
        )

        # Badge circular con icono DEBAJO del texto (centrado horizontalmente)
        # Colocado en la parte inferior (aprox. 40% de la altura)
        icon_bottom_y = rect.top() + rect.height() * 0.72
        badge_center_x = rect.center().x()
        badge_center_y = icon_bottom_y
        badge_rect = QRectF(badge_center_x - 18, badge_center_y - 18, 36, 36)

        painter.setBrush(QColor(255, 255, 255, 40))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(badge_rect)

        if not self._icon.isNull():
            pixmap = self._icon.pixmap(20, 20)
            painter.drawPixmap(
                int(badge_center_x - 10),
                int(badge_center_y - 10),
                pixmap,
            )

        painter.end()