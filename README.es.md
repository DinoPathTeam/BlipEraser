🇬🇧 [Read in English](README.en.md)

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# BlipEraser

Desinstalador de aplicaciones para **CachyOS** (y cualquier distro basada en Arch).

BlipEraser existe para cubrir el hueco que dejan los gestores gráficos tradicionales:
apps instaladas **manualmente** — AppImages, carpetas sueltas de lanzadores de terceros
como Hydra Launcher, programas sin paquete — que **no quedan registradas en ningún
gestor de paquetes** y que, por tanto, ninguna herramienta "de desinstalación"
habitual es capaz de detectar.

## Requisitos del sistema

- CachyOS o cualquier distro basada en Arch (requiere `pacman`).
- KDE Plasma (recomendado, aunque no es estrictamente obligatorio).
- Python 3.11+ y PyQt6 (ver instalación).
- `pkexec` / polkit para las acciones con privilegios.

## Instalación

**Muy importante:** PyQt6 se instala con el gestor del sistema, **no por pip**.
Instalarlo por pip entra en conflicto con las bibliotecas Qt del sistema:

```bash
sudo pacman -S python-pyqt6 python-pytest
```

Después clona la repo e instala el proyecto en modo editable:

```bash
git clone <url-del-repo>
cd blipEraser
pip install -e . --break-system-packages
```

Si prefieres aislar las dependencias del sistema (venv), usa `--system-site-packages`
para que el venv reutilice PyQt6 y pytest de pacman sin re-descargarlos:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

## Uso básico

Ejecuta la app con:

```bash
blip-eraser
# también funciona (con la instalación editable hecha):
python -m blip_eraser
```

> Sin instalar, también puedes correrla directamente desde la raíz del repo con
> `PYTHONPATH=src python -m blip_eraser`.

La ventana tiene dos pestañas:

- **Paquetes (pacman):** lista los paquetes instalados explícitamente (`pacman -Qe`),
  permite seleccionar uno o varios y desinstalarlos con `pkexec pacman -Rns --noconfirm`.
- **Escaneo manual:** recorre ubicaciones típicas (`~/.local/share`, `~/Games`,
  `~/Descargas`, `~/Applications`), calcula el tamaño de cada carpeta/AppImage y
  permite eliminarlas con confirmación.

## Verificación de dependencias

BlipEraser comprueba sus dependencias en **dos niveles**:

1. **Nivel 1 — antes de abrir cualquier ventana:** si PyQt6 falta, no se puede dibujar
   la GUI en absoluto, así que la app avisa por consola con el comando de instalación
   y sale con código de error distinto de cero.
2. **Nivel 2 — con la GUI ya abierta:** verifica en segundo plano (sin bloquear la
   interfaz) si los binarios externos `pacman` y `pkexec` están disponibles. Si falta
   alguno, muestra qué es, por qué se necesita y el comando exacto para instalarlo.

**BlipEraser NUNCA instala nada automáticamente.** Su único trabajo es detectar,
informar y guiar; la instalación de cualquier dependencia la ejecuta siempre el
usuario de forma explícita.

## Desarrollo / Tests

La lógica de negocio (escaneo, cálculo de tamaños, comandos de pacman, verificación
de dependencias) vive en `src/blip_eraser/utils/` **sin ninguna dependencia de PyQt6**,
precisamente para poder testearla sin entorno gráfico — incluso desde Windows o
cualquier Linux sin display.

```bash
pytest tests/ -v
```

Se usan únicamente mocks (de `subprocess`/`shutil.which`) y `tmp_path` de pytest:
la suite no necesita PyQt6 instalado ni un sistema Arch real.

## Seguridad

- Toda operación destructiva (desinstalar paquetes, borrar carpetas) pide
  **confirmación explícita** antes de ejecutarse, indicando exactamente qué se va a
  eliminar.
- Los privilegios elevados se solicitan **por acción** mediante `pkexec`
  (prompt de polkit): no existe un modo "sudo persistente" que mantenga permisos
  de administrador durante toda la sesión.
- La aplicación nunca ejecuta instalaciones ni modificaciones del sistema sin
  respuesta del usuario.

## Licencia

[MIT](LICENSE)