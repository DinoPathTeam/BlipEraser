"""Actividad reciente en la barra lateral.

Muestra las últimas entradas del buffer `utils.log` (la más nueva arriba)
en el espacio libre bajo la navegación. Es un resumen de solo lectura: el
historial completo, con opción de borrarlo, sigue en el panel de registro.
"""

from PyQt6 import sip
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import LogBuffer
from blip_eraser.utils.log import log as global_log

MAX_ROWS = 6
MAX_CHARS = 80


def shorten(message: str, limit: int = MAX_CHARS) -> str:
    """Recorta un mensaje largo con «…» para que no desborde la barra."""
    message = " ".join(message.split())
    if len(message) <= limit:
        return message
    return message[: limit - 1].rstrip() + "…"


class _Row(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivityRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(0)
        self.time = QLabel()
        self.time.setObjectName("ActivityTime")
        self.message = QLabel()
        self.message.setObjectName("ActivityMsg")
        self.message.setWordWrap(True)
        layout.addWidget(self.time)
        layout.addWidget(self.message)

    def set_entry(self, ts: str, message: str, latest: bool) -> None:
        self.time.setText(ts)
        self.message.setText(shorten(message))
        self.setToolTip(message)
        if self.property("latest") != latest:
            self.setProperty("latest", latest)
            style = self.style()
            style.unpolish(self)
            style.polish(self)


class SidebarActivity(QWidget):
    # El buffer puede notificar desde hilos de trabajo: la señal se encola
    # sola hacia el hilo de la GUI.
    _entries_changed = pyqtSignal(list)

    def __init__(self, buffer: LogBuffer | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarActivity")
        self._buffer = buffer if buffer is not None else global_log

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 8)
        layout.setSpacing(6)

        self.title = QLabel(tr("sidebar_activity_title").upper())
        self.title.setObjectName("PanelTitle")
        layout.addWidget(self.title)

        self.empty = QLabel(tr("sidebar_activity_empty"))
        self.empty.setObjectName("SubText")
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

        self._rows = [_Row() for _ in range(MAX_ROWS)]
        for row in self._rows:
            row.hide()
            layout.addWidget(row)
        layout.addStretch(1)

        self._entries_changed.connect(self._render)
        self._buffer.subscribe(self._on_log)

    def _on_log(self, entries: list[tuple[str, str]]) -> None:
        if sip.isdeleted(self):
            raise RuntimeError("SidebarActivity destruido")  # el buffer lo descarta
        self._entries_changed.emit(list(entries))

    def _render(self, entries: list) -> None:
        recent = list(reversed(entries[-MAX_ROWS:]))
        self.empty.setVisible(not recent)
        for i, row in enumerate(self._rows):
            if i < len(recent):
                ts, message = recent[i]
                row.set_entry(ts, message, latest=(i == 0))
                row.show()
            else:
                row.hide()

    def retranslate(self) -> None:
        self.title.setText(tr("sidebar_activity_title").upper())
        self.empty.setText(tr("sidebar_activity_empty"))

    def detach(self) -> None:
        self._buffer.unsubscribe(self._on_log)
