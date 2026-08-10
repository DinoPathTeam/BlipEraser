"""Barra de búsqueda global del encabezado."""

from PyQt6.QtWidgets import QLineEdit

from blip_eraser.utils.i18n import tr


class SearchBar(QLineEdit):
    """Campo de búsqueda; filtra la sección activa según MainWindow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(tr("search_placeholder"))
        self.setClearButtonEnabled(True)

    def retranslate(self) -> None:
        self.setPlaceholderText(tr("search_placeholder"))