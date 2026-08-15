# Updates / Historial de cambios

Registro de adiciones y eliminaciones del proyecto. Se mantiene para que
cualquier persona que trabaje sobre BlipEraser sepa **por qué** una
característica, texto o clave i18n ya no existe, y para evitar errores de
compilación o de traducción tras cada cambio.

Versión del código: `1.0.0` (definida en `src/blip_eraser/__init__.py`).

---

## Últimos cambios

### ❌ Eliminado: opción "Reducir el quota de escritura de plymouth"

- **Claves eliminadas (ES y EN):** `perf_disable_wp`, `perf_disable_wp_help`,
  `perf_disable_wp_tip`.
- **Código eliminado:** bloque de `_PERF_OPTIONS` en
  `src/blip_eraser/pages/performance_page.py`.
- **Por qué:** el "write quota" de plymouth no tiene documentación pública
  fiable (ni en la wiki de CachyOS ni en el código de plymouth). Mantener una
  opción cuyo mecanismo no se puede explicar con certeza genera desconfianza,
  así que se eliminó por completo en lugar de dejar un tooltip especulativo.
- **Verificado:** `grep` global sin referencias a `perf_disable_wp` /
  `plymouth`; la app compila y los tests pasan (el diccionario i18n se
  construye dinámicamente, y `tr()` devuelve `[clave]` si faltara una clave).

### ➕ Añadido: tooltips detallados en Ajustes de rendimiento

- **Claves nuevas (ES y EN):** `perf_trim_mounts_tip`,
  `perf_compress_ram_tip`, `perf_mirror_sort_tip`.
- **Por qué:** antes el tooltip del ícono "?" repetía el texto de la
  descripción corta (ambos usaban la misma clave). Ahora cada tooltip
  profundiza en tres partes: **Mecanismo**, **Consecuencias** y **Beneficio**.
- **Código afectado:** `src/blip_eraser/pages/performance_page.py` separa
  `"desc"` (clave `_help`, línea corta, sin cambios) de `"tip"` (clave `_tip`,
  tooltip). Formato HTML básico (`<b>`/`<br>`) soportado por QToolTip.

### ❌ Eliminado: checkbox "seleccionar todo" del encabezado del Desinstalador

- **Por qué:** `CheckTable` ahora acepta `show_select_all=False` y la página de
  Desinstalador lo usa. Evita desinstalaciones masivas accidentales; la
  selección es solo manual (una a una o arrastrando). El Limpiador conserva su
  comportamiento (checkbox por defecto).
- **Código:** `src/blip_eraser/widgets/check_table.py`,
  `src/blip_eraser/pages/uninstaller_page.py`,
  `tests/test_check_table_gui.py` (se salta sin PyQt6).

### ➕ Añadido: caché del último escaneo por sección

- **Por qué:** al navegar entre secciones la app volvía a escanear el sistema
  completo cada vez. Ahora `utils/scan_cache.py` guarda el último escaneo por
  sección (`uninstaller`, `cleaner_recommended`, `cleaner_manual`) con un
  timeout de 5 minutos; se invalida tras una acción destructiva.
- **Código:** `src/blip_eraser/utils/scan_cache.py`,
  `src/blip_eraser/pages/uninstaller_page.py`, `cleaner_page.py`,
  `overview_page.py`, `widgets/confirm_dialog.py`, `tests/test_scan_cache.py`.

### ➕ Añadido: aviso único de permisos y escalado con pkexec

- **Por qué:** las operaciones de sistema (borrar rutas en `/var`, desinstalar
  paquetes) fallaban con `Errno 13` sin privilegios. Ahora `remove_paths()`
  agrupa los borrados en una sola llamada `pkexec` por lote, y al primer
  arranque se muestra un aviso de "Permisos de BlipEraser" (una sola vez).
- **Código:** `src/blip_eraser/utils/privileges.py`, `utils/permissions.py`,
  `widgets/permissions_dialog.py`, `widgets/confirm_dialog.py`.

### 🔧 Corregido: iconos y fuente al arrancar

- **Por qué:** los iconos del sidebar (`QIcon.fromTheme`) y la fuente
  configurada podían no resolverse si se aplicaban antes de que el
  QIconLoader/QStyleSheetStyle estuvieran listos. Ahora `refresh_appearance()`
  se ejecuta tras el primer pintado vía `QTimer.singleShot(0, ...)`.
- **Código:** `src/blip_eraser/widgets/sidebar.py` (`refresh_icons()`),
  `renderer.py` (`refresh_appearance()`), `main.py`.

### 🔧 Corregido: glow del botón "Escanear ahora"

- **Por qué:** el glow usaba el rojo fijo del tema por defecto. Ahora deriva
  del acento del tema activo (Red/Blue/Green/Purple).
- **Código:** `src/blip_eraser/widgets/scan_button.py`.

### 🔧 Corregido: bloque de color en el encabezado de las tablas

- **Por qué:** el QCheckBox flotante del header heredaba el fondo genérico y
  dejaba un manchón junto a "Nombre/Categoría". Ahora tiene QSS propio
  transparente con `::indicator` de la paleta del tema.
- **Código:** `src/blip_eraser/widgets/check_table.py`,
  `utils/theme.py` (reglas `QCheckBox#SelectAllCheck`), `tests/test_theme.py`.

### 🔧 Corregido: texto cortado en la página de Ayuda

- **Por qué:** el `QFormLayout` de los bloques no propagaba `heightForWidth`
  del label con `wordWrap`, así que el texto se cortaba sin scroll. Reemplazado
  por `QVBoxLayout`; el QScrollArea ahora crece con el contenido real.
- **Código:** `src/blip_eraser/pages/help_page.py`. El diálogo de permisos
  (QMessageBox con claves propias) no usa este widget y no se ve afectado.

### 🔧 Cambiado: tamaño del logo del encabezado

- **Por qué:** el logo se veía en miniatura. Ahora `LOGO_HEIGHT = 48` (antes
  36) en `src/blip_eraser/widgets/logo.py`; el asset es 2816×1536, así que no
  hay borrosidad. `set_accent()` sigue funcionando igual (re-escala con la
  misma constante al cambiar de tema).

---

## Verificación

- Compilación: `python -m py_compile` sobre los módulos modificados, OK.
- Tests: `230 passed, 1 skipped` (el skip es `test_check_table_gui.py`, que
  requiere PyQt6; se salta en entornos sin él).
