"""Página 'Desinstalador': aplicaciones instaladas con desinstalación.

Lista las aplicaciones detectadas (utils.apps.list_installed_apps) y
desinstala con privilegios según la fuente: pacman o borrado manual.
Presentación únicamente; la lógica vive en utils.
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
from blip_eraser.utils.apps import InstalledApp, list_installed_apps
from blip_eraser.utils.file_utils import delete_path
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.pacman import uninstall_packages


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

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [tr("col_name"), tr("col_source"), tr("col_detail")]
        )
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
        self.refresh_btn = QPushButton(tr("refresh_button"))
        self.refresh_btn.clicked.connect(self.load_apps)
        btn_row.addWidget(self.refresh_btn)

        self.uninstall_btn = QPushButton(tr("uninstall_button"))
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        btn_row.addWidget(self.uninstall_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # BasePage
    # ------------------------------------------------------------------
    def retranslate(self):
        self.info_label.setText(tr("uninstaller_info"))
        self.refresh_btn.setText(tr("refresh_button"))
        self.uninstall_btn.setText(tr("uninstall_button"))
        self.table.setHorizontalHeaderLabels(
            [tr("col_name"), tr("col_source"), tr("col_detail")]
        )

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
            self.table.setItem(row, 0, QTableWidgetItem(app.name))
            self.table.setItem(row, 1, QTableWidgetItem(app.source))
            self.table.setItem(row, 2, QTableWidgetItem(app.detail))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def uninstall_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
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