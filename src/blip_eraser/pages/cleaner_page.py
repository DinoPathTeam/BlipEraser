"""Página 'Limpiador del sistema': dos secciones independientes.

- "Limpieza recomendada": basura (~/.cache), caché de pacman y registros del
  sistema (/var/log), mostrando los elementos concretos de cada categoría
  (scan_cleanup_items) y no solo un total.
- "Aplicaciones instaladas" (manual): carpetas sueltas / AppImages del
  escaneo manual (scan_manual_entries).

Cada sección tiene su propio botón de refrescar y su propio 'Eliminar
seleccionados': refrescar o borrar en una no afecta a la otra. Ambas
comparten el diálogo de confirmación (widgets/confirm_dialog -> utils.confirm)
que categoriza lo seleccionado y destaca los borrados grandes. La lógica de
borrado real (delete_path) no se toca.
"""

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.config import get_scan_paths
from blip_eraser.utils.confirm import ConfirmItem, build_confirmation_plan
from blip_eraser.utils.file_utils import (
    human_size,
    path_size_for_display,
    scan_manual_entries,
)
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.scan import CLEANUP_CATEGORY_LABEL_KEYS, scan_cleanup_items
from blip_eraser.utils.scan_cache import (
    SECTION_CLEANER_MANUAL,
    SECTION_CLEANER_RECOMMENDED,
    is_stale,
    mark_scanned,
)
from blip_eraser.widgets.check_table import CheckTable
from blip_eraser.widgets.confirm_dialog import run_destructive_action


class _RecommendedSection(QWidget):
    """Sección (a): 'Limpieza recomendada' (basura + caché + registros)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._found: list[tuple[str, Path, int]] = []
        self._visible: list[tuple[str, Path, int]] = []
        self._filter = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.table = CheckTable(4)
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_category"), tr("col_name"), tr("col_size")]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        self.table.setColumnWidth(3, 110)
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("refresh_button"))
        self.refresh_btn.clicked.connect(self.scan)
        buttons.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton(tr("delete_button"))
        self.delete_btn.clicked.connect(self.delete_selected)
        buttons.addWidget(self.delete_btn)

        layout.addLayout(buttons)

    def retranslate(self):
        self.refresh_btn.setText(tr("refresh_button"))
        self.delete_btn.setText(tr("delete_button"))
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_category"), tr("col_name"), tr("col_size")]
        )
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        self._render()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        if is_stale(SECTION_CLEANER_RECOMMENDED):
            QTimer.singleShot(0, self.scan)

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------
    def scan(self):
        self._found = scan_cleanup_items()
        log_buffer.add(tr("log_cleanup_scanned").format(count=len(self._found)))
        self._render()
        mark_scanned(SECTION_CLEANER_RECOMMENDED)

    def _render(self):
        if self._filter:
            self._visible = [
                entry for entry in self._found if self._filter in str(entry[1]).lower()
            ]
        else:
            self._visible = list(self._found)

        self.table.setRowCount(0)
        for cat_key, path, size in self._visible:
            row = self.table.add_check_row()
            self.table.setItem(
                row, 1, QTableWidgetItem(tr(CLEANUP_CATEGORY_LABEL_KEYS.get(cat_key, "col_name")))
            )
            self.table.setItem(row, 2, QTableWidgetItem(str(path)))
            self.table.setItem(row, 3, QTableWidgetItem(human_size(size)))
        self.table.refresh_header_state()

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def delete_selected(self):
        rows = self.table.checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr("cleanup_nothing_selected")
            )
            return

        items = []
        for row in rows:
            cat_key, path, size = self._visible[row]
            items.append(
                ConfirmItem(
                    label=str(path),
                    category_label=tr(CLEANUP_CATEGORY_LABEL_KEYS.get(cat_key, "col_name")),
                    size_bytes=size,
                    paths=[path],
                )
            )

        run_destructive_action(
            self,
            build_confirmation_plan(items),
            tr("cleanup_confirm_title"),
            invalidate_sections=(SECTION_CLEANER_RECOMMENDED,),
        )
        self.scan()


class _ManualSection(QWidget):
    """Sección (b): 'Aplicaciones instaladas' (carpetas sueltas/AppImages).

    Reutiliza el patrón de checkboxes junto con el diálogo compartido.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._found: list[Path] = []
        self._visible: list[Path] = []
        self._filter = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.table = CheckTable(3)
        self.table.setHorizontalHeaderLabels(["", tr("col_name"), tr("col_size")])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        self.table.setColumnWidth(2, 110)
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("refresh_button"))
        self.refresh_btn.clicked.connect(self.scan)
        buttons.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton(tr("delete_button"))
        self.delete_btn.clicked.connect(self.delete_selected)
        buttons.addWidget(self.delete_btn)

        layout.addLayout(buttons)

    def retranslate(self):
        self.refresh_btn.setText(tr("refresh_button"))
        self.delete_btn.setText(tr("delete_button"))
        self.table.setHorizontalHeaderLabels(["", tr("col_name"), tr("col_size")])
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        self._render()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        if is_stale(SECTION_CLEANER_MANUAL):
            QTimer.singleShot(0, self.scan)

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------
    def scan(self):
        self._found = scan_manual_entries(tuple(get_scan_paths()))
        log_buffer.add(tr("log_scan_finished").format(count=len(self._found)))
        self._render()
        mark_scanned(SECTION_CLEANER_MANUAL)

    def _render(self):
        if self._filter:
            self._visible = [p for p in self._found if self._filter in str(p).lower()]
        else:
            self._visible = list(self._found)

        self.table.setRowCount(0)
        for path in self._visible:
            row = self.table.add_check_row()
            self.table.setItem(row, 1, QTableWidgetItem(str(path)))
            self.table.setItem(
                row, 2, QTableWidgetItem(human_size(path_size_for_display(path)))
            )
        self.table.refresh_header_state()

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def delete_selected(self):
        rows = self.table.checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr("manual_nothing_selected")
            )
            return

        items = [
            ConfirmItem(
                label=str(path),
                category_label=tr("kind_folder"),
                size_bytes=path_size_for_display(path),
                paths=[path],
            )
            for path in (self._visible[row] for row in rows)
        ]

        run_destructive_action(
            self,
            build_confirmation_plan(items),
            tr("delete_confirm_title"),
            invalidate_sections=(SECTION_CLEANER_MANUAL,),
        )
        self.scan()


class CleanerPage(BasePage):
    """Página del Limpiador: dos pestañas operables de forma independiente."""

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("cleaner_info"))
        layout.addWidget(self.info_label)

        self.tabs = QTabWidget()
        self.recommended = _RecommendedSection()
        self.manual = _ManualSection()
        self.tabs.addTab(self.recommended, tr("cleanup_rec_section"))
        self.tabs.addTab(self.manual, tr("cleanup_manual_section"))
        layout.addWidget(self.tabs, 1)

    def retranslate(self):
        self.info_label.setText(tr("cleaner_info"))
        self.tabs.setTabText(0, tr("cleanup_rec_section"))
        self.tabs.setTabText(1, tr("cleanup_manual_section"))
        self.recommended.retranslate()
        self.manual.retranslate()

    def set_search_filter(self, text: str):
        # Cada sección filtra su propia tabla; no comparten estado.
        self.recommended.set_search_filter(text)
        self.manual.set_search_filter(text)
