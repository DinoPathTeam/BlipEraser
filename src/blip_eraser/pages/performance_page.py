"""Página 'Ajustes de rendimiento': opciones seleccionables.

Por ahora es presentación con interruptores visibles; las acciones
efectivas llegarán en fases posteriores (solo estética, sin ejecutar nada
todavía).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QVBoxLayout,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.i18n import tr


class PerformancePage(BasePage):
    def __init__(self):
        super().__init__()
        self._boxes: list[tuple[QCheckBox, str]] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(tr("performance_title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel(tr("performance_hint"))
        hint.setObjectName("SubText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(16)

        for key in (
            "perf_trim_mounts",
            "perf_compress_ram",
            "perf_mirror_sort",
            "perf_disable_wp",
        ):
            box = QCheckBox(tr(key))
            box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            layout.addWidget(box)
            self._boxes.append((box, key))

        layout.addStretch(1)

    def retranslate(self):
        for box, key in self._boxes:
            box.setText(tr(key))