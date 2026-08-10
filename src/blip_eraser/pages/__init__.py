"""Páginas de contenido de la ventana principal."""

from blip_eraser.pages.base import BasePage
from blip_eraser.pages.cleaner_page import CleanerPage
from blip_eraser.pages.help_page import HelpPage
from blip_eraser.pages.overview_page import OverviewPage
from blip_eraser.pages.performance_page import PerformancePage
from blip_eraser.pages.personalize_page import PersonalizePage
from blip_eraser.pages.settings_page import SettingsPage
from blip_eraser.pages.tools_page import ToolsPage
from blip_eraser.pages.uninstaller_page import UninstallerPage

__all__ = [
    "BasePage",
    "CleanerPage",
    "HelpPage",
    "OverviewPage",
    "PerformancePage",
    "PersonalizePage",
    "SettingsPage",
    "ToolsPage",
    "UninstallerPage",
]