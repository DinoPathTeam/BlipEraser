"""Página 'Ayuda': documentación estática traducida.

Solo texto informativo; no ejecuta nada. Las secciones se construyen a
partir de un esquema de claves i18n y se refrescan con retranslate().
El contenido vive dentro de un QScrollArea para que no se recorte si la
ventana es pequeña; al pie se muestra la versión ('Acerca de').
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from blip_eraser import __version__
from blip_eraser.pages.base import BasePage
from blip_eraser.utils.i18n import tr
from blip_eraser.widgets.card import Card

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # El título lo muestra la pestaña; se conserva el QLabel (oculto).
        title = QLabel(tr("help_title"))
        title.setObjectName("PageTitle")
        title.hide()

        self.intro = QLabel(tr("help_intro"))
        self.intro.setWordWrap(True)
        self.intro.setObjectName("SubText")
        layout.addWidget(self.intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)

        container = QWidget()
        container.setObjectName("AppsContainer")  # fondo transparente (ver theme)
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        for title_key, body_key in _SECTIONS:
            content.addWidget(self._make_group(title_key, body_key))
        content.addStretch(1)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        self.about_label = QLabel(
            tr("help_about_body").format(version=__version__)
        )
        self.about_label.setWordWrap(True)
        self.about_label.setObjectName("SubText")
        self.about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.about_label)

    def _make_group(self, title_key: str, body_key: str) -> Card:
        frame = Card()
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        title_label = QLabel()
        title_label.setObjectName("CardRowName")
        title_label.setWordWrap(True)
        body_label = QLabel()
        body_label.setObjectName("SubText")
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(
            body_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        vbox.addWidget(title_label)
        vbox.addWidget(body_label)
        self._group_labels.append((title_label, body_label))

        title_label.setText(tr(title_key))
        body_label.setText(tr(body_key))
        return frame

    def retranslate(self):
        self.intro.setText(tr("help_intro"))
        for (title_key, body_key), (title_label, body_label) in zip(
            _SECTIONS, self._group_labels
        ):
            title_label.setText(tr(title_key))
            body_label.setText(tr(body_key))
        self.about_label.setText(tr("help_about_body").format(version=__version__))