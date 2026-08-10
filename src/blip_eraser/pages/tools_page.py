"""Página 'Herramientas': alberga Personalización, Ajustes y Ayuda.

Una sola sección de la barra lateral que agrupa las utilidades auxiliares
en pestañas internas (QTabWidget), para no poblar la navegación principal.
"""

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from blip_eraser.pages.help_page import HelpPage
from blip_eraser.pages.personalize_page import PersonalizePage
from blip_eraser.pages.settings_page import SettingsPage
from blip_eraser.utils.i18n import tr


class ToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.personalize = PersonalizePage()
        self.settings = SettingsPage()
        self.help_page = HelpPage()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.personalize, tr("personalize_title"))
        self.tabs.addTab(self.settings, tr("settings_theme_title"))
        self.tabs.addTab(self.help_page, tr("help_title"))
        layout.addWidget(self.tabs)

    def retranslate(self):
        self.personalize.retranslate()
        self.settings.retranslate()
        self.help_page.retranslate()
        self.tabs.setTabText(0, tr("personalize_title"))
        self.tabs.setTabText(1, tr("settings_theme_title"))
        self.tabs.setTabText(2, tr("help_title"))