"""Lógica pura para interactuar con pacman / pkexec — sin PyQt6.

Usa solo subprocess para que sea fácil de mockear y testear sin tener
paquetes reales instalados (o siquiera estar en un sistema Arch).

Seguridad (Fase 1 + Fase 2):
- Validación de que los paquetes existen en la BD de pacman antes de desinstalar
- Auditoría estructurada de cada operación
- La BD local se consulta en vivo (`pacman -Q`) en cada validación: sin caché
  que pueda quedar obsoleta ni verificación de firmas de la caché de descargas
  (pacman ya verifica las firmas al instalar; en CachyOS/AUR la caché
  no trae `.sig`)
- Desinstalación vía `pkexec pacman -Rns` (el daemon solo limpia rutas)
"""

from __future__ import annotations

import subprocess

from blip_eraser.utils.log import write_diagnostic
from blip_eraser.utils.host_cmd import host_cmd
from blip_eraser.utils.dbus_client import (
    get_privileged_api,
    DBusError,
    OperationResult,
)


def _query_packages(flag: str) -> list[tuple[str, str]]:
    """[(nombre, versión), ...] desde `pacman <flag>`.

    Lanza FileNotFoundError si pacman no existe y CalledProcessError
    si el comando falla. La GUI se encarga de mostrar el mensaje.
    """
    result = subprocess.run(
        host_cmd(["pacman", flag]),
        capture_output=True,
        text=True,
        check=True,
    )
    packages: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        name = parts[0]
        version = parts[1] if len(parts) > 1 else ""
        packages.append((name, version))
    return packages


def list_explicit_packages() -> list[tuple[str, str]]:
    """Devuelve [(nombre, versión), ...] desde `pacman -Qe`.
    Paquetes instalados explícitamente (las 'aplicaciones').
    """
    return _query_packages("-Qe")


def list_dependency_packages() -> list[tuple[str, str]]:
    """Devuelve [(nombre, versión), ...] desde `pacman -Qd`.

    Paquetes instalados como dependencia de otros (no explícitos).
    Mismo formato de salida que `pacman -Qe`.
    """
    return _query_packages("-Qd")


_QUERY_TIMEOUT = 30


def _get_installed_package_names() -> set[str]:
    """Nombres de todos los paquetes instalados, consultados en vivo.

    Lanza ``RuntimeError`` (con el stderr de pacman) si la consulta falla: un
    fallo NUNCA se interpreta como "no hay paquetes instalados".
    """
    try:
        result = subprocess.run(
            host_cmd(["pacman", "-Q"]),
            capture_output=True,
            text=True,
            check=True,
            timeout=_QUERY_TIMEOUT,
        )
    except (subprocess.SubprocessError, OSError) as e:
        stderr = (getattr(e, "stderr", "") or "").strip()[:300]
        write_diagnostic(f"AUDIT action=pacman_query result=failed detail={e} stderr={stderr}")
        raise RuntimeError(f"No se pudo consultar la base de datos de pacman: {stderr or e}") from e
    names: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            names.add(line.split(None, 1)[0])
    return names


def _validate_packages_exist(packages: list[str]) -> tuple[list[str], list[str]]:
    """Valida que los paquetes existen en la BD de pacman.

    Devuelve (válidos, inválidos). Los inválidos no se desinstalarán.
    """
    installed = _get_installed_package_names()
    valid = [p for p in packages if p in installed]
    invalid = [p for p in packages if p not in installed]
    return valid, invalid


def uninstall_packages(
    packages: list[str],
    noconfirm: bool = True,
) -> str:
    """Desinstala paquetes con `pkexec pacman -Rns` (autorización polkit).

    VALIDACIÓN DE SEGURIDAD (Fase 1 + Fase 2):
    - Verifica que cada paquete existe en la BD de pacman antes de desinstalar
    - Rechaza paquetes que no están instalados (previene typosquatting, etc.)
    - Auditoría completa de la operación

    Devuelve la salida estándar del comando.
    Lanza ValueError si hay paquetes no válidos.
    Lanza DBusError si la operación falla.
    """
    if not packages:
        return ""

    # Validar que los paquetes existen
    valid, invalid = _validate_packages_exist(packages)
    if invalid:
        write_diagnostic(f"AUDIT action=uninstall_packages packages={invalid} result=rejected reason=not_installed")
        raise ValueError(f"Paquetes no instalados (rechazados): {', '.join(invalid)}")

    write_diagnostic(f"AUDIT action=uninstall_packages packages={valid} result=started")

    # Usar API privilegiada unificada (daemon + fallback pkexec)
    api = get_privileged_api()
    result: OperationResult = api.remove_packages(valid, noconfirm=noconfirm)

    if result.success:
        write_diagnostic(f"AUDIT action=uninstall_packages packages={valid} result=success via={'daemon' if result.used_daemon else 'pkexec'}")

        return result.output
    else:
        if result.error:
            write_diagnostic(f"AUDIT action=uninstall_packages packages={valid} result=failed error={result.error.code}")
            raise result.error
        else:
            raise DBusError("INTERNAL", "Error desconocido en desinstalación")