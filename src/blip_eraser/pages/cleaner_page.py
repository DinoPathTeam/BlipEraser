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
from blip_eraser.utils.log import write_diagnostic
from blip_eraser.utils.scan import CLEANUP_CATEGORY_LABEL_KEYS, scan_cleanup_items
from blip_eraser.utils.scan_cache import (
    SECTION_CLEANER_MANUAL,
    SECTION_CLEANER_RECOMMENDED,
    is_stale,
    mark_scanned,
)
from blip_eraser.widgets.check_table import CheckTable
from blip_eraser.widgets.confirm_dialog import run_destructive_action
from blip_eraser.widgets.scan_worker import BackgroundScanMixin


class _SectionBase(QWidget, BackgroundScanMixin):
    """Base común de las secciones del Limpiador (recomendada y manual).

    Ambas comparten esqueleto (tabla + refrescar/eliminar + scan en fondo +
    defensa dura); solo cambian la fuente de datos, las columnas y los
    textos. Los hooks a implementar están marcados abajo.
    """

    # -- hooks (subclase) -------------------------------------------------
    _columns: int = 0
    _cache_section: str = ""
    _forensic: str = ""

    def _headers(self) -> list[str]:
        raise NotImplementedError

    def _scan_source(self):
        """Callable sin args que devuelve la lista encontrada."""
        raise NotImplementedError

    def _log_key(self) -> str:
        raise NotImplementedError

    def _matches(self, item, needle: str) -> bool:
        raise NotImplementedError

    def _cells(self, item) -> list[str]:
        """Textos de las celdas (sin contar la columna 0 del checkbox)."""
        raise NotImplementedError

    def _nothing_key(self) -> str:
        raise NotImplementedError

    def _confirm_title_key(self) -> str:
        raise NotImplementedError

    def _confirm_items(self, rows: list[int]) -> list[ConfirmItem]:
        raise NotImplementedError

    def _results_updated(self) -> None:
        """Hook tras recibir resultados (la manual invalida su caché de tamaños)."""

    # -- esqueleto compartido ----------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self._found: list = []
        self._visible: list = []
        self._filter = ""
        self._build_ui()
        self._init_scan_buttons([self.refresh_btn, self.delete_btn])

        write_diagnostic(
            f"Cleaner{self._forensic.title()}Section CREATED id={id(self)} table_id={id(self.table)}"
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.table = CheckTable(self._columns)
        self.table.setHorizontalHeaderLabels(self._headers())
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(70)
        for col in range(1, self._columns):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        self.table.setColumnWidth(self._columns - 1, 110)
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
        self.table.setHorizontalHeaderLabels(self._headers())
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        self._render()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        # Guard en vuelo (igual que Desinstalador): no apilar hilos al
        # volver a la pestaña mientras el escaneo anterior sigue corriendo.
        if is_stale(self._cache_section) and not getattr(self, "_scanning", False):
            QTimer.singleShot(0, self.scan)

    def scan(self):
        self._start_background_scan(self._scan_source(), self._on_scan_ready)

    def _on_scan_ready(self, entries: list):
        # Defensa dura de TODA la cadena del resultado (la pila dice cuál falló).
        try:
            self._found = entries
            self._results_updated()
            log_buffer.add(tr(self._log_key()).format(count=len(self._found)))
            self._render()
            mark_scanned(self._cache_section)
        except RuntimeError as exc:
            self._render_failure(
                f"cleaner_{self._forensic}._on_scan_ready",
                exc,
                table=self.table,
                extra={"entries_total": len(self._found)},
            )

    def _render(self):
        if self._filter:
            self._visible = [e for e in self._found if self._matches(e, self._filter)]
        else:
            self._visible = list(self._found)

        try:
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            for item in self._visible:
                row = self.table.add_check_row()
                for col, text in enumerate(self._cells(item), start=1):
                    self.table.setItem(row, col, QTableWidgetItem(text))
            self.table.blockSignals(False)
            self.table.refresh_header_state()
        except RuntimeError as exc:
            # Defensa dura (mismo patrón que el crash de Overview en CachyOS):
            # la tabla puede morir en C++ con la sección viva; no tumba la app.
            self._render_failure(
                f"cleaner_{self._forensic}._render",
                exc,
                table=self.table,
                extra={"rows": len(self._visible)},
            )

    def delete_selected(self):
        rows = self.table.checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr(self._nothing_key())
            )
            return

        run_destructive_action(
            self,
            build_confirmation_plan(self._confirm_items(rows)),
            tr(self._confirm_title_key()),
            invalidate_sections=(self._cache_section,),
            on_finished=lambda _ok: self.scan(),
        )


class _RecommendedSection(_SectionBase):
    """Sección (a): 'Limpieza recomendada' (basura + caché + registros)."""

    _columns = 4
    _cache_section = SECTION_CLEANER_RECOMMENDED
    _forensic = "recommended"

    def _headers(self):
        return ["", tr("col_category"), tr("col_name"), tr("col_size")]

    def _scan_source(self):
        return scan_cleanup_items

    def _log_key(self):
        return "log_cleanup_scanned"

    def _matches(self, item, needle):
        return needle in str(item[1]).lower()

    def _cells(self, item):
        cat_key, path, size = item
        return [
            tr(CLEANUP_CATEGORY_LABEL_KEYS.get(cat_key, "col_name")),
            str(path),
            human_size(size),
        ]

    def _nothing_key(self):
        return "cleanup_nothing_selected"

    def _confirm_title_key(self):
        return "cleanup_confirm_title"

    def _confirm_items(self, rows):
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
        return items


class _ManualSection(_SectionBase):
    """Sección (b): 'Aplicaciones instaladas' (carpetas sueltas/AppImages)."""

    _columns = 3
    _cache_section = SECTION_CLEANER_MANUAL
    _forensic = "manual"

    def __init__(self, parent=None):
        # Tamaños cacheados por ruta: evita I/O a disco en cada tecla de filtro.
        self._sizes: dict[Path, int] = {}
        super().__init__(parent)

    def _results_updated(self) -> None:
        self._sizes.clear()

    def _headers(self):
        return ["", tr("col_name"), tr("col_size")]

    def _scan_source(self):
        return lambda: scan_manual_entries(tuple(get_scan_paths()))

    def _log_key(self):
        return "log_scan_finished"

    def _matches(self, item, needle):
        return needle in str(item).lower()

    def _size_of(self, path: Path) -> int:
        if path not in self._sizes:
            self._sizes[path] = path_size_for_display(path)
        return self._sizes[path]

    def _cells(self, item):
        return [str(item), human_size(self._size_of(item))]

    def _nothing_key(self):
        return "manual_nothing_selected"

    def _confirm_title_key(self):
        return "delete_confirm_title"

    def _confirm_items(self, rows):
        return [
            ConfirmItem(
                label=str(path),
                category_label=tr("kind_folder"),
                size_bytes=self._size_of(path),
                paths=[path],
            )
            for path in (self._visible[row] for row in rows)
        ]


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
