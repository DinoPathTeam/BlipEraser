"""Validación compartida de paths y seguridad — usada por daemon y cliente.

Este módulo centraliza la lógica de validación de paths, allowlist,
detección de symlinks y path traversal para evitar duplicación
entre el daemon privilegiado y el cliente (privileges.py).
"""

from __future__ import annotations

import os
import posixpath
from pathlib import Path

# ─── Constantes de seguridad ────────────────────────────────────────────

# Prefijos permitidos para operaciones de sistema (rm -rf, etc.).
# S2: /var/lib/pacman FUERA (la base de datos de pacman: ningún código la
# limpia y borrarla deja el sistema sin mantenimiento posible).
ALLOWED_SYSTEM_PREFIXES: tuple[str, ...] = (
    "/var/cache/pacman/pkg",
    "/var/log",
)

# S4: rastro de auditoría e identidad bajo /var/log: nunca se borra ni se
# cuenta como "recuperable" (borrar el rastro es parte del abuso). Se compara
# la primera componente bajo /var/log y sus rotaciones (`wtmp.1`, `btmp-2026`).
PROTECTED_LOG_NAMES: tuple[str, ...] = (
    "journal", "blip-eraser",            # journal y bitácora propia
    "audit",                              # auditd
    "wtmp", "btmp", "lastlog", "faillog",  # inicios de sesión
    "auth.log", "secure",                 # autenticación (otras distros)
    "pacman.log",                         # historial de instalaciones
)

# Compatibilidad: prefijos exactos (la comprobación real es is_audit_protected).
AUDIT_EXCLUDE_PREFIXES: tuple[str, ...] = tuple(
    f"/var/log/{name}" for name in PROTECTED_LOG_NAMES
)


def is_audit_protected(path: str | Path, log_root: str = "/var/log") -> bool:
    """True si `path` es (o cuelga de) un registro de auditoría protegido.

    Normaliza `..` antes de comparar. `log_root` permite reutilizarla con
    otra raíz (tests, listados).
    """
    norm = posixpath.normpath(str(path).replace("\\", "/"))
    root = posixpath.normpath(log_root)
    if not norm.startswith(root + "/"):
        return False
    first = norm[len(root) + 1:].split("/", 1)[0]
    return any(
        first == name or first.startswith((name + ".", name + "-"))
        for name in PROTECTED_LOG_NAMES
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
    """Valida que una ruta string está dentro de los prefijos permitidos.

    Normaliza `..` léxicamente ANTES del prefijo: sin esto
    `/var/log/../../etc` pasaba el check por empezar con `/var/log/`
    (hallazgo Strix). Sin resolve: puro string, sin tocar el FS.
    """
    path_str = posixpath.normpath(str(path).replace("\\", "/"))
    return any(
        path_str == prefix or path_str.startswith(f"{prefix}/")
        for prefix in ALLOWED_SYSTEM_PREFIXES
    )


def validate_path_resolved(path: Path) -> bool:
    """Valida path resuelto contra allowlist (usa resolve real)."""
    try:
        resolved = path.resolve(strict=False)
        resolved_str = str(resolved).replace("\\", "/")
        return any(
            resolved_str == prefix or resolved_str.startswith(f"{prefix}/")
            for prefix in ALLOWED_SYSTEM_PREFIXES
        )
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
            if attrs != 0xFFFFFFFF and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                return True
        except Exception:
            # Si falla la API de Windows, asumir seguro (no bloquear por false positive)
            pass

    return False


def validate_path(path: Path) -> bool:
    """Valida que una ruta está dentro de los prefijos permitidos (con resolve en POSIX).
    
    Esta es la función principal usada por el cliente (privileges.py).
    Acepta str o Path (coerción a la entrada: fail-closed igual).
    """
    path = Path(path)    # Normalizar separadores para comparación consistente
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
        return any(
            resolved_str == prefix or resolved_str.startswith(f"{prefix}/")
            for prefix in ALLOWED_SYSTEM_PREFIXES
        )

    return any(
        path_str == prefix or path_str.startswith(f"{prefix}/")
        for prefix in ALLOWED_SYSTEM_PREFIXES
    )


def reject_symlinks(path: Path) -> bool:
    """True si la ruta o cualquiera de sus padres es un symlink/reparse point.
    
    Esta es la función principal usada por el cliente (privileges.py).
    Acepta str o Path.
    """
    path = Path(path)    # Comprobación rápida en la ruta dada
    if is_symlink_or_reparse(path):
        return True
    # Comprobar padres
    for parent in path.parents:
        if is_symlink_or_reparse(parent):
            return True
    return False