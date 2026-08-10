"""Temas de color y fuentes — lógica pura, sin PyQt6.

Cada tema define su propia paleta completa (fondo, paneles, sidebar,
texto, acento, iconos…) y su modo claro/oscuro. `build_qss(theme_key)`
produce la hoja de estilos Qt (string) para ese tema. Testable sin GUI.
"""

from __future__ import annotations

THEMES: dict[str, dict] = {
    # Tema 1: Rojo y Negro (oscuro) — el original con el nombre actualizado.
    "red": {
        "label_key": "theme_red",
        "accent": "#E53935",
        "is_dark": True,
        "decorations": "#000000",
        "palette": {
            "bg": "#0d0d0f",
            "panel": "#161618",
            "sidebar": "#0a0a0c",
            "text": "#ececef",
            "subtext": "#9a9aa2",
            "border": "#2a2a2e",
            "hover": "#202024",
            "icon": "#ffffff",
        },
    },
    # Tema 2: Azul y Blanco (claro, profesional).
    "blue": {
        "label_key": "theme_blue",
        "accent": "#2E86DE",
        "is_dark": False,
        "decorations": "#c5cbd3",
        "palette": {
            "bg": "#f6f7f9",
            "panel": "#ffffff",
            "sidebar": "#eef1f5",
            "text": "#22272d",
            "subtext": "#5f6670",
            "border": "#d7dce2",
            "hover": "#e7ebf0",
            "icon": "#2E86DE",
        },
    },
    # Tema 3: Verde y Negro (oscuro, técnico y fresco).
    "green": {
        "label_key": "theme_green",
        "accent": "#00C853",
        "is_dark": True,
        "decorations": "#1a1a1d",
        "palette": {
            "bg": "#101112",
            "panel": "#17191a",
            "sidebar": "#0c0e0f",
            "text": "#e7ece8",
            "subtext": "#8f9b90",
            "border": "#262b28",
            "hover": "#1e2420",
            "icon": "#00C853",
        },
    },
    # Tema 4: Morado y Blanco (claro, moderno/creativo).
    "purple": {
        "label_key": "theme_purple",
        "accent": "#8E24AA",
        "is_dark": False,
        "decorations": "#e8e8ee",
        "palette": {
            "bg": "#faf9fc",
            "panel": "#ffffff",
            "sidebar": "#f0edf5",
            "text": "#2a2730",
            "subtext": "#6f6a78",
            "border": "#e0dbe7",
            "hover": "#eae6f0",
            "icon": "#8E24AA",
        },
    },
}

FONTS: list[dict] = [
    {"id": "system", "label_key": "font_system", "family": None},
    {"id": "roboto", "family": "Roboto"},
    {"id": "lato", "family": "Lato"},
    {"id": "montserrat", "family": "Montserrat"},
    {"id": "opensans", "family": "Open Sans"},
]


def palette_for(theme_key: str) -> dict:
    """Paleta completa de un tema."""
    theme = THEMES.get(theme_key, THEMES["red"])
    return theme["palette"]


def font_family(font_id: str) -> str | None:
    """Familia de la fuente por id; None si es la fuente del sistema."""
    for font in FONTS:
        if font["id"] == font_id:
            return font.get("family")
    return None


def font_label(font_id: str) -> str:
    """Etiqueta de una fuente (traducible si existe label_key)."""
    from blip_eraser.utils.i18n import tr

    for font in FONTS:
        if font["id"] == font_id:
            if font.get("label_key"):
                return tr(font["label_key"])
            return font.get("family") or font_id
    return font_id


def build_qss(theme_key: str) -> str:
    """Hoja de estilos Qt completa para un tema dado (por clave)."""
    theme = THEMES.get(theme_key, THEMES["red"])
    accent = theme["accent"]
    p = theme["palette"]
    return f"""
QWidget {{ background-color: {p['bg']}; color: {p['text']}; }}
QMainWindow {{ background-color: {p['bg']}; }}
QWidget#HeaderBar {{ background-color: {p['panel']}; border-bottom: 1px solid {p['border']}; }}
QWidget#SidebarWrap {{ background-color: {p['sidebar']}; border-right: 1px solid {p['border']}; }}
QListWidget#Sidebar {{ background-color: transparent; border: none; outline: 0; }}
QListWidget#Sidebar::item {{ padding: 12px 14px; border-radius: 6px; margin: 3px 8px; color: {p['subtext']}; }}
QListWidget#Sidebar::item:selected {{ background-color: {accent}; color: #ffffff; }}
QListWidget#Sidebar::item:hover:!selected {{ background-color: {p['hover']}; color: {p['text']}; }}
QListWidget#Sidebar::item:selected:hover {{ background-color: {accent}; color: #ffffff; }}
QLabel#AppTitle {{ color: {accent}; font-weight: bold; font-size: 16px; }}
QLabel#PageTitle {{ color: {p['text']}; font-weight: bold; font-size: 15px; }}
QWidget#PanelCard {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 10px; }}
QLabel#AppsBadge {{ background-color: {accent}; color: #ffffff; border-radius: 9px; padding: 2px 10px; font-weight: bold; }}
QPushButton#DangerButton {{ background-color: transparent; color: {accent}; border: 1px solid {accent}; border-radius: 6px; padding: 4px 10px; }}
QPushButton#DangerButton:hover {{ background-color: {accent}; color: #ffffff; }}
QPushButton {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ background-color: {p['hover']}; }}
QPushButton:pressed {{ background-color: {accent}; color: #ffffff; }}
QPushButton:checked {{ background-color: {accent}; color: #ffffff; border: none; }}
QPushButton#PrimaryButton {{ background-color: {accent}; color: #ffffff; border: none; }}
QPushButton#PrimaryButton:hover {{ background-color: {p['subtext']}; }}
QLineEdit {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 6px 10px; selection-background-color: {accent}; }}
QTableWidget {{ background-color: {p['panel']}; border: 1px solid {p['border']}; gridline-color: {p['border']}; }}
QHeaderView::section {{ background-color: {p['sidebar']}; border: none; border-bottom: 1px solid {p['border']}; padding: 6px; color: {p['subtext']}; }}
QTableWidget::item:selected {{ background-color: {accent}; color: #ffffff; }}
QProgressBar {{ background-color: {p['hover']}; border: none; border-radius: 3px; height: 8px; }}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 3px; }}
QPlainTextEdit#LogView {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; }}
QGroupBox {{ border: 1px solid {p['border']}; border-radius: 6px; margin-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {p['subtext']}; }}
QComboBox, QListWidget {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 4px; }}
QLabel#SubText {{ color: {p['subtext']}; }}
QLabel#PanelTitle {{ color: {p['subtext']}; font-size: 11px; font-weight: bold; }}
""".strip()