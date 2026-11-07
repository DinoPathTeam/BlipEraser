"""Botón pastilla 'SCAN NOW' con resplandor rojo e icono de lupa.

Widget autocontenido: dibuja una cápsula con el acento del tema, texto
principal (SCAN NOW) + subtítulo centrados, y una badge circular con
icono de lupa DEBAJO del texto (no a la derecha).
Emite `clicked` (QPushButton).
"""

from PyQt6.QtCore import QRectF, Qt
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
        self.setMinimumSize(264, 136)

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
        # Margen de 12 px: el resplandor se pinta fuera de la cápsula y, sin
        # él, el widget lo recortaba en una caja cuadrada.
        rect = QRectF(self.rect()).adjusted(12, 12, -12, -12)

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
        painter.drawRoundedRect(rect, 34, 34)

        # Texto centrado en la parte superior (título + subtítulo)
        text_color = QColor(self._on_accent)
        if disabled:
            text_color.setAlpha(160)
        painter.setPen(text_color)

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

        # Badge con icono DEBAJO del texto (centrado horizontalmente).
        # Círculo de 32px con centro a 26px del borde inferior: deja ~14px
        # de aire bajo el subtítulo. Sin relleno (transparencia total),
        # solo el icono de lupa.
        badge_d = 32
        badge_center_x = rect.center().x()
        badge_center_y = rect.bottom() - 8 - badge_d / 2

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)

        if not self._icon.isNull():
            pixmap = self._icon.pixmap(20, 20)
            painter.drawPixmap(
                int(badge_center_x - 10),
                int(badge_center_y - 10),
                pixmap,
            )

        painter.end()