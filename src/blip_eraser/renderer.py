"""Renderer: ventana principal de BlipEraser.

Composición del shell UI:
- Encabezado (HeaderBar): logo de la app, barra de búsqueda global,
  botón de registro.
- Barra lateral (Sidebar) + QStackedWidget con 5 secciones: Overview,
  Uninstaller, System Cleaner, Performance Tweaks y Tools (en ese orden).
- Barra de estado (SystemStatusBar) con CPU/RAM/disco.
- Panel de registro colapsable (LogPanel) suscrito a utils.log.
- Aplicación de tema (QSS) y fuente desde utils.theme + utils.config.

Toda la lógica vive en utils/*; aquí solo hay composición y presentación.
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QActionGroup, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from blip_eraser import __version__
from blip_eraser.pages import (
    CleanerPage,
    OverviewPage,
    PerformancePage,
    ToolsPage,
    UninstallerPage,
)
from blip_eraser.utils import theme as theme_mod
from blip_eraser.utils.config import load_prefs, save_prefs
from blip_eraser.utils.i18n import (
    SUPPORTED_LANGUAGES,
    get_current_language,
    set_language,
    tr,
)
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.ui_text import localized_missing_lines
from blip_eraser.widgets import LogPanel, SearchBar, Sidebar, SystemStatusBar
from blip_eraser.widgets.logo import AppLogo

_SECTION_ORDER = [
    "overview",
    "uninstaller",
    "system_cleaner",
    "performance",
    "tools",
]

# Secciones donde la búsqueda y el acceso al Registro tienen sentido.
_TOOLBAR_SECTIONS = ("uninstaller", "system_cleaner")


def _app_title() -> str:
    """Título de la barra de título: 'BlipEraser - vX.X.X'."""
    return f"BlipEraser - v{__version__}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1180, 720)
        self.setWindowTitle(_app_title())

        self._pages: dict[str, QWidget] = {
            "overview": OverviewPage(),
            "uninstaller": UninstallerPage(),
            "system_cleaner": CleanerPage(),
            "performance": PerformancePage(),
            "tools": ToolsPage(),
        }
        self._overview: OverviewPage = self._pages["overview"]
        self._tools: ToolsPage = self._pages["tools"]

        self._build_ui()
        self._build_language_menu()
        self._connect_signals()
        self._apply_appearance()
        self.retranslate()
        self._update_header_tools("overview")

        log_buffer.add(tr("log_started"))

        # Nivel 2: verificación de binarios en segundo plano (no bloquea la GUI).
        QTimer.singleShot(0, self._warn_missing_binaries)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Encabezado
        header = QWidget()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(10)

        self.app_logo = AppLogo()
        header_layout.addWidget(self.app_logo)

        self.search = SearchBar()
        header_layout.addWidget(self.search, 1)

        self.log_toggle_btn = QPushButton()
        self.log_toggle_btn.setCheckable(True)
        header_layout.addWidget(self.log_toggle_btn)

        outer.addWidget(header)

        # Cuerpo: sidebar + páginas
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        sidebar_wrap = QWidget()
        sidebar_wrap.setObjectName("SidebarWrap")
        sidebar_layout = QVBoxLayout(sidebar_wrap)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = Sidebar()
        sidebar_layout.addWidget(self.sidebar)
        body.addWidget(sidebar_wrap)

        self.stack = QStackedWidget()
        for section in _SECTION_ORDER:
            self.stack.addWidget(self._pages[section])
        body.addWidget(self.stack, 1)

        outer.addLayout(body, 1)

        # Panel de registro (colapsado por defecto)
        self.log_panel = LogPanel()
        self.log_panel.setVisible(False)
        outer.addWidget(self.log_panel)

        self.setCentralWidget(root)

        # Barra de estado
        self.setStatusBar(SystemStatusBar())

    def _build_language_menu(self):
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.language_actions: dict[str, QAction] = {}
        for code in SUPPORTED_LANGUAGES:
            action = QAction(tr(f"lang_name_{code}"), self)
            action.setCheckable(True)
            action.setChecked(code == get_current_language())
            action.triggered.connect(
                lambda _checked=False, lang=code: self._switch_language(lang)
            )
            self.language_group.addAction(action)
            self.language_actions[code] = action

        self.language_menu = QMenu(tr("menu_label"), self)
        for action in self.language_actions.values():
            self.language_menu.addAction(action)
        self.menuBar().addMenu(self.language_menu)

    def _connect_signals(self):
        self.sidebar.currentRowChanged.connect(self._on_section_changed)
        self.search.textChanged.connect(self._on_search_changed)
        self.log_toggle_btn.clicked.connect(self._on_log_toggle)

        self._overview.uninstall_requested.connect(self._on_overview_uninstall)

        settings = self._tools.settings
        settings.theme_changed.connect(self._on_theme_changed)
        settings.font_changed.connect(self._on_font_changed)

    # ------------------------------------------------------------------
    # Navegación y búsqueda
    # ------------------------------------------------------------------
    def _on_section_changed(self, row: int):
        if 0 <= row < len(_SECTION_ORDER):
            section = _SECTION_ORDER[row]
            self.stack.setCurrentWidget(self._pages[section])
            self._update_header_tools(section)
            self._apply_search_to(section)

    def _update_header_tools(self, section: str):
        """Búsqueda y acceso al Registro solo en Desinstalador y Limpiador."""
        visible = section in _TOOLBAR_SECTIONS
        self.search.setVisible(visible)
        self.log_toggle_btn.setVisible(visible)
        if not visible:
            self.log_toggle_btn.setChecked(False)
            self.log_panel.setVisible(False)

    def _current_section(self) -> str | None:
        row = self.sidebar.currentRow()
        if 0 <= row < len(_SECTION_ORDER):
            return _SECTION_ORDER[row]
        return None

    def _on_search_changed(self, text: str):
        section = self._current_section()
        if section:
            self._apply_search_to(section)

    def _apply_search_to(self, section: str):
        page = self._pages[section]
        if hasattr(page, "set_search_filter"):
            page.set_search_filter(self.search.text())

    def _on_log_toggle(self):
        self.log_panel.setVisible(self.log_toggle_btn.isChecked())

    # ------------------------------------------------------------------
    # Ajustes de apariencia
    # ------------------------------------------------------------------
    def _on_overview_uninstall(self, name: str, source: str, detail: str):
        """Uninstall desde Overview: delega al confirm de la página Uninstaller."""
        uninstaller = self._pages["uninstaller"]
        uninstaller.request_uninstall(name, source, detail)

    def _on_theme_changed(self, theme_key: str):
        save_prefs({"theme": theme_key})
        self._apply_appearance()
        theme = theme_mod.THEMES.get(theme_key, theme_mod.THEMES["red"])
        self._overview.set_accent(theme["accent"])
        label = tr(theme["label_key"])
        log_buffer.add(tr("log_theme_changed").format(theme=label))

    def _on_font_changed(self, font_id: str):
        save_prefs({"font": font_id})
        self._apply_appearance()

    def _apply_appearance(self):
        """Aplica tema + fuente a toda la app.

        Verificación manual del caso 'dos cambios seguidos sin pausa':
        1. Abre Ajustes → fuente. Cambia a Roboto y, al instante, a Lato
           (sin pausa entre ambos).
        2. Todo el texto debe quedar ya en Lato (sin cambiar de página,
           sin redimensionar).
        3. Repite Roboto → Lato → Montserrat y comprueba el mismo resultado.
        4. Cambiar de página / redimensionar la ventana NO debe ser
           necesario para ver la fuente nueva.
        """
        prefs = load_prefs()
        theme_key = prefs.get("theme")
        if theme_key not in theme_mod.THEMES:
            theme_key = "red"

        self.setStyleSheet(theme_mod.build_qss(theme_key))

        theme = theme_mod.THEMES.get(theme_key, theme_mod.THEMES["red"])
        accent = theme["accent"]
        palette = theme["palette"]
        self.sidebar.apply_theme(accent, accent, palette.get("hover", "#202024"), palette.get("subtext", "#9a9aa2"))
        self.sidebar.refresh_icons()
        self.app_logo.set_accent(accent)
        self._overview.set_accent(accent)

        family = theme_mod.font_family(prefs.get("font", "system"))
        font = QFont(family) if family else QFont()
        app = QApplication.instance()
        app.setFont(font)
        # QApplication.setFont no re-pule los widgets ya creados: la QSS
        # (QStyleSheetStyle) cachea la fuente resuelta por widget, así que
        # el segundo cambio seguido no se refleja hasta un evento externo
        # (show/resize que fuerza el re-polish). Forzamos polish + repaint.
        style = app.style()
        for widget in app.allWidgets():
            style.unpolish(widget)
            style.polish(widget)
            widget.update()

    def refresh_appearance(self):
        """Rutina completa de arranque: tema + fuente + iconos + textos.

        Es la misma pasada que dispara un cambio manual de idioma o tema,
        ejecutada explícitamente tras el primer pintado para que los iconos
        del tema del sistema y la fuente configurada queden aplicados sin
        depender de que el usuario toque Configuración o el menú Idioma.
        """
        self._apply_appearance()
        self.retranslate()

    # ------------------------------------------------------------------
    # Idioma
    # ------------------------------------------------------------------
    def _switch_language(self, code: str):
        set_language(code)
        for lang, action in self.language_actions.items():
            action.setChecked(lang == code)
        self.retranslate()
        log_buffer.add(
            tr("log_language_changed").format(language=tr(f"lang_name_{code}"))
        )

    def retranslate(self):
        self.setWindowTitle(_app_title())
        self.search.retranslate()
        self.log_toggle_btn.setText(tr("log_toggle"))
        self.language_menu.setTitle(tr("menu_label"))
        for code, action in self.language_actions.items():
            action.setText(tr(f"lang_name_{code}"))
        self.sidebar.retranslate()
        self.log_panel.retranslate()
        self.statusBar().retranslate()
        for page in self._pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()

    # ------------------------------------------------------------------
    # Nivel 2: dependencias
    # ------------------------------------------------------------------
    def _warn_missing_binaries(self):
        lines = localized_missing_lines(["pacman", "pkexec"])
        if not lines:
            return
        QMessageBox.warning(
            self,
            tr("missing_deps_title"),
            tr("missing_deps_intro").format(lines="\n\n".join(lines)),
        )