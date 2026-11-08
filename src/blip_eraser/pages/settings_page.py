"""Página 'Ajustes': tema de color y fuente.

Lee/escribe utils.config y notifica los cambios al renderer con señales
de Qt (theme_changed, font_changed). Cada tema define su propio modo
claro/oscuro y paleta completa.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.tray import launcher as tray_launcher
from blip_eraser.tray import logic as tray_logic
from blip_eraser.utils.config import load_prefs, save_prefs
from blip_eraser.utils.i18n import tr
from blip_eraser.utils import theme as theme_mod
from blip_eraser.widgets.card import Card
from blip_eraser.widgets.choice_buttons import ChoiceButtons, dot_icon
from blip_eraser.widgets.permissions_dialog import show_permissions_dialog


_POSITION_ARROWS = {
    "top-left": "↖", "top": "↑", "top-right": "↗",
    "left": "←", "center": "●", "right": "→",
    "bottom-left": "↙", "bottom": "↓", "bottom-right": "↘",
}


class SettingsPage(BasePage):
    theme_changed = pyqtSignal(str)
    font_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_initial()
        self._sync_tray_position()

    def _build_ui(self):
        # Dos tarjetas: apariencia (tema + fuente + permisos) y bandeja.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # El título lo muestra la pestaña; se conserva el QLabel (oculto).
        title = QLabel(tr("settings_theme_title"))
        title.setObjectName("PageTitle")
        title.hide()

        look_card = Card()
        look = QVBoxLayout(look_card)
        look.setContentsMargins(0, 0, 0, 0)
        look.setSpacing(8)

        self.theme_title = QLabel(tr("settings_theme_title").upper())
        self.theme_title.setObjectName("PanelTitle")
        look.addWidget(self.theme_title)
        self.theme_combo = QComboBox()
        self.theme_choices: ChoiceButtons | None = None
        self._theme_host = QVBoxLayout()
        self._theme_host.setContentsMargins(0, 0, 0, 0)
        look.addLayout(self._theme_host)
        look.addWidget(self.theme_combo)  # oculto por ChoiceButtons
        self.theme_hint = QLabel(tr("theme_hint"))
        self.theme_hint.setWordWrap(True)
        self.theme_hint.setObjectName("SubText")
        look.addWidget(self.theme_hint)

        look.addSpacing(6)
        self.font_title = QLabel(tr("settings_font_title").upper())
        self.font_title.setObjectName("PanelTitle")
        look.addWidget(self.font_title)
        self.font_combo = QComboBox()
        self.font_choices: ChoiceButtons | None = None
        self._font_host = QVBoxLayout()
        self._font_host.setContentsMargins(0, 0, 0, 0)
        look.addLayout(self._font_host)
        look.addWidget(self.font_combo)  # oculto por ChoiceButtons

        look.addSpacing(6)
        perm_row = QHBoxLayout()
        self.permissions_btn = QPushButton(tr("help_security_permissions_button"))
        self.permissions_btn.clicked.connect(lambda: show_permissions_dialog(self))
        perm_row.addWidget(self.permissions_btn)
        perm_row.addStretch(1)
        look.addLayout(perm_row)
        look.addStretch(1)
        layout.addWidget(look_card, 17)

        tray_card = Card()
        tray = QVBoxLayout(tray_card)
        tray.setContentsMargins(0, 0, 0, 0)
        tray.setSpacing(8)
        self.tray_title = QLabel(tr("settings_tray_title").upper())
        self.tray_title.setObjectName("PanelTitle")
        tray.addWidget(self.tray_title)
        tray.addWidget(self._build_tray_position_picker())
        self.tray_hint = QLabel(tr("settings_tray_hint"))
        self.tray_hint.setWordWrap(True)
        self.tray_hint.setObjectName("SubText")
        tray.addWidget(self.tray_hint)
        self.tray_keep_check = QCheckBox(tr("settings_tray_keep"))
        self.tray_keep_check.setChecked(tray_launcher.keep_running_enabled(load_prefs()))
        self.tray_keep_check.toggled.connect(
            lambda on: save_prefs({tray_launcher.PREF_KEEP_RUNNING: bool(on)})
        )
        tray.addWidget(self.tray_keep_check)
        self.tray_custom_label = QLabel(tr("settings_tray_custom"))
        self.tray_custom_label.setObjectName("SubText")
        self.tray_custom_label.setWordWrap(True)
        tray.addWidget(self.tray_custom_label)
        tray.addStretch(1)
        layout.addWidget(tray_card, 10)

    def _build_tray_position_picker(self) -> QWidget:
        """Rejilla 3x3 (esquinas, bordes, centro) + 'junto al icono'."""
        box = QWidget()
        box.setObjectName("Plain")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        grid.setSpacing(4)
        self._pos_group = QButtonGroup(self)
        self._pos_group.setExclusive(True)
        self._pos_buttons: dict[str, QPushButton] = {}

        def make(key: str, text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName("PosButton")
            btn.setFixedSize(40, 30)
            self._pos_group.addButton(btn)
            self._pos_buttons[key] = btn
            btn.clicked.connect(lambda _=False, k=key: self._on_tray_position(k))
            return btn

        for key, col, rw in tray_logic.GRID_POSITIONS:
            grid.addWidget(make(key, _POSITION_ARROWS[key]), rw, col)
        row.addLayout(grid)
        auto = make(tray_logic.POS_AUTO, tr("settings_tray_auto"))
        auto.setFixedSize(130, 30)
        row.addSpacing(12)
        row.addWidget(auto, 0, Qt.AlignmentFlag.AlignTop)
        row.addStretch(1)
        return box

    def _on_tray_position(self, key: str) -> None:
        save_prefs({tray_logic.PREF_POSITION: key})
        self._sync_tray_position()

    def _sync_tray_position(self) -> None:
        """Refleja la preferencia (la bandeja también la cambia al arrastrar)."""
        key = load_prefs().get(tray_logic.PREF_POSITION, tray_logic.POS_AUTO)
        self._pos_group.setExclusive(False)
        for btn_key, btn in self._pos_buttons.items():
            btn.setChecked(btn_key == key)
        self._pos_group.setExclusive(True)
        self.tray_custom_label.setVisible(key == tray_logic.POS_CUSTOM)
        self.tray_keep_check.blockSignals(True)
        self.tray_keep_check.setChecked(tray_launcher.keep_running_enabled(load_prefs()))
        self.tray_keep_check.blockSignals(False)

    def set_accent(self, accent: str, on_accent: str = "#ffffff") -> None:
        """Color de acento del tema para los botones de posición marcados."""
        self._pos_box_qss = (
            "QPushButton#PosButton { padding: 2px; }"
            f"QPushButton#PosButton:checked {{ background-color: {accent}; color: {on_accent};"
            f" border: 1px solid {accent}; }}"
        )
        for btn in self._pos_buttons.values():
            btn.setStyleSheet(self._pos_box_qss)

    def showEvent(self, event) -> None:  # noqa: N802 - API de Qt
        super().showEvent(event)
        self._sync_tray_position()

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

        self.theme_choices = ChoiceButtons(
            self.theme_combo,
            "SwatchButton",
            columns=4,
            icon_for=lambda key: dot_icon(theme_mod.THEMES[key]["accent"]),
        )
        self._theme_host.addWidget(self.theme_choices)
        self.font_choices = ChoiceButtons(self.font_combo, "ChipButton")
        self._font_host.addWidget(self.font_choices)

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
        if self.theme_choices is not None:
            self.theme_choices.retranslate()
        if self.font_choices is not None:
            self.font_choices.retranslate()
        self.theme_title.setText(tr("settings_theme_title").upper())
        self.font_title.setText(tr("settings_font_title").upper())
        self.permissions_btn.setText(tr("help_security_permissions_button"))
        self.theme_hint.setText(tr("theme_hint"))
        self.tray_title.setText(tr("settings_tray_title").upper())
        self.tray_hint.setText(tr("settings_tray_hint"))
        self.tray_custom_label.setText(tr("settings_tray_custom"))
        self.tray_keep_check.setText(tr("settings_tray_keep"))
        self._pos_buttons[tray_logic.POS_AUTO].setText(tr("settings_tray_auto"))