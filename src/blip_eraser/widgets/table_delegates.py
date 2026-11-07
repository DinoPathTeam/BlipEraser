"""Delegados de celda para las tablas del rediseño.

- `TagDelegate`: dibuja el tipo (Aplicación / Dependencia / Carpeta suelta)
  como una etiqueta con contorno, igual que en la Vista general.
- `SubTextDelegate`: texto atenuado (columnas secundarias).

Los colores salen del tema activo; la ventana principal los actualiza con
`set_theme_colors` al aplicar un tema (los delegados los leen al pintar).
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

KIND_ROLE = Qt.ItemDataRole.UserRole

_colors = {
    "subtext": "#a1a1aa",
    "tags": {"app": "#4CAF50", "dep": "#FFB300", "folder": "#42A5F5"},
}
_KIND_TO_TAG = {"app": "app", "dependency": "dep", "folder": "folder"}


def set_theme_colors(subtext: str, tags: dict[str, str]) -> None:
    """Actualiza los colores que usan todos los delegados."""
    _colors["subtext"] = subtext
    _colors["tags"] = dict(tags)


def _draw_item_base(delegate: QStyledItemDelegate, painter, option, index, text: str = "") -> None:
    """Fondo/selección de la celda sin texto (lo dibuja quien llama)."""
    opt = QStyleOptionViewItem(option)
    delegate.initStyleOption(opt, index)
    opt.text = text
    opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay
    style = opt.widget.style() if opt.widget is not None else QApplication.style()
    style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)


class SubTextDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index) -> None:  # noqa: N802 - API de Qt
        super().initStyleOption(option, index)
        option.palette.setColor(option.palette.ColorRole.Text, QColor(_colors["subtext"]))
        option.palette.setColor(option.palette.ColorRole.HighlightedText, QColor(_colors["subtext"]))


class TagDelegate(QStyledItemDelegate):
    """Etiqueta con contorno para la columna Tipo (el tipo va en `KIND_ROLE`)."""

    def paint(self, painter: QPainter, option, index) -> None:
        kind = index.data(KIND_ROLE)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not kind or not text:
            super().paint(painter, option, index)
            return
        _draw_item_base(self, painter, option, index)

        color = QColor(_colors["tags"].get(_KIND_TO_TAG.get(kind, "folder"), "#42A5F5"))
        font = QFont(option.font)
        font.setPointSizeF(max(7.0, option.font.pointSizeF() - 1.5))
        font.setBold(True)
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance(text) + 16
        height = metrics.height() + 4
        rect = QRectF(
            option.rect.left() + 4,
            option.rect.top() + (option.rect.height() - height) / 2,
            min(width, option.rect.width() - 8),
            height,
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), height / 2.2, height / 2.2)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()
