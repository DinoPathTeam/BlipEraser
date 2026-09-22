"""Detección de dependencias — lógica pura, sin PyQt6.

BlipEraser NUNCA instala nada automáticamente: este módulo solo DETECTA
y expone información (*hints* de instalación) para que la GUI o el entry
point decidan cómo avisar al usuario.

Dos niveles:
  - Nivel 1: PyQt6 disponible (check_pyqt6_available). Se ejecuta ANTES
    de crear cualquier ventana, porque sin PyQt6 no hay GUI posible.
  - Nivel 2: binarios externos presentes en el PATH (check_binary_available,
    find_missing_dependencies). Cada sección de la app depende de binarios
    distintos y sigue usable con los que sí están presentes.

Nada de aquí llama a sys.exit() ni lanza QMessageBox: devuelve valores
(bool / listas / textos) que son directamente verificables en tests.
"""

from __future__ import annotations

import importlib
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
import subprocess

# Asume distro Arch — revisar si se soporta multi-distro a futuro
PYQT6_MODULE = "PyQt6.QtWidgets"
PYQT6_INSTALL_HINT = "sudo pacman -S python-pyqt6"
PYQT6_MISSING_MESSAGE = (
    "❌ Falta PyQt6. Instálalo con: " + PYQT6_INSTALL_HINT
)


@dataclass(frozen=True)
class Dependency:
    """Metadatos de una dependencia de binario externo.

    Hay dos escenarios de remedio mutuamente excluyentes:
      - `install_command`: la dependencia se resuelve instalando algo
        (p. ej. pkexec -> "sudo pacman -S polkit").
      - `incompatible_system_message`: no hay nada que instalar porque
        el sistema no soporta la función (p. ej. falta pacman: no se
        puede usar pacman para instalar pacman). En ese caso
        `install_command` debe ser None.
    """

    binary: str
    why: str
    install_command: str | None = None
    incompatible_system_message: str | None = None

    def remediation_suffix(self) -> str:
        """Texto accionable que completa el aviso, según el caso de remedio.

        NUNCA devuelve "Instala con: None": si no hay comando de
        instalación, usa el mensaje de incompatibilidad de sistema.
        """
        if self.install_command is not None:
            return f"Instala con: {self.install_command}"
        if self.incompatible_system_message:
            return self.incompatible_system_message
        return "No hay remedio automático disponible."


# Nivel 2: binarios que la app (o partes de ella) necesita.
BINARY_DEPENDENCIES: dict[str, Dependency] = {
    "pacman": Dependency(
        binary="pacman",
        why="necesario para listar y desinstalar paquetes del sistema "
        "(pestaña 'Paquetes (pacman)')",
        incompatible_system_message=(
            "BlipEraser está diseñado para distribuciones basadas en Arch "
            "(como CachyOS). Si no estás en una de estas distros, la pestaña "
            "'Paquetes (pacman)' no estará disponible, pero el escaneo manual "
            "seguirá funcionando."
        ),
    ),
    "pkexec": Dependency(
        binary="pkexec",
        why="necesario para desinstalar paquetes con privilegios vía polkit",
        install_command="sudo pacman -S polkit",
    ),
}

REQUIRED_BINARIES = tuple(BINARY_DEPENDENCIES.values())


# ----------------------------------------------------------------------
# Nivel 1 — PyQt6
# ----------------------------------------------------------------------
def check_pyqt6_available() -> bool:
    """True si PyQt6 (QtWidgets) se puede importar.

    Envuelve el import en try/except ImportError como pide el diseño.
    No lanza excepciones no controladas: devuelve bool para que el
    entry point decida si continuar y con qué código de salida.
    """
    try:
        importlib.import_module(PYQT6_MODULE)
        return True
    except ImportError:
        return False


# ----------------------------------------------------------------------
# Nivel 2 — binarios externos
# ----------------------------------------------------------------------
def check_binary_available(binary: str) -> bool:
    """True si `binary` está disponible en el PATH (vía shutil.which)."""
    return shutil.which(binary) is not None


def find_missing_dependencies(
    dependencies: Sequence[Dependency] = REQUIRED_BINARIES,
) -> list[Dependency]:
    """Devuelve solo las dependencias cuyo binario no está en el PATH."""
    return [dep for dep in dependencies if not check_binary_available(dep.binary)]


# ----------------------------------------------------------------------
# Nivel 3 — Dependencias del Daemon Privilegiado (Fase 2)
# ----------------------------------------------------------------------
# Cache para resultados de verificación de dependencias daemon (TTL 1 hora)
_DAEMON_DEPS_CACHE: tuple[list[DaemonDependency], float] | None = None
_DAEMON_DEPS_CACHE_TTL = 3600  # 1 hora

@dataclass(frozen=True)
class DaemonDependency:
    """Metadatos de una dependencia del daemon privilegiado."""
    name: str                    # Nombre legible
    check_cmd: str               # Comando para verificar si está instalado/activo
    install_cmd: str             # Comando para instalar (con pkexec)
    check_active_cmd: str        # Comando para verificar si está activo
    requires_restart: bool = False  # Si requiere reinicio del sistema

# Dependencias del daemon privilegiado (Fase 2)
DAEMON_DEPENDENCIES: tuple[DaemonDependency, ...] = (
    DaemonDependency(
        name="Python GObject (PyGObject)",
        check_cmd="python3 -c 'import gi; gi.require_version(\"GLib\", \"2.0\"); from gi.repository import GLib'",
        install_cmd="pkexec pacman -S --noconfirm python-gobject",
        check_active_cmd="python3 -c 'import gi; gi.require_version(\"GLib\", \"2.0\"); from gi.repository import GLib'",
    ),
    DaemonDependency(
        name="GStreamer libav (gst-libav)",
        check_cmd="gst-inspect-1.0 avdec_h264 2>/dev/null | head -1",
        install_cmd="pkexec pacman -S --noconfirm gst-libav",
        check_active_cmd="gst-inspect-1.0 avdec_h264 2>/dev/null | head -1",
    ),
    # NOTA: AppArmor (Fase 3) es OPCIONAL y no bloquea el arranque: el
    # perfil vive en packaging/apparmor/ para quien lo quiera activar.
    # Estuvo aquí y mostraba un modal en cada inicio aunque el daemon
    # funciona sin él.
    DaemonDependency(
        name="D-Bus System Bus (dbus.service)",
        check_cmd="systemctl is-active dbus 2>/dev/null",
        install_cmd="pkexec pacman -S --noconfirm dbus",
        check_active_cmd="systemctl is-active dbus 2>/dev/null",
    ),
)


def _check_daemon_deps_cached() -> list[DaemonDependency]:
    """Verifica dependencias del daemon con cache TTL."""
    global _DAEMON_DEPS_CACHE
    import time
    
    now = time.time()
    if _DAEMON_DEPS_CACHE is not None:
        cached_result, cached_time = _DAEMON_DEPS_CACHE
        if now - cached_time < 3600:  # TTL 1 hora
            return cached_result
    
    missing = []
    for dep in DAEMON_DEPENDENCIES:
        try:
            # Use shell=True for commands with pipes/redirections, but they're hardcoded
            result = subprocess.run(
                dep.check_cmd, shell=True, capture_output=True, timeout=5
            )
            if result.returncode != 0:
                missing.append(dep)
                continue
            
            # Verificar si está activo (para los que tienen check_active_cmd)
            if dep.check_active_cmd:
                active_result = subprocess.run(
                    dep.check_active_cmd, shell=True, capture_output=True, timeout=5
                )
                if active_result.returncode != 0:
                    missing.append(dep)
                    continue
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            missing.append(dep)
    
    _DAEMON_DEPS_CACHE = (missing, time.time())
    return missing


def check_daemon_dependencies() -> list[DaemonDependency]:
    """Verifica qué dependencias del daemon faltan o están inactivas.
    
    Returns:
        Lista de dependencias que faltan o están inactivas (vacío si todo OK).
    """
    return _check_daemon_deps_cached()


def invalidate_daemon_deps_cache() -> None:
    """Invalida el cache de dependencias del daemon."""
    global _DAEMON_DEPS_CACHE
    _DAEMON_DEPS_CACHE = None


def missing_binary_banner(binaries: Sequence[str]) -> str:
    """Texto corto (para una etiqueta de GUI) con los binarios ausentes y su hint.

    Devuelve cadena vacía si no falta ninguno de los pedidos. Esto permite
    que una pestaña avise inline sin entorpecer el resto de la app.
    Para cada ausente usa `Dependency.remediation_suffix()`: comando de
    instalación si aplica, mensaje de incompatibilidad de sistema si no.
    """
    lines = []
    for binary_name in binaries:
        dep = BINARY_DEPENDENCIES.get(binary_name)
        if dep is not None and not check_binary_available(binary_name):
            lines.append(
                f"⚠ {dep.binary} no encontrado — {dep.why}. "
                f"{dep.remediation_suffix()}"
            )
    return "\n".join(lines)