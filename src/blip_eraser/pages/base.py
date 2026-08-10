"""Base para páginas de contenido de la ventana principal."""

from PyQt6.QtWidgets import QWidget


class BasePage(QWidget):
    """Mínimo común de todas las páginas: retranslate y filtro de búsqueda."""

    def retranslate(self) -> None:
        """Refresca textos estáticos tras cambiar de idioma (no-op por defecto)."""
        pass

    def set_search_filter(self, text: str) -> None:
        """Filtra el contenido por `text` (no-op por defecto)."""
        pass