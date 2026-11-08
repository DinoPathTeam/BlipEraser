# Updates / Historial de cambios

Registro de adiciones y eliminaciones del proyecto. Se mantiene para que
cualquier persona que trabaje sobre BlipEraser sepa **por qué** una
característica, texto o clave i18n ya no existe, y para evitar errores de
compilación o de traducción tras cada cambio.

Versión del código: `1.2.1` (definida en `src/blip_eraser/__init__.py`).

---

## Últimos cambios

### 🔔 Bandeja residente en el Flatpak

- **Síntoma**: con el Flatpak, la bandeja se cerraba junto con la app principal.
- **Causa**: la app no lanzaba la bandeja dentro del sandbox (un proceso hijo muere
  con él) y el Flatpak no incluía el lanzador `blip-eraser-tray` ni los permisos de
  la bandeja.
- **Cambio**: en Flatpak la bandeja arranca como instancia independiente en el host
  (`flatpak-spawn --host setsid -f flatpak run --command=blip-eraser-tray …`); el
  lanzador `blip-eraser-tray` y los permisos (`StatusNotifierWatcher`,
  `StatusNotifierItem-2-1`, notificaciones) se añaden al manifiesto; abrir la app
  desde la bandeja y el autoarranque (`~/.config/autostart` del host) también usan
  `flatpak run`.
- **Instancia única**: ahora con `flock` en `$XDG_RUNTIME_DIR/app/<app-id>/` (compartido
  entre sandboxes) en lugar de `QLockFile`, que comprueba PIDs y no sirve entre sandboxes.

### 🧩 install-daemon.sh: sin acceso duplicado para quien usa el Flatpak

- **Síntoma**: tras instalar el daemon y usar solo el Flatpak, el menú tenía dos
  entradas de BlipEraser; la del host (`Exec=blip-eraser`) no abría nada porque
  el comando no existe fuera del Flatpak.
- **Cambio**: el paso 4 del script (accesos `.desktop` + icono) se omite si
  `blip-eraser` no está en el PATH. Se instala igualmente con `DESTDIR`
  (empaquetado/pruebas) o con `sudo INSTALL_DESKTOP=1 ./scripts/install-daemon.sh`.
- Quien ya tenga el acceso huérfano puede quitarlo a mano:
  `/usr/share/applications/blip-eraser.desktop` (y `blip-eraser-tray.desktop`).

### 🚀 v1.2.1: Flatpak sobre el runtime 25.08 y limpieza

- **Flatpak**: el runtime pasa de la 24.08 (fuera de soporte) a la 25.08, con
  soporte hasta septiembre de 2027. El lanzador ya no depende de la versión de
  Python del runtime.
- **Idioma**: el aviso de arranque que ofrece instalar las dependencias del
  daemon privilegiado ya sale en español o inglés según el idioma elegido.
- **Mantenimiento**: se elimina código sin uso (`environment_setup.py` y 46
  claves de traducción).
- Detalle de cada cambio en las entradas siguientes.

### 🌐 Diálogo de dependencias del daemon traducido (ES/EN)

- El aviso de arranque que ofrece instalar las dependencias del daemon
  privilegiado (título, texto, botones, error y resumen final) estaba fijo en
  español. Ahora usa las claves `daemon_deps_*` en ES y EN.
- `_show_installed_summary()` separa el resumen final para poder probarlo.
- Los mensajes de detalle del instalador (`phase2_installer`) siguen en español:
  solo aparecen dentro de «Error instalando …» y en el registro.
### 🧹 Limpieza: claves i18n y módulo sin uso

- **Eliminado** `utils/environment_setup.py` (`EnvironmentValidator`): nadie lo
  importaba; el arranque usa `dependency_check` directamente.
- **Eliminadas 46 claves i18n** (en ES y EN) que ningún código usaba: restos de
  las pestañas y textos anteriores al rediseño (`tab_*`, `nav_packages`,
  `nav_cleaner`, `nav_personalize`, `nav_help`, `nav_settings`, `col_package`,
  `col_version`, `col_path`, `col_source`, `uninstall_button`, `error_title`,
  `pacman_*`, `uninstall_*`, `splash_check_updates`, `splash_check_permissions`,
  `splash_scanning`, `splash_welcome`, `recent_activity_title`, `tools_title`,
  `tools_hint`, `filter_type_*`, `filter_category_*`, `status_title`,
  `settings_mode_title`, `mode_dark`, `mode_light`, `personalize_scan_paths`,
  `list_empty_subtext`, `log_erase_started`, `log_mode_changed`,
  `log_font_changed`, `log_deleted_items`, `manual_tab_info`,
  `packages_uninstalled_ok`, `delete_confirm_body`, `uninstaller_confirm_body`).
- **Se conservan** las claves que se construyen dinámicamente
  (`perf_block_<código>`, `dep_<binario>_why|incompatible`, `lang_name_<código>`)
  y `window_title` / `filter_date_from`, que usan las pruebas.
- Para saber si una clave sigue en uso hay que buscar también su construcción
  con `tr(f"…{x}…")`, no solo la cadena literal.

### 📦 Flatpak: runtime 25.08 (24.08 ya está fuera de soporte)

- `runtime-version` pasa de 24.08 a 25.08 (soporte hasta sep-2027).
- **Lanzador** (`packaging/flatpak/blip-eraser`): ya no fija
  `/app/lib/python3.12/site-packages`; añade el `site-packages` de la versión
  de Python que traiga el runtime (24.08 = 3.12, 25.08 = 3.13).
- **Ruedas**: se añade `pyqt6_sip` para `cp313` (no es abi3); pip instala la
  que coincide con el intérprete. `krb5` se compila con `-std=gnu17` por si el
  compilador del runtime usa C23 por defecto.
- **PyGObject**: `pycairo` se instala antes y por separado, y PyGObject se
  compila con `PYTHONPATH` apuntando a `/app` (su `meson.build` busca los
  encabezados con `find_spec("cairo")`; la 25.08 ya no trae pycairo).
- Pendiente de comprobar en un build real (`flatpak-builder`): no se ha podido
  construir en el entorno de desarrollo.

### 🚀 v1.2.0: rediseño completo, bandeja del sistema y temas renovados

- **Rediseño de toda la interfaz** con tarjetas con sombra, encabezado con el
  título de la sección, barra lateral con píldora en degradado y tablas sin
  rejilla: Vista general, Desinstalador, Limpiador, Rendimiento y las tres
  pestañas de Configuración, con los textos y datos reales de la app.
- **Temas renovados** con paleta de degradados, contraste AA y las cifras de la
  Vista general en tarjetas que siguen el acento de cada tema.
- **Barra lateral**: resumen de la actividad reciente bajo la navegación.
- **Bandeja del sistema** (`blip-eraser-tray`): ventanita temática con estado,
  escanear, limpiar y abrir la app.
- **Ayuda**: la sección «Uso» describe las 5 secciones reales.
- **Corrección**: la app ya no se cierra sola al abrir el Desinstalador (la
  ventana principal no tenía dueño y el recolector de Python podía destruirla).
- Detalle de cada cambio en las entradas siguientes.

### 🐛 Fix: la app se cerraba sola al abrir el Desinstalador

- **Síntoma**: la ventana desaparecía al instante al entrar en la pestaña
  Desinstalador (salida limpia, código 0, sin traceback). El log mostraba un
  `DeferredDelete` sobre la `MainWindow` sin `closeEvent`.
- **Causa**: en `main()` la ventana era una variable local del slot
  `_on_worker_finished` y solo la mantenía un ciclo de referencias (ventana →
  página → callback `_post_scan` → ventana). Sin dueño externo, el recolector
  de Python podía destruirla en cualquier momento; cargar miles de paquetes lo
  provocaba.
- **Arreglo**: `retain_main_window(app, window)` ancla la ventana a la
  `QApplication` desde que se crea. Se añade `scripts/diag_close.py` (rama de
  diagnóstico) para investigar cierres inesperados.

### 🔔 Bandeja del sistema (`blip-eraser-tray`)

- **Qué es**: proceso aparte (`blip-eraser-tray` o `python -m blip_eraser.tray`)
  con un icono de bandeja; no abre la ventana principal. Instancia única
  (`QLockFile`); sale con un mensaje si el escritorio no tiene bandeja.
  Aplica el tema/fuente de la app también a los diálogos de confirmación.
- **Clic izquierdo = ventanita** (`tray/popup.py`) con el tema y la fuente de la
  app principal (relee `prefs.json` cada vez que se abre): barras de CPU/RAM/
  disco, espacio recuperable y tres acciones: **Escanear**, **Limpiar** y
  **Abrir BlipEraser**. Es una ventana `Tool` sin marco (no `Qt.Popup`: en Wayland un
  popup con grab exige una ventana padre con input y falla con "Failed to create
  grabbing popup"); se cierra al perder el foco o con Esc. Se coloca junto al icono (`logic.popup_position`, siempre dentro de la
  pantalla; en Wayland el compositor decide la posición de las ventanas, así que
  allí puede aparecer en otro sitio) y un clic que acaba de cerrarla no la reabre.
- **Posición**: se puede **arrastrar** desde cualquier zona libre (con
  `startSystemMove`, que también funciona en Wayland; si no, arrastre manual).
  En Ajustes de la app padre hay un selector 3x3 (esquinas, bordes y centro) +
  "Junto al icono" (`tray_popup_position`). Tras arrastrar en X11/XWayland se
  guarda la posición (`custom` + `tray_popup_custom`, recortada a la pantalla
  al abrir). En Wayland el compositor no deja a una app elegir dónde se abre
  su ventana, así que la bandeja arranca por XWayland (ver más abajo).
  "Reiniciar bandeja" (clic derecho) la relanza esperando el bloqueo
  (`--wait-lock`).
- **"Junto a la bandeja" (auto)**: Wayland no entrega la posición del icono ni
  deja colocar ventanas, así que la bandeja arranca siempre por XWayland si
  existe (`QT_QPA_PLATFORM=xcb;wayland`, con Wayland nativo de respaldo). Si la
  posición del icono se conoce (geometría del icono, o el cursor en X11 real)
  se abre junto a él; si no, en la esquina donde suele estar la bandeja,
  deducida de dónde hay panel (`guess_tray_corner`: pantalla completa vs área
  disponible).
- **La bandeja sigue al cerrar la app**: al salir, la app principal lanza la
  bandeja si no hay una activa (`tray/launcher.py`, comprobando su bloqueo de
  instancia única) para dejarla en segundo plano; cerrar del todo es un paso
  más ("Salir" en su menú). Casilla en Ajustes ("Mantener la bandeja activa al
  cerrar BlipEraser", `tray_keep_running`, activa por defecto). No se lanza en
  Flatpak.
- **Clic derecho = ajustes**: abrir, iniciar con la sesión, avisos y salir.
- **Consumo en reposo nulo**: CPU/RAM/disco y `scan_cleanup` se calculan en un
  hilo solo al abrir la ventanita o pulsar Escanear.
- **Limpiar usa el mismo flujo que la app** (`run_destructive_action`): lista lo
  que se va a borrar (`cleanup_confirm_items`, compartido con la Vista
  general), pide confirmación y el borrado con privilegios pide la
  contraseña de polkit. Desde la bandeja no hay ningún camino que borre sin
  confirmar. Si el listado falla o está vacío, no se borra nada.
- **Avisos** (`tray/logic.py`, pura y testeada): UNA comprobación 10 s después
  de iniciar, con la caché de 24 h de `check_for_updates`. Versión nueva: una
  vez por versión (`tray_notified_version`). Espacio recuperable ≥ 5 GiB: como
  mucho cada 24 h (`tray_junk_notified_at`); una marca corrupta o futura no
  silencia para siempre. `tray_notifications: false` lo apaga todo. Pulsar el
  aviso de versión abre la página de releases; el de espacio abre la ventanita.
- **Autoarranque opt-in** desde el propio menú: crea/borra
  `~/.config/autostart/blip-eraser-tray.desktop` (respeta `XDG_CONFIG_HOME`).
- **Empaquetado**: script `blip-eraser-tray` en `pyproject.toml`,
  `packaging/blip-eraser-tray.desktop` instalado por el PKGBUILD y por
  `install-daemon.sh`. El Flatpak no la incluye (necesitaría permiso para
  StatusNotifierWatcher).
- Claves i18n nuevas `tray_*` (ES/EN). Tests: `test_tray_logic.py`,
  `test_tray_gui.py`.
### 🎨 Temas renovados y actividad reciente en la barra lateral

- **Temas**: nueva paleta con más jerarquía entre fondo, panel y borde; relleno
  con degradado sutil en botones, selección, insignia y barra de progreso;
  halo en el anillo de salud; texto sobre el acento por tema (`on_accent`:
  oscuro en Verde, donde el blanco daba 2.2:1) y colores de etiquetas
  APP/DEP/CARPETA más oscuros en los temas claros. El hover del botón primario
  usa un tono del propio acento. Claves nuevas en `THEMES`: `fill_top`,
  `fill_bot`, `hover_fill`, `on_accent`, `accent_text`, `tags`. Tests de
  contraste (≥4.5:1) para esos pares en los 4 temas. Las sombras del
  prototipo no se replican: QSS no admite `box-shadow`.
- **Barra lateral**: el espacio libre bajo la navegación muestra ahora las últimas
  6 entradas del registro (la más nueva arriba, resaltada con el acento). Es un
  resumen de solo lectura; el historial completo y el borrado siguen en el
  panel «Actividad de la app». Claves i18n nuevas: `sidebar_activity_title`,
  `sidebar_activity_empty`.

### 🎨 Rediseño (lote 4) — Configuración

- **Tema de color**: dos tarjetas. Apariencia (muestras de color con su punto,
  chips de fuente, «Ver permisos de BlipEraser») y bandeja (cuadrícula de
  posición, «Junto a la bandeja», mantener activa). Los `QComboBox` siguen
  siendo el modelo (ocultos): las muestras y chips los reflejan y los
  controlan, así que señales y preferencias no cambian.
- **Personalización**: lista de rutas en tarjeta con separadores; «Guardar
  cambios» como botón principal.
- **Ayuda**: cada sección en su tarjeta.
- Casillas con marca propia en toda la app y barras de desplazamiento finas.

### 🎨 Rediseño (lote 3) — Ajustes de rendimiento

- Cada ajuste va en su tarjeta: interruptor con perilla (QSS no puede dibujarla:
  imágenes SVG por tema generadas en el directorio temporal), título, descripción,
  vista previa del recurso y «?» de ayuda. El motivo de bloqueo se muestra como
  nota en la propia tarjeta (antes solo en el tooltip).
- Avisos (reinicio, estado, error, «Reaplicar») con el estilo del tema.
- Las vistas previas ahora siguen el tema al cambiarlo (antes quedaban con el
  color del arranque).

### 🎨 Rediseño (lote 2) — Desinstalador y Limpiador

- **Tablas**: sin rejilla, con separador fino por fila, encabezados en
  mayúsculas pequeñas, Peso/Fecha/Tamaño alineados a la derecha y columnas
  secundarias atenuadas. Dentro de una tarjeta con sombra.
- **Tipo** (Desinstalador): etiqueta con contorno (`TagDelegate`) con los
  mismos colores que en la Vista general.
- **Pestañas** (Limpiador, Configuración): control segmentado con degradado en
  la activa. Botón principal a la derecha y «Actualizar lista» a la izquierda;
  el principal se atenúa cuando está deshabilitado. Marca de verificación
  propia en las casillas (SVG generado por color en el directorio temporal).
- **Vista general**: anillo con más aire, cifras en tarjetas con barra y brillo
  del tema (`StatTile`) y botón «Escanear ahora» más compacto.

### 🎨 Rediseño (lote 1) — estructura y Vista general

- **Estructura**: logo y nombre arriba de la barra lateral, navegación solo de
  texto con píldora de degradado y actividad reciente debajo. El encabezado
  muestra el título de la página (los títulos internos de cada página se
  ocultan); búsqueda y «Actividad de la app» siguen solo en Desinstalador y
  Limpiador.
- **Sombras**: nuevo widget `Card` (`widgets/card.py`) que pinta fondo, borde y
  sombra con `QPainter` (QSS no admite `box-shadow`).
- **Vista general**: salud + tres métricas arriba; aplicaciones instaladas e
  información del sistema (con barras de CPU/RAM/disco) en medio; limpieza
  recomendada con «Escanear ahora» / «Limpiar ahora» abajo. Se quita
  «Actividad reciente» de esta página (ya está en la barra lateral). El estado
  del anillo es más oscuro en los temas claros.
- **Ayuda**: la sección «Uso» describe ahora las 5 secciones reales (ES/EN).
- El resto de pestañas se rediseñan en los siguientes lotes
  (`docs/superpowers/specs/2026-11-07-redesign-shell-design.md`).

### 🚀 v1.1.1: fluidez del escaneo, endurecimiento y aviso de versión

- **Fluidez**: el escaneo (botón y autoescaneo) ya no deja la app colgada. La
  lista aparece enseguida (filas por tandas), los pesos de carpetas sueltas se
  calculan en segundo plano con caché, y pacman, limpieza y apps corren a la
  vez. Medido en un equipo real con 1668 apps: de ~9 s a ~2 s por escaneo, con
  la interfaz usable durante todo el proceso.
- **Arranque**: el splash refleja comprobaciones reales (dependencias del
  daemon, binarios necesarios) y ya no bloquea antes de mostrar la ventana.
- **Seguridad**: el daemon abre rutas sin seguir symlinks en ningún tramo y
  usa un filtro mínimo de syscalls; el instalador normaliza permisos de
  código que corre como root y rechaza symlinks.
- **Tweaks**: una sola autorización (pkexec) por ajuste.
- **Aviso de versión nueva** en segundo plano, con caché de 24 h y opción
  `check_updates: false` para desactivarlo.
- **Mantenimiento**: Dependabot agrupa subidas menores y parches en un PR.
- Detalle de cada cambio en las entradas siguientes.

### 🧊 Escaneo: tamaños de carpetas sin acaparar el GIL

- **Medición en host** (1668 apps): pintar 100 filas cuesta 0,3–0,5 s, así que
  el cuelgue de ~15 s no venía de la lista sino del escaneo en segundo plano.
- **Causa probable**: `get_dir_size` recorría `~/.cache`, la caché de pacman y
  `/var/log` con `Path.rglob` + `is_file`/`is_symlink`/`stat` por entrada, todo
  en Python puro: el hilo de fondo retiene el GIL y la interfaz deja de
  responder aunque no esté "bloqueada" a propósito.
- **Cambio**: recorrido iterativo con `os.scandir` (sin crear `Path` por entrada,
  ~5× más rápido en `/usr/lib`: 0,43 s → 0,09 s, mismo resultado) y cesión del
  GIL cada 256 entradas. Mismas reglas: no sigue ni cuenta symlinks.
- **Segunda medición en host** (1668 apps): `list_apps_ms` 7–9 s y
  `cleanup_ms` 0,6 s, ya con `os.scandir`: el cuello es `list_installed_apps`.
  Sus consultas a pacman (`-Qe`, `-Qd`, `-Qi`) y el tamaño de cada carpeta
  manual se hacían en fila; ahora corren a la vez (`ThreadPoolExecutor`), y
  `scan_cleanup` mide sus 4 partes también a la vez, igual que apps y limpieza
  entre sí. El escaneo tarda ahora lo de la parte más lenta, no la suma.
- **Perfil en host** (`scripts/profile_scan.py`): pacman entero cuesta <0,6 s;
  dimensionar las 163 carpetas sueltas (`~/.local`, Steam, `.gradle`…) sumaba
  ~6,3 s y era lo que mantenía la lista vacía. Ahora `list_installed_apps(
  manual_sizes=False)` devuelve la lista al instante y `fill_manual_sizes`
  calcula los pesos en un hilo aparte (3 carpetas a la vez) mientras la
  interfaz ya es usable; al terminar se actualizan las filas (Vista general) o
  se re-renderiza la tabla si no hay selección (Desinstalador). Los pesos se
  cachean 10 min: reescanear o abrir el Desinstalador no vuelve a recorrer.
- `sys.setswitchinterval(0.001)` al arrancar: los hilos de escaneo en Python
  puro ya no retienen el GIL hasta 5 ms cada vez que la interfaz lo pide.
- `scripts/profile_scan.py`: mide cada fase sin GUI
  (`PYTHONPATH=src python scripts/profile_scan.py`).
- Lotes de la lista de 100 a 40 filas (≈0,15 s por lote en tu equipo).
- Nueva línea `PERF overview_scan_worker apps=… list_apps_ms=… cleanup_ms=…`
  para ver cuánto tarda cada fase del escaneo.

### 🧊 Vista general: la lista de apps ya no congela la ventana tras escanear

- **Síntoma** (reportado en CachyOS): tras pulsar "Escanear" y en el
  autoescaneo, la app quedaba colgada ~15 s sin dejar hacer nada.
- **Causa medida** (benchmark sintético, ventana completa con QSS, offscreen):
  `_rebuild_apps` creaba una fila de ~8 widgets por CADA app instalada, de golpe
  y en el hilo de la interfaz. Con 500 apps ≈ 0,4 s; 1500 ≈ 2,1 s; 3000 ≈ 8,3 s:
  el coste crece más que linealmente (estilo QSS + layout con word-wrap). Además
  se escribían 2 líneas de diagnóstico por fila.
- **Cambio**: la lista se renderiza por tandas de `APPS_BATCH = 100` filas; al
  acercarse al final del scroll (o si el contenido no llena la ventana) se crea
  la siguiente. Un escaneo nuevo reinicia la ventana; cambiar de idioma conserva
  lo ya cargado. El contador sigue mostrando el total real. Con 3000 apps el
  bloqueo medido baja de 8,3 s a 0,12 s, y es independiente del número de apps.
- Se quitan los 2 diagnósticos por fila y el `QIcon.fromTheme` de respaldo que se
  evaluaba en cada fila; quedan una línea `PERF overview_rebuild …` por
  reconstrucción y `PERF overview_load_more …` por tanda (ver
  `~/.cache/blip-eraser/diagnostics.log`) para medir en el host.
- **Pendiente de medir en host**: el tiempo del escaneo en segundo plano
  (`list_installed_apps` + `scan_cleanup`) y la tabla del desinstalador.

### 🚦 Arranque: comprobaciones reales, fuera del hilo de la interfaz

- **Hallazgo**: `main()` ejecutaba `_check_and_install_daemon_deps()` de forma
  síncrona ANTES del splash: hasta 6 subprocesos (PyGObject, `gst-inspect`,
  `systemctl`) de 5 s cada uno, y cada comando se lanzaba dos veces porque el de
  "instalado" y el de "activo" eran idénticos. Además `StartupWorker` solo emitía
  5 pasos decorativos de 100 ms, en inglés fijo (las claves `splash_check_*`
  estaban sin usar), y los avisos de binarios y de permisos nunca se calculaban.
- **Ahora**: `StartupWorker` hace dos comprobaciones reales durante el splash
  (binarios `pacman`/`pkexec` y dependencias del daemon), con mensajes traducidos
  y sin esperas artificiales. Un fallo en una comprobación no impide arrancar.
  Los resultados se usan tras el primer escaneo: modal de binarios faltantes
  (solo si falta algo) y oferta de instalar dependencias del daemon, con la
  ventana ya visible.
- **Dependencias del daemon**: un solo subproceso por comprobación (el de
  "activo" solo se lanza si es distinto del de "instalado"). `gst-libav` deja de
  ser "dependencia del daemon" (solo sirve al vídeo del splash, que ya registra
  su propio hint); PyGObject y `dbus` siguen ofreciendo instalación.
- **Permisos**: el diálogo informativo se queda solo en Configuración (decisión
  del mantenedor). Se elimina la rama muerta de `main.py`.
- Claves i18n nuevas: `splash_check_daemon` (ES/EN). Siguen sin uso
  `splash_check_updates`, `splash_check_permissions`, `splash_scanning` y
  `splash_welcome` (el mensaje de "escaneo finalizado" no era cierto: el escaneo
  corre después del splash; se retomará en la revisión de fluidez).
- **Pendiente**: el modal de dependencias del daemon sigue con textos fijos en
  español (no pasa por `tr()`).

### 🤖 Dependabot: subidas menores y parches en un solo PR

- Las acciones de GitHub están pineadas por SHA en las mismas líneas de
  `ci.yml`, así que fusionar un PR de Dependabot dejaba en conflicto a los
  demás (ya ocurrió con #12-#14). Ahora un grupo `actions-minor-patch` reúne
  todas las subidas menores y parches en un único PR por semana.
- Las subidas **mayores** siguen llegando en PR separados: son las que hay que
  revisar con calma. Frecuencia semanal y límite de 3 PR abiertos sin cambios.

### 🔔 Aviso de versión nueva (con caché de 24 h)

- **Hallazgo**: `check_for_updates()` existía (con tests) pero nada la llamaba, y
  los mensajes del splash ("comprobando actualizaciones/permisos/dependencias")
  son decorativos. El aviso de permisos y el de binarios faltantes tampoco se
  calculan (`StartupWorker` los deja vacíos); se revisarán en un PR aparte.
- **Ahora**: `MainWindow.start_update_check()` (llamado desde `main.py` tras
  mostrar la ventana, nunca desde `__init__`) lanza un hilo daemon
  (`widgets/update_notice.UpdateNotifier`). Si hay versión nueva aparece un
  aviso discreto con enlace a la release en la barra de estado: sin diálogo y
  sin descarga automática.
- **Caché**: como máximo 1 consulta a GitHub cada 24 h (`update_latest` y
  `update_checked_at` en `prefs.json`). El tag cacheado se compara siempre con la
  versión actual (tras actualizar deja de avisar). Un fallo de red no se
  cachea. Reloj que retrocede o valores corruptos invalidan la caché.
- **Desactivar**: `"check_updates": false` en `~/.config/blip-eraser/prefs.json`.
- **Flatpak**: el manifiesto no tiene `--share=network`, así que allí nunca
  comprueba (no se amplían permisos solo para esto).
- Tests: caché (hit, caducidad, versión actual, fallo, reloj, opt-out, valores
  corruptos), aviso en la barra (versión, enlace, idioma) y notificador (emite,
  silencioso, tolera excepciones); construir la ventana no abre red.

### ⚡ Tweaks: una sola autorización por ajuste

- **Antes**: activar zram encadenaba hasta 6 `pkexec` (instalar paquete,
  comprobar archivo, respaldar, escribir, `daemon-reload`, `enable`), y cada uno
  podía pedir contraseña; reflector y zswap igual.
- **Ahora**: los pasos privilegiados de cada tweak se agrupan en un único
  `pkexec sh -c` con `set -e` (el primer fallo aborta el resto). Todo valor
  interpolado pasa por `shlex.quote`; el contenido de los archivos se escribe
  con `printf %s`.
- Se conserva la copia `.blip-bak` (solo la primera vez) y su restauración al
  desactivar. Si `systemd-tmpfiles` falla al activar zswap, el propio script
  deshace la configuración.
- También corrige que la escritura de archivos root no pasaba por
  `host_cmd` (fallaba en Flatpak).
- Se eliminan `_write_root_file`, `_backup_root_file`, `_remove_root_file` e
  `_install_pkg_via_pkexec` (sustituidos por `_sh_*` + `_run_privileged`).
- Tests: un solo `pkexec` por tweak y sentido, orden de los pasos, sintaxis
  `sh -n` y ejecución real de los fragmentos (respaldo, restauración,
  rollback, rutas con espacios y comillas).

### 🔒 Daemon: apertura de rutas sin seguir symlinks en ningún tramo

- **Hueco**: `_rm_rf_atomic` abría el directorio padre con `O_NOFOLLOW`, que solo
  protege el último componente; un symlink intermedio cambiado entre la
  validación y la apertura se seguía.
- **Ahora**: `_open_dir_nofollow` abre el prefijo de la allowlist y recorre cada
  componente restante con `O_NOFOLLOW | O_DIRECTORY` relativo al fd anterior
  (equivale a `openat2` con `RESOLVE_NO_SYMLINKS`, en Python puro). Exige ruta
  absoluta canónica dentro de un prefijo permitido.
- **Por qué no `openat2`**: requeriría `ctypes` (choca con
  `MemoryDenyWriteExecute`/AppArmor) y kernel >= 5.6.
- **Por qué no desde `/`**: el perfil de AppArmor solo permite abrir los propios
  prefijos (`/var/log/`, `/var/cache/pacman/pkg/`); además los tramos por encima
  son de root y los que pueden pertenecer a cuentas de servicio están debajo.
- Tests: symlink intermedio y final, rutas no canónicas, fuera de allowlist,
  prefijo más largo, y borrado a través de un enlace intermedio.

### 🔒 Instalador: código de root con permisos normalizados

- **Riesgo**: `install-daemon.sh` copiaba `src/blip_eraser` a `/usr/lib/blip-eraser`
  con `cp -r`, heredando permisos del árbol de origen y el umask del invocador,
  y aceptando symlinks. Ese código lo ejecuta root.
- **Ahora**: el script rechaza symlinks en el origen, normaliza directorios a
  755 y ficheros a 644, y fija `root:root` en la instalación real. El
  `PKGBUILD` hace la misma normalización.
- Test que ejecuta el script real en modo `DESTDIR` contra un árbol con permisos
  laxos (umask 0) y con un symlink.

### 🔒 Daemon: filtro de syscalls mínimo

- **Antes**: `SystemCallFilter` sumaba `@clock @cpu-emulation @debug @module
  @obsolete @raw-io` a `@system-service` (y repetía este último).
- **Ahora**: solo `@system-service`. El daemon borra ficheros y atiende D-Bus;
  un trazado con `strace` de su batería de tests no usó ninguna syscall de los
  grupos retirados (todas caen dentro de `@system-service`).
- Test que impide volver a ampliar el filtro. **Reversión**: restaurar la línea
  anterior de la unidad y `sudo systemctl daemon-reload; sudo systemctl restart
  blip-eraser-privileged`.

### 🚀 v1.1.0: desinstalación fiable, tweaks protegidos y CI

- **Desinstalar**: los paquetes se eliminan con `pkexec pacman -Rns`; el daemon
  solo limpia caché y logs, y atiende las llamadas D-Bus en hilos (un prompt de
  polkit ya no lo congela).
- **Tweaks** (TRIM, zram, zswap, espejos): opcionales y desactivados por
  defecto; se bloquean con explicación si el sistema ya gestiona zram o los
  espejos; al arrancar se reconcilian sin pisar la elección del usuario.
- **Seguridad**: registros de auditoría protegidos, reglas de elevación y
  guardia de puntos de montaje, polkit restringido a `wheel`; el instalador
  copia también las reglas polkit.
- **Descargas** respeta `XDG_DOWNLOAD_DIR`.
- **CI**: ruff, shellcheck y tests de GUI offscreen; Dependabot semanal para
  las acciones de GitHub.
- **Documentación**: README ES/EN reescritos y guías de instalación con venv.
- Los paquetes publicados (v1.0.6) no incluyen nada de esto hasta publicar la
  release.

### 🧵 Daemon: un prompt de polkit ya no lo congela

- **Problema**: cada llamada D-Bus corría en el bucle principal; con un
  diálogo de polkit abierto (hasta 180 s) el daemon no atendía ni `Ping`, y el
  cliente cortaba a los 25 s (timeout por defecto de GDBus) mientras el daemon
  seguía esperando: si el usuario escribía la contraseña después, borraba pese
  al error mostrado.
- **Cambio**: cada llamada se atiende en un hilo daemon (máx. 8); un solo
  prompt/operación por UID (el resto recibe `LimitsExceeded`); la cuota por
  UID se aplica **antes** de polkit (cancelar o fallar el prompt también
  cuenta); la limpieza en sí se serializa; el cliente espera hasta 200 s.
- Tests: Ping responde con un prompt abierto, segunda operación del mismo UID
  rechazada, cuota previa a polkit, ranura liberada tras fallo, servidor
  ocupado, timeout del cliente > prompt de polkit.

### 🐛 Desinstalar paquetes: el daemon ya no ejecuta pacman

- **Bug real (CachyOS, reproducido en host)**: el daemon arrancaba con
  `pacman_cache_init count=0` (su `pacman -Q` fallaba con código 255 dentro
  del sandbox) y rechazaba TODA desinstalación como
  `Paquetes no instalados (rechazados)`, aunque el paquete estuviera instalado.
- **Causa de fondo**: `pacman -Rns` ejecuta hooks (snapper, limine-snapper-sync,
  initramfs…) y escribe en `/usr`, `/etc` y `/var/lib/pacman`; no encaja con
  `ProtectSystem=strict` + AppArmor.
- **Cambio**: se elimina `RemovePackages` del daemon (método D-Bus, caché de
  paquetes, verificación de firmas, refresco periódico). La desinstalación va por
  `pkexec pacman -Rns` (acción polkit `pacman-remove`); el daemon solo limpia
  caché y logs. Perfil AppArmor y unidad systemd sin rastro de pacman.
- **Cliente**: la validación consulta `pacman -Q` en vivo, sin caché. Si la
  consulta falla se informa el stderr: un fallo ya no equivale a "0 paquetes".
- **Se elimina el gate de firmas de la caché** (`.sig`): en CachyOS/AUR la caché
  no trae firmas, así que bloqueaba todo (y cerraba la app). pacman ya verifica
  firmas al instalar.
- Tests de regresión: consulta fallida ≠ BD vacía, `RemovePackages` desconocido
  en el daemon, `pkexec` siempre en el cliente.

### ✨ v1.0.6: splash sin franja gris

- Mensaje del video sin panel: texto blanco en negrita con sombra,
  legible directo sobre el video (el fallback nunca tuvo panel).

### 📦 v1.0.5: seguridad auditada + video en Flatpak

- Rate-limit del daemon por UID (evadible reconectando antes).
- Hallazgos Strix/Cloudflare: `..` normalizado, `--` en pacman,
  binarios absolutos, quote sh, pins SHA en CI.
- Flatpak: krb5 empaquetado (QtMultimedia importaba por
  `libgssapi_krb5` ausente; H.264 verificado decodificando en sandbox:
  401 frames, 0 errores) + fallbacks del splash diagnosticados.
- AppArmor: tune guiado GUI (`aa-tune-gui.sh`) + autostart `aa-notify`.

### 🛡️ Red Team: rate-limit por UID (evadible reconectando)

- **PoC**: 12× `RemovePackages` con conexión nueva cada vez → 0
  `LimitsExceeded`; misma prueba en una conexión → 11ª y 12ª limitadas.
  La cuota se indexaba por nombre único D-Bus (`:1.NNN`, efímero).
- **Fix**: cuota por UID real (`_authorized_uid`, ya resuelto en auth)
  + test de regresión + verificado en vivo contra el daemon.
  Redesplegar con `./scripts/install-daemon.sh`.

### ⚡ v1.0.4: fluidez (sin hilos duplicados, render por lotes)

- `showEvent` no programa escaneo con otro en vuelo (Desinstalador,
  Limpiador): navegar y volver ya no apila hilos de `pacman`.
- `_render` del Desinstalador por lotes (era O(n²) por `itemChanged`);
  headers a Stretch con mínimo en ambas tablas.
- Tests de pacman aislados del FS real. Suite 610 passed.

### 🔧 v1.0.3: disco real en Flatpak + splash diagnosticado

- **Disco**: `shutil.disk_usage("/")` medía el overlay del sandbox → 0%.
  En Flatpak se pregunta al host (`df -B1` vía spawn) en `disk_usage_percent`
  y `disk_total_bytes` + tests.
- **Splash**: `_on_media_error` ya no es silencioso — `SPLASH_VIDEO_ERROR`
  en bitácora (error + hint `gst-libav`/FFmpeg) y aviso `splash_no_video`
  (ES/EN) en la barra + tests.

### 🔧 v1.0.2: GUI (botón SCAN NOW + splash video fullscreen)

- Botón: altura 112, badge sin relleno (transparencia total), subtítulo ES
  acortado; tests de píxeles ES/EN.
- Splash: asset `splash-intro.mp4`, `setSource` real, `_start_intro()`
  invocado, video fullscreen con recorte, overlays con geometría y orden
  video→fondo→texto; `_intro_done` también en modo video.
- Flatpak de este release construido del tag (el v1.0.1 salió del working
  tree: misma versión de código, distinta revisión).

### 📦 v1.0.1: AUR (PKGBUILD validado con makepkg)

- **Fix**: eliminados `data-files` absolutos de `pyproject.toml` (el wheel
  los anidaba bajo `site-packages` en vez de `/usr`, `/etc`). Cada vía
  instala lo suyo: `install-daemon.sh` (nativo), `package()` del PKGBUILD
  (AUR); el flatpak los excluye por diseño.
- **Nuevo**: `packaging/aur/` (`PKGBUILD`, `blip-eraser.install`) —
  paquete `blip-eraser` validado con `makepkg`: binario, daemon en
  `/usr/lib/blip-eraser`, systemd + D-Bus + polkit + AppArmor + `.desktop`
  + icono + licencia, todo en su sitio.
- Fuente AUR: asset `BlipEraser-1.0.1.tar.gz` del release (el tarball
  auto-generado de GitHub daba 404; el repo es privado y AUR exige
  fuentes de descarga anónima — ver decisión pendiente).

### 🛡️ AppArmor en enforce (Fase 3 verificada en host real)

- **Hallazgo**: el daemon corría `unconfined` — con shebang el kernel
  ejecuta `python3` y el perfil jamás se adjuntaba. Fix: `AppArmorProfile=`
  en la unidad systemd (`packaging/systemd/`).
- **Trampa documentada**: las reglas `deny /** w` se aplican INCLUSO en
  complain (niegan en silencio, sin log) y rompían todo borrado. Fuera:
  por defecto ya niega lo no permitido.
- **Perfil endurecido con evidencia** (`audit.log`): `abstractions/python`,
  exec `pacman/pacman-key/pacman-conf/loginctl/gpg/gpgconf/gpgsm/grep`
  (`rix`), lecturas makepkg/`pacman.conf`/mirrorlists/`nsswitch`/`userdb`,
  `boot_id`, `mounts`, XML de la interfaz, `/dev/tty rw`, `/dev/null`,
  peer D-Bus `unconfined` + GUI; capacidades mínimas (sin setuid/setgid);
  sin red. Perfil GUI a complain (dormido: no existe `/usr/bin/blip-eraser`).
- **Verificado en enforce**: Ping + `CleanSystemPaths` real + rechazo de
  `RemovePackages`, **0 DENIED**. `install-daemon.sh` ahora carga enforce.

### ✅ v1.1 cerrado + release v1.0.0 con Flatpak descargable

- **v1.1 (hecho)**: suite verde (`591 passed, 3 skipped`) + CI mínimo
  (`.github/workflows/ci.yml`: `compileall` + `pytest` en cada push/PR);
  allowlist/denylist única en `utils/validation.py` (`dbus_client`
  deduplicado a re-export); versión `1.0.0` sincronizada; raíz limpia.
- **v1.3 (parcial, lo que faltaba barato)**: `check_for_updates()` real
  contra GitHub Releases (stdlib `urllib`, timeout 5s, fail-closed;
  `tests/test_updates.py` mockea `urlopen`, sin red real) +
  rate-limit del daemon (10 ops destructivas/min por sender, `Ping`
  exento, error `LimitsExceeded`) + tests (`TestRateLimit`).
- **Flatpak sideload** (puente hasta Flathub): `packaging/flatpak/`
  (`io.github.DinoPathTeam.BlipEraser.yml`, lanzador, metainfo) +
  shim `utils/host_cmd.py` (`flatpak-spawn --host` + `$HOME`/`~` del
  host en `scan`, `file_utils`, `privileges`, `pacman`, `system_stats`,
  `dependency_check`, `performance`, `dbus_client`;
  `phase2_installer` queda fuera: desde el sandbox se usa
  `install-daemon.sh` en el host). Verificado: build OK, PyQt 6.11,
  spawn al host, arranque offscreen 25s sin errores.
- **Release**: tag `v1.0.0` + asset `BlipEraser-v1.0.0-x86_64.flatpak`
  (91 MB) + pasos Flatpak en README (EN+ES).
- **Queda**: AppArmor en enforce (hoy complain), PyGObject en el bundle
  (hoy fallback pkexec-host), gettext, E2E, Flathub ⏸️.

### 🎬 Splash Screen con video de intro + migración a QVideoSink

- **Qué**: sustituye la animación de logo del splash por un video real (6.2s, 1080p, H.264) con mensajes de progreso superpuestos.
- **Problema resuelto**: el video no se decodificaba en CachyOS por falta de codecs H.264 → `gst-plugins-good` no los incluye (licencias). La app caía en fallback silencioso a logo animado (con borde visible = "barras negras" reportadas).
- **Fix**:
  1. `pyproject.toml`: documenta `gst-libav` como dependencia **requerida** (`sudo pacman -S gst-libav`).
  2. `splash_screen.py`: migración de `QVideoWidget` (superficie nativa que tapa widgets hermanos) a `QVideoSink` + `_VideoWidget` con `paintEvent` manual. Esto permite:
     - `KeepAspectRatioByExpanding` sin letterboxing (recorta 16:9 al contenedor).
     - z-order normal: mensaje de progreso como hijo del mismo padre, `raise_()` en cada frame.
  3. `_on_media_error`: detecta errores de "shared library"/"plugin"/"decoder" y loggea hint automático: `SPLASH_CODEC_HINT: sudo pacman -S gst-libav`.
- **Archivos**: `src/blip_eraser/widgets/splash_screen.py`, `pyproject.toml`, `src/blip_eraser/assets/splash-intro.mp4` (nuevo, sin marca de agua).
- **Tests**: `tests/test_splash_screen.py` extendido (`TestVideoWidget`, `test_message_visible_over_video_widget`).

### 🛡️ Firewall de seguridad (Fase 1 completada)

- **Objetivo**: restringir operaciones privilegiadas (`pkexec pacman -Rns`, `pkexec rm -rf`) a allowlist estricta y validar paths antes de ejecutar.
- **Alcance Fase 1 (completado)**: policy polkit custom (`/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy`) + validación estricta en `privileges.py` (resolve + allowlist `/var/cache/pacman/pkg`, `/var/log`, `/var/lib/pacman` + rechazo symlinks) + auditoría estructurada en bitácora forense + validación de paquetes en `pacman.py` antes de desinstalar.
- **Alcance Fase 2 (completado - daemon D-Bus)**: demonio systemd D-Bus (`blip-eraser-privileged`) con separación real de privilegios.
  - **Implementado**: `src/blip_eraser/daemon/privileged_daemon.py` (daemon D-Bus), `packaging/systemd/blip-eraser-privileged.service`, `packaging/dbus/blip-eraser-privileged.conf` (policy restrictiva a grupo `wheel`), `packaging/scripts/blip-eraser-privileged` (wrapper).
  - **Validaciones**: allowlist de paths, rechazo symlinks, verificación de firmas de paquetes (pacman-key), caché thread-safe de paquetes instalados.
  - **Política D-Bus**: restrictiva a grupo `wheel` (usuarios admin en Arch), deny por defecto.
  - **Tests**: `tests/test_privileged_daemon.py` (24 tests: validaciones, operaciones, caché, firmas, integración).
  - **Integración cliente**: `dbus_client.py` usa daemon con fallback a pkexec.
- **Alcance Fase 3 (pendiente)**: AppArmor profile (opcional).
- **Pendientes internos** (no públicos):
  - P0: Eliminar TOCTOU (requiere daemon Fase 2 — ahora implementado)
  - P1: `_reject_symlinks()` en Windows/WSL
  - P1: Pacman DB: cache + firma al inicio (Supply chain — implementado en daemon)
  - Fase 3: AppArmor profile (opcional)

### 📦 Instalación y activación del daemon privilegiado (Fase 2)

```bash
# 1. Instalar dependencias del daemon
sudo pacman -S python-gobject

# 2. Copiar archivos del sistema (requiere root)
sudo cp packaging/systemd/blip-eraser-privileged.service /usr/lib/systemd/system/
sudo cp packaging/dbus/blip-eraser-privileged.conf /usr/share/dbus-1/system.d/
sudo cp packaging/dbus/com.dinopath.BlipEraser.Privileged.xml /usr/share/dbus-1/interfaces/
sudo cp packaging/scripts/blip-eraser-privileged /usr/lib/blip-eraser/
sudo chmod +x /usr/lib/blip-eraser/blip-eraser-privileged

# 3. Recargar systemd y D-Bus
sudo systemctl daemon-reload
sudo systemctl enable --now blip-eraser-privileged.service

# 4. Verificar estado
systemctl status blip-eraser-privileged.service
# Debe mostrar: Active: active (running)

# 5. En la app: el cliente (dbus_client.py) usa el daemon automáticamente
#    si está disponible; si no, cae a pkexec (prefer_daemon=True por defecto).
```

> **Nota**: El daemon requiere que el usuario pertenezca al grupo `wheel` (estándar en Arch para usuarios admin). Si no, el D-Bus policy deniega el acceso y la app usa fallback pkexec.

- **Por qué:** tras contener `_rebuild_apps`, el crash volvió en el MISMO
  arranque pero en OTRO widget de OverviewPage: `QLabel has been deleted` en
  `_on_scan_done → _apply_cleanup → cleanup_junk_label.setText`. El widget
  muerto no tiene relación estructural con el anterior (`_apps_layout`) —
  apunta a que algo afecta a un bloque amplio (o toda) la página durante la
  ventana del arranque, no a un widget aislado. Fin del whack-a-mole.
- **Defensa por cadena:** `_on_scan_done` (Overview), `_on_apps_loaded`
  (Desinstalador) y ambos `_on_scan_ready` (Limpiador) envuelven el handler
  COMPLETO en un `try/except RuntimeError` único (no cada sub-llamada): si
  CUALQUIER widget muere en cualquier punto del procesamiento del resultado
  (o uno futuro), queda contenido en un solo lugar.
- **Forense con la pila exacta:** `_render_failure` ahora adjunta
  `traceback.format_exc()` a la bitácora → el próximo incidente revelará la
  línea y el atributo EXACTOS que se tocaban, sin depender de identificarlos
  de antemano.
- **Forense de instancias (hipótesis de página duplicada):**
  `__init__` de OverviewPage/UninstallerPage/secciones del Limpiador registra
  `CREATED id=<id(self)> ..._id=<id(widget)>` al construirse; el except del
  handler ya registra `page_id=<id(self)>`. Si vuelve a pasar, basta comparar
  el `id()` del crash contra los `CREATED` de la sesión: una sola construcción
  + ids de widgets distintos confirmaría reasignación; DOS construcciones
  confirmaría la instancia duplicada.
- **Grep exhaustivo:** `OverviewPage()` solo existe en `renderer.py:75`,
  dentro de `MainWindow.__init__`, y `MainWindow()` solo en `main.py:125`
  (`_on_worker_finished`, conectado una vez). No hay segundo camino de
  construcción en producción ni en código muerto; los dialogs de idioma/
  permisos no reconstruyen páginas.
- **Verificación:** `tests/test_render_hardening_gui.py` ampliado (+8 tests):
  el escenario NUEVO (cleanup_junk_label muere DESPUÉS de que `_rebuild_apps`
  corrió bien, dentro del mismo `_on_scan_done`) queda contenido con
  `RENDER_FAILED overview_page._on_scan_done` + pila con `cleanup_junk_label.
  setText`; camino feliz de `_on_scan_done`; el log `CREATED` de `__init__`;
  handlers de Desinstalador/Limpiador contienen fallos fuera del `_render`
  interno; y caminos felices de las 3 páginas. Suite: con PyQt6 `301 passed`;
  sin PyQt6 `239 passed, 8 skipped`.
- **Código:** `src/blip_eraser/widgets/scan_worker.py`,
  `src/blip_eraser/pages/overview_page.py`, `src/blip_eraser/pages/uninstaller_page.py`,
  `src/blip_eraser/pages/cleaner_page.py`, `tests/test_render_hardening_gui.py`,
  y fixtures `diag_redirect` en 4 test files GUI (bitácora forense fuera de la
  ruta real durante los tests).

### 🛡️ Defensa dura + instrumentación forense para renders (crash recurrente de CachyOS)

- **Por qué:** el crash `RuntimeError: wrapped C/C++ object of type QVBoxLayout
  has been deleted` en `overview_page._rebuild_apps` reapareció **3 veces** en
  CachyOS pese a los guards de entrada (commits `2074ecf` y `ca49ecf`). El
  número de línea del traceback confirmaba que el guard SÍ estaba desplegado,
  por lo que el layout muere a **MITAD** de la reconstrucción, después del
  guard inicial (la causa raíz exacta sigue sin diagnosticarse: el objetivo de
  esta ronda es que la app no se caiga y que el próximo fallo deje evidencia).
- **Defensa dura:** `_rebuild_apps` (Overview) y los `_render` del Desinstalador
  y las dos secciones del Limpiador envuelven su cuerpo en `try/except
  RuntimeError` que NO relanza: si un widget/layout muere en C++ durante el
  render, se avisa al usuario en el log ("No se pudo actualizar la lista;
  pulsa «Actualizar lista» para reintentar") y la app sigue funcionando.
- **Instrumentación forense:** nueva bitácora `write_diagnostic()` en
  `utils/log.py` → `~/.cache/blip-eraser/diagnostics.log` (timestamp + hilo,
  truncada a 2 MB, best-effort). En cada fallo se registran: `sip.isdeleted()`
  de página/layout/widget implicado, `id()` del layout (detecta reasignaciones),
  filas limpiadas / fila en curso / total, y `threading.current_thread().name`.
  Además, `_rebuild_apps` traza a nivel debug cada `deleteLater()` de fila y
  cada `addWidget[i]` para reconstruir la secuencia de destrucciones.
- **Helpers compartidos:** `BackgroundScanMixin._render_failure()` (contención
  + evidencia + aviso) y `_forensic_debug()` (línea forense de depuración), así
  que cualquier página futura hereda la misma defensa.
- **Verificación:** `tests/test_log.py` (+4 tests puros del logger forense) y
  `tests/test_render_hardening_gui.py` (nuevo, +8 tests GUI): layout que muere
  A MITAD de `_rebuild_apps` (después de limpiar filas viejas, antes del
  addWidget) → sin crash, error registrado, evidencia forense completa;
  layout muerto al entrar → descarte con evidencia; tabla muerta en
  Desinstalador/Limpiador → contenida; y camino feliz sin cambios. Suite: con
  PyQt6 `293 passed`; sin PyQt6 `239 passed, 8 skipped`.
- **Código:** `src/blip_eraser/utils/log.py`, `src/blip_eraser/utils/i18n.py`,
  `src/blip_eraser/widgets/scan_worker.py`, `src/blip_eraser/pages/overview_page.py`,
  `src/blip_eraser/pages/uninstaller_page.py`, `src/blip_eraser/pages/cleaner_page.py`,
  `tests/test_log.py`, `tests/test_render_hardening_gui.py` (nuevo).

### 🔧 Corregido: crash persistente al primer arranque cuando el layout de apps muere solo (CachyOS)

- **Por qué:** el crash `RuntimeError: wrapped C/C++ object of type
  QVBoxLayout has been deleted` seguía apareciendo en CachyOS en el primer
  arranque, pocos segundos tras el splash, en `overview_page.py:377`
  (`self._apps_layout.addWidget(row)`), aunque la página en sí seguía viva.
  La guarda anterior (`_widget_is_alive()` del mixin) solo comprobaba
  `sip.isdeleted(self)`; la página (OverviewPage) y su layout
  (`self._apps_layout`) son objetos C++ independientes, y Qt puede destruir
  el layout por separado dejando la página viva. Con la página viva la guarda
  pasaba, el resultado se entregaba y `_rebuild_apps` crasheaba.
- **Cómo (1):** `OverviewPage` sobrescribe `_widget_is_alive()` para
  comprobar también `sip.isdeleted(self._apps_layout)`: si el layout ya no
  existe en C++, el resultado del escaneo (y el fallo del worker) se
  descartan en silencio, igual que cuando muere la página entera.
- **Cómo (2):** defensa extra al inicio de `_rebuild_apps()` (la ruta de
  `retranslate()` no pasa por el guard del mixin): no tocar un layout que Qt
  ya destruyó.
- **Verificación:** `tests/test_overview_crash_gui.py` ampliado (+4 tests):
  página viva + layout muerto detectado por el guard, resultado de escaneo
  descartado en esa situación, `_rebuild_apps` directo sin RuntimeError, y
  control positivo con layout vivo. No se pudo reproducir el crash de
  CachyOS en Windows (offscreen): dos repros fieles del arranque (splash →
  worker → MainWindow, con y sin diálogos modales del primer arranque)
  mantienen el layout vivo todo el flujo; la reproducción local es
  determinística solo destruyendo el layout por separado.
- **Código:** `src/blip_eraser/pages/overview_page.py`,
  `tests/test_overview_crash_gui.py`.

### 🔧 Corregido: crash al cerrar la app durante un escaneo de Overview (CachyOS)

- **Por qué:** en CachyOS la app crasheaba con `RuntimeError: wrapped C/C++
  object of type QVBoxLayout has been deleted` al cerrar la ventana mientras
  un escaneo de fondo seguía en marcha. El hilo daemon (`threading.Thread`)
  mantiene viva la referencia al bound method de la página, así que el
  wrapper Python sobrevive al cierre, pero Qt ya destruyó el C++ del widget
  y de sus layouts; cuando el resultado llegaba al hilo principal y el slot
  tocaba `_apps_layout.addWidget(...)`, Qt lanzaba el RuntimeError y la app
  se cerraba sola.
- **Cómo (1):** `OverviewPage` migra de su `threading.Thread` propio +
  señales a `BackgroundScanMixin` (el patrón ya usado por Desinstalador y
  Limpiador), con token de generación por escaneo.
- **Cómo (2):** el mixin añade `_widget_is_alive()` (`PyQt6.sip.isdeleted`)
  y lo comprueba al inicio de `_on_scan_result_ready` y `_on_scan_failed`:
  si la página ya no existe en C++ (cierre de app/ventana), el resultado se
  descarta en silencio sin tocar botones ni widgets. Beneficia también a
  Desinstalador y Limpiador.
- **Cómo (3):** el buffer de log (`utils/log.py`) ahora es auto-curativo:
  `_notify()` descarta listeners cuyo widget C++ ya fue destruido (los
  que lanzan `RuntimeError` al notificar), y `_on_log` de OverviewPage
  comprueba la vida del widget antes de tocar `activity_list`. `LogPanel`
  hace lo propio con `sip.isdeleted(self)`.
- **Verificación:** `tests/test_overview_crash_gui.py` (nuevo, +7 tests:
  resultado que llega tras destruir la página se descarta, worker que falla
  tras la destrucción, control positivo con widget vivo, token obsoleto
  ignorado, y notificación al log tras la muerte del widget/página sin
  crash). Además 10 arranques/cierres de la app con el escaneo en vuelo sin
  RuntimeError.
- **Código:** `src/blip_eraser/pages/overview_page.py`,
  `src/blip_eraser/widgets/scan_worker.py`, `src/blip_eraser/utils/log.py`,
  `src/blip_eraser/widgets/log_panel.py`, `tests/test_overview_crash_gui.py`
  (nuevo).

### 🖼️ Añadido: ícono de aplicación propio (barra de título y barra de tareas)

- **Por qué:** BlipEraser usaba el ícono genérico por defecto de Qt en la
  barra de título y en la barra de tareas/dock. Ahora se integra el asset
  `desktopiconBlip.png` (2048×2048, PNG 32-bit) para mostrar la marca en:
  1. La barra de título de `MainWindow` y del `SplashScreen`.
  2. La barra de tareas/dock del escritorio (Linux/GNOME/KDE Plasma).
- **Cómo:** nuevo `app_icon()` en `widgets/logo.py` que devuelve un `QIcon`
  si el asset existe y es legible, o un `QIcon()` vacío si no (fallback
  silencioso, mismo patrón que `ASSET_LOGO_PATH`). Se aplica con
  `app.setWindowIcon(app_icon())` en `main.py` (nivel aplicación) y con
  `self.setWindowIcon(app_icon())` en `MainWindow.__init__` y en
  `SplashScreen.__init__` (nivel ventana).
- **Alt+Tab / entre escritorios:** `setWindowIcon()` a nivel de app y de
  ventana es lo que Qt expone y cubre esto en desarrollo.
- **Fuera de alcance (pendiente de empaquetado):** que la barra de tareas
  asocie el ícono por *proceso* requiere un archivo `.desktop` con la
  entrada `Icon=` en `~/.local/share/applications/` (o
  `/usr/share/applications/` al empaquetar). El repo aún no tiene
  `.desktop` ni PKGBUILD; eso se resuelve cuando se empaquete formalmente
  vía AUR.
- **Código:** `src/blip_eraser/widgets/logo.py` (`app_icon()`,
  `ASSET_ICON_PATH`), `src/blip_eraser/main.py`, `src/blip_eraser/renderer.py`,
  `src/blip_eraser/widgets/splash_screen.py`,
  `src/blip_eraser/assets/desktopiconBlip.png` (nuevo),
  `tests/test_app_icon_gui.py` (nuevo, +4 tests: `app_icon()` no nulo con
  asset, `QIcon()` vacío con asset ausente, y `MainWindow` + `SplashScreen`
  se construyen sin excepción en ambos casos).
- **Verificación:**
  - Con PyQt6 (offscreen): `270 passed, 0 skipped` (266 previos + 4 del
    módulo del ícono). Suite completa verde y estable en corridas
    consecutivas.
  - Sin PyQt6 (este Windows): `235 passed, 6 skipped` (el módulo del ícono
    se suma a los 5 módulos GUI que requieren PyQt6).

### 🔤 Arreglado: cambiar la fuente en Ajustes con la app abierta (regresión)

- **Por qué:** al cambiar la fuente desde Ajustes, el texto no se actualizaba
  hasta cambiar de página o redimensionar la ventana. El re-polish se hacía
  con `app.style()`, pero la QSS envuelve el estilo base en un `QStyleSheetStyle`
  propio por widget, así que la caché de fuente resuelta quedaba intacta.
- **Fix:** el unpolish/polish ahora se hace con `widget.style()` por widget
  (sobre `app.allWidgets()`, incluidas las páginas ocultas del QStackedWidget),
  y se fuerza `update()` para que el repintado use la fuente nueva.
- **Robustez para la suite GUI:** el unpolish/polish bajo QSS deja programado el
  borrado diferido (`DeferredDelete`) del `QStyleSheetStyle` anterior. Si quedan
  pendientes, el driver global de `QPropertyAnimation` de la QApplication deja de
  hacer ticks para animaciones creadas después (el splash de arranque en los tests
  se quedaba en `Running` sin avanzar). Se procesan los `DeferredDelete` al final
  de `_apply_appearance()` para no dejar el driver en mal estado.
- **Código:** `src/blip_eraser/renderer.py` (`_apply_appearance`),
  `tests/test_font_change_gui.py` (nuevo, +4 tests: señal `font_changed` actualiza
  `QApplication.font()`, widgets de todas las páginas, segundo cambio seguido sin
  pausa, y persistencia en `prefs.json`).
- **Verificación:**
  - Con PyQt6 (offscreen): `266 passed, 0 skipped` (262 previos + 4 del nuevo
    módulo de fuente). Suite completa verde y estable en corridas consecutivas.
  - Sin PyQt6 (este Windows): `235 passed, 5 skipped` (el nuevo módulo de fuente
    se suma a los 4 módulos GUI que requieren PyQt6).

### ⚙️ Cambiado: escaneos del Desinstalador y del Limpiador en segundo plano

- **Por qué:** al abrir "Desinstalador" o "Limpiador del sistema" (y tras cada
  borrado o "Actualizar lista"), la app se congelaba unos segundos mientras
  `list_installed_apps()`, `scan_cleanup_items()` y `scan_manual_entries()`
  corrían en el hilo principal. Ahora esos escaneos corren en un hilo de fondo
  con el mismo patrón que ya usaba la Vista general: `threading.Thread` +
  `pyqtSignal`, entregando el resultado de forma queued al hilo principal.
- **Worker reutilizable:** nuevo `widgets/scan_worker.py` con `BackgroundScanMixin`
  (patrón compartido por las 3 fuentes pesadas). Garantiza:
  1. **Botones deshabilitados durante el escaneo:** "Actualizar lista" y
     "Eliminar seleccionados"/"Desinstalar seleccionados" de la página concreta
     que está escaneando (no las demás). Se re-habilitan al llegar el resultado.
  2. **Token por generación:** si se lanza un segundo escaneo antes de que
     llegue el primero (doble clic en refrescar, o navegar y volver mientras un
     escaneo corre), el resultado anterior se descarta para no aplicar datos
     obsoletos.
  3. **Seguridad de navegación:** las páginas viven toda la sesión en el
     `QStackedWidget` (nunca se destruyen al navegar), así que aplicar el
     resultado aunque la página esté oculta es seguro y deja los datos listos.
- **`scan_cache.py` sin cambios:** `is_stale()`/`mark_scanned()` siguen
  decidiendo CUÁNDO escanear (caché de 5 min, invalidación tras borrar); este
  cambio solo mueve el CÓMO (hilo de fondo) a `mark_scanned()` cuando el
  resultado real llega.
- **Overview confirmado OK:** la Vista general ya escaneaba en segundo plano
  (`_scan_worker`, `_refresh_cleanup_summary`); `_apply_metrics()` solo pinta un
  dict que ya viene calculado y no llama a `scan_cleanup()`, así que no requirió
  cambios.
- **Código:** `src/blip_eraser/widgets/scan_worker.py` (nuevo),
  `src/blip_eraser/pages/uninstaller_page.py`, `src/blip_eraser/pages/cleaner_page.py`,
  `tests/test_refresh_after_delete_gui.py` (+3 tests: escaneo lento no congela
  la GUI, resultado obsoleto descartado al lanzar otro escaneo, Desinstalador
  también escanea en segundo plano con botones deshabilitados).
- **Verificado con PyQt6 real (offscreen):** 262 passed, 0 skipped. Sin PyQt6:
  235 passed, 4 skipped.

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
- Tests sin PyQt6 (este Windows): `235 passed, 6 skipped` (skips: `test_check_table_gui.py`,
  `test_splash_gui.py`, `test_refresh_after_delete_gui.py`, `test_theme_contrast_gui.py`,
  `test_font_change_gui.py` y `test_app_icon_gui.py`, requieren PyQt6).
- Tests con PyQt6 (offscreen / CachyOS): `270 passed, 0 skipped` - incluye la
  suite GUI del splash (animación de entrada + encolado de mensajes), el
  refresco tras acción destructiva, la selección masiva del CheckTable, el
  contraste del gauge + tinte de íconos del sidebar, los escaneos en segundo
  plano del Desinstalador y del Limpiador (no bloqueo de la GUI, descarte de
  resultados obsoletos), el cambio de fuente en caliente desde Ajustes
  (señal `font_changed` → `QApplication.font()`, widgets y persistencia), y el
  ícono de aplicación propio (`app_icon()` con fallback silencioso a `QIcon()`
  vacío, y construcción de `MainWindow` + `SplashScreen` con y sin asset).

## Tweaks: protecciones y zswap
- zram y espejos gestionados por el sistema (p. ej. CachyOS) ya no se sobrescriben: el tweak queda bloqueado con el motivo en el tooltip.
- Nuevo tweak opcional **zswap** (apagado por defecto): persistente vía `/etc/tmpfiles.d/blip-eraser-zswap.conf`, sin tocar el bootloader; bloqueado si el swap es zram, si no hay swap en disco o si el kernel ya lo activa.
- El tweak antes llamado "zswap" (que en realidad configuraba zram) se llama ahora "zram". Textos ES/EN detallados para cada tweak.

## Tweaks: reconciliación al arrancar
- Tu elección guardada ya no se sobrescribe con el estado del sistema. Si dejaste un ajuste activado y el sistema lo perdió, la página de Rendimiento lo avisa y ofrece "Reaplicar".
- Tests de GUI reales para la página de Rendimiento.

---

## Historial de hitos (v0.1 – v1.3)

> Reconstruido desde cero: dónde estaría cada pieza si se hubiera
> planificado por versiones, dónde estamos (~70% funcional) y qué falta
> para producción. **Flathub en pausa** (≥1 mes, a decisión del creador).

- [x] **v0.1 — Fundación**: scaffold `src/blip_eraser/`, lógica pura en
  `utils/` sin Qt, lectura pacman (`-Qe/-Qd/-Qi`), ventana y navegación base.
- [x] **v0.2 — Desinstalador unificado**: tabla pacman + entradas manuales
  (AppImages, `~/Games`), selección manual sin "seleccionar todo",
  filtros por tipo/peso/fecha.
- [x] **v0.3 — Limpieza y sistema**: Limpiador (recomendada + manual),
  Overview con gauge de salud, ajustes de rendimiento (fstrim/zram/mirrors),
  temas, ES/EN en caliente, caché de escaneo (5 min).
- [x] **v0.4 — Seguridad Fase 1**: allowlist de paths, rechazo de symlinks,
  validación de paquetes, confirmación obligatoria, aviso ≥5 GiB,
  auditoría forense (`diagnostics.log`).
- [x] **v0.5 — Privilegios Fase 2 + arranque**: daemon D-Bus systemd
  (`CleanSystemPaths`/`Ping`) con fallback pkexec; la desinstalación de paquetes va por `pkexec pacman -Rns`,
  splash con vídeo, escaneos en segundo plano con token, icono propio.
- [x] **v1.0 — Estabilización CachyOS**: defensa dura `sip.isdeleted`,
  `BackgroundScanMixin` en las 3 páginas, instrumentación forense.
  **Estado actual**: código `1.0.0`, funcional en Arch/CachyOS.
- [x] **v1.1 — Orden y calidad (hecho)**:
  - Suite verde (591 passed, 3 skipped) + CI mínimo
    (`pytest` + `compileall`) en cada push/PR a `main`.
  - Borrado en segundo plano con diálogo de progreso ("Eliminando… n/N",
    se cierra solo): adiós al "No responde"; modal sin cancelar (un
    borrado a medias no se puede interrumpir).
  - Allowlist/denylist única en `utils/validation.py` (daemon, cliente
    pkexec y GUI la comparten; `dbus_client` solo re-exporta).
  - Sincronizar versión `pyproject.toml` → `1.0.0`.
  - Limpieza de raíz (sin artefactos `Z:/`, sin logs sueltos).
  - Extras del release: `check_for_updates` real (GitHub Releases,
    fail-closed), rate-limit D-Bus (10 ops destructivas/min por sender),
    tag + release `v1.0.0` en GitHub con Flatpak descargable
    (`io.github.DinoPathTeam.BlipEraser`).
- [x] **v1.2 — Empaquetado AUR (empaquetado, subida ⏸️)**: `.desktop`
  con `Icon=`, PKGBUILD 1.0.1 + `.SRCINFO` validados con `makepkg`
  (`packaging/aur/`), instalador que cubre polkit + AppArmor, guía sin
  `--break-system-packages` (venv `--system-site-packages`).
  > Nota: la subida a AUR está en pausa — los 3 archivos de
  > `packaging/aur/` están listos para pushear cuando se reactive.
- [x] **v1.3 — Producción (hecho)**: AppArmor en enforce verificado en
  host real (`AppArmorProfile=` en systemd, perfil endurecido con
  evidencia, 0 DENIED), `check_for_updates` real (GitHub Releases),
  auditoría del `rm -rf` fd-atómico, rate-limit D-Bus, tags `v1.0.0`/`v1.0.1`.
- [ ] **Futuro**: migrar i18n a gettext, tests E2E, PyGObject en el bundle
  Flatpak (hoy fallback pkexec-host), **Flathub ⏸️**.

> Movido desde el README para mantenerlo corto; el estado actual está en el README y los cambios recientes arriba.

## README
- README reescrito y dividido: `README.md` (EN) y `README.es.md` (ES). Corrige versión, funciones reales (TRIM/zram/zswap/espejos), modelo de seguridad actual (daemon solo limpia; desinstalar va por pkexec), distros (solo CachyOS probado), instalación (PKGBUILD, fuente, Flatpak sin sandbox real) y quita contadores que caducan.
- El roadmap detallado se movió a "Historial de hitos" de este archivo.
- `vendor_url` de la política polkit apunta al repositorio real.

## Endurecimiento: registros de auditoría, elevación y Descargas
- **Registros protegidos**: además de `journal` y la bitácora propia, ya no se pueden borrar ni cuentan como "recuperables" `audit/`, `wtmp`, `btmp`, `lastlog`, `faillog`, `auth.log`, `secure` y `pacman.log` (con sus rotaciones `.1`, `-fecha`). Un único helper `is_audit_protected()` lo aplica en el daemon, el fallback pkexec y la capa de privilegios; el listado del Limpiador los oculta y el total de logs ya no incluye el journal.
- **Elevación**: rutas desnudas como `/var`, `/usr` o `/mnt` ahora se tratan como de sistema (antes se saltaban la validación). Un archivo propio en `/mnt`, `/media`, `/srv` u `/opt` se borra sin elevar; nunca se borra un punto de montaje.
- **Descargas**: la carpeta de escaneo por defecto se lee de `user-dirs.dirs` (XDG) en vez de asumir `~/Descargas`.
- Importante: tras actualizar, re-ejecuta `./scripts/install-daemon.sh` para que el daemon instalado use la nueva validación.

## CI y calidad
- El CI ahora tiene dos jobs: **lint** (`compileall`, `ruff check` con reglas F/E9 y `shellcheck` de `scripts/*.sh`) y **test** (Python 3.11 y 3.14, con PyQt6 en modo offscreen, de modo que los tests de GUI se ejecutan en vez de omitirse).
- Dependabot propone actualizar los SHA pineados de las acciones de GitHub (semanal).
- Se limpiaron imports/variables sin usar en tests y variables muertas de `scripts/aa-tune-gui.sh`.

## Puesta al día
- El instalador automático de la app (`phase2_installer`) ahora copia también `49-blip-eraser.rules` (solo miembros de `wheel` pueden autorizar) y lo comprueba al detectar la instalación; antes solo copiaba la política.
- Test que impide que `.policy` y `.rules` se desincronicen y que las anotaciones de `pacman-remove` sigan coincidiendo con el comando real de desinstalación (pkexec elige la acción por `exec.path`/`argv`).
- Guías de instalación (ES/EN): entorno virtual con `--system-site-packages` como método principal (sin `--break-system-packages`), variante para fish y paso opcional para instalar el daemon.
- Comentarios de las acciones de GitHub con el formato `# vX.Y.Z` que Dependabot mantiene.
