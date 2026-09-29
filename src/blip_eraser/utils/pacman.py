"""Lógica pura para interactuar con pacman / pkexec — sin PyQt6.

Usa solo subprocess para que sea fácil de mockear y testear sin tener
paquetes reales instalados (o siquiera estar en un sistema Arch).

Seguridad (Fase 1 + Fase 2):
- Validación de que los paquetes existen en la BD de pacman antes de desinstalar
- Auditoría estructurada de cada operación
- Caché de BD de paquetes con verificación de firmas (Supply chain #5)
- **Fase 2**: Daemon D-Bus systemd con fallback a pkexec
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from blip_eraser.utils.log import write_diagnostic
from blip_eraser.utils.host_cmd import host_cmd
from blip_eraser.utils.dbus_client import (
    get_privileged_api,
    DBusError,
    OperationResult,
)

# =========================================================================
# CACHÉ DE BD DE PAQUETES CON VERIFICACIÓN DE FIRMAS (Supply chain #5)
# =========================================================================
# Carga perezosa (lazy) de la lista de paquetes instalados + verificación
# de firmas de los paquetes en /var/cache/pacman/pkg.
# La caché se popula al primer uso y se mantiene en memoria para la sesión.

_PACKAGE_CACHE: set[str] | None = None
_CACHE_LOCK = threading.Lock()
_CACHE_INITIALIZED = False
_PACKAGE_IDENTITY_TRUSTED = True


class PackageIdentityUntrustedError(RuntimeError):
    """La identidad de los paquetes no pudo verificarse de forma segura."""


def _verify_package_signatures() -> bool:
    """Verifica las firmas de los paquetes en el caché de pacman.

    Usa `pacman-key --verify` sobre los archivos .sig en /var/cache/pacman/pkg.
    Devuelve True si TODOS los paquetes verificables tienen firma válida,
    False si alguna firma falla o hay paquetes sin firma en el caché.
    """
    cache_dir = Path("/var/cache/pacman/pkg")
    if not cache_dir.exists():
        return True  # Sin caché = nada que verificar

    try:
        # Buscar archivos .pkg.tar.zst y sus .sig correspondientes
        pkg_files = list(cache_dir.glob("*.pkg.tar.zst"))
        if not pkg_files:
            return True

        for pkg_file in pkg_files:
            sig_file = pkg_file.with_suffix(pkg_file.suffix + ".sig")
            if not sig_file.exists():
                write_diagnostic(
                    f"AUDIT action=pacman_verify package={pkg_file.name} result=missing_signature"
                )
                return False

            # Verificar firma con pacman-key
            result = subprocess.run(
                host_cmd(["pacman-key", "--verify", str(sig_file), str(pkg_file)]),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                write_diagnostic(
                    f"AUDIT action=pacman_verify package={pkg_file.name} result=invalid_signature "
                    f"stderr={result.stderr.strip()[:200]}"
                )
                return False

        write_diagnostic(
            f"AUDIT action=pacman_verify_all result=success count={len(pkg_files)}"
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        write_diagnostic(f"AUDIT action=pacman_verify result=error detail={e}")
        return False


def _load_package_cache() -> set[str]:
    """Carga y verifica la caché de paquetes instalados.

    1. Verifica firmas de paquetes en caché (supply chain)
    2. Carga lista de paquetes instalados desde `pacman -Q`
    3. Cachea en memoria para la sesión
    """
    global _PACKAGE_CACHE, _CACHE_INITIALIZED, _PACKAGE_IDENTITY_TRUSTED

    with _CACHE_LOCK:
        if _CACHE_INITIALIZED:
            return _PACKAGE_CACHE or set()

        # Verificar firmas ANTES de confiar en la BD local
        _PACKAGE_IDENTITY_TRUSTED = _verify_package_signatures()
        if not _PACKAGE_IDENTITY_TRUSTED:
            write_diagnostic("AUDIT action=pacman_cache_init result=signature_verification_failed")
            _PACKAGE_CACHE = set()
            _CACHE_INITIALIZED = True
            return _PACKAGE_CACHE

        # Cargar lista de paquetes
        try:
            result = subprocess.run(
                host_cmd(["pacman", "-Q"]),
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            names = set()
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                name = line.split(None, 1)[0]
                names.add(name)
            _PACKAGE_CACHE = names
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            write_diagnostic(f"AUDIT action=pacman_cache_init result=failed detail={e}")
            _PACKAGE_CACHE = set()

        _CACHE_INITIALIZED = True
        write_diagnostic(f"AUDIT action=pacman_cache_init result=success count={len(_PACKAGE_CACHE)}")
        return _PACKAGE_CACHE or set()


def get_cached_package_names() -> set[str]:
    """Devuelve la caché de nombres de paquetes (inicializa si es necesario)."""
    if not _CACHE_INITIALIZED:
        return _load_package_cache()
    return _PACKAGE_CACHE or set()


def invalidate_package_cache() -> None:
    """Invalida la caché para forzar recarga (útil tras instalar/desinstalar)."""
    global _PACKAGE_CACHE, _CACHE_INITIALIZED, _PACKAGE_IDENTITY_TRUSTED
    with _CACHE_LOCK:
        _PACKAGE_CACHE = None
        _CACHE_INITIALIZED = False
        _PACKAGE_IDENTITY_TRUSTED = True
        write_diagnostic("AUDIT action=pacman_cache_invalidate result=success")


def reset_package_cache_state() -> None:
    """Resetea el estado de la caché para tests (NO usar en producción).

    Fuerza la re-inicialización completa ignorando el estado previo.
    """
    global _PACKAGE_CACHE, _CACHE_INITIALIZED, _PACKAGE_IDENTITY_TRUSTED
    with _CACHE_LOCK:
        _PACKAGE_CACHE = None
        _CACHE_INITIALIZED = False
        _PACKAGE_IDENTITY_TRUSTED = True


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


def _get_installed_package_names() -> set[str]:
    """Devuelve un set con los nombres de todos los paquetes instalados.

    Usa la caché verificada en lugar de llamar a `pacman -Q` cada vez.
    """
    return get_cached_package_names()


def _validate_packages_exist(packages: list[str]) -> tuple[list[str], list[str]]:
    """Valida que los paquetes existen en la BD de pacman.

    Devuelve (válidos, inválidos). Los inválidos no se desinstalarán.
    """
    installed = _get_installed_package_names()
    if not _PACKAGE_IDENTITY_TRUSTED:
        raise PackageIdentityUntrustedError(
            "Identidad de paquetes no reconocida; la desinstalación se bloqueó."
        )

    valid = [p for p in packages if p in installed]
    invalid = [p for p in packages if p not in installed]
    return valid, invalid


def uninstall_packages(
    packages: list[str],
    noconfirm: bool = True,
) -> str:
    """Desinstala paquetes vía daemon D-Bus (con fallback a `pkexec pacman -Rns`).

    VALIDACIÓN DE SEGURIDAD (Fase 1 + Fase 2):
    - Verifica que cada paquete existe en la BD de pacman antes de desinstalar
    - Rechaza paquetes que no están instalados (previene typosquatting, etc.)
    - Auditoría completa de la operación
    - Invalida caché tras desinstalación exitosa
    - **Fase 2**: Usa daemon D-Bus privilegiado con fallback a pkexec

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

        # Invalidar caché tras desinstalación exitosa
        invalidate_package_cache()

        return result.output
    else:
        if result.error:
            write_diagnostic(f"AUDIT action=uninstall_packages packages={valid} result=failed error={result.error.code}")
            raise result.error
        else:
            raise DBusError("INTERNAL", "Error desconocido en desinstalación")