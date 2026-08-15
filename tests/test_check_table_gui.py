"""Tests de GUI para widgets/check_table.py (requieren PyQt6).

Este archivo necesita PyQt6 y, en la práctica, un entorno con display para
que `isVisible()` tenga sentido. `pytest.importorskip("PyQt6")` al inicio
hace que el módulo entero se reporte como *skipped* en entornos sin PyQt6
(CachyOS con PyQt6 instalado es donde realmente corren).

Nota: un widget recién construido (sin window mostrada aún) no es
"visible" aunque no esté oculto. Por eso las aserciones usan `isHidden()`
para distinguir "oculto explícitamente" (show_select_all=False) de "no
mostrado todavía" (caso por defecto), y `isVisible()` solo como
confirmación del requisito pedido.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.widgets.check_table import CheckTable


@pytest.fixture(scope="module")
def app():
    """QApplication compartida: necesaria para construir QWidgets."""
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestCheckTableSelectAll:
    def test_show_select_all_false_hides_box(self, app):
        table = CheckTable(2, show_select_all=False)
        box = table.select_all_box
        assert box is not None
        assert box.isHidden() is True
        assert box.isVisible() is False

    def test_default_shows_box_not_explicitly_hidden(self, app):
        table = CheckTable(2)
        box = table.select_all_box
        assert box is not None
        assert box.isHidden() is False

    def test_default_build_does_not_raise(self, app):
        table = CheckTable(2)
        table.setHorizontalHeaderLabels(["", "Nombre"])
        table.add_check_row()
        assert table.rowCount() == 1
        table.refresh_header_state()