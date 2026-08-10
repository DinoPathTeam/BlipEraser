"""Página 'Limpiador del sistema': AppImages/carpetas sueltas encontradas.

Usa utils.file_utils (scan_manual_entries) sobre las rutas configuradas
(utils.config) y borra con confirmación. Sin lógica de GUI en utils.
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
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("personalize_hint"))
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([tr("col_name"), tr("col_size")])
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
        self.scan_btn.clicked.connect(self.scan)
        btn_row.addWidget(self.scan_btn)

        self.delete_btn = QPushButton(tr("delete_button"))
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)

    def retranslate(self):
        self.info_label.setText(tr("personalize_hint"))
        self.scan_btn.setText(tr("scan_button"))
        self.delete_btn.setText(tr("delete_button"))
        self.table.setHorizontalHeaderLabels([tr("col_name"), tr("col_size")])

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------
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
            size = path_size_for_display(path)
            self.table.setItem(row, 0, QTableWidgetItem(str(path)))
            self.table.setItem(row, 1, QTableWidgetItem(human_size(size)))

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def delete_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
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