"""Panel de registro colapsable: muestra las entradas de utils.log.

Se suscribe al buffer global `blip_eraser.utils.log.log` y refresca su
visor ante cualquier cambio, sin conocer quién escribe en el buffer.
"""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel(tr("log_toggle"))
        self.title.setObjectName("SubText")
        self.clear_btn = QPushButton(tr("log_clear"))
        self.clear_btn.clicked.connect(self._clear)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.clear_btn)
        layout.addLayout(header)

        self.view = QPlainTextEdit()
        self.view.setObjectName("LogView")
        self.view.setReadOnly(True)
        layout.addWidget(self.view)

        log_buffer.subscribe(self._on_log)

    def retranslate(self) -> None:
        self.title.setText(tr("log_toggle"))
        self.clear_btn.setText(tr("log_clear"))

    def _on_log(self, entries: list[tuple[str, str]]) -> None:
        lines = [f"[{ts}] {msg}" for ts, msg in entries]
        self.view.setPlainText("\n".join(lines))

    def _clear(self) -> None:
        log_buffer.clear()