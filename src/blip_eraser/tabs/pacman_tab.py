"""Pestaña 'Paquetes (pacman)' — GUI sobre utils.pacman.

Solo contiene código de presentación: la lógica de paquetes vive en
blip_eraser.utils.pacman y se testea sin GUI. Los textos visibles se
resuelven con tr() y se refrescan con retranslate() al cambiar de idioma.
"""

import subprocess

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

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.ui_text import localized_missing_banner


class PacmanTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_packages()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("pacman_tab_info"))
        layout.addWidget(self.info_label)

        self.deps_warning = QLabel("")
        self.deps_warning.setWordWrap(True)
        self.deps_warning.setStyleSheet("color: #b58900; font-weight: bold;")
        self.deps_warning.hide()
        layout.addWidget(self.deps_warning)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([tr("col_package"), tr("col_version")])
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
        self.refresh_btn.clicked.connect(self.load_packages)
        btn_row.addWidget(self.refresh_btn)

        self.uninstall_btn = QPushButton(tr("uninstall_button"))
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        btn_row.addWidget(self.uninstall_btn)

        layout.addLayout(btn_row)

    def retranslate(self):
        """Refresca los textos estáticos tras cambiar el idioma."""
        self.info_label.setText(tr("pacman_tab_info"))
        self.refresh_btn.setText(tr("refresh_button"))
        self.uninstall_btn.setText(tr("uninstall_button"))
        self.table.setHorizontalHeaderLabels([tr("col_package"), tr("col_version")])
        self.refresh_dependency_banner()

    def refresh_dependency_banner(self):
        """Aviso inline (no modal) si falta pacman/pkexec.

        Es informativo: no instala nada. La pestaña de escaneo manual
        sigue siendo usable aunque aquí faltaran binarios.
        """
        message = localized_missing_banner(["pacman", "pkexec"])
        self.deps_warning.setText(message)
        self.deps_warning.setVisible(bool(message))

    def load_packages(self):
        """Rellena la tabla con el resultado de `pacman -Qe`."""
        self.refresh_dependency_banner()
        self.table.setRowCount(0)
        try:
            packages = list_explicit_packages()
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                tr("error_title"),
                tr("pacman_not_found"),
            )
            return
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self,
                tr("error_title"),
                tr("pacman_list_failed").format(error=e),
            )
            return

        self.table.setRowCount(len(packages))
        for row, (name, version) in enumerate(packages):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(version))

    def uninstall_selected(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.information(
                self,
                tr("nothing_selected_title"),
                tr("pacman_nothing_selected"),
            )
            return

        packages = [self.table.item(row, 0).text() for row in selected_rows]

        confirm = QMessageBox.question(
            self,
            tr("uninstall_confirm_title"),
            tr("uninstall_confirm_body").format(packages="\n".join(packages)),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            uninstall_packages(packages)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self,
                tr("error_title"),
                tr("uninstall_failed").format(error=e),
            )
        else:
            QMessageBox.information(
                self,
                tr("done_title"),
                tr("packages_uninstalled_ok"),
            )
            self.load_packages()