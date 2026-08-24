<p align="center">
  <img src="src/blip_eraser/assets/BlipEraserLogo.png" alt="BlipEraser Logo" width="480"/>
</p>

<p align="center">
  <b>Desinstalador y Limpiador del Sistema para CachyOS y Arch Linux</b>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://cachyos.org/"><img src="https://img.shields.io/badge/OS-CachyOS%20%7C%20Arch%20Linux-red.svg" alt="CachyOS / Arch"></a>
  <a href="https://riverbankcomputing.com/software/pyqt/"><img src="https://img.shields.io/badge/GUI-PyQt6-informational.svg" alt="PyQt6"></a>
</p>

<p align="center">
  <a href="README.es.md"><b>Español</b></a> \u00b7 <a href="README.en.md"><b>English</b></a>
</p>

---

## \uD83D\uDE80 Acerca de BlipEraser

**BlipEraser** cubre el hueco que dejan los gestores gr\u00e1ficos tradicionales: detecta y gestiona aplicaciones instaladas **manualmente** (AppImages, lanzadores como Hydra, programas en `~/Games`, `~/.local/share` o `~/Descargas`) que **no quedan registradas en el gestor de paquetes**, combin\u00e1ndolas en una sola interfaz limpia junto con los paquetes de `pacman`.

Adem\u00e1s, incluye diagn\u00f3stico de salud del sistema, limpiador de cach\u00e9 y registros por categor\u00eda, optimizaciones de rendimiento probadas para CachyOS/Arch y personalizaci\u00f3n de temas.

---

## \u2728 Caracter\u00edsticas Principales

- **\uD83D\uDCCA Vista General (Overview)**:
  - Gauge radial de **Salud del Sistema** (*GOOD / FAIR / POOR*) con puntuaci\u00f3n din\u00e1mica.
  - Especificaciones en tiempo real: CPU, GPU, uso de RAM y espacio en disco.
  - Resumen *"Limpieza del sistema recomendada"* con un clic para liberar basura, cach\u00e9 y registros.
- **\uD83D\uDCE6 Desinstalador Unificado**:
  - Tabla multiselecci\u00f3n con selecci\u00f3n **manual por fila** (sin checkbox "seleccionar todo" en el encabezado, para evitar desinstalaciones masivas accidentales).
  - Clasificaci\u00f3n clara de tipo: **Aplicaci\u00f3n** (pacman expl\u00edcito), **Dependencia** o **Carpeta suelta** (manual).
  - Bot\u00f3n din\u00e1mico *"Desinstalar seleccionados (N)"*.
- **\uD83E\uDDF9 Limpiador del Sistema (2 Secciones Independientes)**:
  - **Limpieza recomendada**: Detalle \u00edtem por \u00edtem de Basura (`~/.cache`), Cach\u00e9 de Pacman (`/var/cache/pacman/pkg`) y Registros (`/var/log`).
  - **Aplicaciones instaladas (manual)**: Carpetas sueltas y AppImages detectados en las rutas de escaneo.
- **\uD83D\uDEE1\uFE0F Confirmaci\u00f3n de Seguridad y Umbral de Gran Tama\u00f1o**:
  - Di\u00e1logo de confirmaci\u00f3n con desglose de categor\u00edas y total a liberar.
  - **Advertencia visual destacada (rojo / negrita)** para operaciones de gran tama\u00f1o (\u2265 5 GiB).
  - **Confirmaci\u00f3n obligatoria sin excepci\u00f3n**: no existe opci\u00f3n de *"no volver a preguntar"*.
- **\u26A1 Ajustes de Rendimiento**:
  - Optimizaciones seguras de un solo clic para Arch/CachyOS: `fstrim` (SSD), compresi\u00f3n de RAM `zswap` y espejos de pacman ordenados por velocidad.
  - Cada opci\u00f3n incluye un tooltip detallado (mecanismo, consecuencias y beneficio).
- **\uD83C\uDFA8 Personalizaci\u00f3n e Idioma**:
  - Selector de tema visual (Red, Blue, Green, Purple, Dark) y familias de fuentes del sistema.
  - Soporte completo biling\u00fce (**Espa\u00f1ol** e **Ingl\u00e9s**) con cambio de idioma en caliente.

---

## \uD83D\uDEE0 Requisitos del Sistema

- **S.O.**: CachyOS o cualquier distribuci\u00f3n basada en Arch Linux (requiere `pacman`).
- **Python**: 3.11 o superior.
- **GUI**: PyQt6 y **PyGObject** (instalados v\u00eda `pacman`, no por `pip`).
- **Privilegios**: `pkexec` / Polkit para acciones de desinstalaci\u00f3n de paquetes del sistema.
- **Sistema**: `systemd` + D-Bus (bus de sistema) para daemon privilegiado (Fase 2).

---

## \uD83D\uDCE6 Instalaci\u00f3n

> **IMPORTANTE**: Instala PyQt6 y PyGObject con el gestor de paquetes del sistema (`pacman`) para evitar conflictos con las librer\u00edas de CachyOS/Arch.

```bash
# 1. Instalar dependencias del sistema
sudo pacman -S python-pyqt6 python-gobject python-pytest

# 2. Clonar el repositorio
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser

# 3. Instalaci\u00f3n editable
pip install -e . --break-system-packages
```

### Opcional: Entorno Virtual (venv)

Si prefieres usar un entorno virtual aislado:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

---

## \uD83C\uDFAE Uso

Ejecuta la aplicaci\u00f3n desde la terminal:

```bash
blip-eraser
```

Tambi\u00e9n puedes ejecutarla directamente con Python:

```bash
python -m blip_eraser
```

---

## \uD83E\uDDCA Desarrollo y Tests

Toda la l\u00f3gica pura (escaneo, categorizaci\u00f3n, umbral de confirmaci\u00f3n, normalizaci\u00f3n de fechas de pacman) vive en `src/blip_eraser/utils/` sin dependencia de PyQt6. Esto permite ejecutar la suite de pruebas sin entorno gr\u00e1fico:

```bash
pytest
```

---

## \uD83D\uDCC4 Licencia

Este proyecto est\u00e1 bajo la Licencia [MIT](LICENSE).