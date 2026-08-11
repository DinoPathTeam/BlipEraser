"""Página 'Ajustes': tema de color y fuente.

Lee/escribe utils.config y notifica los cambios al renderer con señales
de Qt (theme_changed, font_changed). Cada tema define su propio modo
claro/oscuro y paleta completa.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.i18n import tr
from blip_eraser.utils import theme as theme_mod
from blip_eraser.widgets.permissions_dialog import show_permissions_dialog


class SettingsPage(BasePage):
    theme_changed = pyqtSignal(str)
    font_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_initial()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(tr("settings_theme_title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.theme_combo = QComboBox()
        layout.addWidget(self.theme_combo)
        self.theme_hint = QLabel(tr("theme_hint"))
        self.theme_hint.setWordWrap(True)
        self.theme_hint.setObjectName("SubText")
        layout.addWidget(self.theme_hint)

        layout.addSpacing(12)
        layout.addWidget(QLabel(tr("settings_font_title")))
        self.font_combo = QComboBox()
        layout.addWidget(self.font_combo)

        layout.addSpacing(20)
        self.permissions_btn = QPushButton(tr("help_security_permissions_button"))
        self.permissions_btn.clicked.connect(
            lambda: show_permissions_dialog(self)
        )
        layout.addWidget(self.permissions_btn)

        layout.addStretch(1)

    def _load_initial(self):
        prefs = load_prefs()

        for key, info in theme_mod.THEMES.items():
            self.theme_combo.addItem(tr(info["label_key"]), key)
        current_theme = prefs.get("theme")
        if current_theme in theme_mod.THEMES:
            self.theme_combo.setCurrentIndex(
                list(theme_mod.THEMES).index(current_theme)
            )

        for font in theme_mod.FONTS:
            label = tr(font["label_key"]) if font.get("label_key") else font["family"]
            self.font_combo.addItem(label, font["id"])
        current_font = prefs.get("font")
        for i in range(self.font_combo.count()):
            if self.font_combo.itemData(i) == current_font:
                self.font_combo.setCurrentIndex(i)
                break

        self.theme_combo.currentIndexChanged.connect(
            lambda idx: self.theme_changed.emit(self.theme_combo.itemData(idx))
        )
        self.font_combo.currentIndexChanged.connect(
            lambda idx: self.font_changed.emit(self.font_combo.itemData(idx))
        )

    def retranslate(self):
        for i in range(self.theme_combo.count()):
            key = self.theme_combo.itemData(i)
            self.theme_combo.setItemText(i, tr(theme_mod.THEMES[key]["label_key"]))
        for i in range(self.font_combo.count()):
            font_id = self.font_combo.itemData(i)
            for font in theme_mod.FONTS:
                if font["id"] == font_id:
                    label = tr(font["label_key"]) if font.get("label_key") else font["family"]
                    self.font_combo.setItemText(i, label)
                    break
        self.theme_hint.setText(tr("theme_hint"))