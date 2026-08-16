"""Página 'Desinstalador': aplicaciones instaladas con desinstalación.

Lista las aplicaciones detectadas (utils.apps.list_installed_apps) y
desinstala con privilegios según la fuente: pacman o borrado manual.
Presentación únicamente; la lógica vive en utils. La confirmación usa el
diálogo compartido (widgets/confirm_dialog, basado en utils.confirm), el
mismo que el Limpiador del sistema.
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
    QVBoxLayout,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.apps import (
    KIND_APP,
    KIND_FOLDER,
    InstalledApp,
    kind_label_key,
    list_installed_apps,
)
from blip_eraser.utils.confirm import ConfirmItem, build_confirmation_plan
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.pacman import uninstall_packages
from blip_eraser.utils.scan_cache import SECTION_UNINSTALLER, is_stale, mark_scanned
from blip_eraser.widgets.check_table import CheckTable
from blip_eraser.widgets.confirm_dialog import run_destructive_action
from blip_eraser.widgets.scan_worker import BackgroundScanMixin

_COLUMNS = 6  # Sel | Nombre | Tipo | Detalle | Peso | Fecha


def _manual_target(app: InstalledApp) -> Path:
    """Ruta real a borrar para una app manual (carpeta suelta/AppImage)."""
    return Path(app.detail) if app.detail else Path.home() / app.name


class UninstallerPage(BasePage, BackgroundScanMixin):
    def __init__(self):
        super().__init__()
        self._apps: list[InstalledApp] = []
        self._visible: list[InstalledApp] = []
        self._filter = ""
        self._build_ui()
        self._init_scan_buttons([self.refresh_btn, self.uninstall_btn])

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("uninstaller_info"))
        layout.addWidget(self.info_label)

        # Sin checkbox de "seleccionar todo" en el encabezado: el
        # Desinstalador solo permite selección manual (una a una o
        # arrastrando) para evitar desinstalaciones masivas accidentales.
        self.table = CheckTable(_COLUMNS, show_select_all=False)
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_type"), tr("col_detail"), tr("col_weight"), tr("col_date")]
        )
        header = self.table.horizontalHeader()
        # Columnas redimensionables arrastrando el borde (Interactive).
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        for idx, width in ((1, 200), (2, 130), (3, 320), (4, 90), (5, 130)):
            self.table.setColumnWidth(idx, width)
        layout.addWidget(self.table)

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

    def _update_uninstall_btn(self):
        """Contador dinámico 'Desinstalar seleccionados (N)' + estado del header."""
        count = len(self.table.checked_rows())
        self.uninstall_btn.setText(tr("uninstall_button_count").format(n=count))
        # Durante un escaneo en segundo plano el botón queda deshabilitado
        # (el mixin lo re-habilita al llegar el resultado).
        self.uninstall_btn.setEnabled(count > 0 and not self._scanning)
        self.table.refresh_header_state()

    # ------------------------------------------------------------------
    # BasePage
    # ------------------------------------------------------------------
    def retranslate(self):
        self.info_label.setText(tr("uninstaller_info"))
        self.refresh_btn.setText(tr("refresh_button"))
        self.uninstall_btn.setText(
            tr("uninstall_button_count").format(n=len(self.table.checked_rows()))
        )
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        self.table.setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_type"), tr("col_detail"), tr("col_weight"), tr("col_date")]
        )
        # Refresca el texto de la columna de tipo si ya hay datos cargados.
        self._render()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        # Escaneo automático al mostrar la página solo si el caché está
        # viciado (primera vez, timeout de 5 min, o invalidado tras una
        # desinstalación). El botón "Actualizar lista" escanea siempre.
        if is_stale(SECTION_UNINSTALLER):
            QTimer.singleShot(0, self.load_apps)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def load_apps(self):
        self._start_background_scan(list_installed_apps, self._on_apps_loaded)

    def _on_apps_loaded(self, apps: list[InstalledApp]):
        self._apps = apps
        self._render()
        mark_scanned(SECTION_UNINSTALLER)

    def _render(self):
        if self._filter:
            self._visible = [
                app for app in self._apps if self._filter in app.name.lower()
            ]
        else:
            self._visible = list(self._apps)

        self.table.setRowCount(0)
        for app in self._visible:
            row = self.table.add_check_row()
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
        rows = self.table.checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr("pacman_nothing_selected")
            )
            return

        apps = [self._visible[row] for row in rows]
        items: list[ConfirmItem] = []

        pacman_names = [a.name for a in apps if a.source == "pacman"]
        manual_apps = [a for a in apps if a.source != "pacman"]

        if pacman_names:
            # Un solo `pkexec pacman -Rns` para todo el lote (una autenticación).
            items.append(
                ConfirmItem(
                    label=", ".join(pacman_names),
                    category_label=tr("kind_app"),
                    size_bytes=sum(
                        (a.size_bytes or 0) for a in apps if a.source == "pacman"
                    ),
                    remove=lambda: uninstall_packages(pacman_names),
                )
            )
        for app in manual_apps:
            target = _manual_target(app)
            items.append(
                ConfirmItem(
                    label=app.name,
                    category_label=tr(kind_label_key(app.kind)),
                    size_bytes=app.size_bytes or 0,
                    paths=[target],
                )
            )

        plan = build_confirmation_plan(items)
        if run_destructive_action(
            self, plan, tr("uninstaller_confirm_title"),
            invalidate_sections=(SECTION_UNINSTALLER,),
        ):
            log_buffer.add(
                tr("log_uninstalled_packages").format(
                    packages=", ".join(a.name for a in apps)
                )
            )
        self.load_apps()

    def request_uninstall(self, name: str, source: str, detail: str = ""):
        """Desinstala por nombre+fuente+detalle (llamado desde Overview)."""
        kind = KIND_APP if source == "pacman" else KIND_FOLDER

        if source == "pacman":
            item = ConfirmItem(
                label=name,
                category_label=tr(kind_label_key(kind)),
                size_bytes=0,
                remove=lambda: uninstall_packages([name]),
            )
        else:
            target = Path(detail) if detail else Path.home() / name
            item = ConfirmItem(
                label=name,
                category_label=tr(kind_label_key(kind)),
                size_bytes=0,
                paths=[target],
            )

        plan = build_confirmation_plan([item])
        if run_destructive_action(
            self, plan, tr("uninstaller_confirm_title"),
            invalidate_sections=(SECTION_UNINSTALLER,),
        ):
            log_buffer.add(tr("log_uninstalled_packages").format(packages=name))
        self.load_apps()