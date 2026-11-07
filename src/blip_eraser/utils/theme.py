"""Temas de color y fuentes — lógica pura, sin PyQt6.

Cada tema define su propia paleta completa (fondo, paneles, sidebar,
texto, acento, iconos…) y su modo claro/oscuro. `build_qss(theme_key)`
produce la hoja de estilos Qt (string) para ese tema. Testable sin GUI.
"""

from __future__ import annotations

from typing import Any

# Colores de las etiquetas APP / DEP / CARPETA: los de los temas oscuros se
# leen bien sobre fondo oscuro; en los claros hace falta una versión más
# oscura para pasar 4.5:1 sobre el panel blanco.
_TAGS_DARK = {"app": "#4CAF50", "dep": "#FFB300", "folder": "#42A5F5"}
_TAGS_LIGHT = {"app": "#2E7D32", "dep": "#8A5A00", "folder": "#1565C0"}

# Claves de cada tema:
# - accent: color sólido del acento (el que se usa como relleno de botones).
# - fill_top / fill_bot: degradado vertical de rellenos (botones, selección).
# - hover_fill: relleno del botón primario al pasar el ratón.
# - on_accent: color del texto sobre un relleno de acento (≥4.5:1).
# - accent_text: acento para usarlo COMO TEXTO sobre el fondo (≥4.5:1).
THEMES: dict[str, dict[str, Any]] = {
    # Tema 1: Rojo y Negro (oscuro).
    "red": {
        "label_key": "theme_red",
        "accent": "#D32F2F",
        "fill_top": "#D32F2F",
        "fill_bot": "#B71C1C",
        "hover_fill": "#B71C1C",
        "on_accent": "#ffffff",
        "accent_text": "#FF5A52",
        "tags": _TAGS_DARK,
        "is_dark": True,
        "decorations": "#000000",
        "palette": {
            "bg": "#0b0b0d",
            "panel": "#151518",
            "sidebar": "#09090b",
            "text": "#f1f1f4",
            "subtext": "#a1a1aa",
            "border": "#2a2a30",
            "hover": "#202026",
            "icon": "#ffffff",
        },
    },
    # Tema 2: Azul y Blanco (claro, profesional).
    "blue": {
        "label_key": "theme_blue",
        "accent": "#1F6FD1",
        "fill_top": "#1F6FD1",
        "fill_bot": "#1558A8",
        "hover_fill": "#1558A8",
        "on_accent": "#ffffff",
        "accent_text": "#1F6FD1",
        "tags": _TAGS_LIGHT,
        "is_dark": False,
        "decorations": "#c5cbd3",
        "palette": {
            "bg": "#f4f6fa",
            "panel": "#ffffff",
            "sidebar": "#e9eef6",
            "text": "#1b2330",
            "subtext": "#5a6270",
            "border": "#d5dce8",
            "hover": "#e3e9f3",
            "icon": "#1F6FD1",
        },
    },
    # Tema 3: Verde y Negro (oscuro, técnico y fresco). El verde es claro,
    # así que el texto sobre el relleno es oscuro (blanco daba 2.2:1).
    "green": {
        "label_key": "theme_green",
        "accent": "#00C853",
        "fill_top": "#00E676",
        "fill_bot": "#00C853",
        "hover_fill": "#00E676",
        "on_accent": "#06210F",
        "accent_text": "#2BE07A",
        "tags": _TAGS_DARK,
        "is_dark": True,
        "decorations": "#1a1a1d",
        "palette": {
            "bg": "#0a0d0b",
            "panel": "#131815",
            "sidebar": "#070a08",
            "text": "#e9efea",
            "subtext": "#94a396",
            "border": "#232c26",
            "hover": "#1c241f",
            "icon": "#00C853",
        },
    },
    # Tema 4: Morado y Blanco (claro, moderno/creativo).
    "purple": {
        "label_key": "theme_purple",
        "accent": "#8E24AA",
        "fill_top": "#9C27B0",
        "fill_bot": "#7B1FA2",
        "hover_fill": "#6A1B9A",
        "on_accent": "#ffffff",
        "accent_text": "#8E24AA",
        "tags": _TAGS_LIGHT,
        "is_dark": False,
        "decorations": "#e8e8ee",
        "palette": {
            "bg": "#faf9fc",
            "panel": "#ffffff",
            "sidebar": "#f1edf8",
            "text": "#231f2b",
            "subtext": "#6a6474",
            "border": "#e2dcec",
            "hover": "#ebe6f3",
            "icon": "#8E24AA",
        },
    },
}

FONTS: list[dict[str, Any]] = [
    {"id": "system", "label_key": "font_system", "family": None},
    {"id": "roboto", "family": "Roboto"},
    {"id": "lato", "family": "Lato"},
    {"id": "montserrat", "family": "Montserrat"},
    {"id": "opensans", "family": "Open Sans"},
]


def palette_for(theme_key: str) -> dict[str, Any]:
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


def fill_gradient(theme_key: str) -> str:
    """Degradado vertical de relleno (para QSS) del acento de un tema."""
    theme = THEMES.get(theme_key, THEMES["red"])
    return (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {theme['fill_top']}, stop:1 {theme['fill_bot']})"
    )


def check_icon_path(color: str) -> str:
    """Ruta (con '/') de un SVG con la marca de verificación en `color`.

    QSS no admite colores dentro de imágenes ni data-URI, así que se genera un
    archivo pequeño por color en el directorio temporal (se reutiliza).
    """
    import tempfile
    from pathlib import Path

    folder = Path(tempfile.gettempdir()) / "bliperaser-qss"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"check-{color.lstrip('#').lower()}.svg"
    if not target.exists():
        target.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f'<path d="M3.6 8.4l2.9 2.9 5.9-6.2" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>',
            encoding="utf-8",
        )
    return target.as_posix()


def switch_icon_paths(theme: dict) -> dict[str, str]:
    """SVG del interruptor (apagado/encendido, normal/deshabilitado) del tema.

    QSS no puede dibujar la perilla de un interruptor, así que el indicador del
    QCheckBox#TweakSwitch usa estas imágenes (generadas en el directorio
    temporal, una vez por combinación de colores).
    """
    import hashlib
    import tempfile
    from pathlib import Path

    p = theme["palette"]
    off_track, off_knob = p["hover"], p["subtext"]
    top, bot, knob_on = theme["fill_top"], theme["fill_bot"], theme["on_accent"]
    folder = Path(tempfile.gettempdir()) / "bliperaser-qss"
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{off_track}{off_knob}{top}{bot}{knob_on}".encode()).hexdigest()[:10]

    def svg(on: bool, disabled: bool) -> str:
        opacity = "0.45" if disabled else "1"
        if on:
            track = (
                f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/>'
                f"</linearGradient></defs>"
                f'<rect width="40" height="22" rx="11" fill="url(#g)"/>'
            )
            knob = f'<circle cx="29" cy="11" r="8" fill="{knob_on}"/>'
        else:
            track = (
                f'<rect x="0.5" y="0.5" width="39" height="21" rx="10.5" fill="{off_track}" '
                f'stroke="{p["border"]}"/>'
            )
            knob = f'<circle cx="11" cy="11" r="8" fill="{off_knob}"/>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="22" viewBox="0 0 40 22">'
            f'<g opacity="{opacity}">{track}{knob}</g></svg>'
        )

    paths: dict[str, str] = {}
    for name, on, disabled in (
        ("off", False, False),
        ("on", True, False),
        ("off_disabled", False, True),
        ("on_disabled", True, True),
    ):
        target = folder / f"switch-{key}-{name}.svg"
        if not target.exists():
            target.write_text(svg(on, disabled), encoding="utf-8")
        paths[name] = target.as_posix()
    return paths


def build_qss(theme_key: str) -> str:
    """Hoja de estilos Qt completa para un tema dado (por clave)."""
    theme = THEMES.get(theme_key, THEMES["red"])
    accent = theme["accent"]
    p = theme["palette"]
    fill = fill_gradient(theme_key)
    on = theme["on_accent"]
    atext = theme["accent_text"]
    hover_fill = theme["hover_fill"]
    bot = theme["fill_bot"]
    tags = theme["tags"]
    check = check_icon_path(on)
    sw = switch_icon_paths(theme)
    return f"""
QWidget {{ background-color: {p['bg']}; color: {p['text']}; }}
QMainWindow {{ background-color: {p['bg']}; }}
QLabel {{ background: transparent; }}
QToolButton#HelpIcon {{ padding: 0; background: transparent; color: {p['subtext']}; border: 1px solid {p['subtext']}; border-radius: 8px; min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px; font-weight: bold; }}
QToolButton#HelpIcon:hover {{ color: {atext}; border-color: {atext}; }}
QToolButton#HelpIcon:focus {{ outline: none; }}
QWidget#HeaderBar {{ background-color: {p['panel']}; border-bottom: 1px solid {p['border']}; }}
QWidget#SidebarWrap {{ background-color: {p['sidebar']}; border-right: 1px solid {p['border']}; }}
QListWidget#Sidebar {{ background-color: transparent; border: none; outline: 0; }}
QListWidget#Sidebar::item {{ padding: 12px 14px; border-radius: 6px; margin: 3px 8px; color: {p['subtext']}; }}
QListWidget#Sidebar::item:selected {{ background: {fill}; color: {on}; }}
QListWidget#Sidebar::item:hover:!selected {{ background-color: {p['hover']}; color: {p['text']}; }}
QListWidget#Sidebar::item:selected:hover {{ background: {fill}; color: {on}; }}
QLabel#AppTitle {{ color: {atext}; font-weight: bold; font-size: 16px; }}
QLabel#PageTitle {{ color: {p['text']}; font-weight: bold; font-size: 15px; }}
QScrollArea {{ background: transparent; border: none; }}
QWidget#AppsContainer {{ background: transparent; }}
QLabel#HeaderTitle {{ color: {p['text']}; font-weight: bold; font-size: 17px; }}
QLabel#StatValue {{ color: {atext}; font-weight: bold; font-size: 22px; }}
QLabel#CardValue {{ color: {atext}; font-weight: bold; font-size: 18px; }}
QLabel#CardValueNeutral {{ color: {p['text']}; font-weight: bold; font-size: 20px; }}
QLabel#CardRowName {{ color: {p['text']}; font-weight: 600; }}
QWidget#AppRow {{ background: transparent; border-top: 1px solid {p['border']}; }}
QProgressBar#InfoBar {{ background: {p['hover']}; border: none; border-radius: 4px; }}
QProgressBar#InfoBar::chunk {{ background: {fill}; border-radius: 4px; }}
QWidget#PanelCard {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 10px; }}
QLabel#AppsBadge {{ background: {fill}; color: {on}; border-radius: 9px; padding: 2px 10px; font-weight: bold; }}
QPushButton#DangerButton {{ background-color: transparent; color: {atext}; border: 1px solid {atext}; border-radius: 6px; padding: 4px 10px; }}
QPushButton#DangerButton:hover {{ background: {fill}; color: {on}; border-color: {accent}; }}
QPushButton {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ background-color: {p['hover']}; }}
QPushButton:pressed {{ background-color: {bot}; color: {on}; }}
QPushButton:checked {{ background: {fill}; color: {on}; border: none; }}
QPushButton#PrimaryButton {{ background: {fill}; color: {on}; border: none; }}
QPushButton#PrimaryButton:hover {{ background-color: {hover_fill}; }}
QPushButton#PrimaryButton:disabled {{ background: {p['hover']}; color: {p['subtext']}; }}
QPushButton:disabled {{ color: {p['subtext']}; }}
QLineEdit {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 6px 10px; selection-background-color: {accent}; selection-color: {on}; }}
QTableWidget {{ background: transparent; border: none; outline: 0; gridline-color: transparent; selection-background-color: transparent; }}
QTableWidget::item {{ border-bottom: 1px solid {p['border']}; padding: 0 6px; }}
QTableWidget::item:selected {{ background-color: {p['hover']}; color: {p['text']}; }}
QTableWidget::item:hover {{ background-color: {p['hover']}; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; border: none; padding: 0 6px; color: {p['subtext']}; font-size: 11px; font-weight: bold; }}
QHeaderView::section:first {{ padding: 0; }}
QTableView::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {p['subtext']}; background-color: {p['bg']}; }}
QTableView::indicator:hover {{ border-color: {accent}; }}
QTableView::indicator:checked {{ background-color: {accent}; border-color: {accent}; image: url({check}); }}
QTableView::indicator:indeterminate {{ background-color: {accent}; border-color: {accent}; }}
QPushButton#SwatchButton {{ background: {p['bg']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 12px 14px; font-weight: 600; text-align: left; }}
QPushButton#SwatchButton:hover {{ background: {p['hover']}; }}
QPushButton#SwatchButton:checked {{ background: {p['bg']}; color: {p['text']}; border: 2px solid {accent}; padding: 11px 13px; }}
QPushButton#ChipButton {{ background: {p['bg']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 7px 14px; }}
QPushButton#ChipButton:hover {{ background: {p['hover']}; }}
QPushButton#ChipButton:checked {{ background: {fill}; color: {on}; border: none; padding: 8px 15px; }}
QPushButton#PosButton {{ background: {p['bg']}; border: 1px solid {p['border']}; border-radius: 6px; }}
QListWidget#PathList {{ background: transparent; border: none; outline: 0; padding: 0; }}
QListWidget#PathList::item {{ border-bottom: 1px solid {p['border']}; padding: 10px 8px; font-weight: 600; }}
QListWidget#PathList::item:selected {{ background: {p['hover']}; color: {p['text']}; }}
QCheckBox {{ background: transparent; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {p['subtext']}; background-color: {p['bg']}; }}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; image: url({check}); }}
QWidget#Plain {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p['subtext']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; background: transparent; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border']}; border-radius: 4px; min-width: 28px; }}
QScrollBar::handle:horizontal:hover {{ background: {p['subtext']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; background: transparent; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
QCheckBox#TweakSwitch {{ background: transparent; spacing: 12px; font-weight: 600; }}
QCheckBox#TweakSwitch::indicator {{ width: 40px; height: 22px; border: none; background: transparent; image: url({sw['off']}); }}
QCheckBox#TweakSwitch::indicator:checked {{ image: url({sw['on']}); }}
QCheckBox#TweakSwitch::indicator:disabled {{ image: url({sw['off_disabled']}); }}
QCheckBox#TweakSwitch::indicator:checked:disabled {{ image: url({sw['on_disabled']}); }}
QCheckBox#TweakSwitch:disabled {{ color: {p['subtext']}; }}
QLabel#RebootBanner {{ background: {p['hover']}; color: {p['text']}; border: 1px solid {p['border']}; border-left: 3px solid {accent}; border-radius: 10px; padding: 10px 14px; }}
QLabel#StatusBanner {{ background: {p['hover']}; color: {p['text']}; border: 1px solid {p['border']}; border-left: 3px solid {tags['app']}; border-radius: 10px; padding: 10px 14px; }}
QLabel#ErrorBanner {{ background: {p['hover']}; color: {p['text']}; border: 1px solid {p['border']}; border-left: 3px solid {atext}; border-radius: 10px; padding: 10px 14px; }}
QLabel#BlockNote {{ color: {p['subtext']}; font-style: italic; font-size: 11px; }}
QTabWidget::pane {{ border: none; top: 6px; }}
QTabWidget::tab-bar {{ left: 0px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: {p['panel']}; color: {p['subtext']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 7px 16px; margin: 0 4px 0 0; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ background: {p['hover']}; color: {p['text']}; }}
QTabBar::tab:selected {{ background: {fill}; color: {on}; border: none; padding: 8px 17px; }}
QCheckBox#SelectAllCheck {{ background: transparent; spacing: 0; }}
QCheckBox#SelectAllCheck::indicator {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 3px; width: 14px; height: 14px; }}
QCheckBox#SelectAllCheck::indicator:hover {{ border-color: {accent}; }}
QCheckBox#SelectAllCheck::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}
QCheckBox#SelectAllCheck::indicator:indeterminate {{ background-color: {accent}; border-color: {accent}; }}
QProgressBar {{ background-color: {p['hover']}; border: none; border-radius: 3px; height: 8px; }}
QProgressBar::chunk {{ background: {fill}; border-radius: 3px; }}
QPlainTextEdit#LogView {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; }}
QGroupBox {{ border: 1px solid {p['border']}; border-radius: 6px; margin-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {p['subtext']}; }}
QComboBox, QListWidget {{ background-color: {p['panel']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 4px 8px; }}
QToolButton {{ background-color: {p['panel']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 6px 12px; }}
QToolButton:hover {{ background-color: {p['hover']}; }}
QToolButton::menu-indicator {{ subcontrol-position: right center; right: 6px; }}
QLabel#SubText {{ color: {p['subtext']}; }}
QLabel#PanelTitle {{ color: {p['subtext']}; font-size: 11px; font-weight: bold; }}
QWidget#SidebarActivity {{ background: transparent; }}
QWidget#ActivityRow {{ background: transparent; border-left: 2px solid {p['border']}; }}
QWidget#ActivityRow[latest="true"] {{ border-left: 2px solid {accent}; }}
QLabel#ActivityTime {{ color: {p['subtext']}; font-size: 10px; }}
QLabel#ActivityMsg {{ color: {p['text']}; font-size: 11px; }}
QLabel#KindTagApp {{ color: {tags['app']}; border: 1px solid {tags['app']}; border-radius: 7px; padding: 1px 7px; font-size: 10px; font-weight: bold; }}
QLabel#KindTagDep {{ color: {tags['dep']}; border: 1px solid {tags['dep']}; border-radius: 7px; padding: 1px 7px; font-size: 10px; font-weight: bold; }}
QLabel#KindTagFolder {{ color: {tags['folder']}; border: 1px solid {tags['folder']}; border-radius: 7px; padding: 1px 7px; font-size: 10px; font-weight: bold; }}
""".strip()
