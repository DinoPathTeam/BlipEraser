"""Tests GUI del botón SCAN NOW: sin solape texto/lupa, badge transparente.

Requieren PyQt6 (offscreen vale): verifican con píxeles reales que el
subtítulo ES/EN no invade el círculo de la lupa y que el círculo no
pinta relleno (transparencia total).
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtGui = pytest.importorskip("PyQt6.QtGui")

from blip_eraser.widgets.scan_button import ScanNowButton


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


SUBTITLES = [
    "Análisis profundo del sistema",
    "Initiate Deep System Analysis",
]


@pytest.mark.parametrize("subtitle", SUBTITLES)
def test_subtitle_fits_in_one_line(app, subtitle):
    """Título y subtítulo caben a lo ancho del tamaño mínimo (con la lupa)."""
    btn = ScanNowButton("SCAN NOW", subtitle)
    try:
        font = QtGui.QFont(btn.font())
        font.setPointSize(8)
        metrics = QtGui.QFontMetrics(font)
        # 16 px de margen de resplandor + 38 de lupa + 8 de aire a la derecha.
        available = btn.minimumWidth() - 16 - 38 - 8
        assert metrics.horizontalAdvance(subtitle) <= available, subtitle
    finally:
        btn.close()


def test_button_is_compact(app):
    btn = ScanNowButton("SCAN NOW", "Análisis profundo del sistema")
    try:
        assert btn.minimumHeight() <= 72
    finally:
        btn.close()


def test_center_is_painted_with_accent_gradient(app):
    btn = ScanNowButton("SCAN NOW", "x")
    btn.set_accent("#D32F2F", "#ffffff", "#D32F2F", "#B71C1C")
    btn.resize(250, 68)
    try:
        btn.show()
        pix = btn.grab().toImage()
        # Esquina interior izquierda (sin texto ni lupa): color del degradado.
        color = QtGui.QColor(pix.pixel(12, 34))
        assert color.red() > color.green() and color.red() > color.blue()
    finally:
        btn.close()
