"""Página 'Limpiador del sistema': AppImages/carpetas sueltas encontradas.

Usa utils.file_utils (scan_manual_entries) sobre las rutas configuradas
(utils.config) y borra con confirmación. Sin lógica de GUI en utils.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.config import get_scan_paths
from blip_eraser.utils.file_utils import (
    delete_path,
    human_size,
    path_size_for_display,
    scan_manual_entries,
)
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer


class CleanerPage(BasePage):
    def __init__(self):
        super().__init__()
        self._found: list[Path] = []
        self._visible: list[Path] = []
        self._filter = ""
        self._auto_scanned = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("personalize_hint"))
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_size")]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 36)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        # El checkbox de fila es la selección primaria.
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Checkbox del encabezado: seleccionar todo / ninguno.
        self.select_all_box = QCheckBox(header)
        self.select_all_box.setTristate(True)
        self.select_all_box.setToolTip(tr("select_all_tooltip"))
        self.select_all_box.toggled.connect(self._select_all_toggled)
        header.sectionResized.connect(lambda *_args: self._place_select_all())
        header.geometriesChanged.connect(self._place_select_all)
        self._place_select_all()

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(tr("refresh_button"))
        self.scan_btn.clicked.connect(self.scan)
        btn_row.addWidget(self.scan_btn)

        self.delete_btn = QPushButton(tr("delete_button"))
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)

        self.table.itemChanged.connect(self._update_header_state)

    def _place_select_all(self):
        """Posiciona el checkbox del encabezado sobre la columna de selección."""
        header = self.table.horizontalHeader()
        if header.isHidden():
            return
        x = header.sectionViewportPosition(0)
        w = header.sectionSize(0)
        if x < 0 or w <= 0:
            return
        box = self.select_all_box
        box.setGeometry(
            x + (w - box.width()) // 2,
            (header.height() - box.height()) // 2,
            box.width(),
            box.height(),
        )
        box.show()

    def _checked_rows(self) -> list[int]:
        """Filas visibles cuyas casillas están marcadas."""
        rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def _update_header_state(self):
        count = len(self._checked_rows())
        state = (
            Qt.CheckState.Checked
            if count and count == self.table.rowCount()
            else Qt.CheckState.Unchecked if count == 0 else Qt.CheckState.PartiallyChecked
        )
        self.select_all_box.blockSignals(True)
        self.select_all_box.setCheckState(state)
        self.select_all_box.blockSignals(False)

    def _select_all_toggled(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def retranslate(self):
        self.info_label.setText(tr("personalize_hint"))
        self.scan_btn.setText(tr("refresh_button"))
        self.delete_btn.setText(tr("delete_button"))
        self.select_all_box.setToolTip(tr("select_all_tooltip"))
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_size")]
        )
        self._update_header_state()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        # Escaneo automático la primera vez que se abre la página.
        if not self._auto_scanned:
            self._auto_scanned = True
            QTimer.singleShot(0, self.scan)

    def scan(self):
        try:
            self._found = scan_manual_entries(tuple(get_scan_paths()))
        except (OSError, PermissionError):
            self._found = []
        finally:
            log_buffer.add(tr("log_scan_finished").format(count=len(self._found)))
            self._render()

    def _render(self):
        if self._filter:
            self._visible = [p for p in self._found if self._filter in str(p).lower()]
        else:
            self._visible = list(self._found)

        self.table.setRowCount(len(self._visible))
        for row, path in enumerate(self._visible):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            size = path_size_for_display(path)
            self.table.setItem(row, 1, QTableWidgetItem(str(path)))
            self.table.setItem(row, 2, QTableWidgetItem(human_size(size)))
        self._update_header_state()

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def delete_selected(self):
        rows = self._checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr("manual_nothing_selected")
            )
            return

        paths = [self._visible[row] for row in rows]

        confirm = QMessageBox.question(
            self,
            tr("delete_confirm_title"),
            tr("delete_confirm_body").format(paths="\n".join(str(p) for p in paths)),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        errors = []
        for path in paths:
            try:
                delete_path(path)
            except (OSError, PermissionError) as e:
                errors.append(f"{path}: {e}")

        deleted = len(paths) - len(errors)
        if deleted:
            log_buffer.add(tr("log_deleted_items").format(count=deleted))
        if errors:
            QMessageBox.warning(self, tr("some_errors_title"), "\n".join(errors))
        else:
            QMessageBox.information(self, tr("done_title"), tr("items_deleted_ok"))

        self.scan()