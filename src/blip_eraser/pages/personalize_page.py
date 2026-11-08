"""Página 'Personalización': gestión de rutas de escaneo.

Edita la lista de rutas en memoria y la persiste con utils.config
(set_scan_paths). No escanea ni borra nada aquí.
"""

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
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
from blip_eraser.widgets.card import Card


class PersonalizePage(BasePage):
    def __init__(self):
        super().__init__()
        self._paths: list[str] = list(get_scan_paths())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # El título lo muestra la pestaña; se conserva el QLabel (oculto).
        title = QLabel(tr("personalize_title"))
        title.setObjectName("PageTitle")
        title.hide()

        self.hint = QLabel(tr("personalize_hint"))
        self.hint.setObjectName("SubText")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("PathList")
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self._refresh_list()
        card = Card(padding=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addWidget(self.list_widget)
        layout.addWidget(card, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(tr("personalize_add_path"))
        self.add_btn.clicked.connect(self._add_path)
        btn_row.addWidget(self.add_btn)

        self.remove_btn = QPushButton(tr("personalize_remove_path"))
        self.remove_btn.clicked.connect(self._remove_path)
        btn_row.addWidget(self.remove_btn)

        self.save_btn = QPushButton(tr("save_button"))
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch(1)

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