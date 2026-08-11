"""Ejecución de borrados con privilegios — lógica pura, sin PyQt6.

Centraliza la decisión de CUÁNDO una operación destructiva necesita escalar
privilegios y CÓMO ejecutarla:

- Rutas dentro de $HOME (p. ej. ~/.cache, carpetas manuales del usuario):
  se borran directamente con `delete_path`, sin pedir contraseña.
- Rutas de sistema (p. ej. /var/cache/pacman/pkg, /var/log): la app NUNCA
  se eleva toda entera; únicamente el `rm` concreto se ejecuta vía
  `pkexec rm -rf -- <rutas>`. Un lote completo de rutas de sistema se envía
  en UNA sola llamada a pkexec, de modo que la autenticación se pide una
  sola vez por lote.

Los errores se devuelven de forma estructurada (código + detalle), nunca
como excepciones técnicas: la GUI los traduce a mensajes claros y
localizados sin exponer tracebacks ni rutas crudas pormenorizadas.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from blip_eraser.utils.file_utils import delete_path

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

# Códigos de retorno de pkexec (man pkexec).
PKEXEC_RC_AUTH_CANCELLED = 126
PKEXEC_RC_EXECUTION_FAILED = 127


@dataclass
class RemovalError:
    """Fallo de borrado estructurado para la GUI (no raw OSError).

    - `paths`: rutas afectadas (una, o todo el lote de sistema).
    - `code`: "cancelled" | "pkexec_missing" | "denied" | "failed".
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


def _run_pkexec_rm(paths: list[Path]) -> RemovalError | None:
    """Ejecuta `pkexec rm -rf -- <paths>`. Devuelve un RemovalError o None si OK."""
    cmd = ["pkexec", "rm", "-rf", "--", *(str(p) for p in paths)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return RemovalError(paths=paths, code="pkexec_missing")
    if proc.returncode == PKEXEC_RC_AUTH_CANCELLED:
        return RemovalError(
            paths=paths, code="cancelled", detail=(proc.stderr or "").strip()
        )
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()
        code = "failed"
        if proc.returncode == PKEXEC_RC_EXECUTION_FAILED:
            code = "failed"
        return RemovalError(paths=paths, code=code, detail=detail)
    return None


def remove_paths(paths: list[Path]) -> RemovalOutcome:
    """Borra `paths` con el nivel de privilegios que corresponde a cada uno.

    - Rutas de $HOME: `delete_path` directo.
    - Rutas de sistema: UN solo `pkexec rm -rf` con todo el lote (una única
      solicitud de autenticación para el lote).

    Devuelve un RemovalOutcome con el conteo y errores estructurados.
    """
    outcome = RemovalOutcome()
    home_paths: list[Path] = []
    system_paths: list[Path] = []

    for path in paths:
        safe = path.expanduser()
        (system_paths if needs_elevation(safe) else home_paths).append(safe)

    for path in home_paths:
        try:
            delete_path(path)
            outcome.removed += 1
        except (OSError, PermissionError) as exc:
            outcome.errors.append(_home_removal_error(path, exc))

    if system_paths:
        error = _run_pkexec_rm(system_paths)
        if error is None:
            outcome.removed += len(system_paths)
        else:
            outcome.errors.append(error)

    return outcome