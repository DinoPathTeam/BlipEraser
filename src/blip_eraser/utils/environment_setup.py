"""Módulo para la verificación y preparación del entorno de ejecución.

Este módulo centraliza la lógica necesaria para asegurar que el entorno
cumpla con los requisitos mínimos de la aplicación antes de iniciar la GUI.
"""

from .dependency_check import check_pyqt6_available, find_missing_dependencies, PYQT6_MISSING_MESSAGE, REQUIRED_BINARIES
from .privileged_daemon_manager import PrivilegedDaemonManager
from ..errors import BlipEraserEnvironmentError


class EnvironmentValidator:
    """Validador centralizado del entorno de ejecución."""

    @staticmethod
    def validate_pyqt6() -> bool:
        """Verifica si PyQt6 está disponible."""
        return check_pyqt6_available()

    @staticmethod
    def get_pyqt6_error_message() -> str:
        """Obtiene el mensaje de error si PyQt6 no está disponible."""
        return PYQT6_MISSING_MESSAGE

    @staticmethod
    def validate_system_binaries() -> list:
        """Verifica si las dependencias de sistema (binarios) están disponibles."""
        return find_missing_dependencies(REQUIRED_BINARIES)

    @staticmethod
    def validate_daemon_requirements() -> tuple[bool, list]:
        """Verifica si los requisitos para el daemon privilegiado están disponibles."""
        # Esta función ahora puede ser más específica o delegar en el manager.
        # Para mantener compatibilidad, simularemos una verificación simple.
        # En un refactor completo, esta lógica podría residir en el manager.
        from .phase2_installer import check_daemon_installed, check_dependencies_installed
        daemon_files_ok, missing_files = check_daemon_installed()
        missing_system_deps = check_dependencies_installed()
        all_missing_items = missing_files + missing_system_deps
        return daemon_files_ok and not missing_system_deps, all_missing_items


def ensure_environment() -> tuple[bool, str]:
    """Garantiza que el entorno cumpla con los requisitos mínimos.

    Returns:
        Una tupla (success, message) indicando si el entorno es válido.
    """
    # Validar PyQt6
    if not EnvironmentValidator.validate_pyqt6():
        return False, EnvironmentValidator.get_pyqt6_error_message()

    # Validar binarios del sistema
    missing_system_deps = EnvironmentValidator.validate_system_binaries()
    if missing_system_deps:
        missing_names = [dep.binary for dep in missing_system_deps]
        return False, f"Faltan dependencias del sistema: {', '.join(missing_names)}"

    # Validar requisitos del daemon (opcional para funcionalidad básica)
    daemon_ok, missing_daemon_items = EnvironmentValidator.validate_daemon_requirements()
    if not daemon_ok:
        # No es fatal, pero se puede loggear
        print(f"Advertencia: Algunos componentes del daemon privilegiado no están disponibles: {', '.join(missing_daemon_items)}")

    return True, "Entorno de ejecución válido."