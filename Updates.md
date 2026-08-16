# Updates / Historial de cambios

Registro de adiciones y eliminaciones del proyecto. Se mantiene para que
cualquier persona que trabaje sobre BlipEraser sepa **por qué** una
característica, texto o clave i18n ya no existe, y para evitar errores de
compilación o de traducción tras cada cambio.

Versión del código: `1.0.0` (definida en `src/blip_eraser/__init__.py`).

---

## Últimos cambios

### ✨ Añadido: animación de entrada en el splash (logo + título deslizantes)

- **Por qué:** el splash de arranque mostraba logo y mensaje estáticos. Ahora
  el logo y el título "BLIPERASER" entran con una animación (deslizamiento
  desde la derecha + fade-in), para dar una primera impresión más pulida.
- **Animación:** logo desde la derecha (800ms, `OutQuart`) → pequeño respiro
  (200ms, vía animación "puente" de opacidad nula) → título (600ms). Se usa
  `QSequentialAnimationGroup` real (no timers sueltos) para que el orden sea
  determinista. El área hero (logo+título) vive en un widget SIN layout: los
  hijos se posicionan a mano con `move()`, porque un QVBoxLayout activo
  pelearía contra `QPropertyAnimation` sobre `pos`.
- **Encolado de mensajes:** mientras la intro corre, los `set_message()` del
  `StartupWorker` se guardan en `_pending_message` (el último gana) y se
  muestran apenas termina la entrada, para no competir visualmente con ella.
  Tras la intro, cada mensaje nuevo hace fade-out del anterior + fade-in.
- **Logo 4K:** `assets/BlipEraserLogo.png` se sustituyó por la versión 4K
  (3960×2160, antes 2816×1536). `ASSET_LOGO_PATH` apunta al mismo nombre, así
  que header y splash la aprovechan sin cambios de código.
- **Interface intacta:** `SplashScreen`, `set_message()` y la señal `closed`
  no cambian; `main.py` no requirió ninguna modificación.
- **Código:** `src/blip_eraser/widgets/splash_screen.py`,
  `src/blip_eraser/assets/BlipEraserLogo.png`,
  `tests/test_splash_gui.py` (tests adaptados al encolado: mensaje pendiente
  durante la intro, el último gana, aparición tras fade).
- **Verificado con PyQt6 real (offscreen):** 259 passed, 0 skipped. Sin PyQt6:
  235 passed, 4 skipped.

### 🔧 Corregido: porcentaje del gauge y ícono del Limpiador invisibles en temas claros

- **Por qué:** en los temas Azul/Morado (fondo claro) dos elementos se veían
  como "marca de agua" (contraste insuficiente):
  1. El porcentaje del anillo "SALUD DEL SISTEMA" se pintaba con un blanco fijo
     `QColor(245, 245, 245)` que solo funciona sobre fondo oscuro.
  2. El ícono del "Limpiador del sistema" en el sidebar (`edit-clear`) se veía
     en blanco: a diferencia de los otros 4 íconos (que son *symbolic* y heredan
     la paleta del tema), este resuelve a un asset del tema del sistema con
     color blanco incrustado que no reacciona al tema activo.
- **Fix (gauge):** el porcentaje ahora usa el color de texto del tema activo
  (`palette['text']`) vía nuevo `set_text_color()` en `HealthGauge`, conectado
  desde `Renderer` (`_overview.set_text_color`). Rojo/Verde siguen claros sobre
  fondo oscuro; Azul/Morado quedan oscuros sobre fondo claro.
- **Fix (sidebar):** nuevo `tint_icon()` en `widgets/sidebar.py` que recubre
  cada ícono con `palette['icon']` preservando su alpha (forma), y
  `Sidebar.set_icon_color()` lo aplica desde el Renderer. Los 5 íconos quedan
  con el color del tema activo en los 4 temas.
- **Contraste verificado (WCAG AA ≥3:1):** texto sobre panel: 14.6–15.3:1 en
  los 4 temas; ícono sobre sidebar: 3.3–19.8:1.
- **Código:** `src/blip_eraser/widgets/health_gauge.py`,
  `src/blip_eraser/widgets/sidebar.py`, `src/blip_eraser/renderer.py`,
  `src/blip_eraser/pages/overview_page.py` (set_text_color),
  `tests/test_theme.py` (nuevo `TestContrast`), `tests/test_theme_contrast_gui.py`
  (nuevo: píxel real del porcentaje + tinte por tema).
- **Verificado con PyQt6 real (offscreen):** 257 passed, 0 skipped. Sin PyQt6:
  235 passed, 4 skipped.

### 🔧 Corregido: Vista general no refrescaba sus métricas tras "Limpiar ahora"

- **Por qué:** tras un borrado exitoso en la Vista general, solo se repintaban
  los tres labels del resumen "SYSTEM CLEANUP RECOMMENDED" (`_apply_cleanup`),
  pero las métricas del panel izquierdo (Archivos basura / Paquetes huérfanos /
  Entradas sueltas) quedaban con los valores viejos hasta pulsar SCAN NOW. La
  invalidación del caché solo afectaba a la próxima visita a Limpiador, no a la
  propia Vista general.
- **Fix:** nuevo `_apply_metrics(cleanup)` compartido por `_on_scan_done` y
  `_on_cleanup_summary_ready`: tras "Limpiar ahora", la Vista general recalcula
  sus números ya mismo con la misma pasada única de `scan_cleanup()` que ya
  alimentaba el resumen (sin escaneo duplicado ni loop).
- **Verificado (Limpiador):** `_RecommendedSection.delete_selected()` SÍ llama a
  `self.scan()` tras `run_destructive_action`, y `scan()` repinta sin depender de
  `is_stale()` (ignora el caché, igual que "Actualizar lista"). La cadena del
  Limpiador ya era correcta; solo faltaba la Vista general.
- **Código:** `src/blip_eraser/pages/overview_page.py`,
  `tests/test_refresh_after_delete_gui.py` (+4 tests: Limpiador re-escanea y
  repinta tras borrar; Vista general repinta resumen+métricas; una sola pasada).
- **Verificado con PyQt6 real (offscreen):** 249 passed, 0 skipped. Sin PyQt6:
  233 passed, 3 skipped.

### 🔧 Corregido: checkbox "seleccionar todo" del encabezado invisible en el Limpiador

- **Por qué:** `_place_select_all()` posicionaba el checkbox con
  `box.width()`/`box.height()`, que devuelven el tamaño por defecto de Qt
  (100×30) hasta que el widget se muestra y coloca, y esa geometría se
  auto-preservaba. El indicator de 16px quedaba desplazado fuera del header
  (x=-32), invisible e inutilizable. El fix del manchón (fondo transparente)
  lo destapó: antes el bloque sólido ocultaba el desajuste.
- **Fix:** usar `sizeHint()` (16×16) para centrar el box sobre la columna 0.
- **Código:** `src/blip_eraser/widgets/check_table.py`,
  `tests/test_check_table_gui.py` (+4 tests de posicionamiento, toggle
  todos/ninguno y tristate, que corren con PyQt6 en CachyOS).
- **Bonus:** `tests/test_splash_gui.py` tenía 2 bugs que solo saltaban con
  PyQt6 presente: `QSignalSpy` vive en `QtCore.QTest`, no en `QtCore`, y
  `requestInterruption()` solo marca el flag con el thread corriendo.
  Corregidos para que la suite pase completa con PyQt6.
- **Verificado:** con PyQt6 real (offscreen): 245 passed, 0 skipped. Sin
  PyQt6 (este Windows): 233 passed, 2 skipped.

### ➕ Añadido: pantalla de arranque (splash) con mensajes de progreso

- **Por qué:** al arrancar, la ventana principal aparecía completa pero
  "congelada" unos segundos mientras se preparaba el entorno. Ahora se muestra
  un splash (logo + mensajes de progreso) ANTES de construir `MainWindow`, que
  se revela solo cuando el arranque está listo.
- **Flujo:** `StartupWorker` (QThread) ejecuta 5 pasos y va emitiendo mensajes:
  1. "Comprobando actualizaciones" → `utils/updates.py::check_for_updates()`
     (stub sin red, devuelve siempre "sin actualización"; el `# TODO` marca
     dónde consultar GitHub Releases en el futuro).
  2. "Comprobando permisos" → `should_show_permissions_notice()` (el diálogo
     se muestra después, con la ventana visible).
  3. "Comprobando dependencias" → `localized_missing_lines(["pacman",
     "pkexec"])`; el chequeo de binarios se movió aquí (antes corría en
     segundo plano desde `MainWindow`), y el aviso se muestra tras el arranque
     sin duplicar el trabajo.
  4. "Escaneando el PC…" → un escaneo de referencia (`list_installed_apps()`)
     cuyo resultado se descarta (no se guarda en caché ni se pasa a ninguna
     página; estas siguen escaneando perezosamente en su `showEvent`).
  5. "Escaneo finalizado, ¡Bienvenido!" → se construye y muestra la ventana.
- **Cierre limpio:** si el usuario cierra el splash a mitad (Alt+F4), se
  interrumpe el worker y la app sale limpiamente. El cierre programático del
  camino de éxito usa `hide()`, no `close()`, para que la señal `closed` solo
  signifique "el usuario lo cerró".
- **Claves nuevas (ES y EN):** `splash_check_updates`, `splash_check_permissions`,
  `splash_check_dependencies`, `splash_scanning`, `splash_welcome`.
- **Código:** `src/blip_eraser/widgets/splash_screen.py`,
  `src/blip_eraser/utils/updates.py`, `main.py` (flujo de arranque),
  `renderer.py` (se retira el chequeo de binarios en segundo plano),
  `utils/i18n.py`, `tests/test_updates.py`, `tests/test_splash_gui.py`.
- **Nota:** el paso 2 comprueba `should_show_permissions_notice()`, y el paso 3
  es quien ejecuta el chequeo autoritativo de binarios (`localized_missing_lines`).
  La comprobación individual `check_binary_available("pkexec")` del paso 2 se
  eliminó: duplicaba al paso 3 y su resultado no se usaba.

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
- Tests sin PyQt6 (este Windows): `235 passed, 4 skipped` (skips: `test_check_table_gui.py`,
  `test_splash_gui.py`, `test_refresh_after_delete_gui.py` y `test_theme_contrast_gui.py`,
  requieren PyQt6).
- Tests con PyQt6 (offscreen / CachyOS): `259 passed, 0 skipped` — incluye la
  suite GUI del splash (animación de entrada + encolado de mensajes), el
  refresco tras acción destructiva, la selección masiva del CheckTable y el
  contraste del gauge + tinte de íconos del sidebar.
