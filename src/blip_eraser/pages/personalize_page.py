"""Página 'Personalización': gestión de rutas de escaneo.

Edita la lista de rutas en memoria y la persiste con utils.config
(set_scan_paths). No escanea ni borra nada aquí.
"""

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.config import get_scan_paths, set_scan_paths
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer


class PersonalizePage(BasePage):
    def __init__(self):
        super().__init__()
        self._paths: list[str] = list(get_scan_paths())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(tr("personalize_title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.hint = QLabel(tr("personalize_hint"))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.list_widget = QListWidget()
        self._refresh_list()
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(tr("personalize_add_path"))
        self.add_btn.clicked.connect(self._add_path)
        btn_row.addWidget(self.add_btn)

        self.remove_btn = QPushButton(tr("personalize_remove_path"))
        self.remove_btn.clicked.connect(self._remove_path)
        btn_row.addWidget(self.remove_btn)

        self.save_btn = QPushButton(tr("save_button"))
        self.save_btn.clicked.connect(self._save)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def retranslate(self):
        self.hint.setText(tr("personalize_hint"))
        self.add_btn.setText(tr("personalize_add_path"))
        self.remove_btn.setText(tr("personalize_remove_path"))
        self.save_btn.setText(tr("save_button"))
        for i, path in enumerate(self._paths):
            self.list_widget.item(i).setText(path)

    def _refresh_list(self):
        self.list_widget.clear()
        for path in self._paths:
            self.list_widget.addItem(path)

    def _add_path(self):
        chosen = QFileDialog.getExistingDirectory(
            self, tr("path_dialog_title")
        )
        if chosen and chosen not in self._paths:
            self._paths.append(chosen)
            self._refresh_list()

    def _remove_path(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        if 0 <= row < len(self._paths):
            self._paths.pop(row)
            self._refresh_list()

    def _save(self):
        set_scan_paths(self._paths)
        log_buffer.add(tr("log_scan_paths_updated"))