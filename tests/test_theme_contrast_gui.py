"""Tests GUI del contraste de porcentaje del gauge y de los íconos del sidebar.

El porcentaje "SALUD DEL SISTEMA" debe pintarse con el color de texto del
tema activo (no un blanco fijo) y los íconos del sidebar deben teñirse con
`palette['icon']` (no heredar el color fijo de `edit-clear`). Requieren
PyQt6; se reportan como *skipped* en entornos sin él.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")
QtGui = pytest.importorskip("PyQt6.QtGui")

from blip_eraser.utils.theme import THEMES
from blip_eraser.widgets.health_gauge import HealthGauge
from blip_eraser.widgets.sidebar import Sidebar, tint_icon


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestGaugeTextColor:
    def test_gauge_paints_percentage_with_text_color(self, app):
        """El píxel del porcentaje coincide con `set_text_color`."""
        gauge = HealthGauge()
        gauge.resize(240, 210)
        gauge.set_value(50)
        gauge.set_text_color("#FF00FF")
        pixmap = gauge.grab()
        image = pixmap.toImage()
        found = False
        for x in range(image.width()):
            for y in range(image.height()):
                c = image.pixelColor(x, y)
                if c.alpha() > 0 and c.red() == 255 and c.green() == 0 and c.blue() == 255:
                    found = True
                    break
            if found:
                break
        assert found

    def test_gauge_text_color_setter_updates(self, app):
        gauge = HealthGauge()
        gauge.set_text_color("#123456")
        assert gauge._text_color == "#123456"

    def test_theme_text_on_panel_has_contrast(self, app):
        for key, theme in THEMES.items():
            p = theme["palette"]
            gauge = HealthGauge()
            gauge.set_accent(theme["accent"])
            gauge.set_text_color(p["text"])
            assert gauge._text_color == p["text"]


class TestSidebarIconTint:
    def test_tint_icon_applies_palette_icon_color(self, app):
        """`tint_icon` recubre el asset con el color pedido."""
        from PyQt6.QtGui import QColor, QIcon, QPixmap

        src = QPixmap(26, 26)
        src.fill(QtCore.Qt.GlobalColor.white)
        icon = QIcon(src)
        tinted = tint_icon(icon, "#2E86DE")
        pixmap = tinted.pixmap(26, 26)
        image = pixmap.toImage()
        sample = image.pixelColor(13, 13)
        assert sample.red() == 0x2E
        assert sample.green() == 0x86
        assert sample.blue() == 0xDE

    def test_tint_icon_preserves_alpha(self, app):
        from PyQt6.QtGui import QIcon, QPixmap

        src = QPixmap(26, 26)
        src.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(src)
        painter.fillRect(2, 2, 20, 20, QtGui.QColor("#000000"))
        painter.end()
        tinted = tint_icon(QIcon(src), "#00C853")
        image = tinted.pixmap(26, 26).toImage()
        assert image.pixelColor(1, 1).alpha() == 0
        c = image.pixelColor(13, 13)
        assert c.alpha() > 0
        assert c.green() == 0xC8

    def test_sidebar_icons_use_theme_icon_color(self, app, monkeypatch):
        """El ícono del Limpiador del sistema queda teñido del color del tema."""
        import blip_eraser.widgets.sidebar as sidebar_mod
        from PyQt6.QtGui import QIcon, QPixmap

        src = QPixmap(26, 26)
        src.fill(QtCore.Qt.GlobalColor.white)
        monkeypatch.setattr(
            sidebar_mod.QIcon,
            "fromTheme",
            staticmethod(lambda name, fallback=None: QIcon(src)),
        )
        sidebar = Sidebar()
        item = sidebar.item(2)  # system_cleaner
        assert item is not None
        for key, theme in THEMES.items():
            icon_color = theme["palette"]["icon"]
            sidebar.set_icon_color(icon_color)
            icon = item.icon()
            assert not icon.isNull()
            image = icon.pixmap(26, 26).toImage()
            expected = QtGui.QColor(icon_color)
            found = False
            for x in range(image.width()):
                for y in range(image.height()):
                    c = image.pixelColor(x, y)
                    if c.alpha() > 0:
                        assert c.red() == expected.red()
                        assert c.green() == expected.green()
                        assert c.blue() == expected.blue()
                        found = True
                        break
                if found:
                    break
            assert found, f"{key}: el ícono no se tiñó con {icon_color}"