"""Botón principal 'SCAN NOW': rectángulo redondeado con degradado y lupa.

Widget autocontenido: dibuja el degradado del tema con un resplandor suave,
icono de lupa a la izquierda y título + subtítulo. Mismo lenguaje visual que
la píldora activa de la barra lateral. Emite `clicked` (QPushButton).
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QPushButton


class ScanNowButton(QPushButton):
    def __init__(self, title: str, subtitle: str, icon_name: str = "system-search", parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon = QIcon.fromTheme(icon_name)
        self._accent = QColor("#E53935")
        self._on_accent = QColor(255, 255, 255)
        self._fill_top: QColor | None = None
        self._fill_bot: QColor | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Altura con margen real: título + subtítulo arriba, badge abajo
        # sin solape (el subtítulo ES largo invadía el círculo).
        self.setMinimumSize(250, 68)

    def set_texts(self, title: str, subtitle: str):
        self._title = title
        self._subtitle = subtitle
        self.update()

    def set_accent(
        self,
        color: str,
        on_accent: str = "#ffffff",
        fill_top: str | None = None,
        fill_bot: str | None = None,
    ):
        self._accent = QColor(color)
        self._on_accent = QColor(on_accent)
        self._fill_top = QColor(fill_top) if fill_top else None
        self._fill_bot = QColor(fill_bot) if fill_bot else None
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Margen para el resplandor, que se pinta fuera del botón.
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        disabled = not self.isEnabled()

        # Resplandor suave (acento del tema activo, nunca un color fijo).
        if not disabled:
            for i, alpha in enumerate((18, 30, 46)):
                glow = QColor(self._accent)
                glow.setAlpha(alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow)
                grow = 6 - i * 2
                painter.drawRoundedRect(rect.adjusted(-grow, -grow, grow, grow), 12 + grow, 12 + grow)

        if self._fill_top is not None and self._fill_bot is not None:
            top, bot = QColor(self._fill_top), QColor(self._fill_bot)
        else:
            top = bot = QColor(self._accent)
        if disabled:
            top.setAlpha(120)
            bot.setAlpha(120)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bot)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 12, 12)
        # Reflejo superior fino, como en la píldora de la barra lateral.
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawLine(
            QPointF(rect.left() + 10, rect.top() + 0.5), QPointF(rect.right() - 10, rect.top() + 0.5)
        )

        text_color = QColor(self._on_accent)
        if disabled:
            text_color.setAlpha(160)
        painter.setPen(text_color)

        # Icono de lupa a la izquierda; título y subtítulo centrados en el resto.
        text_left = rect.left()
        if not self._icon.isNull():
            painter.drawPixmap(int(rect.left() + 14), int(rect.center().y() - 10), self._icon.pixmap(20, 20))
            text_left = rect.left() + 38

        title_font = QFont(self.font())
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        title_rect = QRectF(text_left, rect.top() + 9, rect.right() - text_left - 8, 22)
        painter.drawText(
            title_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self._title
        )

        sub_font = QFont(self.font())
        sub_font.setPointSize(8)
        painter.setFont(sub_font)
        sub_rect = QRectF(text_left, title_rect.bottom() + 1, rect.right() - text_left - 8, 18)
        painter.drawText(
            sub_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self._subtitle
        )
