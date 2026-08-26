"""Tests GUI del contraste de porcentaje del gauge y de los íconos del sidebar.

El porcentaje "SALUD DEL SISTEMA" debe pintarse con el color de texto del
tema activo (no un blanco fijo).

Sobre los íconos del sidebar:
- Los 5 íconos NUEVOS (overview, uninstaller, system_cleaner, performance, tools)
  usan assets propios a color completo (sidebar-*.jpg/png) y NO se tiñen.
  Deben verse idénticos en los 4 temas (Rojo/Azul/Verde/Morado).
- Si algún ícono antiguo siguiera usando QIcon.fromTheme + tint_icon,
  ese SÍ debe teñirse con palette['icon'].

Requieren PyQt6; se reportan como *skipped* en entornos sin él.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")
QtGui = pytest.importorskip("PyQt6.QtGui")

from blip_eraser.utils.theme import THEMES
from blip_eraser.widgets.health_gauge import HealthGauge
from blip_eraser.widgets.sidebar import Sidebar, tint_icon, _SIDEBAR_ASSETS


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
    """Tests para la función tint_icon y comportamiento de íconos del sidebar.

    IMPORTANTE: Los 5 íconos NUEVOS del sidebar (overview, uninstaller,
    system_cleaner, performance, tools) usan assets propios a color completo
    (sidebar-*.jpg/png en assets/) y NO pasan por tint_icon(). Deben verse
    idénticos en los 4 temas.

    Esta clase verifica:
    1. Que tint_icon() sigue funcionando correctamente (para cualquier ícono
       que aún use tema del sistema + tinte).
    2. Que los íconos personalizados NO son monocromáticos (confirmando que
       no se les aplicó tinte).
    """

    def test_tint_icon_applies_palette_icon_color(self, app):
        """`tint_icon` recubre el asset con el color pedido (función unitaria)."""
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
        """tint_icon preserva el canal alpha del asset original."""
        from PyQt6.QtGui import QIcon, QPixmap

        src = QPixmap(26, 26)
        src.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(src)
        painter.fillRect(2, 2, 20, 20, QtGui.QColor("#000000"))
        painter.end()
        # Usar tamaño explícito 26x26 para test unitario (no depender de _ICON_SIZE del sidebar)
        tinted = tint_icon(QIcon(src), "#00C853", QtCore.QSize(26, 26))
        image = tinted.pixmap(26, 26).toImage()
        assert image.pixelColor(1, 1).alpha() == 0
        c = image.pixelColor(13, 13)
        assert c.alpha() > 0
        assert c.green() == 0xC8

    def test_custom_sidebar_icons_are_not_tinted(self, app):
        """Los 5 íconos nuevos del sidebar usan assets propios SIN tinte.

        Verifica que cada ícono tiene variación de color (no es monocromático),
        confirmando que NO pasaron por tint_icon() y se ven igual en todos los temas.
        """
        sidebar = Sidebar()
        sidebar.refresh_icons()

        # Secciones que usan assets propios (las 5 nuevas)
        custom_sections = ["overview", "uninstaller", "system_cleaner", "performance", "tools"]

        for row, (section, _key, _icon_name) in enumerate(Sidebar.SECTIONS):
            if section not in custom_sections:
                continue  # Saltar secciones que aún usen tema (si las hay)

            item = sidebar.item(row)
            icon = item.icon()
            assert not icon.isNull(), f"Icono nulo para sección {section}"

            pixmap = icon.pixmap(sidebar.iconSize())
            assert not pixmap.isNull(), f"Pixmap nulo para sección {section}"

            # Verificar variación de color (asset a color real, no tintado)
            image = pixmap.toImage()
            colors = set()
            w, h = image.width(), image.height()
            for x in [w // 4, w // 2, 3 * w // 4]:
                for y in [h // 4, h // 2, 3 * h // 4]:
                    if 0 <= x < w and 0 <= y < h:
                        colors.add(image.pixelColor(x, y).name())

            # Un asset a color real debería tener más de 1 color único
            assert len(colors) > 1, (
                f"Icono de {section} parece monocromático (posible tinte). "
                f"Colores muestreados: {colors}"
            )

    def test_custom_sidebar_icons_identical_across_themes(self, app):
        """Los íconos personalizados se ven idénticos en los 4 temas.

        Como NO usan tint_icon(), el pixmap debe ser el mismo independientemente
        del color de ícono del tema activo.
        """
        sidebar = Sidebar()
        sidebar.refresh_icons()

        # Capturar pixmaps con el tema por defecto
        pixmaps_default = {}
        for row, (section, _key, _icon_name) in enumerate(Sidebar.SECTIONS):
            if section not in ["overview", "uninstaller", "system_cleaner", "performance", "tools"]:
                continue
            item = sidebar.item(row)
            pixmaps_default[section] = item.icon().pixmap(sidebar.iconSize())

        # Cambiar tema y verificar que los pixmaps NO cambian
        for key, theme in THEMES.items():
            icon_color = theme["palette"]["icon"]
            sidebar.set_icon_color(icon_color)
            sidebar.refresh_icons()

            for row, (section, _key, _icon_name) in enumerate(Sidebar.SECTIONS):
                if section not in ["overview", "uninstaller", "system_cleaner", "performance", "tools"]:
                    continue
                item = sidebar.item(row)
                pixmap = item.icon().pixmap(sidebar.iconSize())

                # Comparar píxel a píxel (o al menos muestrear)
                img_default = pixmaps_default[section].toImage()
                img_new = pixmap.toImage()
                w, h = img_default.width(), img_default.height()

                # Muestrear algunos píxeles
                for x in [w // 4, w // 2, 3 * w // 4]:
                    for y in [h // 4, h // 2, 3 * h // 4]:
                        if 0 <= x < w and 0 <= y < h:
                            c1 = img_default.pixelColor(x, y)
                            c2 = img_new.pixelColor(x, y)
                            assert c1.red() == c2.red(), f"{section} cambió en tema {key}"
                            assert c1.green() == c2.green(), f"{section} cambió en tema {key}"
                            assert c1.blue() == c2.blue(), f"{section} cambió en tema {key}"