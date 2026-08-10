"""Internacionalización (i18n) — lógica pura, sin PyQt6.

Prioridad de idioma:
  1. Preferencia guardada por el usuario (~/.config/blip-eraser/settings.json).
  2. Idioma del sistema operativo (detección vía `locale`).
  3. Fallback: inglés (idioma más universal).

`locale.getdefaultlocale()` está deprecado en Python 3.11 y fue eliminado
en 3.13, así que se usa `locale.getlocale()`, que no está deprecado.

Toda la lógica es testable con pytest: la ruta del archivo de config se
expone como `SETTINGS_FILE` (monkeypachable) y `locale.getlocale()` se
mockea igual que `subprocess.run` en test_pacman.py.
"""

from __future__ import annotations

import json
import locale
from pathlib import Path

SUPPORTED_LANGUAGES = ("es", "en")

TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        # Ventana principal
        "window_title": "BlipEraser — Desinstalador de CachyOS",
        "tab_packages": "Paquetes (pacman)",
        "tab_manual_scan": "Escaneo manual",
        # Pestaña pacman
        "pacman_tab_info": (
            "Paquetes instalados explícitamente (pacman -Qe). Selecciona uno o "
            "varios y pulsa 'Desinstalar seleccionados'."
        ),
        "col_package": "Paquete",
        "col_version": "Versión",
        "refresh_button": "Actualizar lista",
        "uninstall_button": "Desinstalar seleccionados",
        "uninstall_button_count": "Desinstalar seleccionados ({n})",
        "error_title": "Error",
        "pacman_not_found": (
            "No se encontró el comando 'pacman'. ¿Estás en una distro basada en Arch?"
        ),
        "pacman_list_failed": "Fallo al listar paquetes:\n{error}",
        "nothing_selected_title": "Nada seleccionado",
        "pacman_nothing_selected": "Selecciona al menos un paquete.",
        "uninstall_confirm_title": "Confirmar desinstalación",
        "uninstall_confirm_body": (
            "Vas a desinstalar:\n\n{packages}\n\n"
            "Esto usará 'pkexec pacman -Rns'. ¿Continuar?"
        ),
        "uninstall_failed": "Fallo al desinstalar:\n{error}",
        "done_title": "Listo",
        "packages_uninstalled_ok": "Paquetes desinstalados correctamente.",
        # Pestaña escaneo manual
        "manual_tab_info": (
            "Carpetas de nivel superior encontradas en ubicaciones típicas "
            "(AppImages, juegos manuales, etc.). Revisa antes de borrar."
        ),
        "col_path": "Ruta",
        "col_size": "Tamaño",
        "scan_button": "Escanear carpetas",
        "delete_button": "Eliminar seleccionados",
        "manual_nothing_selected": "Selecciona al menos una carpeta o archivo.",
        "delete_confirm_title": "Confirmar eliminación",
        "delete_confirm_body": (
            "Vas a eliminar PERMANENTEMENTE:\n\n{paths}\n\n¿Continuar?"
        ),
        "some_errors_title": "Algunos errores",
        "items_deleted_ok": "Elementos eliminados correctamente.",
        # Verificación de dependencias (MainWindow)
        "missing_deps_title": "Faltan dependencias",
        "missing_deps_intro": (
            "BlipEraser no instala nada por ti — algunas secciones no "
            "funcionarán porque faltan estas herramientas:\n\n{lines}"
        ),
        "dep_line_template": "• {binary}: {why}.\n    {remediation}",
        # Textos localizados de dependencias (banner y diálogo Nivel 2)
        "dep_pacman_why": (
            "necesario para listar y desinstalar paquetes del sistema "
            "(pestaña 'Paquetes (pacman)')"
        ),
        "dep_pkexec_why": (
            "necesario para desinstalar paquetes con privilegios vía polkit"
        ),
        "dep_install_command": "Instala con: {command}",
        "dep_pacman_incompatible": (
            "BlipEraser está diseñado para distribuciones basadas en Arch "
            "(como CachyOS). Si no estás en una de estas distros, la pestaña "
            "'Paquetes (pacman)' no estará disponible, pero el escaneo manual "
            "seguirá funcionando."
        ),
        "dep_no_remediation": "No hay remedio automático disponible.",
        "dep_banner_line": "⚠ {binary} no encontrado — {why}. {remediation}",
        # Idioma (diálogo de primer arranque y menú)
        "lang_name_es": "Español",
        "lang_name_en": "English",
        "menu_label": "Idioma",
        "language_first_run_title": "Elige tu idioma",
        "language_first_run_text": (
            "¿En qué idioma prefieres usar BlipEraser?"
        ),
        # Navegación lateral
        "nav_packages": "Gestor de paquetes",
        "nav_cleaner": "Limpiador del sistema",
        "nav_personalize": "Personalización",
        "nav_help": "Ayuda",
        "nav_settings": "Ajustes",
        # Navegación lateral (v2)
        "nav_overview": "Vista general",
        "nav_uninstaller": "Desinstalador",
        "nav_system_cleaner": "Limpiador del sistema",
        "nav_performance": "Ajustes de rendimiento",
        "nav_tools": "Configuración",
        # Overview
        "overview_health_title": "SALUD DEL SISTEMA",
        "overview_erase_button": "Escanear ahora",
        "overview_erase_subtitle": "Iniciar análisis profundo del sistema",
        "overview_scanning": "ESCANEANDO…",
        "overview_status_good": "BUENA",
        "overview_status_fair": "ACEPTABLE",
        "overview_status_poor": "CRÍTICA",
        "metric_junk": "Archivos basura",
        "metric_orphans": "Paquetes huérfanos",
        "metric_loose": "Entradas sueltas",
        "apps_count_label": "{count} apps",
        "cleanup_junk": "Basura",
        "cleanup_cache": "Caché",
        "cleanup_logs": "Registros",
        "log_scan_completed": "Escaneo completado: {count} apps, {space} usados",
        "system_info_title": "INFORMACIÓN DEL SISTEMA",
        "recent_activity_title": "Actividad reciente",
        "list_empty_subtext": "Sin actividad todavía",
        "installed_apps_title": "APLICACIONES INSTALADAS",
        "cleanup_recommended_title": "LIMPIEZA DEL SISTEMA RECOMENDADA",
        "gpu_label": "GPU",
        "apps_empty": "No se encontraron aplicaciones.",
        "uninstaller_confirm_title": "Confirmar desinstalación",
        "uninstaller_confirm_body": (
            "¿Desinstalar esta aplicación?\n\n{apps}\n\nSe hará con privilegios "
            "de administrador cuando sea necesario."
        ),
        "log_erase_started": "Eliminación profunda del sistema iniciada",
        "uninstaller_info": (
            "Aplicaciones detectadas (paquetes de pacman y AppImages/carpetas "
            "sueltas). Selecciona lo que quieras eliminar."
        ),
        "performance_title": "Ajustes de rendimiento",
        "performance_hint": (
            "Optimizaciones seguras y probadas para Arch/CachyOS. Cada cambio "
            "se aplica al instante y se puede revertir."
        ),
        "perf_trim_mounts": "Activar récorte automático de SSD (fstrim)",
        "perf_compress_ram": "Comprimir memoria en uso (zswap)",
        "perf_mirror_sort": "Sincronizar y ordenar los espejos de pacman",
        "perf_disable_wp": "Reducir el quota de escritura de plymouth",
        "perf_trim_mounts_help": (
            "Programa fstrim para recortar automáticamente las unidades SSD "
            "y prolongar su vida útil."
        ),
        "perf_compress_ram_help": (
            "Habilita zswap para comprimir en RAM los datos poco usados "
            "y reducir el intercambio a disco."
        ),
        "perf_mirror_sort_help": (
            "Sincroniza los listados de los espejos de pacman y los ordena "
            "por velocidad para acelerar las descargas."
        ),
        "perf_disable_wp_help": (
            "Reduce la cuota de escritura de plymouth para acelerar el "
            "arranque en equipos con discos lentos."
        ),
        "perf_effect_disk": "Disco",
        "perf_effect_ram": "RAM",
        "perf_effect_network": "Red",
        "tools_title": "Configuración",
        "tools_hint": (
            "Configuración y utilidades auxiliares: personalización, tema "
            "y documentación."
        ),
        # Encabezado, búsqueda y registro
        "search_placeholder": "Buscar paquetes y funciones…",
        "log_toggle": "Registro",
        "log_clear": "Limpiar registro",
        "col_name": "Nombre",
        "col_source": "Fuente",
        "col_detail": "Detalle",
        "col_type": "Tipo",
        "col_weight": "Peso",
        "col_date": "Fecha",
        "select_all_tooltip": "Seleccionar o desmarcar todas las filas",
        # Tipos de aplicación
        "kind_app": "Aplicación",
        "kind_dependency": "Dependencia",
        "kind_folder": "Carpeta suelta",
        "save_button": "Guardar cambios",
        "uninstall_short": "Desinstalar",
        # Estado del sistema
        "status_title": "Estado del sistema",
        "status_cpu": "CPU",
        "status_ram": "RAM",
        "status_disk": "Disco",
        "status_na": "N/D",
        # Ajustes de apariencia
        "settings_theme_title": "Tema de color",
        "settings_mode_title": "Modo de apariencia",
        "settings_font_title": "Fuente de la interfaz",
        "theme_red": "Rojo",
        "theme_blue": "Azul",
        "theme_green": "Verde",
        "theme_purple": "Morado",
        "mode_dark": "Oscuro",
        "mode_light": "Claro",
        "font_system": "Predeterminada del sistema",
        "theme_hint": (
            "Cambia el acento de color y el modo claro/oscuro de toda la "
            "interfaz al instante."
        ),
        # Personalización
        "personalize_title": "Personalización",
        "personalize_scan_paths": "Rutas de escaneo",
        "personalize_hint": (
            "BlipEraser escaneará estas ubicaciones en busca de aplicaciones "
            "instaladas manualmente (AppImages, carpetas sueltas, etc.)."
        ),
        "personalize_add_path": "Añadir ruta…",
        "personalize_remove_path": "Quitar seleccionada",
        "path_dialog_title": "Selecciona una carpeta",
        # Ayuda
        "help_title": "Ayuda y documentación",
        "help_intro": (
            "BlipEraser desinstala aplicaciones en CachyOS/Arch, incluidas las "
            "que los gestores gráficos no detectan (AppImages, carpetas "
            "sueltas, lanzadores de terceros)."
        ),
        "help_usage_title": "Uso",
        "help_usage_body": (
            "1. Gestor de paquetes: lista los paquetes explícitos (pacman -Qe) "
            "para desinstalarlos.\n"
            "2. Limpiador del sistema: encuentra AppImages y carpetas sueltas "
            "en tus rutas de escaneo.\n"
            "3. Personalización: ajusta las rutas que se escanean.\n"
            "4. Ajustes: tema de color, fuente e idioma.\n"
            "La barra de búsqueda filtra los paquetes y los resultados de "
            "limpieza."
        ),
        "help_install_title": "Instalación de dependencias",
        "help_install_body": (
            "PyQt6 debe instalarse con el gestor del sistema, no por pip:\n"
            "sudo pacman -S python-pyqt6"
        ),
        "help_fonts_title": "Fuentes",
        "help_fonts_body": (
            "Para usar Roboto, Lato, Montserrat u Open Sans, instálalas:\n"
            "sudo pacman -S ttf-roboto ttf-lato ttf-montserrat ttf-opensans"
        ),
        "help_icons_title": "Iconos",
        "help_icons_body": (
            "BlipEraser usa los iconos del sistema (Breeze en KDE Plasma, "
            "etc.). Si no los ves, instala un tema de iconos:\n"
            "sudo pacman -S breeze-icons"
        ),
        "help_safety_title": "Seguridad",
        "help_safety_body": (
            "Toda acción destructiva pide confirmación explícita y los "
            "privilegios se solicitan por acción con pkexec. BlipEraser nunca "
            "instala nada automáticamente."
        ),
        "help_about_body": (
            "BlipEraser {version} — Desinstalador y limpiador del sistema "
            "para CachyOS / Arch Linux. Licencia MIT."
        ),
        # Registro (log)
        "log_started": "BlipEraser iniciado",
        "log_theme_changed": "Tema cambiado a {theme}",
        "log_mode_changed": "Modo cambiado a {mode}",
        "log_font_changed": "Fuente cambiada a {font}",
        "log_language_changed": "Idioma cambiado a {language}",
        "log_scan_finished": "Escaneo completado: {count} elemento(s)",
        "log_deleted_items": "Eliminados: {count}",
        "log_uninstalled_packages": "Desinstalados: {packages}",
        "log_scan_paths_updated": "Rutas de escaneo actualizadas",
    },
    "en": {
        # Main window
        "window_title": "BlipEraser — CachyOS Uninstaller",
        "tab_packages": "Packages (pacman)",
        "tab_manual_scan": "Manual scan",
        # pacman tab
        "pacman_tab_info": (
            "Explicitly installed packages (pacman -Qe). Select one or more "
            "and press 'Uninstall selected'."
        ),
        "col_package": "Package",
        "col_version": "Version",
        "refresh_button": "Refresh list",
        "uninstall_button": "Uninstall selected",
        "uninstall_button_count": "Uninstall selected ({n})",
        "error_title": "Error",
        "pacman_not_found": (
            "'pacman' command not found. Are you on an Arch-based distro?"
        ),
        "pacman_list_failed": "Failed to list packages:\n{error}",
        "nothing_selected_title": "Nothing selected",
        "pacman_nothing_selected": "Select at least one package.",
        "uninstall_confirm_title": "Confirm uninstall",
        "uninstall_confirm_body": (
            "You are about to uninstall:\n\n{packages}\n\n"
            "This uses 'pkexec pacman -Rns'. Continue?"
        ),
        "uninstall_failed": "Uninstall failed:\n{error}",
        "done_title": "Done",
        "packages_uninstalled_ok": "Packages uninstalled successfully.",
        # Manual scan tab
        "manual_tab_info": (
            "Top-level folders found in typical locations (AppImages, manually "
            "installed games, etc.). Review before deleting."
        ),
        "col_path": "Path",
        "col_size": "Size",
        "scan_button": "Scan folders",
        "delete_button": "Delete selected",
        "manual_nothing_selected": "Select at least one folder or file.",
        "delete_confirm_title": "Confirm deletion",
        "delete_confirm_body": (
            "You are about to delete PERMANENTLY:\n\n{paths}\n\nContinue?"
        ),
        "some_errors_title": "Some errors",
        "items_deleted_ok": "Items deleted successfully.",
        # Dependency checking (MainWindow)
        "missing_deps_title": "Missing dependencies",
        "missing_deps_intro": (
            "BlipEraser never installs anything for you — some sections won't "
            "work because these tools are missing:\n\n{lines}"
        ),
        "dep_line_template": "• {binary}: {why}.\n    {remediation}",
        # Localized dependency text (banner and Level 2 dialog)
        "dep_pacman_why": (
            "needed to list and uninstall system packages "
            "(the 'Packages (pacman)' tab)"
        ),
        "dep_pkexec_why": (
            "needed to uninstall packages with elevated privileges via polkit"
        ),
        "dep_install_command": "Install with: {command}",
        "dep_pacman_incompatible": (
            "BlipEraser is designed for Arch-based distributions (such as "
            "CachyOS). If you are not on one of these distros, the 'Packages "
            "(pacman)' tab won't be available, but the manual scan will still "
            "work."
        ),
        "dep_no_remediation": "No automatic fix available.",
        "dep_banner_line": "⚠ {binary} not found — {why}. {remediation}",
        # Language (first-run dialog and menu)
        "lang_name_es": "Español",
        "lang_name_en": "English",
        "menu_label": "Language",
        "language_first_run_title": "Choose your language",
        "language_first_run_text": (
            "Which language would you prefer BlipEraser to use?"
        ),
        # Sidebar navigation
        "nav_packages": "Package Manager",
        "nav_cleaner": "System Cleaner",
        "nav_personalize": "Personalization",
        "nav_help": "Help",
        "nav_settings": "Settings",
        # Sidebar navigation (v2)
        "nav_overview": "Overview",
        "nav_uninstaller": "Uninstaller",
        "nav_system_cleaner": "System Cleaner",
        "nav_performance": "Performance Tweaks",
        "nav_tools": "Settings",
        # Overview
        "overview_health_title": "SYSTEM HEALTH",
        "overview_erase_button": "Scan now",
        "overview_erase_subtitle": "Initiate Deep System Analysis",
        "overview_scanning": "SCANNING…",
        "overview_status_good": "GOOD",
        "overview_status_fair": "FAIR",
        "overview_status_poor": "POOR",
        "metric_junk": "Junk Files",
        "metric_orphans": "Orphan Packages",
        "metric_loose": "Loose Entries",
        "apps_count_label": "{count} apps",
        "cleanup_junk": "Junk",
        "cleanup_cache": "Cache",
        "cleanup_logs": "Logs",
        "log_scan_completed": "Scan completed: {count} apps, {space} used",
        "system_info_title": "SYSTEM INFORMATION",
        "recent_activity_title": "Recent activity",
        "list_empty_subtext": "No activity yet",
        "installed_apps_title": "INSTALLED APPLICATIONS",
        "cleanup_recommended_title": "SYSTEM CLEANUP RECOMMENDED",
        "gpu_label": "GPU",
        "apps_empty": "No applications found.",
        "uninstaller_confirm_title": "Confirm uninstall",
        "uninstaller_confirm_body": (
            "Uninstall this application?\n\n{apps}\n\nAdministrator "
            "privileges will be requested when needed."
        ),
        "log_erase_started": "Deep system removal started",
        "uninstaller_info": (
            "Detected applications (pacman packages and loose AppImages/"
            "folders). Select the ones you want to remove."
        ),
        "performance_title": "Performance Tweaks",
        "performance_hint": (
            "Safe, tested optimizations for Arch/CachyOS. Every change is "
            "applied instantly and can be reverted."
        ),
        "perf_trim_mounts": "Enable automatic SSD trim (fstrim)",
        "perf_compress_ram": "Compress memory in use (zswap)",
        "perf_mirror_sort": "Sync and sort pacman mirrors",
        "perf_disable_wp": "Reduce plymouth write quota",
        "perf_trim_mounts_help": (
            "Schedules fstrim to automatically trim SSD drives and extend "
            "their lifespan."
        ),
        "perf_compress_ram_help": (
            "Enables zswap to compress rarely used data in RAM and reduce "
            "swapping to disk."
        ),
        "perf_mirror_sort_help": (
            "Syncs the pacman mirror lists and sorts them by speed to speed "
            "up downloads."
        ),
        "perf_disable_wp_help": (
            "Lowers plymouth's write quota to speed up boot on slower disks."
        ),
        "perf_effect_disk": "Disk",
        "perf_effect_ram": "RAM",
        "perf_effect_network": "Network",
        "tools_title": "Settings",
        "tools_hint": (
            "App configuration and utilities: personalization, appearance "
            "and documentation."
        ),
        # Header, search and log
        "search_placeholder": "Search packages and features…",
        "log_toggle": "Log",
        "log_clear": "Clear log",
        "col_name": "Name",
        "col_source": "Source",
        "col_detail": "Detail",
        "col_type": "Type",
        "col_weight": "Weight",
        "col_date": "Date",
        "select_all_tooltip": "Check or uncheck all rows",
        # App types
        "kind_app": "Application",
        "kind_dependency": "Dependency",
        "kind_folder": "Loose folder",
        "save_button": "Save changes",
        "uninstall_short": "Uninstall",
        # System status
        "status_title": "System status",
        "status_cpu": "CPU",
        "status_ram": "RAM",
        "status_disk": "Disk",
        "status_na": "N/D",
        # Appearance settings
        "settings_theme_title": "Color theme",
        "settings_mode_title": "Appearance mode",
        "settings_font_title": "Interface font",
        "theme_red": "Red",
        "theme_blue": "Blue",
        "theme_green": "Green",
        "theme_purple": "Purple",
        "mode_dark": "Dark",
        "mode_light": "Light",
        "font_system": "System default",
        "theme_hint": (
            "Change the accent color and light/dark mode of the whole "
            "interface instantly."
        ),
        # Personalization
        "personalize_title": "Personalization",
        "personalize_scan_paths": "Scan paths",
        "personalize_hint": (
            "BlipEraser will scan these locations for manually installed "
            "applications (AppImages, loose folders, etc.)."
        ),
        "personalize_add_path": "Add path…",
        "personalize_remove_path": "Remove selected",
        "path_dialog_title": "Select a folder",
        # Help
        "help_title": "Help and documentation",
        "help_intro": (
            "BlipEraser uninstalls applications on CachyOS/Arch, including "
            "the ones graphical managers don't detect (AppImages, loose "
            "folders, third-party launchers)."
        ),
        "help_usage_title": "Usage",
        "help_usage_body": (
            "1. Package Manager: lists explicit packages (pacman -Qe) so you "
            "can uninstall them.\n"
            "2. System Cleaner: finds AppImages and loose folders in your "
            "scan paths.\n"
            "3. Personalization: adjust which paths are scanned.\n"
            "4. Settings: color theme, font and language.\n"
            "The search bar filters packages and cleanup results."
        ),
        "help_install_title": "Installing dependencies",
        "help_install_body": (
            "PyQt6 must be installed with your system package manager, not "
            "with pip:\nsudo pacman -S python-pyqt6"
        ),
        "help_fonts_title": "Fonts",
        "help_fonts_body": (
            "To use Roboto, Lato, Montserrat or Open Sans, install them:\n"
            "sudo pacman -S ttf-roboto ttf-lato ttf-montserrat ttf-opensans"
        ),
        "help_icons_title": "Icons",
        "help_icons_body": (
            "BlipEraser uses your system icon theme (Breeze on KDE Plasma, "
            "etc.). If you don't see them, install an icon theme:\n"
            "sudo pacman -S breeze-icons"
        ),
        "help_safety_title": "Safety",
        "help_safety_body": (
            "Every destructive action asks for explicit confirmation and "
            "privileges are requested per action with pkexec. BlipEraser "
            "never installs anything automatically."
        ),
        "help_about_body": (
            "BlipEraser {version} — Uninstaller and system cleaner for "
            "CachyOS / Arch Linux. MIT License."
        ),
        # Logging
        "log_started": "BlipEraser started",
        "log_theme_changed": "Theme changed to {theme}",
        "log_mode_changed": "Mode changed to {mode}",
        "log_font_changed": "Font changed to {font}",
        "log_language_changed": "Language changed to {language}",
        "log_scan_finished": "Scan finished: {count} item(s)",
        "log_deleted_items": "Deleted: {count}",
        "log_uninstalled_packages": "Uninstalled: {packages}",
        "log_scan_paths_updated": "Scan paths updated",
    },
}

CONFIG_DIR = Path.home() / ".config" / "blip-eraser"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

_current_language: str | None = None


# ----------------------------------------------------------------------
# Detección de idioma del sistema
# ----------------------------------------------------------------------
def detect_system_language() -> str:
    """'es' si el idioma del sistema empieza por 'es'; en cualquier otro
    caso (incluyendo detección fallida/None) devuelve 'en'."""
    try:
        lang_code, _encoding = locale.getlocale()
    except (locale.Error, TypeError):
        return "en"
    if lang_code and lang_code.lower().startswith("es"):
        return "es"
    return "en"


# ----------------------------------------------------------------------
# Preferencia guardada
# ----------------------------------------------------------------------
def load_saved_language() -> str | None:
    """Lee la preferencia guardada; None si no existe o el archivo está corrupto."""
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    language = data.get("language") if isinstance(data, dict) else None
    return language if isinstance(language, str) else None


def set_language(language: str) -> None:
    """Establece el idioma activo y lo persiste en el archivo de config.

    Si el idioma no está soportado, cae a 'en'. La persistencia es
    best-effort: un fallo al escribir a disco no rompe la app.
    """
    global _current_language
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    _current_language = language

    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps({"language": language}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def get_current_language() -> str:
    """Idioma activo, resolviendo en memoria o con la lógica de prioridad."""
    global _current_language
    if _current_language is None:
        saved = load_saved_language()
        if saved in SUPPORTED_LANGUAGES:
            _current_language = saved
        else:
            _current_language = detect_system_language()
    return _current_language


# ----------------------------------------------------------------------
# Traducción
# ----------------------------------------------------------------------
def tr(key: str) -> str:
    """Devuelve la cadena `key` en el idioma activo.

    Fallback a inglés si la clave falta en el idioma activo, y a '[clave]'
    si falta en ambos (visible en desarrollo, sin romper la app).
    """
    language = get_current_language()
    table = TRANSLATIONS.get(language, TRANSLATIONS["en"])
    if key in table:
        return table[key]
    if key in TRANSLATIONS["en"]:
        return TRANSLATIONS["en"][key]
    return f"[{key}]"