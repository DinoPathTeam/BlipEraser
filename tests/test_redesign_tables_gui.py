"""Tests del rediseño de tablas: encabezados, etiquetas de tipo y estilo."""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import Qt

from blip_eraser.utils import theme as theme_mod
from blip_eraser.widgets import table_delegates
from blip_eraser.widgets.check_table import CheckTable


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_headers_are_uppercase_and_right_aligned(app):
    table = CheckTable(3)
    table.set_right_aligned_columns((2,))
    table.setHorizontalHeaderLabels(["", "Nombre", "Peso"])
    assert table.horizontalHeaderItem(1).text() == "NOMBRE"
    assert table.horizontalHeaderItem(2).text() == "PESO"
    align = table.horizontalHeaderItem(2).textAlignment()
    assert int(align) & int(Qt.AlignmentFlag.AlignRight)


def test_table_has_no_grid_and_no_vertical_header(app):
    table = CheckTable(2)
    assert not table.showGrid()
    assert table.verticalHeader().isHidden()


def test_tag_delegate_paints_outline_in_tag_color(app):
    from PyQt6.QtGui import QColor, QImage, QPainter
    from PyQt6.QtWidgets import QStyleOptionViewItem, QTableWidgetItem

    table_delegates.set_theme_colors("#888888", {"app": "#00ff00", "dep": "#ffff00", "folder": "#0000ff"})
    table = CheckTable(3)
    table.setRowCount(1)
    item = QTableWidgetItem("Aplicación")
    item.setData(table_delegates.KIND_ROLE, "app")
    table.setItem(0, 2, item)
    delegate = table_delegates.TagDelegate(table)
    table.setItemDelegateForColumn(2, delegate)
    table.resize(400, 120)
    table.show()
    image = QImage(160, 38, QImage.Format.Format_ARGB32)
    image.fill(QColor("#101010"))
    painter = QPainter(image)
    option = QStyleOptionViewItem()
    option.rect = image.rect()
    option.widget = table
    delegate.paint(painter, option, table.model().index(0, 2))
    painter.end()
    greens = sum(
        1
        for x in range(image.width())
        for y in range(image.height())
        if QColor(image.pixel(x, y)).green() > 150 and QColor(image.pixel(x, y)).red() < 100
    )
    assert greens > 20  # el contorno y el texto usan el color de la etiqueta
    table.close()


def test_qss_styles_tables_tabs_and_primary_disabled():
    qss = theme_mod.build_qss("red")
    assert "QTableWidget::item" in qss
    assert "QTabBar::tab:selected" in qss
    assert "QPushButton#PrimaryButton:disabled" in qss
    assert "QTableView::indicator:checked" in qss


def test_check_icon_is_generated_once_per_color():
    first = theme_mod.check_icon_path("#ffffff")
    second = theme_mod.check_icon_path("#ffffff")
    assert first == second
    assert first.endswith("check-ffffff.svg")
    assert "\\" not in first
    assert "stroke=\"#ffffff\"" in open(first, encoding="utf-8").read()
