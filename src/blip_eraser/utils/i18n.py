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
        # Pantalla de arranque (splash)
        "splash_check_updates": "Comprobando actualizaciones",
        "splash_check_permissions": "Comprobando permisos",
        "splash_check_dependencies": "Comprobando dependencias",
        "splash_scanning": (
            "Escaneando el PC, por favor mantente en espera unos segundos"
        ),
        "splash_welcome": "Escaneo finalizado, ¡Bienvenido!",
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
        # Limpiador del sistema (dos secciones independientes)
        "cleaner_info": (
            "Limpieza del sistema: basura, caché de pacman, registros y carpetas "
            "sueltas. Revisa cada sección antes de eliminar."
        ),
        "cleanup_rec_section": "Limpieza recomendada",
        "cleanup_manual_section": "Aplicaciones instaladas (manual)",
        "col_category": "Categoría",
        "cleanup_nothing_selected": "Selecciona al menos un elemento de limpieza.",
        "cleanup_confirm_title": "Confirmar limpieza",
        "cleanup_run_button": "Limpiar ahora",
        "cleanup_list_empty": "No hay nada que limpiar en las categorías seleccionadas.",
        "log_cleanup_scanned": "Limpieza del sistema escaneada: {count} elementos",
        "log_destructive_removed": "{count} elementos eliminados",
        # Confirmación compartida de acciones destructivas
        "confirm_summary_intro": "Se eliminará lo siguiente:",
        "confirm_total": "Total a liberar",
        "confirm_large_size": "Eliminación de gran tamaño",
        "confirm_large_warning": (
            "Esta operación libera una gran cantidad de espacio. Comprueba la "
            "selección antes de continuar."
        ),
        "performance_title": "Ajustes de rendimiento",
        "performance_hint": (
            "Optimizaciones seguras y probadas para Arch/CachyOS. Cada cambio "
            "se aplica al instante y se puede revertir."
        ),
        "perf_trim_mounts": "Activar récorte automático de SSD (fstrim)",
        "perf_compress_ram": "Comprimir memoria en uso (zswap)",
        "perf_mirror_sort": "Sincronizar y ordenar los espejos de pacman",
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
        "perf_trim_mounts_tip": (
            "<b>Mecanismo:</b> TRIM es un comando ATA/NVMe con el que el "
            "sistema avisa al SSD qué bloques ya no se usan. Sin él, la "
            "controladora no sabe qué celdas liberar y su recolección de "
            "basura trabaja sobre todo el disco, degradando la escritura "
            "con el tiempo. fstrim emite esos avisos en lote sobre los "
            "sistemas montados y se programa con un temporizador de systemd."
            "<br><b>Consecuencias:</b> La primera pasada recorre el espacio "
            "libre y puede tardar unos segundos usando algo de CPU. Es "
            "seguro: solo informa de bloques libres, no toca datos. En "
            "NVMe modernos el beneficio es menor (ya hacen recolección de "
            "basura), pero es inofensivo."
            "<br><b>Beneficio:</b> Mantiene estable la velocidad de "
            "escritura a largo plazo y prolonga la vida útil del SSD."
        ),
        "perf_compress_ram_tip": (
            "<b>Mecanismo:</b> zswap es una caché de compresión en RAM del "
            "kernel: cuando la memoria escasea, comprime las páginas "
            "(zstd/lzo) y las guarda en un pool en RAM en lugar de escribir "
            "a swap. Solo cuando ese pool se llena (por defecto ~20 % de la "
            "RAM) las páginas pasan al swap real en disco."
            "<br><b>Consecuencias:</b> Comprimir consume algo de CPU al "
            "escribir y leer páginas. Requiere que exista una partición o "
            "archivo de swap, o no tiene efecto. Reduce drásticamente el "
            "uso de swap en disco bajo presión de memoria."
            "<br><b>Beneficio:</b> En momentos de memoria llena evita el "
            "intercambio a disco (mucho más lento): el sistema responde "
            "mejor y se reduce el desgaste del SSD."
        ),
        "perf_mirror_sort_tip": (
            "<b>Mecanismo:</b> pacman descarga paquetes de los servidores "
            "espejo listados en /etc/pacman.d/mirrorlist, probándolos en "
            "orden. Esta opción sincroniza el listado desde el repositorio "
            "de espejos y lo reordena midiendo latencia y velocidad real de "
            "cada uno, reescribiendo el archivo."
            "<br><b>Consecuencias:</b> La medición tarda unos minutos "
            "(descarga de prueba desde cada espejo) y necesita permisos de "
            "administrador para reescribir el mirrorlist. No borra nada; "
            "solo cambia el orden de preferencia."
            "<br><b>Beneficio:</b> Descargas e instalaciones más rápidas, "
            "sobre todo en actualizaciones grandes, al usar primero los "
            "espejos más rápidos."
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
        "log_toggle": "Actividad de la app",
        "log_clear_activity": "Borrar historial de actividad",
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
        "help_security_permissions_button": "Ver permisos de BlipEraser",
        # Aviso único de permisos (primera ejecución + Configuración/Ayuda)
        "permissions_notice_title": "Permisos de BlipEraser",
        "permissions_notice_intro": (
            "BlipEraser trabaja con permisos de usuario normales y pide "
            "autorización únicamente en el momento exacto en que hace falta."
        ),
        "permissions_point_scan": (
            "• Escaneo: la Vista general, el Desinstalador y el Limpiador "
            "del sistema analizan tu sistema con los permisos de tu usuario, "
            "sin pedir contraseña."
        ),
        "permissions_point_actions": (
            "• Acciones destructivas (eliminar la caché de pacman, los "
            "registros del sistema o desinstalar paquetes): se necesita "
            "autorización mediante pkexec. El sistema pedirá tu contraseña "
            "en el momento en que confirmes una acción de este tipo — nunca "
            "antes ni sin que tú lo solicites."
        ),
        "permissions_point_root": (
            "• BlipEraser nunca se ejecuta como root de forma permanente ni "
            "escala privilegios en silencio. Solo la operación concreta se "
            "ejecuta con permisos de administrador."
        ),
        "permissions_understood": "Entendido",
        # Errores claros de la capa de privilegios (pkexec)
        "priv_error_cancelled": (
            "Autorización cancelada: no se hizo ningún cambio con privilegios."
        ),
        "priv_error_missing": (
            "No se encontró 'pkexec'. Revisa la sección de Ayuda para "
            "instalar las dependencias necesarias."
        ),
        "priv_error_denied": (
            "Permiso denegado al eliminar: {path}. Puede que necesites "
            "autorización de administrador."
        ),
        "priv_error_failed": (
            "No se pudo eliminar: {path}. Revisa el registro para más detalle."
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
        # Startup splash screen
        "splash_check_updates": "Checking for updates",
        "splash_check_permissions": "Checking permissions",
        "splash_check_dependencies": "Checking dependencies",
        "splash_scanning": (
            "Scanning your PC, please wait a few seconds"
        ),
        "splash_welcome": "Scan finished, welcome!",
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
        # System Cleaner (two independent sections)
        "cleaner_info": (
            "System cleanup: junk, pacman cache, logs and loose folders. "
            "Review each section before deleting."
        ),
        "cleanup_rec_section": "Recommended cleanup",
        "cleanup_manual_section": "Installed applications (manual)",
        "col_category": "Category",
        "cleanup_nothing_selected": "Select at least one cleanup item.",
        "cleanup_confirm_title": "Confirm cleanup",
        "cleanup_run_button": "Clean now",
        "cleanup_list_empty": "Nothing to clean in the selected categories.",
        "log_cleanup_scanned": "System cleanup scanned: {count} items",
        "log_destructive_removed": "{count} items removed",
        # Shared destructive-action confirmation
        "confirm_summary_intro": "The following will be removed:",
        "confirm_total": "Total to free",
        "confirm_large_size": "Large deletion",
        "confirm_large_warning": (
            "This operation frees a large amount of space. Check the "
            "selection before continuing."
        ),
        "performance_title": "Performance Tweaks",
        "performance_hint": (
            "Safe, tested optimizations for Arch/CachyOS. Every change is "
            "applied instantly and can be reverted."
        ),
        "perf_trim_mounts": "Enable automatic SSD trim (fstrim)",
        "perf_compress_ram": "Compress memory in use (zswap)",
        "perf_mirror_sort": "Sync and sort pacman mirrors",
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
        "perf_trim_mounts_tip": (
            "<b>Mechanism:</b> TRIM is an ATA/NVMe command that tells the "
            "SSD which blocks are no longer in use. Without it, the "
            "controller cannot free cells and its garbage collection works "
            "over the whole disk, degrading writes over time. fstrim issues "
            "those hints in batches for mounted filesystems and is scheduled "
            "by a systemd timer."
            "<br><b>Consequences:</b> The first pass walks the free space "
            "and may take a few seconds using some CPU. It is safe: it only "
            "reports free blocks, never touches data. On modern NVMe drives "
            "the benefit is smaller (they already do garbage collection), "
            "but it is harmless."
            "<br><b>Benefit:</b> Keeps write speed stable in the long term "
            "and extends the SSD's lifespan."
        ),
        "perf_compress_ram_tip": (
            "<b>Mechanism:</b> zswap is a compressed cache in kernel RAM: "
            "when memory is low, it compresses pages (zstd/lzo) and keeps "
            "them in a RAM pool instead of writing to swap. Only when that "
            "pool fills up (by default ~20% of RAM) do pages go to real "
            "swap on disk."
            "<br><b>Consequences:</b> Compression uses some CPU when "
            "writing and reading pages. It requires a defined swap partition "
            "or file, otherwise it has no effect. It drastically reduces "
            "disk swapping under memory pressure."
            "<br><b>Benefit:</b> Under heavy memory load it avoids the much "
            "slower disk swap: the system responds better and SSD wear is "
            "reduced."
        ),
        "perf_mirror_sort_tip": (
            "<b>Mechanism:</b> pacman downloads packages from the mirror "
            "servers listed in /etc/pacman.d/mirrorlist, trying them in "
            "order. This option syncs the listing from the mirror "
            "repository and reorders it by measuring each mirror's latency "
            "and real speed, rewriting the file."
            "<br><b>Consequences:</b> Measuring takes a few minutes (test "
            "downloads from every mirror) and needs administrator rights to "
            "rewrite the mirrorlist. Nothing is deleted; only the "
            "preference order changes."
            "<br><b>Benefit:</b> Faster downloads and installs, especially "
            "on large updates, by using the fastest mirrors first."
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
        "log_toggle": "App activity",
        "log_clear_activity": "Clear activity history",
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
        "help_security_permissions_button": "View BlipEraser permissions",
        # One-time permissions notice (first run + Settings/Help)
        "permissions_notice_title": "BlipEraser Permissions",
        "permissions_notice_intro": (
            "BlipEraser runs with your normal user permissions and asks for "
            "authorization only at the exact moment it is needed."
        ),
        "permissions_point_scan": (
            "• Scanning: Overview, Uninstaller and the System Cleaner analyze "
            "your system with your user permissions, without asking for a "
            "password."
        ),
        "permissions_point_actions": (
            "• Destructive actions (removing the pacman cache, system logs or "
            "uninstalling packages): authorization via pkexec is required. "
            "The system will ask for your password at the moment you confirm "
            "such an action — never before, never without your explicit "
            "request."
        ),
        "permissions_point_root": (
            "• BlipEraser never runs as root permanently nor escalates "
            "privileges silently. Only the specific operation runs with "
            "administrator privileges."
        ),
        "permissions_understood": "Got it",
        # Clear errors from the privileged layer (pkexec)
        "priv_error_cancelled": (
            "Authorization cancelled: no privileged change was made."
        ),
        "priv_error_missing": (
            "'pkexec' was not found. Check the Help section to install the "
            "required dependencies."
        ),
        "priv_error_denied": (
            "Permission denied while removing {path}. Administrator "
            "authorization may be required."
        ),
        "priv_error_failed": (
            "Could not remove {path}. Check the activity log for details."
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
    best-effort: un fallo al escribir a disco no rompe la app. Preserva
    cualquier otra clave del archivo (p. ej. permissions_notice_shown) para
    no pisar configuración coexistente.
    """
    global _current_language
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    _current_language = language

    try:
        data = _read_settings_file()
        data["language"] = language
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _read_settings_file() -> dict:
    """Lee settings.json como dict ({} si no existe/corrupto). No persiste nada."""
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


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