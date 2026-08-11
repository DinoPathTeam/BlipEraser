🇬🇧 [Read in English](README.en.md)

<p align="center">
  <img src="src/blip_eraser/assets/BlipEraserLogo.png" alt="BlipEraser Logo" width="450"/>
</p>

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# BlipEraser

Desinstalador de aplicaciones y limpiador del sistema para **CachyOS** (y cualquier distro basada en Arch).

BlipEraser existe para cubrir el hueco que dejan los gestores gráficos tradicionales:
apps instaladas **manualmente** — AppImages, carpetas sueltas de lanzadores de terceros
como Hydra Launcher, programas sin paquete — que **no quedan registradas en ningún
gestor de paquetes** y que, por tanto, ninguna herramienta tradicional es capaz de detectar.

## 🌟 Navegación y Secciones

1. **Vista general (Overview)**: Puntuación de salud radial (*GOOD / FAIR / POOR*), estadísticas de CPU/GPU/RAM/Disco y botón de acción rápida *"Limpiar ahora"*.
2. **Desinstalador**: Lista unificada de paquetes de `pacman` y carpetas manuales, con ordenación, filtro de búsqueda y casillas multiselección.
3. **Limpiador del sistema**:
   - **Limpieza recomendada**: Basura (`~/.cache`), Caché de pacman (`/var/cache/pacman/pkg`) y Registros (`/var/log`) desglosados ítem por ítem.
   - **Aplicaciones instaladas (manual)**: Carpetas sueltas y AppImages detectados.
4. **Ajustes de rendimiento**: Optimizaciones seguras de CachyOS/Arch (`fstrim`, `zswap`).
5. **Configuración**: Selección de temas cromáticos, fuentes tipográficas y borrado de historial de actividad.

## 🛡️ Confirmación de Seguridad y Umbral de Gran Tamaño

- Toda operación destructiva muestra la categorización exacta y el peso total a liberar.
- Si la selección supera el umbral de **5 GiB**, se muestra una **advertencia destacada en rojo y negrita**.
- **Confirmación obligatoria sin excepción**: la app no incluye casillas de *"no volver a preguntar"*.

## 🛠️ Requisitos del sistema

- CachyOS o cualquier distro basada en Arch (requiere `pacman`).
- Python 3.11+ y PyQt6 (instalado vía `pacman`).
- `pkexec` / polkit para las acciones con privilegios de administrador.

## 📦 Instalación

**Muy importante:** PyQt6 se instala con el gestor del sistema, **no por pip**.

```bash
sudo pacman -S python-pyqt6 python-pytest
```

Después clona el repo e instala el proyecto en modo editable:

```bash
git clone https://github.com/DinoPathTeam/BlipEraser.git
cd BlipEraser
pip install -e . --break-system-packages
```

## 🎮 Uso básico

Ejecuta la app con:

```bash
blip-eraser
```

## 🧪 Pruebas / Tests

```bash
pytest
```

## 📄 Licencia

[MIT](LICENSE)