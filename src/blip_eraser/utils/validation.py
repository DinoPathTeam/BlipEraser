"""Validación compartida de paths y seguridad — usada por daemon y cliente.

Este módulo centraliza la lógica de validación de paths, allowlist,
detección de symlinks y path traversal para evitar duplicación
entre el daemon privilegiado y el cliente (privileges.py).
"""

from __future__ import annotations

import os
from pathlib import Path

# ─── Constantes de seguridad ────────────────────────────────────────────

# Prefijos permitidos para operaciones de sistema (rm -rf, etc.)
ALLOWED_SYSTEM_PREFIXES: tuple[str, ...] = (
    "/var/cache/pacman/pkg",
    "/var/log",
    "/var/lib/pacman",
)

# Denylist dentro de $HOME (nunca se usa en daemon, pero por consistencia)
HOME_DENYLIST_PREFIXES: tuple[str, ...] = (
    ".ssh",
    ".gnupg",
    ".config",
    ".local/share/keyrings",
    ".local/share/gnupg",
    ".cache/gpg",
    ".cache/ssh",
    ".password-store",
    ".gnupg/secring.gpg",
    ".gnupg/pubring.gpg",
    ".gnupg/trustdb.gpg",
)


# ─── Validaciones de paths ──────────────────────────────────────────────

def validate_path_str(path: str) -> bool:
    """Valida que una ruta string está dentro de los prefijos permitidos (sin resolve)."""
    path_str = str(path).replace("\\", "/")
    return any(path_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)


def validate_path_resolved(path: Path) -> bool:
    """Valida path resuelto contra allowlist (usa resolve real)."""
    try:
        resolved = path.resolve(strict=False)
        resolved_str = str(resolved).replace("\\", "/")
        return any(resolved_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)
    except OSError:
        return False


def reject_symlinks_atomic(path: Path) -> bool:
    """Verifica symlinks sin seguir resolve - usa lstat en cada componente."""
    try:
        # Verificar el path mismo
        if path.is_symlink():
            return True
        # Verificar cada padre
        for parent in path.parents:
            if parent == Path("/"):
                break
            if parent.is_symlink():
                return True
    except OSError:
        return True  # Error al acceder = sospechoso
    return False


def is_symlink_or_reparse(path: Path) -> bool:
    """Detecta symlinks (POSIX/Windows) y reparse points (Windows)."""
    try:
        # POSIX y Windows 3.8+: Path.is_symlink() detecta symlinks propiamente dichos
        if path.is_symlink():
            return True
    except OSError:
        return True  # Error al acceder = sospechoso

    # Windows: detectar reparse points (junctions, mount points)
    # que NO son symlinks pero sí redirigen a otra ubicación
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            GetFileAttributesW = kernel32.GetFileAttributesW
            GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
            GetFileAttributesW.restype = wintypes.DWORD

            FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            attrs = GetFileAttributesW(str(path))
            if attrs != 0xFFFFFFFF and (attrs & 0x400):
                return True
        except Exception:
            # Si falla la API de Windows, asumir seguro (no bloquear por false positive)
            pass

    return False


def validate_path(path: Path) -> bool:
    """Valida que una ruta está dentro de los prefijos permitidos (con resolve en POSIX).
    
    Esta es la función principal usada por el cliente (privileges.py).
    """
    # Normalizar separadores para comparación consistente
    path_str = str(path).replace("\\", "/")

    # Verificación rápida del prefijo en el string original
    if not any(path_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES):
        return False

    # En POSIX (Linux), resolver y verificar de nuevo para detectar
    # path traversal via symlinks. En Windows, saltar resolve.
    if os.name == "posix":
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            return False
        resolved_str = str(resolved).replace("\\", "/")
        return any(resolved_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)

    return True


def reject_symlinks(path: Path) -> bool:
    """True si la ruta o cualquiera de sus padres es un symlink/reparse point.
    
    Esta es la función principal usada por el cliente (privileges.py).
    """
    # Comprobación rápida en la ruta dada
    if is_symlink_or_reparse(path):
        return True
    # Comprobar padres
    for parent in path.parents:
        if is_symlink_or_reparse(parent):
            return True
    return False