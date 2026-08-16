"""QTableWidget con selección por checkbox y 'todo/ninguno' en el encabezado.

Encapsula el patrón repetido en Desinstalador y Limpiador: columna 0 con
casillas por fila, checkbox tristate flotando sobre el encabezado, estado
del encabezado sincronizado con las filas y consulta de filas marcadas.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


class CheckTable(QTableWidget):
    def __init__(self, columns: int, show_select_all: bool = True, parent=None):
        super().__init__(0, columns, parent)
        self._show_select_all = show_select_all
        self.select_all_box = QCheckBox(self.horizontalHeader())
        self.select_all_box.setObjectName("SelectAllCheck")
        self.select_all_box.setTristate(True)
        self.select_all_box.toggled.connect(self._select_all_toggled)
        self.select_all_box.setToolTip("")
        if not show_select_all:
            self.select_all_box.hide()

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 36)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # El checkbox de fila es la selección primaria.
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        header.sectionResized.connect(lambda *_args: self._place_select_all())
        header.geometriesChanged.connect(self._place_select_all)
        self.itemChanged.connect(self.refresh_header_state)
        self._place_select_all()

    # ------------------------------------------------------------------
    # Encabezado / selección
    # ------------------------------------------------------------------
    def checked_rows(self) -> list[int]:
        """Filas visibles cuyas casillas están marcadas."""
        rows = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def add_check_row(self) -> int:
        """Añade una fila nueva con checkbox desmarcado y devuelve su índice."""
        row = self.rowCount()
        self.setRowCount(row + 1)
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        check.setCheckState(Qt.CheckState.Unchecked)
        self.setItem(row, 0, check)
        return row

    def refresh_header_state(self) -> None:
        """Sincroniza el checkbox del encabezado con el estado de las filas."""
        count = len(self.checked_rows())
        state = (
            Qt.CheckState.Checked
            if count and count == self.rowCount()
            else Qt.CheckState.Unchecked if count == 0 else Qt.CheckState.PartiallyChecked
        )
        self.select_all_box.blockSignals(True)
        self.select_all_box.setCheckState(state)
        self.select_all_box.blockSignals(False)

    def _select_all_toggled(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def _place_select_all(self):
        """Posiciona el checkbox del encabezado sobre la columna de selección."""
        box = self.select_all_box
        if not self._show_select_all:
            box.hide()
            return
        header = self.horizontalHeader()
        if header.isHidden():
            return
        x = header.sectionViewportPosition(0)
        w = header.sectionSize(0)
        if x < 0 or w <= 0:
            return
        # Usar sizeHint: box.width()/height() devuelven el tamaño por defecto
        # de Qt (100x30) hasta que el widget se muestra y coloca, y al ser
        # autoresistente esa geometría queda desalineada (indicator fuera del
        # header). Con sizeHint el box se centra sobre la columna real.
        size = box.sizeHint()
        box.setGeometry(
            x + (w - size.width()) // 2,
            (header.height() - size.height()) // 2,
            size.width(),
            size.height(),
        )
        box.show()