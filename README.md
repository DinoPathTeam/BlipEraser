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
  <a href="README.es.md"><b>Español</b></a> • <a href="README.en.md"><b>English</b></a>
</p>

---

## 🚀 Acerca de BlipEraser

**BlipEraser** cubre el hueco que dejan los gestores gráficos tradicionales: detecta y gestiona aplicaciones instaladas **manualmente** (AppImages, lanzadores como Hydra, programas en `~/Games`, `~/.local/share` o `~/Descargas`) que **no quedan registradas en el gestor de paquetes**, combinándolas en una sola interfaz limpia junto con los paquetes de `pacman`.

Además, incluye diagnóstico de salud del sistema, limpiador de caché y registros por categoría, optimizaciones de rendimiento probadas para CachyOS/Arch y personalización de temas.

---

## ✨ Características Principales

- **📊 Vista General (Overview)**:
  - Gauge radial de **Salud del Sistema** (*GOOD / FAIR / POOR*) con puntuación dinámica.
  - Especificaciones en tiempo real: CPU, GPU, uso de RAM y espacio en disco.
  - Resumen *"Limpieza del sistema recomendada"* con un clic para liberar basura, caché y registros.
- **📦 Desinstalador Unificado**:
  - Tabla multiselección con selección **manual por fila** (sin checkbox "seleccionar todo" en el encabezado, para evitar desinstalaciones masivas accidentales).
  - Clasificación clara de tipo: **Aplicación** (pacman explícito), **Dependencia** o **Carpeta suelta** (manual).
  - Botón dinámico *"Desinstalar seleccionados (N)"*.
- **🧹 Limpiador del Sistema (2 Secciones Independientes)**:
  - **Limpieza recomendada**: Detalle ítem por ítem de Basura (`~/.cache`), Caché de Pacman (`/var/cache/pacman/pkg`) y Registros (`/var/log`).
  - **Aplicaciones instaladas (manual)**: Carpetas sueltas y AppImages detectados en las rutas de escaneo.
- **🛡️ Confirmación de Seguridad y Umbral de Gran Tamaño**:
  - Diálogo de confirmación con desglose de categorías y total a liberar.
  - **Advertencia visual destacada (rojo / negrita)** para operaciones de gran tamaño (≥ 5 GiB).
  - **Confirmación obligatoria sin excepción**: no existe opción de *"no volver a preguntar"*.
- **⚡ Ajustes de Rendimiento**:
  - Optimizaciones seguras de un solo clic para Arch/CachyOS: `fstrim` (SSD), compresión de RAM `zswap` y espejos de pacman ordenados por velocidad.
  - Cada opción incluye un tooltip detallado (mecanismo, consecuencias y beneficio).
- **🎨 Personalización e Idioma**:
  - Selector de tema visual (Red, Blue, Green, Purple, Dark) y familias de fuentes del sistema.
  - Soporte completo bilingüe (**Español** e **Inglés**) con cambio de idioma en caliente.

---

## 🛠️ Requisitos del Sistema

- **S.O.**: CachyOS o cualquier distribución basada en Arch Linux (requiere `pacman`).
- **Python**: 3.11 o superior.
- **GUI**: PyQt6 (instalado vía `pacman`, no por `pip`).
- **Privilegios**: `pkexec` / Polkit para acciones de desinstalación de paquetes del sistema.

---

## 📦 Instalación

> **IMPORTANTE**: Instala PyQt6 con el gestor de paquetes del sistema (`pacman`) para evitar conflictos con las librerías Qt de CachyOS/Arch.

```bash
# 1. Instalar dependencias del sistema
sudo pacman -S python-pyqt6 python-pytest

# 2. Clonar el repositorio
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser

# 3. Instalación editable
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

## 🎮 Uso

Ejecuta la aplicación desde la terminal:

```bash
blip-eraser
```

También puedes ejecutarla directamente con Python:

```bash
python -m blip_eraser
```

---

## 🧪 Desarrollo y Tests

Toda la lógica pura (escaneo, categorización, umbral de confirmación, normalización de fechas de pacman) vive en `src/blip_eraser/utils/` sin dependencia de PyQt6. Esto permite ejecutar la suite de pruebas sin entorno gráfico:

```bash
pytest
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia [MIT](LICENSE).