"""Página 'Desinstalador': aplicaciones instaladas con desinstalación.

Lista las aplicaciones detectadas (utils.apps.list_installed_apps) y
desinstala con privilegios según la fuente: pacman o borrado manual.
Presentación únicamente; la lógica vive en utils.
"""

from pathlib import Path

from PyQt6.QtCore import Qt
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
from blip_eraser.utils.apps import (
    InstalledApp,
    kind_label_key,
    list_installed_apps,
)
from blip_eraser.utils.file_utils import delete_path, human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.pacman import uninstall_packages

_COLUMNS = 6  # Sel | Nombre | Tipo | Detalle | Peso | Fecha


class UninstallerPage(BasePage):
    def __init__(self):
        super().__init__()
        self._apps: list[InstalledApp] = []
        self._visible: list[InstalledApp] = []
        self._filter = ""
        self._build_ui()
        self.load_apps()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("uninstaller_info"))
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, _COLUMNS)
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_type"), tr("col_detail"), tr("col_weight"), tr("col_date")]
        )
        header = self.table.horizontalHeader()
        # Columnas redimensionables arrastrando el borde (Interactive).
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        for idx, width in ((0, 36), (1, 200), (2, 130), (3, 320), (4, 90), (5, 130)):
            self.table.setColumnWidth(idx, width)
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
        self.refresh_btn = QPushButton(tr("refresh_button"))
        self.refresh_btn.clicked.connect(self.load_apps)
        btn_row.addWidget(self.refresh_btn)

        self.uninstall_btn = QPushButton(tr("uninstall_button_count").format(n=0))
        self.uninstall_btn.setEnabled(False)
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        btn_row.addWidget(self.uninstall_btn)

        layout.addLayout(btn_row)

        self.table.itemChanged.connect(self._update_uninstall_btn)

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

    def _update_uninstall_btn(self):
        """Contador dinámico 'Desinstalar seleccionados (N)' + estado del header."""
        count = len(self._checked_rows())
        self.uninstall_btn.setText(tr("uninstall_button_count").format(n=count))
        self.uninstall_btn.setEnabled(count > 0)
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

    # ------------------------------------------------------------------
    # BasePage
    # ------------------------------------------------------------------
    def retranslate(self):
        self.info_label.setText(tr("uninstaller_info"))
        self.refresh_btn.setText(tr("refresh_button"))
        self.uninstall_btn.setText(
            tr("uninstall_button_count").format(n=len(self._checked_rows()))
        )
        self.select_all_box.setToolTip(tr("select_all_tooltip"))
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_type"), tr("col_detail"), tr("col_weight"), tr("col_date")]
        )
        # Refresca el texto de la columna de tipo si ya hay datos cargados.
        self._render()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def load_apps(self):
        self._apps = list_installed_apps()
        self._render()

    def _render(self):
        if self._filter:
            self._visible = [
                app for app in self._apps if self._filter in app.name.lower()
            ]
        else:
            self._visible = list(self._apps)

        self.table.setRowCount(len(self._visible))
        for row, app in enumerate(self._visible):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(app.name))
            self.table.setItem(row, 2, QTableWidgetItem(tr(kind_label_key(app.kind))))
            self.table.setItem(row, 3, QTableWidgetItem(app.detail))
            self.table.setItem(
                row, 4, QTableWidgetItem(human_size(app.size_bytes) if app.size_bytes else "")
            )
            self.table.setItem(row, 5, QTableWidgetItem(app.install_date))
        self._update_uninstall_btn()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def uninstall_selected(self):
        rows = self._checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr("pacman_nothing_selected")
            )
            return

        apps = [self._visible[row] for row in rows]
        names = "\n".join(
            f"{app.name} ({app.detail})" if app.detail else app.name for app in apps
        )

        confirm = QMessageBox.question(
            self,
            tr("uninstaller_confirm_title"),
            tr("uninstaller_confirm_body").format(apps=names),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        errors = []
        for app in apps:
            try:
                if app.source == "pacman":
                    uninstall_packages([app.name])
                else:
                    delete_path(Path(app.detail))
            except (OSError, PermissionError) as e:
                errors.append(f"{app.name}: {e}")

        uninstalled = [app.name for app in apps]
        if uninstalled:
            log_buffer.add(
                tr("log_uninstalled_packages").format(packages=", ".join(uninstalled))
            )
        if errors:
            QMessageBox.warning(self, tr("some_errors_title"), "\n".join(errors))

        self.load_apps()

    def request_uninstall(self, name: str, source: str, detail: str = ""):
        """Desinstala por nombre+fuente+detalle (llamado desde Overview)."""
        confirm = QMessageBox.question(
            self,
            tr("uninstaller_confirm_title"),
            tr("uninstaller_confirm_body").format(apps=name),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            if source == "pacman":
                uninstall_packages([name])
            else:
                target = Path(detail) if detail else Path.home() / name
                delete_path(target)
        except (OSError, PermissionError) as e:
            QMessageBox.warning(self, tr("some_errors_title"), f"{name}: {e}")
            return
        log_buffer.add(tr("log_uninstalled_packages").format(packages=name))
        self.load_apps()