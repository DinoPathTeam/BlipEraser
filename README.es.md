<p align="center">
  <img src="src/blip_eraser/assets/BlipEraserLogo.png" alt="BlipEraser Logo" width="480"/>
</p>

<p align="center">
  <a href="https://github.com/DinoPathTeam/BlipEraser/actions/workflows/ci.yml"><img src="https://github.com/DinoPathTeam/BlipEraser/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/DinoPathTeam/BlipEraser/releases/latest"><img src="https://img.shields.io/github/v/release/DinoPathTeam/BlipEraser" alt="Última versión"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="Licencia MIT"></a>
  <a href="https://riverbankcomputing.com/software/pyqt/"><img src="https://img.shields.io/badge/GUI-PyQt6-informational.svg" alt="PyQt6"></a>
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> · <b>Español</b>
</p>

# BlipEraser

Desinstalador de aplicaciones y limpiador del sistema para **Arch Linux** y distribuciones basadas en Arch.

BlipEraser cubre el hueco que dejan los gestores gráficos de paquetes: apps
instaladas **manualmente** (AppImages, carpetas sueltas de lanzadores de
terceros, programas sin paquete) que **ningún gestor registra**, por lo que
las herramientas de "desinstalar" habituales no las ven.

## Funciones

- **Vista general**: puntuación de salud (*GOOD / FAIR / POOR*), estadísticas en vivo de CPU/GPU/RAM/disco y un resumen "Limpiar ahora" de la limpieza recomendada.
- **Desinstalador**: una lista única de paquetes de `pacman` y carpetas manuales, con ordenación, búsqueda y **selección manual por fila** (a propósito no hay "seleccionar todo", para evitar desinstalaciones masivas por accidente). Los paquetes se eliminan con `pkexec pacman -Rns`.
- **Limpiador**: *limpieza recomendada* (`~/.cache`, la caché de pacman `/var/cache/pacman/pkg` y los registros de `/var/log`) y *aplicaciones instaladas a mano* (carpetas sueltas y AppImages en las rutas de escaneo).
- **Confirmación de seguridad**: toda operación destructiva lista exactamente qué se eliminará; las selecciones de más de **5 GiB** muestran una advertencia destacada. La confirmación es obligatoria, no hay "no volver a preguntar".
- **Ajustes de rendimiento**: todos opcionales, **desactivados por defecto**, cada uno con una explicación detallada (mecanismo, consecuencias, beneficio) dentro de la app:
  - **TRIM** (`fstrim.timer`) para SSD/NVMe.
  - **zram** (swap comprimido en RAM) mediante `zram-generator`.
  - **zswap** (caché de compresión del kernel delante del swap en disco).
  - **Espejos más rápidos** con `reflector`.

  Los ajustes nunca pisan lo que tu distribución ya gestiona: si el sistema trae zram propio (p. ej. CachyOS), usa una lista de espejos generada por otra herramienta, o su swap es zram (lo que haría redundante a zswap), el ajuste aparece **desactivado con el motivo**. Si el sistema pierde después un ajuste que activaste, la app te avisa y ofrece reaplicarlo en vez de sobrescribir tu elección en silencio.
- **Configuración**: tema, fuentes, idioma (ES/EN, cambio en caliente) y gestión del registro de actividad.

## Sistemas compatibles

| Estado | Distribuciones |
|---|---|
| **Probado** | CachyOS |
| **Debería funcionar, sin probar** | Arch Linux, EndeavourOS, Garuda Linux, Manjaro |

BlipEraser necesita `pacman`, `systemd`, polkit y D-Bus en el bus del sistema.
Otras derivadas de Arch que los incluyan pueden funcionar; si pruebas alguna,
un issue con el resultado (bueno o malo) se agradece mucho.

## Requisitos

- Una distro basada en Arch con `pacman`, `systemd`, polkit (`pkexec`) y D-Bus.
- Python 3.11+, **PyQt6** y **PyGObject** instalados con `pacman` (no con pip).
- Opcional: `gst-libav` (vídeo H.264 del splash; sin él la app usa una animación del logo) y AppArmor (el perfil de confinamiento del daemon está en `packaging/apparmor/`).

## Instalación

### Compilar el paquete en local (PKGBUILD)

`packaging/aur/` contiene el `PKGBUILD` que compila el tarball de la versión e
instala todo (app, daemon privilegiado, política y reglas de polkit, D-Bus,
unidad systemd, perfil AppArmor, entrada de escritorio):

```bash
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser/packaging/aur
makepkg -si
sudo systemctl enable --now blip-eraser-privileged.service
```

> El daemon corre como root; es recomendable pero opcional: sin él la app
> recurre a `pkexec` para limpiar. Solo los miembros del grupo `wheel`
> pueden autorizar sus acciones.

### Desde el código fuente

```bash
# 1. Dependencias del sistema (PyQt6 y PyGObject NO deben venir de pip)
sudo pacman -S python-pyqt6 python-gobject polkit gst-libav

# 2. Obtener el código
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser

# 3. Desplegar el daemon privilegiado (idempotente; pide sudo; repítelo tras cambios de código)
./scripts/install-daemon.sh

# 4. Ejecutar sin instalar...
PYTHONPATH=src python -m blip_eraser
```

Para tener el comando `blip-eraser`, usa un entorno virtual que reutilice los paquetes del sistema:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate        # fish: source .venv/bin/activate.fish
pip install -e .
blip-eraser
```

<details>
<summary>Qué hace <code>install-daemon.sh</code> (equivalente manual)</summary>

```bash
sudo install -Dm755 packaging/scripts/blip-eraser-privileged /usr/lib/blip-eraser/blip-eraser-privileged
sudo install -Dm644 packaging/systemd/blip-eraser-privileged.service /usr/lib/systemd/system/
sudo install -Dm644 packaging/dbus/blip-eraser-privileged.conf /usr/share/dbus-1/system.d/
sudo install -Dm644 packaging/dbus/com.dinopath.BlipEraser.Privileged.xml /usr/share/dbus-1/interfaces/
sudo install -Dm644 packaging/polkit/com.dinopath.blip-eraser.policy /usr/share/polkit-1/actions/
sudo install -Dm644 packaging/polkit/49-blip-eraser.rules /etc/polkit-1/rules.d/49-blip-eraser.rules
# Solo si AppArmor está activo:
sudo install -Dm644 packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged /etc/apparmor.d/
sudo apparmor_parser -r /etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged
sudo systemctl daemon-reload
```

El script es la referencia; úsalo en vez de copiar estas líneas a mano.
</details>

### Icono de bandeja (opcional)

`blip-eraser-tray` lanza un icono de bandeja aparte y ligero (no abre la ventana principal). En reposo no calcula nada: al abrir su menú muestra CPU/RAM/disco y el espacio recuperable, calculados en ese momento. "Limpieza rápida…" abre BlipEraser directo en la confirmación de limpieza de siempre; la bandeja nunca borra nada por sí misma. Una vez al iniciar usa la misma caché de 24 h para avisar de una versión nueva, y avisa (como mucho una vez al día) si se pueden recuperar 5 GiB o más. En el menú puedes activar el inicio con la sesión y silenciar los avisos (`"tray_notifications": false` en `prefs.json`). Solo en la instalación nativa: el Flatpak no la incluye.

### Flatpak

Cada [release](https://github.com/DinoPathTeam/BlipEraser/releases/latest) incluye un paquete `.flatpak`. Instala primero el daemon en el host (`./scripts/install-daemon.sh`) y luego `flatpak install --user BlipEraser-v<versión>-x86_64.flatpak`.

> **Aquí el Flatpak no es un sandbox.** Para gestionar el host necesita
> `--filesystem=host` y `--talk-name=org.freedesktop.Flatpak`
> (`flatpak-spawn --host`), lo que le da en la práctica acceso total a tu
> sesión. Si te importa el confinamiento, prefiere la instalación nativa.

Guías paso a paso para principiantes: [`Installation guide.es.txt`](Installation%20guide.es.txt) · [`Installation guide.en.txt`](Installation%20guide.en.txt).

## Arquitectura

```
main.py ── check PyQt6 → idioma primer arranque → splash + comprobaciones
            │
            ▼
MainWindow (cabecera + barra lateral + páginas + barra de estado + panel de log)
  pages/   overview · uninstaller · cleaner · performance · settings · ...
  widgets/ splash, tablas, diálogos, mixin de escaneo en segundo plano
            │
            ▼
utils/  módulos puros, sin Qt (testeables sin pantalla)
  scan / apps / pacman (detección) · validation / privileges / dbus_client
  (seguridad) · performance (ajustes) · i18n / theme / config / log ...
      │                                      │
      ▼                                      ▼
bus de sistema D-Bus → daemon root     pkexec + polkit
  Ping, CleanSystemPaths                 pacman -Rns (desinstalar)
  (solo limpia caché y logs)             ajustes: systemctl, archivos de config
```

Stack: Python ≥ 3.11 · PyQt6 + QSS · D-Bus con PyGObject (`gi`) · polkit · systemd · AppArmor · instaladores en Bash.

## Modelo de seguridad

- **Confirmación primero**: toda operación destructiva lista lo que se eliminará y exige confirmación explícita. Las selecciones de más de 5 GiB llevan una advertencia extra.
- **Privilegios por acción**: las acciones de root se autorizan con polkit en cada petición (las reglas de polkit solo aceptan miembros de `wheel`, y polkit puede conservar la autorización unos instantes). No existe un "modo sudo" persistente.
- **La desinstalación de paquetes no pasa por el daemon.** Es una llamada `pkexec pacman -Rns` autorizada con un aviso de polkit, así el daemon nunca necesita escribir en la base de datos de pacman ni ejecutar hooks.
- **El daemon privilegiado es deliberadamente pequeño.** Solo expone `Ping` y `CleanSystemPaths` en el bus del sistema y solo borra dentro de una lista permitida: `/var/cache/pacman/pkg` y `/var/log` (nunca `/var/log/journal` ni los logs propios de BlipEraser). Las rutas se normalizan antes de comprobarlas y el borrado recorre el árbol por descriptor de archivo con `O_NOFOLLOW`, de modo que nunca se siguen enlaces simbólicos.
- **Límites anti-abuso**: máximo 10 llamadas destructivas por minuto por llamante, una operación en curso por usuario, y el límite también cuenta las autorizaciones denegadas o canceladas.
- **Endurecimiento**: la unidad systemd usa `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `MemoryDenyWriteExecute` y un filtro de llamadas al sistema, y se confina con un perfil AppArmor cuando AppArmor está activo.
- **Uso de red**: la única petición de red es una comprobación de actualizaciones contra la API pública de GitHub Releases, en segundo plano y como máximo una vez cada 24 horas; no envía nada de tu sistema y solo muestra un aviso discreto en la barra de estado (sin descarga automática). Para desactivarla pon `"check_updates": false` en `~/.config/blip-eraser/prefs.json`. La versión Flatpak no tiene permiso de red, así que nunca comprueba.
- **Rastro de auditoría**: los eventos relevantes para la seguridad se escriben en `~/.cache/blip-eraser/diagnostics.log`.
- **Sin cambios silenciosos**: la app instala un paquete (`zram-generator`, `reflector`) solo cuando activas un ajuste que lo necesita, y nunca toca el gestor de arranque.
- **Límites que debes conocer**: es un proyecto joven y no ha pasado una auditoría de seguridad independiente. La versión Flatpak no tiene un sandbox real (ver arriba).

## Comprobación de dependencias

Al arrancar, la app comprueba sus dependencias en dos niveles. Sin PyQt6 no se puede dibujar ninguna ventana, así que imprime el comando de instalación y sale. Con la GUI abierta, comprueba en segundo plano que existan `pacman` y `pkexec` y, si falta alguno, muestra qué es y el comando exacto para instalarlo. **BlipEraser nunca instala dependencias por sí mismo.**

## Desarrollo y pruebas

La lógica (escaneo, validación, comandos de pacman, ajustes) vive en `src/blip_eraser/utils/` sin depender de PyQt6, por lo que se puede probar sin pantalla:

```bash
pytest tests/ -q
```

Las pruebas de GUI necesitan PyQt6 y se omiten si falta; para ejecutarlas sin pantalla: `QT_QPA_PLATFORM=offscreen pytest tests/ -q`. El CI ejecuta `compileall` y la suite en cada push y pull request a `main`.

## Estado y hoja de ruta

Versión actual: mira la insignia de arriba (la versión del código está en `src/blip_eraser/__init__.py`). Los cambios del día a día están en [`Updates.md`](Updates.md), que también guarda los hitos históricos (v0.1 – v1.3).

Ideas pendientes: migrar i18n a gettext, pruebas de extremo a extremo, filtro de llamadas al sistema de systemd más estricto, resolución de rutas más estricta (`openat2`), PyGObject dentro del paquete Flatpak y Flathub (en pausa).

## Licencia

[MIT](LICENSE)
