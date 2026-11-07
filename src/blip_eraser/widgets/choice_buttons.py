"""Botones de elección sincronizados con un QComboBox.

El QComboBox sigue siendo el modelo (y la API pública de la página: tests,
señales, persistencia); este widget lo oculta y lo muestra como una fila de
botones excluyentes (muestras de color o chips). Cambiar el combo —por código
o con un clic— actualiza los botones y viceversa.
"""

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QButtonGroup, QComboBox, QGridLayout, QPushButton, QWidget


def dot_icon(color: str, size: int = 14) -> QIcon:
    """Círculo relleno del color dado (muestra de tema)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return QIcon(pixmap)


class ChoiceButtons(QWidget):
    """Fila (o rejilla) de botones que refleja un QComboBox."""

    def __init__(
        self,
        combo: QComboBox,
        object_name: str,
        columns: int = 0,
        icon_for: Callable[[object], QIcon | None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("Plain")
        self._combo = combo
        self._object_name = object_name
        self._columns = columns
        self._icon_for = icon_for
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        combo.hide()
        combo.currentIndexChanged.connect(self._sync_checked)
        self.rebuild()

    def rebuild(self) -> None:
        """Crea los botones a partir de los elementos actuales del combo."""
        for btn in self._buttons:
            self._group.removeButton(btn)
            self._grid.removeWidget(btn)
            btn.deleteLater()
        self._buttons = []
        for index in range(self._combo.count()):
            btn = QPushButton(self._combo.itemText(index))
            btn.setObjectName(self._object_name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if self._icon_for is not None:
                icon = self._icon_for(self._combo.itemData(index))
                if icon is not None:
                    btn.setIcon(icon)
            btn.clicked.connect(lambda _=False, i=index: self._combo.setCurrentIndex(i))
            self._group.addButton(btn)
            row, col = (0, index) if not self._columns else divmod(index, self._columns)
            self._grid.addWidget(btn, row, col)
            self._buttons.append(btn)
        if self._columns:
            for col in range(self._columns):
                self._grid.setColumnStretch(col, 1)
        self._sync_checked()

    def retranslate(self) -> None:
        for index, btn in enumerate(self._buttons):
            btn.setText(self._combo.itemText(index))

    def _sync_checked(self, *_args) -> None:
        current = self._combo.currentIndex()
        for index, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(index == current)
            btn.blockSignals(False)

    def buttons(self) -> list[QPushButton]:
        return list(self._buttons)
