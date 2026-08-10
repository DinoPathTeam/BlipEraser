"""Página 'Ayuda': documentación estática traducida.

Solo texto informativo; no ejecuta nada. Las secciones se construyen a
partir de un esquema de claves i18n y se refrescan con retranslate().
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QVBoxLayout,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.i18n import tr

_SECTIONS = [
    ("help_usage_title", "help_usage_body"),
    ("help_install_title", "help_install_body"),
    ("help_fonts_title", "help_fonts_body"),
    ("help_icons_title", "help_icons_body"),
    ("help_safety_title", "help_safety_body"),
]


class HelpPage(BasePage):
    def __init__(self):
        super().__init__()
        self._group_labels: list[tuple[QLabel, QLabel]] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(tr("help_title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        intro = QLabel(tr("help_intro"))
        intro.setWordWrap(True)
        intro.setObjectName("SubText")
        layout.addWidget(intro)

        for title_key, body_key in _SECTIONS:
            layout.addWidget(self._make_group(title_key, body_key))

        layout.addStretch(1)

    def _make_group(self, title_key: str, body_key: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        form = QFormLayout(frame)

        title_label = QLabel()
        title_label.setStyleSheet("font-weight: bold;")
        body_label = QLabel()
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(
            body_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow(title_label, body_label)
        self._group_labels.append((title_label, body_label))

        title_label.setText(tr(title_key))
        body_label.setText(tr(body_key))
        return frame

    def retranslate(self):
        for (title_key, body_key), (title_label, body_label) in zip(
            _SECTIONS, self._group_labels
        ):
            title_label.setText(tr(title_key))
            body_label.setText(tr(body_key))