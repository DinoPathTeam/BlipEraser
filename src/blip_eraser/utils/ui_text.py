"""Texto localizado para la GUI — lógica pura, sin PyQt6.

dependency_check.py, file_utils.py, pacman.py e i18n.py se mantienen
intactos (ya validados). Aquí solo se consume su lógica pura
(check_binary_available, BINARY_DEPENDENCIES, tr...) para armar el
texto final que verá el usuario, respetando el idioma activo.

Todo es testable con pytest mockeando check_binary_available y el
idioma activo, igual que el resto de la suite.
"""

from __future__ import annotations

from collections.abc import Sequence

from blip_eraser.utils.dependency_check import (
    BINARY_DEPENDENCIES,
    check_binary_available,
)
from blip_eraser.utils.i18n import (
    SUPPORTED_LANGUAGES,
    detect_system_language,
    tr,
)


# ----------------------------------------------------------------------
# Dependencias: texto visible (banner y diálogo del Nivel 2)
# ----------------------------------------------------------------------
def _missing_dependencies(binaries: Sequence[str]):
    """Yield de Dependency cuya binario no está disponible."""
    for binary in binaries:
        dep = BINARY_DEPENDENCIES.get(binary)
        if dep is not None and not check_binary_available(binary):
            yield dep


def _localized_remediation(dep) -> str:
    """Remedio según el caso: comando de instalación o incompatibilidad.

    No usa `dep.remediation_suffix()` (que está en español): construye el
    texto con tr() para respetar el idioma activo.
    """
    if dep.install_command is not None:
        return tr("dep_install_command").format(command=dep.install_command)
    if dep.incompatible_system_message:
        return tr(f"dep_{dep.binary}_incompatible")
    return tr("dep_no_remediation")


def localized_missing_lines(binaries: Sequence[str]) -> list[str]:
    """Líneas para el QMessageBox del Nivel 2 (una por binario ausente)."""
    return [
        tr("dep_line_template").format(
            binary=dep.binary,
            why=tr(f"dep_{dep.binary}_why"),
            remediation=_localized_remediation(dep),
        )
        for dep in _missing_dependencies(binaries)
    ]


def localized_missing_banner(binaries: Sequence[str]) -> str:
    """Banner corto para una etiqueta; "" si no falta ninguno."""
    return "\n".join(
        tr("dep_banner_line").format(
            binary=dep.binary,
            why=tr(f"dep_{dep.binary}_why"),
            remediation=_localized_remediation(dep),
        )
        for dep in _missing_dependencies(binaries)
    )


# ----------------------------------------------------------------------
# Idioma de primer arranque
# ----------------------------------------------------------------------
def should_ask_for_language(saved_language: str | None) -> bool:
    """True si es la primera vez: no hay preferencia guardada."""
    return saved_language is None


def resolve_initial_language(chosen: str | None) -> str:
    """Idioma final tras el diálogo de primer arranque.

    `chosen` es lo que eligió el usuario ("es"/"en"), o None si cerró el
    diálogo sin elegir. En ese caso (y para valores no soportados, por
    defensa) se detecta el idioma del sistema.
    """
    if chosen in SUPPORTED_LANGUAGES:
        return chosen
    return detect_system_language()