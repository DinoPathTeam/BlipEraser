"""Ejecución de borrados con privilegios — lógica pura, sin PyQt6.

Centraliza la decisión de CUÁNDO una operación destructiva necesita escalar
privilegios y CÓMO ejecutarla:

- Rutas dentro de $HOME (p. ej. ~/.cache, carpetas manuales del usuario):
  se borran directamente con `delete_path`, sin pedir contraseña.
- Rutas de sistema (p. ej. /var/cache/pacman/pkg, /var/log): la app NUNCA
  se eleva toda entera; únicamente el `rm` concreto se ejecuta vía
  daemon D-Bus privilegiado (con fallback a `pkexec rm -rf`). Un lote completo
  de rutas de sistema se envía en UNA sola llamada, de modo que la
  autenticación se pide una sola vez por lote.

Los errores se devuelven de forma estructurada (código + detalle), nunca
como excepciones técnicas: la GUI los traduce a mensajes claros y
localizados sin exponer tracebacks ni rutas crudas pormenorizadas.

Seguridad (Fase 1 + Fase 2):
- Allowlist estricta de prefijos de sistema permitidos para `rm -rf`
- Validación con `Path.resolve()` para prevenir path traversal
- Rechazo de symlinks en cualquier nivel de la ruta
- Auditoría estructurada de cada operación privilegiada
- Allowlist de operaciones permitidas (elimina RCE vía callables arbitrarios)
- Validación de rutas $HOME (denylist: .ssh, .gnupg, .config, etc.)
- **Fase 2**: Daemon D-Bus systemd con separación real de privilegios
  (fallback a pkexec si el daemon no está disponible)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable

from blip_eraser.utils.validation import (
    validate_path,
    reject_symlinks,
    is_symlink_or_reparse,
    ALLOWED_SYSTEM_PREFIXES,  # noqa: F401 (re-export; performance/tests lo importaban de aquí)
    HOME_DENYLIST_PREFIXES,
)
from blip_eraser.utils.dbus_client import (
    get_privileged_api,
    DBusError,
    OperationResult,
)
from blip_eraser.utils.file_utils import delete_path
from blip_eraser.utils.log import write_diagnostic

# Backward compatibility aliases for tests and legacy code
_validate_path = validate_path
_reject_symlinks = reject_symlinks
_is_symlink_or_reparse = is_symlink_or_reparse

# Rutas de sistema cuyo borrado requiere privilegios. Un path que no cae en
# $HOME y empieza por uno de estos prefijos se considera privilegiado.
SYSTEM_PATH_PREFIXES: tuple[str, ...] = (
    "/var/",
    "/etc/",
    "/usr/",
    "/opt/",
    "/boot/",
    "/root/",
    "/srv/",
    "/mnt/",
    "/media/",
)

# NOTA: ALLOWED_SYSTEM_PREFIXES y HOME_DENYLIST_PREFIXES viven en
# utils.validation (fuente única, compartida con el daemon). Aquí se
# re-exportan vía el import superior para compatibilidad
# (performance.py y tests los importan desde este módulo).

# Códigos de retorno de pkexec (man pkexec) - mantenidos para compatibilidad fallback
PKEXEC_RC_AUTH_CANCELLED = 126
PKEXEC_RC_EXECUTION_FAILED = 127


@dataclass
class RemovalError:
    """Fallo de borrado estructurado para la GUI (no raw OSError).

    - `paths`: rutas afectadas (una, o todo el lote de sistema).
    - `code`: "cancelled" | "pkexec_missing" | "denied" | "failed" | "validation_failed" | "dbus_unavailable".
    - `detail`: texto corto del comando heredado (opcional, ya saneado).
    """
    paths: list[Path]
    code: str
    detail: str = ""


@dataclass
class RemovalOutcome:
    """Resultado agregado de `remove_paths`: cuántos se borraron y qué falló."""
    removed: int = 0
    errors: list[RemovalError] = field(default_factory=list)


# =========================================================================
# ALLOWLIST DE OPERACIONES PERMITIDAS (elimina RCE vía callables arbitrarios)
# =========================================================================
# Cada operación tiene un ID string y una función asociada. SOLO estas
# operaciones pueden ejecutarse vía ConfirmItem.operation.
# El registro se construye aquí para que confirm_dialog.py lo importe.

def _op_pacman_remove(packages: list[str]) -> str:
    """Operación permitida: desinstala paquetes vía daemon/pkexec pacman -Rns."""
    from blip_eraser.utils.pacman import uninstall_packages
    return uninstall_packages(packages)


def _op_rm_rf(paths: list[Path]) -> RemovalOutcome:
    """Operación permitida: borra rutas de sistema vía daemon/pkexec rm -rf."""
    return remove_paths(paths)


# Registro de operaciones permitidas. La clave es el ID que usa ConfirmItem.operation.
# SOLO estas operaciones pueden invocarse. Cualquier otro ID es rechazado.
ALLOWED_OPERATIONS: dict[str, Callable] = {
    "pacman_remove": _op_pacman_remove,
    "rm_rf": _op_rm_rf,
}


def get_allowed_operation(op_id: str) -> Callable | None:
    """Obtiene la función permitida para un ID de operación.

    Returns None si el ID no está en la allowlist (rechazo seguro).
    """
    return ALLOWED_OPERATIONS.get(op_id)





def _audit_log(action: str, paths: list[Path], result: str, detail: str = "") -> None:
    """Registra una entrada de auditoría estructurada en la bitácora forense.

    Formato: [timestamp] [thread] AUDIT action=... paths=... result=... detail=...

    SEGURIDAD: Los paths se haslean INDIVIDUALMENTE antes de unirlos,
    para que _sanitize_message no falle con rutas separadas por comas.
    """
    from blip_eraser.utils.log import _hash_path
    path_strs = ",".join(f"{p}#{_hash_path(str(p))}" for p in paths)
    msg = f"AUDIT action={action} paths={path_strs} result={result}"
    if detail:
        msg += f" detail={detail}"
    write_diagnostic(msg)


def _is_path_denied_in_home(path: Path, home: Path | None = None) -> bool:
    """True si la ruta está en el denylist de $HOME (nunca borrar)."""
    if home is None:
        home = Path.home()
    try:
        expanded = path.expanduser()
        resolved = expanded.resolve()
        rel = resolved.relative_to(home.resolve())
        rel_str = str(rel).replace("\\", "/")
        return any(rel_str.startswith(prefix) for prefix in HOME_DENYLIST_PREFIXES)
    except (OSError, ValueError):
        return False


def needs_elevation(path: Path, home: Path | None = None) -> bool:
    """True si borrar `path` requiere privilegios (está fuera de $HOME).

    Reglas:
      1. Todo lo que quede dentro de $HOME se borra sin elevar.
      2. Fuera de $HOME, solo se eleva si la ruta cae bajo SYSTEM_PATH_PREFIXES
         (nunca se asume sobre una ruta arbitraria del usuario).
    """
    if home is None:
        home = Path.home()
    expanded = path.expanduser()
    try:
        resolved = expanded.resolve()
    except OSError:
        resolved = expanded.absolute()

    try:
        resolved.relative_to(home.resolve())
        return False
    except ValueError:
        pass

    # El match de prefijos se hace sobre el texto tal cual se escribió la
    # ruta (mantiene el prefijo /var/ incluso en sistemas donde resolve()
    # lo reescribiría, p. ej. pruebas en Windows). Normaliza separadores
    # para que funcione igual en Windows (\var) y Linux (/var).
    text = str(expanded).replace("\\", "/")
    return any(text.startswith(prefix) for prefix in SYSTEM_PATH_PREFIXES)


def _home_removal_error(path: Path, exc: BaseException) -> RemovalError:
    if isinstance(exc, PermissionError):
        return RemovalError(paths=[path], code="denied", detail=str(exc))
    return RemovalError(paths=[path], code="failed", detail=str(exc))


def _convert_dbus_error_to_removal(paths: list[Path], error: DBusError) -> RemovalError:
    """Convierte un DBusError a RemovalError para compatibilidad con GUI."""
    code_map = {
        "CANCELLED": "cancelled",
        "VALIDATION_FAILED": "validation_failed",
        "EXECUTION_FAILED": "failed",
        "COMMAND_NOT_FOUND": "pkexec_missing",
        "DAEMON_UNAVAILABLE": "dbus_unavailable",
        "INTERNAL": "failed",
    }
    code = code_map.get(error.code, "failed")
    return RemovalError(paths=paths, code=code, detail=error.message)


def remove_paths(paths: list[Path], on_progress: Callable[[int, int], None] | None = None) -> RemovalOutcome:
    """Borra `paths` con el nivel de privilegios que corresponde a cada uno.

    - Rutas de $HOME: `delete_path` directo.
    - Rutas de sistema: UNA sola llamada al daemon D-Bus (con fallback a
      `pkexec rm -rf`) con todo el lote (una única solicitud de autenticación
      para el lote).

    `on_progress(done, total)` se llama tras cada ruta de $HOME y una vez
    al completar el lote de sistema (para diálogos de progreso; el lote es
    una sola operación indivisible).

    VALIDACIONES DE SEGURIDAD (Fase 1 + Fase 2):
    - Cada ruta de sistema debe pasar _validate_path (allowlist estricta)
    - Cada ruta de sistema debe pasar _reject_symlinks (no symlinks)
    - Rutas de $HOME deben pasar _is_path_denied_in_home (denylist)
    - Auditoría completa de cada operación
    - **Fase 2**: Usa daemon D-Bus privilegiado con fallback a pkexec
    """
    outcome = RemovalOutcome()
    home_paths: list[Path] = []
    system_paths: list[Path] = []
    total = len(paths)
    done = 0

    def _tick(step: int = 1) -> None:
        nonlocal done
        done += step
        if on_progress is not None:
            on_progress(done, total)

    for path in paths:
        safe = path.expanduser()
        (system_paths if needs_elevation(safe) else home_paths).append(safe)

    for path in home_paths:
        # Validación denylist en $HOME
        if _is_path_denied_in_home(path):
            err = RemovalError(paths=[path], code="validation_failed", detail="path_in_home_denylist")
            outcome.errors.append(err)
            _audit_log("remove_home", [path], "rejected", "path_in_home_denylist")
            _tick()
            continue
        try:
            delete_path(path)
            outcome.removed += 1
            _audit_log("remove_home", [path], "success")
        except (OSError, PermissionError) as exc:
            outcome.errors.append(_home_removal_error(path, exc))
            _audit_log("remove_home", [path], "failed", str(exc))
        _tick()

    if system_paths:
        # Validación estricta ANTES de invocar operación privilegiada
        validated_paths: list[Path] = []
        for path in system_paths:
            if _reject_symlinks(path):
                err = RemovalError(paths=[path], code="validation_failed", detail="symlink_detected")
                outcome.errors.append(err)
                _audit_log("remove_system", [path], "rejected", "symlink_detected")
                continue
            if not _validate_path(path):
                err = RemovalError(paths=[path], code="validation_failed", detail="path_not_in_allowlist")
                outcome.errors.append(err)
                _audit_log("remove_system", [path], "rejected", "path_not_in_allowlist")
                continue
            validated_paths.append(path)

        if validated_paths:
            # Usar API privilegiada unificada (daemon + fallback pkexec)
            api = get_privileged_api()
            result: OperationResult = api.clean_system_paths(validated_paths)
            if result.success:
                outcome.removed += len(validated_paths)
                _audit_log("remove_system", validated_paths, "success")
            else:
                if result.error:
                    outcome.errors.append(_convert_dbus_error_to_removal(validated_paths, result.error))
                    _audit_log("remove_system", validated_paths, "failed", result.error.message)
                else:
                    err = RemovalError(paths=validated_paths, code="failed", detail="unknown_error")
                    outcome.errors.append(err)
                    _audit_log("remove_system", validated_paths, "failed", "unknown_error")
            _tick(len(validated_paths))
        elif not outcome.errors:
            # Todas las rutas de sistema fueron rechazadas por validación
            _audit_log("remove_system", system_paths, "rejected_all", "no_valid_paths_after_validation")

    return outcome