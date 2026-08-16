"""Barra lateral de navegación: icono encima de texto con barra indicadora.

Usa un delegate que dibuja el icono del tema del sistema por encima de la
etiqueta (estilo de la imagen de referencia) y una barra de acento a la
izquierda en el elemento activo. Todos los colores se toman del tema.
"""

from PyQt6.QtCore import QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

from blip_eraser.utils.i18n import tr

_ICON_FALLBACK = "applications-other"
_ICON_SIZE = QSize(26, 26)


def tint_icon(icon: QIcon, color: str, size: QSize = _ICON_SIZE) -> QIcon:
    """Recolorea un ícono del tema del sistema con el color dado.

    `QIcon.fromTheme` puede devolver íconos *symbolic* (que Qt tiñe con la
    paleta) o íconos de color fijo incrustado (p. ej. `edit-clear` en blanco
    sobre fondo claro, invisible en Azul/Morado). Para garantizar legibilidad
    en los 4 temas, pintamos el asset con el color de ícono de la paleta
    activa (`palette['icon']`) preservando su alpha (forma).
    """
    pixmap = icon.pixmap(size)
    if pixmap.isNull():
        return icon
    tinted = QPixmap(size)
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return QIcon(tinted)


class _SidebarDelegate(QStyledItemDelegate):
    """Dibuja icono arriba, texto abajo, y resalta el elemento activo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = QColor("#E53935")
        self._active_bg = QColor("#E53935")
        self._hover = QColor("#202024")
        self._text = QColor("#9a9aa2")

    def apply_theme(self, accent: str, active_bg: str, hover: str, text: str) -> None:
        self._accent = QColor(accent)
        self._active_bg = QColor(active_bg)
        self._hover = QColor(hover)
        self._text = QColor(text)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        rect = QRectF(option.rect)

        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._active_bg)
            painter.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 8, 8)
            painter.setBrush(self._accent)
            painter.drawRoundedRect(QRectF(rect.left() + 6, rect.top() + 12, 4, rect.height() - 24), 2, 2)
        elif is_hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._hover)
            painter.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 8, 8)

        text_color = Qt.GlobalColor.white if is_selected else self._text

        base_x = option.rect.left() + option.rect.width() / 2
        icon_rect = QRect(
            int(base_x - _ICON_SIZE.width() / 2),
            option.rect.top() + 8,
            _ICON_SIZE.width(),
            _ICON_SIZE.height(),
        )
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, icon_rect)

        text_rect = QRect(
            option.rect.left(),
            option.rect.top() + _ICON_SIZE.height() + 10,
            option.rect.width(),
            option.rect.height() - _ICON_SIZE.height() - 14,
        )
        font = QFont(option.font)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, index.data(Qt.ItemDataRole.DisplayRole))

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width() if option.rect.width() else 96, 76)


class Sidebar(QListWidget):
    """Lista vertical con las secciones en orden fijo (5 entradas)."""

    SECTIONS = [
        ("overview", "nav_overview", "view-grid"),
        ("uninstaller", "nav_uninstaller", "edit-delete"),
        ("system_cleaner", "nav_system_cleaner", "edit-clear"),
        ("performance", "nav_performance", "preferences-system-performance"),
        ("tools", "nav_tools", "preferences-system"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setItemDelegate(_SidebarDelegate(self))
        self.setIconSize(_ICON_SIZE)
        self.setSpacing(4)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

        self._icon_color = "#ffffff"
        self._rows: list[tuple[int, str]] = []
        for row, (section, key, icon_name) in enumerate(self.SECTIONS):
            item = QListWidgetItem(tr(key))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addItem(item)
            self._rows.append((row, section))
        self.refresh_icons()
        self.setCurrentRow(0)

    def refresh_icons(self) -> None:
        """Recarga los iconos del tema del sistema, recoloreados por tema.

        Al construir, `QIcon.fromTheme` puede resolverse antes de que el
        QIconLoader esté listo (sin window aún, sin event loop) y devolver
        iconos vacíos que el delegate no pinta. Este método re-ejecuta la
        resolución y se invoca como parte del refresco completo de
        apariencia al arrancar y al cambiar tema/idioma.

        Además tiñe cada ícono con el color de ícono de la paleta activa:
        los íconos *symbolic* del tema del sistema ya heredan la paleta,
        pero los de color fijo (como `edit-clear`) se verían en blanco
        sobre los fondos claros (Azul/Morado). El tinte garantiza
        legibilidad en los 4 temas.
        """
        for row, (_section, _key, icon_name) in enumerate(self.SECTIONS):
            item = self.item(row)
            if item is None:
                continue
            icon = QIcon.fromTheme(icon_name, QIcon.fromTheme(_ICON_FALLBACK))
            item.setIcon(tint_icon(icon, self._icon_color))
        self.viewport().update()

    def set_icon_color(self, color: str) -> None:
        self._icon_color = color
        self.refresh_icons()

    def apply_theme(self, accent: str, active_bg: str, hover: str, text: str) -> None:
        delegate = self.itemDelegate()
        if isinstance(delegate, _SidebarDelegate):
            delegate.apply_theme(accent, active_bg, hover, text)
        self.viewport().update()

    def current_section(self) -> str:
        row = self.currentRow()
        for r, section in self._rows:
            if r == row:
                return section
        return self.SECTIONS[0][0]

    def retranslate(self) -> None:
        for row, (section, key, _icon) in enumerate(self.SECTIONS):
            self.item(row).setText(tr(key))
        self.viewport().update()