"""Módulo para gestionar el daemon privilegiado (Fase 2).

Este módulo encapsula la lógica de verificación, instalación y gestión
del daemon privilegiado, incluyendo sus dependencias, políticas y servicios.
"""

from .phase2_installer import (
    check_daemon_installed,
    install_all_phase2,
    InstallResult,
)
from .dependency_check import check_daemon_dependencies


class PrivilegedDaemonManager:
    """Gestor del daemon privilegiado."""

    @staticmethod
    def is_fully_installed() -> bool:
        """Verifica si el daemon privilegiado está completamente instalado."""
        installed, _ = check_daemon_installed()
        return installed

    @staticmethod
    def is_running() -> bool:
        """Verifica si el servicio del daemon está activo."""
        try:
            import subprocess
            from blip_eraser.utils.host_cmd import host_cmd
            result = subprocess.run(host_cmd(["systemctl", "is-active", "blip-eraser-privileged.service"]), capture_output=True, text=True, timeout=5)
            return result.returncode == 0 and result.stdout.strip() == "active"
        except Exception:
            return False

    @staticmethod
    def are_dependencies_met() -> bool:
        """Verifica si todas las dependencias del daemon están instaladas y activas."""
        missing_deps = check_daemon_dependencies()
        return len(missing_deps) == 0

    @classmethod
    def install_if_needed(cls) -> InstallResult:
        """Instala el daemon privilegiado y sus dependencias si es necesario."""
        if cls.is_fully_installed():
            return InstallResult(success=True, message="Daemon privilegiado ya instalado.")

        if not cls.are_dependencies_met():
            # Aquí iría la lógica para instalar dependencias específicas del daemon si no están presentes.
            # Por simplicidad en este refactor, asumimos que install_all_phase2 las maneja.
            pass

        success, message, needs_restart = install_all_phase2()
        return InstallResult(success=success, message=message, needs_restart=needs_restart)

    @classmethod
    def ensure_running(cls) -> InstallResult:
        """Garantiza que el daemon esté instalado y corriendo."""
        install_result = cls.install_if_needed()
        if not install_result.success:
            return install_result

        if cls.is_running():
            return InstallResult(success=True, message="Daemon privilegiado está corriendo.")
        else:
            # Si está instalado pero no corriendo, intentar iniciarlo.
            # Esta lógica podría estar en install_all_phase2 o en una nueva función.
            # Por ahora, asumimos que install_all_phase2 lo inicia.
            return InstallResult(success=False, message="El daemon se instaló pero no se pudo iniciar.")


# Función de conveniencia para usar en el entry point si se desea un chequeo más profundo.
def ensure_privileged_daemon() -> tuple[bool, str]:
    """Garantiza que el daemon privilegiado esté instalado y corriendo."""
    manager = PrivilegedDaemonManager()
    install_result = manager.install_if_needed()

    if not install_result.success:
        return False, f"Error instalando daemon: {install_result.message}"

    if not manager.is_running():
        return False, "El daemon privilegiado no está corriendo."

    message = "Daemon privilegiado listo."
    if install_result.needs_restart:
        message += " Se requiere reiniciar el sistema para que algunos cambios surtan efecto (AppArmor)."
    return True, message