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