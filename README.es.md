🇬🇧 [Read in English](README.en.md)

<p align="center">
  <img src="src/blip_eraser/assets/BlipEraserLogo.png" alt="BlipEraser Logo" width="450"/>
</p>

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# BlipEraser

Desinstalador de aplicaciones y limpiador del sistema para **Arch Linux** (y cualquier distro basada en Arch).

BlipEraser existe para cubrir el hueco que dejan los gestores gráficos tradicionales:
apps instaladas **manualmente** — AppImages, carpetas sueltas de lanzadores de terceros
como Hydra Launcher, programas sin paquete — que **no quedan registradas en ningún
gestor de paquetes** y que, por tanto, ninguna herramienta tradicional es capaz de detectar.

### 🎯 Distribuciones compatibles

BlipEraser funciona en **cualquier distribución basada en Arch Linux** que use `pacman` como gestor de paquetes y `systemd` + D-Bus, incluyendo (pero no limitado a):

- **Arch Linux** (oficial)
- **CachyOS**
- **EndeavourOS**
- **Manjaro**
- **Garuda Linux**
- **ArcoLinux**
- **Artix Linux** (con systemd)
- **Hyperbola** (con systemd)
- **Parabola GNU/Linux-libre**
- **RebornOS**
- **Archcraft**
- **ArchBang**
- **Namib Linux**
- **Obarun** (con systemd)
- **Arch Linux ARM**, y otras derivadas que mantengan compatibilidad con `pacman`, `systemd` y D-Bus

> **Nota**: Si tu distribución usa `pacman`, `systemd` y tiene D-Bus en el bus de sistema, BlipEraser debería funcionar. Si encuentras problemas en una derivada específica, reporta un issue.

## 🌟 Navegación y Secciones

1. **Vista general (Overview)**: Puntuación de salud radial (*GOOD / FAIR / POOR*), estadísticas de CPU/GPU/RAM/Disco y botón de acción rápida *"Limpiar ahora"*.
2. **Desinstalador**: Lista unificada de paquetes de `pacman` y carpetas manuales, con ordenación, filtro de búsqueda y selección manual por fila (sin checkbox de "seleccionar todo").
3. **Limpiador del sistema**:
   - **Limpieza recomendada**: Basura (`~/.cache`), Caché de pacman (`/var/cache/pacman/pkg`) y Registros (`/var/log`) desglosados ítem por ítem.
   - **Aplicaciones instaladas (manual)**: Carpetas sueltas y AppImages detectados.
4. **Ajustes de rendimiento**: Optimizaciones seguras de Arch Linux (`fstrim`, `zswap`, espejos de pacman por velocidad), cada una con tooltip de mecanismo, consecuencias y beneficio.
5. **Configuración**: Selección de temas cromáticos, fuentes tipográficas y borrado de historial de actividad.

## 🛡️ Confirmación de Seguridad y Umbral de Gran Tamaño

- Toda operación destructiva muestra la categorización exacta y el peso total a liberar.
- Si la selección supera el umbral de **5 GiB**, se muestra una **advertencia destacada en rojo y negrita**.
- **Confirmación obligatoria sin excepción**: la app no incluye casillas de *"no volver a preguntar"*.

## 🛠️ Requisitos del sistema

- Cualquier distro basada en Arch (requiere `pacman`, `systemd`, D-Bus).
- Python 3.11+, PyQt6 y **PyGObject** (instalados vía `pacman`).
- **Multimedia**: `gst-libav` (plugin GStreamer para video de intro H.264).
- `pkexec` / polkit para las acciones con privilegios de administrador.
- `systemd` + D-Bus (bus de sistema) para el daemon privilegiado (Fase 2).
- **Seguridad**: AppArmor (perfil incluido en `packaging/apparmor/`).

## 📦 Instalación

**Muy importante:** PyQt6, PyGObject y gst-libav se instalan con el gestor del sistema, **no por pip**. El daemon privilegiado (Fase 2) requiere PyGObject para D-Bus y gst-libav para el video de intro H.264.

```bash
# 1. Instalar dependencias del sistema (incluye gst-libav para video de intro)
sudo pacman -S python-pyqt6 python-gobject gst-libav

# 2. Instalar AppArmor profile (para daemon privilegiado Fase 2)
sudo cp packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged /etc/apparmor.d/
sudo apparmor_parser -r /etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged

# 3. Instalar systemd service (para daemon privilegiado Fase 2)
sudo mkdir -p /usr/lib/blip-eraser/
sudo cp packaging/systemd/blip-eraser-privileged.service /usr/lib/systemd/system/
sudo cp packaging/dbus/blip-eraser-privileged.conf /usr/share/dbus-1/system.d/
sudo cp packaging/dbus/com.dinopath.BlipEraser.Privileged.xml /usr/share/dbus-1/interfaces/
sudo cp packaging/scripts/blip-eraser-privileged /usr/lib/blip-eraser/
sudo chmod +x /usr/lib/blip-eraser/blip-eraser-privileged
sudo systemctl daemon-reload
sudo systemctl enable --now blip-eraser-privileged.service

# 4. Clona el repo e instala el proyecto en modo editable
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