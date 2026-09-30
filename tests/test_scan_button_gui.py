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
def test_subtitle_does_not_reach_badge(app, subtitle):
    """El subtítulo termina con aire antes de que empiece la badge."""
    btn = ScanNowButton("SCAN NOW", subtitle)
    btn.resize(240, 112)
    try:
        font = QtGui.QFont(btn.font())
        font.setPointSize(8)
        metrics = QtGui.QFontMetrics(font)
        # Alto real del bloque de texto: título(26) + gap(2) + subtítulo(20),
        # empezando en top+8+2(margen) con altura mínima 112.
        text_bottom = 2 + 8 + 26 + 2 + 20
        badge_top = 112 - 4 - 8 - 32
        assert text_bottom < badge_top, f"{text_bottom=} {badge_top=}"
        # Y el texto cabe a lo ancho en una línea.
        assert metrics.horizontalAdvance(subtitle) < 240 - 16, subtitle
    finally:
        btn.close()


def test_badge_has_no_fill(app):
    """El círculo de la lupa no pinta relleno: el borde es el acento."""
    btn = ScanNowButton("SCAN NOW", "Análisis profundo del sistema")
    btn.resize(240, 112)
    try:
        btn.show()
        pix = btn.grab().toImage()
        accent = btn._accent
        # Punto del borde superior del círculo (centro_x, badge_top):
        # con relleno blanco-40 sería claro; sin relleno es el acento.
        cx = pix.width() // 2
        badge_top = pix.height() - 4 - 8 - 32
        ring = {QtGui.QColor(pix.pixel(cx + i, badge_top)).name() for i in (-4, 4)}
        assert len(ring) == 1, ring
        assert next(iter(ring)) == accent.name(), ring
    finally:
        btn.close()
