"""Cliente D-Bus para el daemon privilegiado — con fallback a pkexec.

Proporciona una API asíncrona/síncrona unificada para que la UI llame
a operaciones privilegiadas. Si el daemon no está disponible, cae a pkexec
directo (modo desarrollo/tests).
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from blip_eraser.utils.log import write_diagnostic

# ─── Excepciones ────────────────────────────────────────────────────────

class DBusError(Exception):
    """Error base para operaciones D-Bus."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class DaemonUnavailable(DBusError):
    """El daemon no está disponible en el bus."""
    def __init__(self, message: str = "Daemon privilegiado no disponible"):
        super().__init__("DAEMON_UNAVAILABLE", message)


class ValidationFailed(DBusError):
    """Validación falló en el daemon."""
    def __init__(self, message: str):
        super().__init__("VALIDATION_FAILED", message)


class ExecutionFailed(DBusError):
    """Ejecución falló en el daemon."""
    def __init__(self, message: str):
        super().__init__("EXECUTION_FAILED", message)


class CommandNotFound(DBusError):
    """Comando no encontrado en el daemon."""
    def __init__(self, message: str):
        super().__init__("COMMAND_NOT_FOUND", message)


# ─── Cliente asíncrono (Gio) ──────────────────────────────────────────

class PrivilegedClient:
    """Cliente D-Bus asíncrono para com.dinopath.BlipEraser.Privileged."""

    BUS_NAME = "com.dinopath.BlipEraser.Privileged"
    OBJECT_PATH = "/com/dinopath/BlipEraser/Privileged"
    INTERFACE = "com.dinopath.BlipEraser.Privileged"

    def __init__(self):
        self._proxy: Optional["Gio.DBusProxy"] = None
        self._lock = threading.Lock()
        self._connected = False
        self._connection_error: Optional[Exception] = None

    def _ensure_gi(self) -> bool:
        """Verifica que PyGObject está disponible."""
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio
            return True
        except (ImportError, ValueError):
            return False

    def _get_proxy(self) -> "Gio.DBusProxy":
        """Obtiene (o crea) el proxy D-Bus."""
        with self._lock:
            if self._proxy is not None:
                return self._proxy
            if not self._ensure_gi():
                raise DaemonUnavailable("PyGObject (gi) no disponible")
            import gi
            from gi.repository import Gio
            try:
                self._proxy = Gio.DBusProxy.new_sync(
                    Gio.bus_get_sync(Gio.BusType.SYSTEM, None),
                    Gio.DBusProxyFlags.NONE,
                    None,  # interface_info
                    self.BUS_NAME,
                    self.OBJECT_PATH,
                    self.INTERFACE,
                    None  # cancellable
                )
                self._connected = True
                return self._proxy
            except Exception as e:
                self._connection_error = e
                raise DaemonUnavailable(f"No se pudo conectar al daemon: {e}")

    def is_available(self) -> bool:
        """Verifica si el daemon está disponible (no bloqueante)."""
        if self._connected and self._proxy:
            return True
        try:
            self._get_proxy()
            return True
        except DaemonUnavailable:
            return False

    def ping(self) -> bool:
        """Ping al daemon para verificar disponibilidad."""
        proxy = self._get_proxy()
        result = proxy.call_sync(
            "Ping", None,  # parámetros
            Gio.DBusCallFlags.NONE, -1, None  # timeout, cancellable
        )
        return result[0]  # bool

    def remove_packages(self, packages: list[str]) -> str:
        """Desinstala paquetes (síncrono)."""
        proxy = self._get_proxy()
        result = proxy.call_sync(
            "RemovePackages",
            GLib.Variant("(as)", (packages,)),
            Gio.DBusCallFlags.NONE, -1, None
        )
        return result[0]  # string

    def clean_system_paths(self, paths: list[str]) -> str:
        """Limpia rutas de sistema (síncrono)."""
        proxy = self._get_proxy()
        result = proxy.call_sync(
            "CleanSystemPaths",
            GLib.Variant("(as)", (paths,)),
            Gio.DBusCallFlags.NONE, -1, None
        )
        return result[0]


# ─── Fallback pkexec (síncrono, para tests/dev) ──────────────────────

# Allowlist igual que en privileges.py
ALLOWED_SYSTEM_PREFIXES: tuple[str, ...] = (
    "/var/cache/pacman/pkg",
    "/var/log",
    "/var/lib/pacman",
)

PKEXEC_RC_AUTH_CANCELLED = 126
PKEXEC_RC_EXECUTION_FAILED = 127


def _validate_path_pkexec(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    if not any(path_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES):
        return False
    if os.name == "posix":
        try:
            resolved = path.resolve(strict=False)
            resolved_str = str(resolved).replace("\\", "/")
            return any(resolved_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)
        except OSError:
            return False
    return True


def _reject_symlinks_pkexec(path: Path) -> bool:
    if path.is_symlink():
        return True
    for parent in path.parents:
        if parent.is_symlink():
            return True
    return False


def _run_pkexec_rm(paths: list[Path]) -> str:
    cmd = ["pkexec", "rm", "-rf", "--", *(str(p) for p in paths)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise DBusError("COMMAND_NOT_FOUND", "pkexec o rm no encontrado")
    if proc.returncode == PKEXEC_RC_AUTH_CANCELLED:
        raise DBusError("CANCELLED", "Autenticación cancelada")
    if proc.returncode != 0:
        raise DBusError("EXECUTION_FAILED",
            f"pkexec rm falló (código {proc.returncode}): {proc.stderr.strip()}")
    return f"Eliminadas {len(paths)} ruta(s)"


def _run_pkexec_pacman(packages: list[str], noconfirm: bool = True) -> str:
    cmd = ["pkexec", "pacman", "-Rns"]
    if noconfirm:
        cmd.append("--noconfirm")
    cmd.extend(packages)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise DBusError("COMMAND_NOT_FOUND", "pkexec o pacman no encontrado")
    except subprocess.CalledProcessError as e:
        if e.returncode == PKEXEC_RC_AUTH_CANCELLED:
            raise DBusError("CANCELLED", "Autenticación cancelada")
        raise DBusError("EXECUTION_FAILED",
            f"pacman falló (código {e.returncode}): {e.stderr.strip()}")
    return proc.stdout


# ─── API unificada (cliente + fallback) ──────────────────────────────

@dataclass
class OperationResult:
    """Resultado unificado de una operación privilegiada."""
    success: bool
    output: str = ""
    error: Optional[DBusError] = None
    used_daemon: bool = False


class PrivilegedAPI:
    """API unificada: intenta daemon primero, cae a pkexec."""

    def __init__(self, prefer_daemon: bool = True):
        self._client = PrivilegedClient() if prefer_daemon else None
        self._daemon_available_checked = False
        self._daemon_available = False

    def _check_daemon(self) -> bool:
        if not self._client:
            return False
        if self._daemon_available_checked:
            return self._daemon_available
        self._daemon_available = self._client.is_available()
        self._daemon_available_checked = True
        write_diagnostic(f"privileged_api: daemon_available={self._daemon_available}")
        return self._daemon_available

    def remove_packages(self, packages: list[str], noconfirm: bool = True) -> OperationResult:
        """Desinstala paquetes."""
        if not packages:
            return OperationResult(success=True, output="")

        # Intentar daemon
        if self._check_daemon():
            try:
                output = self._client.remove_packages(packages)
                write_diagnostic(f"AUDIT action=uninstall_packages packages={packages} result=success via=daemon")
                return OperationResult(success=True, output=output, used_daemon=True)
            except (DaemonUnavailable, ValidationFailed, ExecutionFailed, CommandNotFound) as e:
                write_diagnostic(f"AUDIT action=uninstall_packages packages={packages} result=daemon_failed error={e.code}")
                # Caer a pkexec

        # Fallback pkexec
        try:
            output = _run_pkexec_pacman(packages, noconfirm=noconfirm)
            write_diagnostic(f"AUDIT action=uninstall_packages packages={packages} result=success via=pkexec")
            return OperationResult(success=True, output=output, used_daemon=False)
        except DBusError as e:
            return OperationResult(success=False, error=e)
        except Exception as e:
            return OperationResult(success=False, error=DBusError("INTERNAL", str(e)))

    def clean_system_paths(self, paths: list[Path]) -> OperationResult:
        """Limpia rutas de sistema."""
        if not paths:
            return OperationResult(success=True, output="")

        str_paths = [str(p) for p in paths]

        # Intentar daemon
        if self._check_daemon():
            try:
                output = self._client.clean_system_paths(str_paths)
                write_diagnostic(f"AUDIT action=clean_system_paths paths={str_paths} result=success via=daemon")
                return OperationResult(success=True, output=output, used_daemon=True)
            except (DaemonUnavailable, ValidationFailed, ExecutionFailed, CommandNotFound) as e:
                write_diagnostic(f"AUDIT action=clean_system_paths paths={str_paths} result=daemon_failed error={e.code}")

        # Fallback pkexec con validación local
        validated = []
        for p in paths:
            if _reject_symlinks_pkexec(p):
                write_diagnostic(f"AUDIT action=clean_rejected path={p} reason=symlink_detected via=pkexec")
                return OperationResult(success=False, error=ValidationFailed(f"Symlink detectado: {p}"))
            if not _validate_path_pkexec(p):
                write_diagnostic(f"AUDIT action=clean_rejected path={p} reason=path_not_in_allowlist via=pkexec")
                return OperationResult(success=False, error=ValidationFailed(f"Ruta no permitida: {p}"))
            validated.append(p)

        if not validated:
            return OperationResult(success=False, error=ValidationFailed("Ninguna ruta válida"))

        try:
            output = _run_pkexec_rm(validated)
            write_diagnostic(f"AUDIT action=clean_system_paths paths={str_paths} result=success via=pkexec")
            return OperationResult(success=True, output=output, used_daemon=False)
        except subprocess.CalledProcessError as e:
            if e.returncode == PKEXEC_RC_AUTH_CANCELLED:
                return OperationResult(success=False, error=DBusError("CANCELLED", "Autenticación cancelada"))
            return OperationResult(success=False, error=DBusError("EXECUTION_FAILED",
                f"rm falló (código {e.returncode}): {e.stderr.strip()}"))
        except FileNotFoundError:
            return OperationResult(success=False, error=CommandNotFound("pkexec o rm no encontrado"))
        except DBusError:
            raise
        except Exception as e:
            return OperationResult(success=False, error=DBusError("INTERNAL", str(e)))


# Instancia global para uso sencillo
_default_api: Optional[PrivilegedAPI] = None


def get_privileged_api(prefer_daemon: bool = True) -> PrivilegedAPI:
    """Obtiene la instancia singleton de la API privilegiada."""
    global _default_api
    if _default_api is None:
        _default_api = PrivilegedAPI(prefer_daemon=prefer_daemon)
    return _default_api


def reset_privileged_api() -> None:
    """Resetea la instancia (para tests)."""
    global _default_api
    _default_api = None