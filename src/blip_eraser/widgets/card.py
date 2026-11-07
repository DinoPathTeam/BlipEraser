"""Tarjeta con sombra pintada a mano (QPainter).

QSS no soporta `box-shadow` y `QGraphicsDropShadowEffect` reescribe el widget
entero a un pixmap en cada repintado (lento con listas con scroll). Aquí se
pinta una sombra suave apilando rectángulos redondeados semitransparentes
alrededor de la tarjeta, y encima el fondo y el borde del tema.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
        self._shadow = True
        self._hover = QColor("#202026")
        self._accent_top = QColor("#D32F2F")
        self._accent_bot = QColor("#B71C1C")
        self._apply_margins()

    def _apply_margins(self) -> None:
        if not self._shadow:
            self.setContentsMargins(self._padding, self._padding, self._padding, self._padding)
            return
        inset = SHADOW_BLUR + self._padding
        self.setContentsMargins(inset, inset - SHADOW_OFFSET_Y, inset, inset + SHADOW_OFFSET_Y)

    def set_padding(self, padding: int) -> None:
        self._padding = padding
        self._apply_margins()

    def set_theme(
        self,
        panel: str,
        border: str,
        dark: bool,
        hover: str | None = None,
        accent_top: str | None = None,
        accent_bot: str | None = None,
    ) -> None:
        """Colores del tema. `hover`/`accent_*` los usan solo las variantes
        que los necesitan (StatTile); en Card base se ignoran."""
        self._panel = QColor(panel)
        self._border = QColor(border)
        self._dark = dark
        self._hover = QColor(hover) if hover else QColor(panel)
        if accent_top:
            self._accent_top = QColor(accent_top)
            self._accent_bot = QColor(accent_bot or accent_top)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        body = self._body_rect()
        if self._shadow:
            self._paint_shadow(painter, body)
        self._paint_body(painter, body)

    def _body_rect(self) -> QRectF:
        if not self._shadow:
            return QRectF(self.rect())
        return QRectF(self.rect()).adjusted(
            SHADOW_BLUR, SHADOW_BLUR - SHADOW_OFFSET_Y, -SHADOW_BLUR, -SHADOW_BLUR - SHADOW_OFFSET_Y
        )

    def _paint_shadow(self, painter: QPainter, body: QRectF) -> None:
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

    def _paint_body(self, painter: QPainter, body: QRectF) -> None:
        painter.setBrush(self._panel)
        painter.setPen(QPen(self._border, 1))
        painter.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)


class StatTile(Card):
    """Tarjeta de una cifra: etiqueta pequeña, valor grande y detalle de acento.

    Minimalista y válida en los 4 temas: una barra vertical con el degradado del
    tema a la izquierda y un resplandor tenue en la esquina superior derecha.
    `flat=True` la dibuja sin sombra y sobre el tono `hover` del tema, para
    usarla dentro de otra tarjeta.
    """

    def __init__(self, parent: QWidget | None = None, flat: bool = False):
        super().__init__(parent, padding=10 if flat else 14)
        self._flat = flat
        self._shadow = not flat
        self._apply_margins()
        self._label_text = ""
        self._value_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)  # deja sitio a la barra de acento
        layout.setSpacing(2)
        self.label = QLabel()
        self.label.setObjectName("SubText")
        self.value = QLabel()
        self.value.setObjectName("StatValue")
        layout.addStretch(1)
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addStretch(1)

    def set_stat(self, label: str, value: str) -> None:
        self._label_text = label
        self._value_text = value
        self.label.setText(label)
        self.value.setText(value)

    def setText(self, text: str) -> None:  # noqa: N802 - API tipo QLabel
        """Acepta 'Etiqueta: valor' (la forma que usaba el QLabel anterior)."""
        label, sep, value = text.partition(": ")
        if sep:
            self.set_stat(label, value)
        else:
            self.set_stat("", text)

    def text(self) -> str:
        """'Etiqueta: valor' (misma forma que el QLabel anterior)."""
        return f"{self._label_text}: {self._value_text}"

    def _paint_body(self, painter: QPainter, body: QRectF) -> None:
        fill = self._hover if self._flat else self._panel
        painter.setBrush(fill)
        painter.setPen(QPen(self._border, 1))
        inner = body.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(inner, RADIUS, RADIUS)

        # Resplandor tenue en la esquina superior derecha, recortado a la tarjeta.
        clip = QPainterPath()
        clip.addRoundedRect(inner, RADIUS, RADIUS)
        painter.save()
        painter.setClipPath(clip)
        glow = QColor(self._accent_top)
        glow.setAlpha(46 if self._dark else 34)
        radial = QRadialGradient(QPointF(inner.right() - 8, inner.top() + 8), inner.height() * 1.1)
        radial.setColorAt(0.0, glow)
        glow.setAlpha(0)
        radial.setColorAt(1.0, glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(radial)
        painter.drawRect(inner)
        painter.restore()

        # Barra de acento vertical con el degradado del tema.
        bar = QRectF(inner.left() + 10, inner.top() + 12, 4, inner.height() - 24)
        gradient = QLinearGradient(bar.topLeft(), bar.bottomLeft())
        gradient.setColorAt(0.0, self._accent_top)
        gradient.setColorAt(1.0, self._accent_bot)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(bar, 2, 2)
