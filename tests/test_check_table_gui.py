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
QtCore = pytest.importorskip("PyQt6.QtCore")
QtTest = pytest.importorskip("PyQt6.QtTest")

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

    def _shown_table(self, app, columns=4, rows=5):
        """CheckTable mostrado con filas, en una ventana visible."""
        from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

        window = QMainWindow()
        central = QWidget()
        window.setCentralWidget(central)
        layout = QVBoxLayout(central)
        table = CheckTable(columns)
        table.setHorizontalHeaderLabels(
            ["", "Cat", "Nombre", "Tamaño"][:columns]
        )
        for _ in range(rows):
            r = table.add_check_row()
            for col in range(1, columns):
                table.setItem(r, col, QtWidgets.QTableWidgetItem("x"))
        layout.addWidget(table)
        window.resize(600, 300)
        window.show()
        app.processEvents()
        # Mantener viva la ventana: si se recolecta, PyQt destruye el table.
        self._window = window
        return table

    def test_select_all_box_is_positioned_over_section_zero(self, app):
        table = self._shown_table(app)
        box = table.select_all_box
        header = table.horizontalHeader()
        app.processEvents()
        assert box.isVisible()
        x = header.sectionViewportPosition(0)
        w = header.sectionSize(0)
        assert w > 0
        box_x, box_y, box_w, box_h = box.geometry().getRect()
        # El box debe quedar centrado sobre la columna 0 (checkbox de fila),
        # no desplazado fuera de la vista (regresión del tamaño por defecto).
        assert box_x >= x
        assert box_x + box_w <= x + w
        assert box_w > 0 and box_h > 0

    def test_select_all_box_toggles_all_rows(self, app):
        table = self._shown_table(app)
        box = table.select_all_box
        assert table.checked_rows() == []
        QtTest.QTest.mouseClick(box, QtCore.Qt.MouseButton.LeftButton, pos=box.rect().center())
        app.processEvents()
        assert table.checked_rows() == list(range(5))

    def test_select_all_box_untoggles_all_rows(self, app):
        table = self._shown_table(app)
        box = table.select_all_box
        QtTest.QTest.mouseClick(box, QtCore.Qt.MouseButton.LeftButton, pos=box.rect().center())
        app.processEvents()
        assert len(table.checked_rows()) == 5
        QtTest.QTest.mouseClick(box, QtCore.Qt.MouseButton.LeftButton, pos=box.rect().center())
        app.processEvents()
        assert table.checked_rows() == []

    def test_select_all_reflects_partial_state(self, app):
        from PyQt6.QtCore import Qt

        table = self._shown_table(app)
        for r in range(2):
            table.item(r, 0).setCheckState(Qt.CheckState.Checked)
        app.processEvents()
        assert (box := table.select_all_box)
        assert box.checkState() == Qt.CheckState.PartiallyChecked
        # Marcar todas manualmente -> Checked
        for r in range(5):
            table.item(r, 0).setCheckState(Qt.CheckState.Checked)
        app.processEvents()
        assert box.checkState() == Qt.CheckState.Checked
        # Desmarcar todas -> Unchecked
        for r in range(5):
            table.item(r, 0).setCheckState(Qt.CheckState.Unchecked)
        app.processEvents()
        assert box.checkState() == Qt.CheckState.Unchecked

    def test_show_select_all_false_keeps_box_hidden_even_when_shown(self, app):
        from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

        window = QMainWindow()
        central = QWidget()
        window.setCentralWidget(central)
        layout = QVBoxLayout(central)
        table = CheckTable(2, show_select_all=False)
        layout.addWidget(table)
        window.resize(600, 300)
        window.show()
        app.processEvents()
        assert table.select_all_box.isHidden()
        assert table.select_all_box.isVisible() is False