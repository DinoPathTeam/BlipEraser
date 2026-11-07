"""Barra lateral de navegación: entradas de texto con píldora de degradado.

Un delegate dibuja cada entrada (texto a la izquierda) y, en la activa, una
píldora con el degradado del tema. Los iconos se siguen cargando (API
estable) pero ya no se dibujan. Todos los colores se toman del tema.
"""

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QSizePolicy, QStyle, QStyledItemDelegate

from blip_eraser.utils.i18n import tr

_ICON_FALLBACK = "applications-other"
_ICON_SIZE = QSize(28, 28)
_ROW_HEIGHT = 44

# Assets propios para sidebar (opcionales, fallback silencioso si faltan)
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_SIDEBAR_ASSETS = {
    "overview": _ASSETS_DIR / "sidebar-overview.png",
    "uninstaller": _ASSETS_DIR / "sidebar-uninstaller.png",
    "system_cleaner": _ASSETS_DIR / "sidebar-system-cleaner.png",
    "performance": _ASSETS_DIR / "sidebar-performance.jpg",
    "tools": _ASSETS_DIR / "sidebar-tools.jpg",
}


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
    """Dibuja el texto de cada entrada y resalta la activa con un degradado."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = QColor("#E53935")
        self._active_bg = QColor("#E53935")
        self._hover = QColor("#202024")
        self._text = QColor("#9a9aa2")
        self._on_accent = QColor("#ffffff")
        self._fill_top = QColor("#E53935")
        self._fill_bot = QColor("#E53935")

    def apply_theme(
        self,
        accent: str,
        active_bg: str,
        hover: str,
        text: str,
        on_accent: str = "#ffffff",
        fill_top: str | None = None,
        fill_bot: str | None = None,
    ) -> None:
        self._accent = QColor(accent)
        self._active_bg = QColor(active_bg)
        self._hover = QColor(hover)
        self._text = QColor(text)
        self._on_accent = QColor(on_accent)
        self._fill_top = QColor(fill_top or active_bg)
        self._fill_bot = QColor(fill_bot or active_bg)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        rect = QRectF(option.rect)
        body = rect.adjusted(4, 1, -4, -1)

        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            gradient = QLinearGradient(body.topLeft(), body.bottomLeft())
            gradient.setColorAt(0.0, self._fill_top)
            gradient.setColorAt(1.0, self._fill_bot)
            painter.setBrush(gradient)
            painter.drawRoundedRect(body, 8, 8)
            # Reflejo superior fino: da volumen al degradado.
            sheen = QColor(255, 255, 255, 40)
            painter.setPen(QPen(sheen, 1))
            painter.drawLine(
                QPointF(body.left() + 8, body.top() + 0.5), QPointF(body.right() - 8, body.top() + 0.5)
            )
        elif is_hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._hover)
            painter.drawRoundedRect(body, 8, 8)

        font = QFont(option.font)
        font.setBold(is_selected)
        painter.setFont(font)
        painter.setPen(self._on_accent if is_selected else self._text)
        text_rect = body.adjusted(14, 0, -8, 0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            index.data(Qt.ItemDataRole.DisplayRole),
        )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width() if option.rect.width() else 190, _ROW_HEIGHT)


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
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._icon_color = "#ffffff"
        self._rows: list[tuple[int, str]] = []
        for row, (section, key, icon_name) in enumerate(self.SECTIONS):
            item = QListWidgetItem(tr(key))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addItem(item)
            self._rows.append((row, section))
        self.refresh_icons()
        self.setCurrentRow(0)
        # Altura justa al contenido: el espacio libre de la barra lateral
        # queda para la actividad reciente.
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed)
        self.setFixedHeight(
            self.count() * (self.sizeHintForRow(0) + 2 * self.spacing()) + 2 * self.frameWidth()
        )

    def refresh_icons(self) -> None:
        """Recarga los iconos: primero assets propios (color completo, sin tinte),
        luego tema del sistema con tinte por paleta.

        Los assets propios (en `src/blip_eraser/assets/sidebar-*.jpg|png`) son
        opcionales. Si existen y cargan, se usan TAL CUAL (sin tint_icon),
        para que se vean igual en los 4 temas. Si no existen o fallan,
        caen al comportamiento original: QIcon.fromTheme con tint_icon.
        """
        for row, (section, _key, icon_name) in enumerate(self.SECTIONS):
            item = self.item(row)
            if item is None:
                continue

            asset_path = _SIDEBAR_ASSETS.get(section)
            icon = None
            if asset_path and asset_path.exists():
                pixmap = QPixmap(str(asset_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        _ICON_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    icon = QIcon(scaled)

            if icon is None:
                theme_icon = QIcon.fromTheme(icon_name, QIcon.fromTheme(_ICON_FALLBACK))
                icon = tint_icon(theme_icon, self._icon_color)

            item.setIcon(icon)

        self.viewport().update()

    def set_icon_color(self, color: str) -> None:
        self._icon_color = color
        self.refresh_icons()

    def apply_theme(self, accent: str, active_bg: str, hover: str, text: str, **colors: str) -> None:
        delegate = self.itemDelegate()
        if isinstance(delegate, _SidebarDelegate):
            delegate.apply_theme(accent, active_bg, hover, text, **colors)
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