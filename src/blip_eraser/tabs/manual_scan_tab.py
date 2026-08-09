"""Pestaña 'Escaneo manual' — GUI sobre utils.file_utils.

Todo el escaneo, cálculo de tamaños y borrado vive en file_utils
(lógica pura, testable sin GUI). Aquí solo queda la presentación; los
textos visibles se resuelven con tr() y se refrescan con retranslate().
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.utils.file_utils import (
    delete_path,
    human_size,
    path_size_for_display,
    scan_manual_entries,
)
from blip_eraser.utils.i18n import tr


class ManualScanTab(QWidget):
    def __init__(self):
        super().__init__()
        self._found_paths: list[Path] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("manual_tab_info"))
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([tr("col_path"), tr("col_size")])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(tr("scan_button"))
        self.scan_btn.clicked.connect(self.scan_folders)
        btn_row.addWidget(self.scan_btn)

        self.delete_btn = QPushButton(tr("delete_button"))
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)

    def retranslate(self):
        """Refresca los textos estáticos tras cambiar el idioma."""
        self.info_label.setText(tr("manual_tab_info"))
        self.scan_btn.setText(tr("scan_button"))
        self.delete_btn.setText(tr("delete_button"))
        self.table.setHorizontalHeaderLabels([tr("col_path"), tr("col_size")])

    def scan_folders(self):
        self.table.setRowCount(0)
        self._found_paths = []
        try:
            self._found_paths = scan_manual_entries()
        except (OSError, PermissionError):
            pass

        self.table.setRowCount(len(self._found_paths))
        for row, path in enumerate(self._found_paths):
            size = path_size_for_display(path)
            self.table.setItem(row, 0, QTableWidgetItem(str(path)))
            self.table.setItem(row, 1, QTableWidgetItem(human_size(size)))

    def delete_selected(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.information(
                self,
                tr("nothing_selected_title"),
                tr("manual_nothing_selected"),
            )
            return

        paths = [self._found_paths[row] for row in selected_rows]

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

        if errors:
            QMessageBox.warning(
                self,
                tr("some_errors_title"),
                "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self,
                tr("done_title"),
                tr("items_deleted_ok"),
            )

        self.scan_folders()