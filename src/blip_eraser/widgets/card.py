"""Tarjeta con sombra pintada a mano (QPainter).

QSS no soporta `box-shadow` y `QGraphicsDropShadowEffect` reescribe el widget
entero a un pixmap en cada repintado (lento con listas con scroll). Aquí se
pinta una sombra suave apilando rectángulos redondeados semitransparentes
alrededor de la tarjeta, y encima el fondo y el borde del tema.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

SHADOW_BLUR = 10  # px de sombra a cada lado (zona reservada en los márgenes)
SHADOW_OFFSET_Y = 3
RADIUS = 12


class Card(QWidget):
    """Contenedor con fondo, borde y sombra del tema.

    Los hijos se colocan con un layout normal; `Card` reserva en
    `contentsMargins` el espacio de la sombra más el padding interno.
    """

    def __init__(self, parent: QWidget | None = None, padding: int = 16):
        super().__init__(parent)
        self.setObjectName("Card")
        self._panel = QColor("#151518")
        self._border = QColor("#2a2a30")
        self._dark = True
        self._padding = padding
        self._apply_margins()

    def _apply_margins(self) -> None:
        inset = SHADOW_BLUR + self._padding
        self.setContentsMargins(inset, inset - SHADOW_OFFSET_Y, inset, inset + SHADOW_OFFSET_Y)

    def set_padding(self, padding: int) -> None:
        self._padding = padding
        self._apply_margins()

    def set_theme(self, panel: str, border: str, dark: bool) -> None:
        self._panel = QColor(panel)
        self._border = QColor(border)
        self._dark = dark
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        body = QRectF(self.rect()).adjusted(
            SHADOW_BLUR, SHADOW_BLUR - SHADOW_OFFSET_Y, -SHADOW_BLUR, -SHADOW_BLUR - SHADOW_OFFSET_Y
        )

        # Sombra: capas concéntricas cada vez más tenues hacia afuera.
        base_alpha = 7 if self._dark else 5
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(SHADOW_BLUR, 0, -1):
            shadow = QColor(0, 0, 0 if self._dark else 30)
            shadow.setAlpha(base_alpha)
            painter.setBrush(shadow)
            painter.drawRoundedRect(
                body.adjusted(-i, -i + SHADOW_OFFSET_Y, i, i + SHADOW_OFFSET_Y),
                RADIUS + i,
                RADIUS + i,
            )

        painter.setBrush(self._panel)
        painter.setPen(QPen(self._border, 1))
        painter.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
