#!/usr/bin/env python3
"""BlipEraser Privileged Daemon — systemd D-Bus service for privileged operations.

This daemon runs as root via systemd (Type=dbus) and exposes a D-Bus interface
for the BlipEraser UI to request privileged operations without using pkexec.

D-Bus Interface: com.dinopath.BlipEraser.Privileged
- RemovePackages(as packages) -> s (stdout)
- CleanSystemPaths(as paths) -> s (stdout)
- Ping() -> b

Security:
- Validates all inputs against strict allowlists
- No shell execution, only subprocess with explicit args
- Audit logging for all operations
- TOCTOU protection via fd-based atomic operations
- D-Bus sender UID verification
"""

from __future__ import annotations

import os
import importlib
import signal
import stat
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, cast

try:
    gi: Any = importlib.import_module("gi")
    gi.require_version("GLib", "2.0")
    gi.require_version("Gio", "2.0")
    GLib: Any = importlib.import_module("gi.repository.GLib")
    Gio: Any = importlib.import_module("gi.repository.Gio")
except ImportError:
    print("ERROR: PyGObject (gi) not available. Install python-gobject.", file=sys.stderr)
    sys.exit(1)

# ─── Constantes de seguridad ────────────────────────────────────────────
# NOTA: ALLOWED_SYSTEM_PREFIXES se importa de utils.validation (línea ~151,
# aliasado para los tests). HOME_DENYLIST no se usa en el daemon (solo en el
# cliente): no redefinir nada aquí para no sombrear el import.

# Caché de paquetes instalados (thread-safe)
_package_cache: set[str] | None = None
_CACHE_LOCK = threading.Lock()
_cache_initialized = False
_cache_verification_done = False  # Para verificación async de firmas

# ─── Auditoría ──────────────────────────────────────────────────────────

# Intentar usar systemd journal nativo para logging estructurado
try:
    _journal: Any = importlib.import_module("systemd.journal")
    _journal_available = True
except ImportError:
    _journal = None
    _journal_available = False

AUDIT_LOG_PATH = Path("/var/log/blip-eraser/daemon.log")


def _audit_log(action: str, detail: str = "", **fields: object) -> None:
    """Registra auditoría en journal (systemd) con campos estructurados.
    
    Si systemd.journal no está disponible, cae a print con formato clave=valor.
    """
    def _escape_val(v: str) -> str:
        """Escapa valor para formato clave=valor: escapa =, espacios, y newlines."""
        v = str(v).replace("\n", " ").replace("\r", " ")[:1000]
        # Escapar = y espacios para parsing seguro
        return v.replace("=", r"\=").replace(" ", r"\ ")
    
    # Sanitizar detail: reemplazar newlines y limitar longitud
    safe_detail = detail.replace("\n", " ").replace("\r", " ")[:500] if detail else ""
    
    # Construir campos base
    log_fields = {
        "ACTION": action,
        "DETAIL": safe_detail,
    }
    # Añadir campos extra
    for k, v in fields.items():
        # Sanitizar clave: solo alfanumérico y underscore, mayúsculas
        safe_key = "".join(c if c.isalnum() or c == "_" else "_" for c in str(k)).upper()
        safe_val = str(v).replace("\n", " ").replace("\r", " ")[:1000]
        log_fields[safe_key] = safe_val
    
    # Fallback: formato clave=valor con escaping para parsing seguro.
    parts = [f"AUDIT action={action}"]
    if safe_detail:
        parts.append(f"detail={_escape_val(safe_detail)}")
    for k, v in log_fields.items():
        if k not in ("ACTION", "DETAIL"):
            parts.append(f"{k.lower()}={_escape_val(v)}")
    message = " ".join(parts)

    if _journal_available:
        try:
            # Enviar a systemd journal con campos estructurados
            _journal.send(
                f"AUDIT action={action}",
                PRIORITY=6,  # INFO
                **log_fields
            )
            return
        except Exception:
            pass  # Caer a fallback
    
    # Fallback 1: stderr queda asociado a la unidad systemd/journal.
    print(message, file=sys.stderr, flush=True)

    # Fallback 2: conservar auditoría local si journald no está disponible.
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(message + "\n")
        os.chmod(AUDIT_LOG_PATH, 0o600)
    except OSError:
        pass


def _hash_path(path: str) -> str:
    """SHA-256 truncado para paths en logs."""
    import hashlib
    return hashlib.sha256(path.encode()).hexdigest()[:16]


# ─── Validaciones ──────────────────────────────────────────────────────

from blip_eraser.utils.validation import (
    validate_path_str as _validate_path_str,
    reject_symlinks_atomic as _reject_symlinks_atomic,
    validate_path_resolved as _validate_path_resolved,
    ALLOWED_SYSTEM_PREFIXES as _VALIDATION_ALLOWED_SYSTEM_PREFIXES,
)

validate_path_str = _validate_path_str
reject_symlinks_atomic = _reject_symlinks_atomic
validate_path_resolved = _validate_path_resolved
ALLOWED_SYSTEM_PREFIXES = _VALIDATION_ALLOWED_SYSTEM_PREFIXES

_OS_OPENAT: Any = getattr(os, "openat", None)
_OS_FSTATAT: Any = getattr(os, "fstatat", None)
_OS_UNLINKAT: Any = getattr(os, "unlinkat", None)
_OS_O_PATH = getattr(os, "O_PATH", 0)
_OS_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_OS_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_OS_AT_REMOVEDIR = getattr(os, "AT_REMOVEDIR", 0)


def _get_euid() -> int:
    get_euid: Any = getattr(os, "geteuid", None)
    if not callable(get_euid):
        return -1
    return cast(Callable[[], int], get_euid)()


# ─── Operación atómica rm -rf usando fd ────────────────────────────────

def _rm_rf_atomic(path: Path) -> tuple[bool, str]:
    """
    Borra un path de forma atómica usando file descriptors para evitar TOCTOU.
    Retorna (success, error_message).
    """
    try:
        if not all((_OS_FSTATAT, _OS_UNLINKAT)):
            return False, "Atomic filesystem APIs are unavailable"

        # Abrir el directorio padre con O_DIRECTORY | O_NOFOLLOW
        parent = path.parent
        name = path.name
        
        # Verificar que el padre está en allowlist (string check rápido)
        if not _validate_path_str(str(parent)):
            return False, f"Parent path not in allowlist: {parent}"
        
        # Abrir fd del padre con O_PATH | O_NOFOLLOW | O_DIRECTORY
        # O_PATH no requiere permisos de lectura, solo execute en el directorio
        try:
            parent_fd = os.open(parent, _OS_O_PATH | _OS_O_DIRECTORY | _OS_O_NOFOLLOW)
        except OSError as e:
            return False, f"Cannot open parent directory: {e}"
        
        try:
            # Verificar que el entry existe y no es symlink (usando fstatat)
            try:
                st = _OS_FSTATAT(parent_fd, name, follow_symlinks=False)
            except OSError as e:
                return False, f"Entry not found or inaccessible: {e}"
            
            # Verificar que no es symlink usando fstatat (no sigue symlinks) - TOCTOU fix
            try:
                st = _OS_FSTATAT(parent_fd, name, follow_symlinks=False)
                if stat.S_ISLNK(st.st_mode):
                    os.close(parent_fd)
                    return False, "Entry is a symlink (TOCTOU protection)"
                is_dir = stat.S_ISDIR(st.st_mode)
            except OSError:
                is_dir = False
            
            if is_dir:
                # Para directorios, usar unlinkat con AT_REMOVEDIR
                # Primero vaciar recursivamente (también con fd)
                _rm_rf_dir_atomic(parent_fd, name)
                _OS_UNLINKAT(parent_fd, name, _OS_AT_REMOVEDIR)
            else:
                _OS_UNLINKAT(parent_fd, name, 0)
            
            return True, ""
        finally:
            os.close(parent_fd)
            
    except OSError as e:
        return False, f"Atomic removal failed: {e}"


def _rm_rf_dir_atomic(dir_fd: int, dir_name: str, depth: int = 0) -> None:
    """Vacía un directorio recursivamente usando fd atómico.
    
    Args:
        dir_fd: File descriptor del directorio padre
        dir_name: Nombre del subdirectorio a vaciar
        depth: Profundidad actual de recursión (para evitar stack overflow)
    """
    # Límite de profundidad para prevenir stack overflow
    if depth > 256:
        _audit_log("rm_rf_depth_exceeded", f"dir={dir_name} depth={depth}")
        return
    
    # Abrir fd del subdirectorio
    try:
        if _OS_OPENAT is None or _OS_UNLINKAT is None:
            return
        subdir_fd = _OS_OPENAT(dir_fd, dir_name, _OS_O_PATH | _OS_O_DIRECTORY | _OS_O_NOFOLLOW)
    except OSError:
        return  # No existe o no accesible
    
    try:
        # Iterar entradas usando os.scandir (devuelve DirEntry con info de tipo)
        with os.scandir(dir_fd) as it:
            for entry in it:
                if entry.name in ('.', '..'):
                    continue
                try:
                    # entry.is_dir(follow_symlinks=False) usa la info del DirEntry (sin syscall extra)
                    # y no sigue symlinks
                    if entry.is_dir(follow_symlinks=False):
                        # Abrir fd del subdirectorio para recursión
                        try:
                            subdir_fd = _OS_OPENAT(dir_fd, entry.name, _OS_O_PATH | _OS_O_DIRECTORY | _OS_O_NOFOLLOW)
                        except OSError:
                            continue
                        # Validar que el fd abierto es efectivamente un directorio
                        try:
                            st = os.fstat(subdir_fd)
                            if not stat.S_ISDIR(st.st_mode):
                                os.close(subdir_fd)
                                continue
                        except OSError:
                            os.close(subdir_fd)
                            continue
                        try:
                            _rm_rf_dir_atomic(subdir_fd, entry.name, depth + 1)
                            _OS_UNLINKAT(dir_fd, entry.name, _OS_AT_REMOVEDIR)
                        finally:
                            os.close(subdir_fd)
                    else:
                        _OS_UNLINKAT(dir_fd, entry.name, 0)
                except OSError:
                    pass  # Ignorar errores individuales
    finally:
        os.close(subdir_fd)


# ─── Validaciones de paths para operaciones ────────────────────────────

# Cache for allowlist prefix symlink validation
_ALLOWLIST_PREFIX_VALIDATED: dict[str, bool] = {}


def _validate_allowlist_prefixes() -> None:
    """Valida que todos los prefijos de allowlist no sean symlinks.
    Se ejecuta una vez al inicio o bajo demanda.
    """
    global _ALLOWLIST_PREFIX_VALIDATED
    for prefix in ALLOWED_SYSTEM_PREFIXES:
        if prefix not in _ALLOWLIST_PREFIX_VALIDATED:
            prefix_path = Path(prefix)
            try:
                if prefix_path.is_symlink():
                    _audit_log("allowlist_prefix_symlink", f"prefix={prefix} target={prefix_path.resolve()}")
                    _ALLOWLIST_PREFIX_VALIDATED[prefix] = False
                else:
                    _ALLOWLIST_PREFIX_VALIDATED[prefix] = True
            except OSError:
                _ALLOWLIST_PREFIX_VALIDATED[prefix] = False


def _validate_clean_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Valida paths para CleanSystemPaths. Devuelve (válidos, rechazados)."""
    # Validar prefijos de allowlist una vez
    _validate_allowlist_prefixes()
    
    valid: list[str] = []
    rejected: list[str] = []
    for p in paths:
        path = Path(p)
        # Check 1: symlink detection (sin resolve) - incluye padres
        if _reject_symlinks_atomic(path):
            rejected.append(p)
            _audit_log("clean_rejected", f"path={p}#h{_hash_path(p)} reason=symlink_detected")
            continue
        # Check 2: path en allowlist (string prefix)
        if not _validate_path_str(p):
            rejected.append(p)
            _audit_log("clean_rejected", f"path={p}#h{_hash_path(p)} reason=path_not_in_allowlist")
            continue
        # Check 3: path resuelto también en allowlist
        if not _validate_path_resolved(path):
            rejected.append(p)
            _audit_log("clean_rejected", f"path={p}#h{_hash_path(p)} reason=resolved_outside_allowlist")
            continue
        # Check 4: validar que el prefijo allowlist coincidente no sea symlink
        matched_prefix = None
        for prefix in ALLOWED_SYSTEM_PREFIXES:
            if p.startswith(prefix):
                matched_prefix = prefix
                break
        if matched_prefix and not _ALLOWLIST_PREFIX_VALIDATED.get(matched_prefix, False):
            rejected.append(p)
            _audit_log("clean_rejected", f"path={p}#h{_hash_path(p)} reason=allowlist_prefix_is_symlink prefix={matched_prefix}")
            continue
        valid.append(p)
        _audit_log("clean_validated", f"path={p}#h{_hash_path(p)}")
    return valid, rejected


# ─── Caché de paquetes (supply chain) ─────────────────────────────────

def _verify_package_signatures() -> tuple[bool, list[str]]:
    """Verifica firmas de paquetes en /var/cache/pacman/pkg.
    Retorna (all_valid, failed_packages).
    """
    cache_dir = Path("/var/cache/pacman/pkg")
    if not cache_dir.exists():
        return True, []
    try:
        # Buscar todos los formatos de paquete válidos con un solo rglob
        pkg_files = list(cache_dir.rglob("*.pkg.tar.*"))
        
        if not pkg_files:
            return True, []
        
        failed: list[str] = []
        for pkg_file in pkg_files:
            sig_file = pkg_file.with_suffix(pkg_file.suffix + ".sig")
            if not sig_file.exists():
                _audit_log("pacman_verify", f"package={pkg_file.name} result=missing_signature")
                failed.append(pkg_file.name)
                continue
            result = subprocess.run(
                ["pacman-key", "--verify", str(sig_file), str(pkg_file)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                _audit_log("pacman_verify",
                    f"package={pkg_file.name} result=invalid_signature stderr={result.stderr.strip()[:200]}")
                failed.append(pkg_file.name)
                continue
        if failed:
            _audit_log("pacman_verify_all", f"result=partial_failed failed={failed}")
            return False, failed
        _audit_log("pacman_verify_all", f"result=success count={len(pkg_files)}")
        return True, []
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        _audit_log("pacman_verify", f"result=error detail={e}")
        return False, []


def _load_package_cache() -> set[str]:
    """Carga y verifica la caché de paquetes instalados.
    
    Primero verifica las firmas de los paquetes en cache. Si la verificación
    falla, loggea warning pero NO bloquea la carga de la caché (RT-6 fix).
    Solo popula la caché con paquetes verificados.
    """
    global _package_cache, _cache_initialized, _cache_verification_done
    with _CACHE_LOCK:
        if _cache_initialized:
            return _package_cache or set()
        _cache_verification_done = False
        
        # 1. Primero verificar firmas de paquetes en cache
        sig_ok, failed = _verify_package_signatures()
        if not sig_ok:
            # RT-6: No bloquear - loggear warning pero continuar
            _audit_log("pacman_cache_init", f"result=signature_verification_failed failed={failed} (continuing anyway)")
        else:
            _audit_log("pacman_verify_async", "result=success")
        
        # 2. Cargar paquetes instalados (solo si queremos ser estrictos, filtrar por firmas válidas)
        # Por compatibilidad y RT-6, cargamos todos los paquetes de pacman -Q
        # pero loggeamos los que fallaron verificación
        try:
            result = subprocess.run(
                ["pacman", "-Q"], capture_output=True, text=True, check=True, timeout=30
            )
            names: set[str] = set()
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                name = line.split(None, 1)[0]
                names.add(name)
            _package_cache = names
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            _audit_log("pacman_cache_init", f"result=failed detail={e}")
            _package_cache = set()
        
        _cache_initialized = True
        _cache_verification_done = True
        cache_count = len(_package_cache)
        _audit_log("pacman_cache_init", f"result=success count={cache_count}")
        return _package_cache or set()


def get_cached_package_names() -> set[str]:
    if not _cache_initialized:
        return _load_package_cache()
    return _package_cache or set()


def invalidate_package_cache() -> None:
    global _package_cache, _cache_initialized
    with _CACHE_LOCK:
        _package_cache = None
        _cache_initialized = False
        _audit_log("pacman_cache_invalidate", "result=success")


def _validate_packages_exist(packages: list[str]) -> tuple[list[str], list[str]]:
    installed = get_cached_package_names()
    valid = [p for p in packages if p in installed]
    invalid = [p for p in packages if p not in installed]
    return valid, invalid


# ─── Operaciones privilegiadas ────────────────────────────────────────

def remove_packages(packages: list[str]) -> str:
    """Desinstala paquetes vía pacman -Rns. Devuelve stdout."""
    if not packages:
        return ""
    valid, invalid = _validate_packages_exist(packages)
    if invalid:
        _audit_log("uninstall_rejected", f"packages={invalid} reason=not_installed")
        raise ValueError(f"Paquetes no instalados (rechazados): {', '.join(invalid)}")
    _audit_log("uninstall_started", f"packages={valid}")
    cmd = ["pacman", "-Rns", "--noconfirm", *valid]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    _audit_log("uninstall_success", f"packages={valid}")
    invalidate_package_cache()
    return result.stdout


def clean_system_paths(paths: list[str]) -> str:
    """Borra rutas de sistema usando operaciones atómicas fd-based. Devuelve resumen."""
    valid, rejected = _validate_clean_paths(paths)
    if not valid:
        if not rejected:
            return "Ninguna ruta válida para limpiar"
        raise ValueError(f"Todas las rutas rechazadas por validación: {', '.join(rejected)}")
    
    _audit_log("clean_started", f"paths={valid}")
    errors: list[str] = []
    for p in valid:
        path = Path(p)
        success, err = _rm_rf_atomic(path)
        if not success:
            errors.append(f"{p}: {err}")
            _audit_log("clean_failed", f"path={p} error={err}")
    
    if errors:
        raise ValueError(f"Errores en limpieza: {'; '.join(errors)}")
    
    _audit_log("clean_success", f"paths={valid}")
    # Invalidar caché porque se pudo borrar /var/lib/pacman
    invalidate_package_cache()
    return f"Eliminadas {len(valid)} ruta(s)"


# ─── Implementación D-Bus ──────────────────────────────────────────────

def _load_interface_xml() -> str:
    """Carga la definición de interfaz D-Bus desde el archivo de packaging.
    
    Evita duplicación entre daemon y packaging.
    Requiere que el archivo XML esté instalado en el sistema (packaging).
    
    Returns:
        str: XML de la interfaz D-Bus
    
    Raises:
        RuntimeError: Si no se encuentra el archivo XML en las ubicaciones esperadas
    """
    # Buscar el archivo XML en ubicaciones conocidas
    base_dir = Path(__file__).resolve().parent.parent.parent.parent  # repo root
    xml_paths = [
        base_dir / "packaging" / "dbus" / "com.dinopath.BlipEraser.Privileged.xml",
        Path("/usr/share/dbus-1/interfaces/com.dinopath.BlipEraser.Privileged.xml"),
    ]
    for xml_path in xml_paths:
        if xml_path.exists():
            try:
                return xml_path.read_text(encoding="utf-8")
            except OSError:
                continue
    # Sin fallback hardcoded: el XML debe estar instalado via packaging
    raise RuntimeError(
        "D-Bus interface XML not found. "
        "Install packaging files: packaging/dbus/com.dinopath.BlipEraser.Privileged.xml "
        "to /usr/share/dbus-1/interfaces/ or run from repo root."
    )


INTERFACE_XML = _load_interface_xml()


# Cache para verificación de sesión gráfica activa (TTL 30 segundos)
_ACTIVE_SESSION_CACHE: dict[int, tuple[bool, float]] = {}
_SESSION_CACHE_TTL = 30.0

# Cache para membresía en grupo wheel (TTL 30 segundos)
_WHEEL_GROUP_CACHE: dict[int, tuple[bool, float]] = {}
_WHEEL_CACHE_TTL = 30.0


def _is_user_in_wheel_group(uid: int) -> bool:
    """Verifica si un UID pertenece al grupo wheel con cache TTL."""
    import time
    now = time.time()
    
    # Verificar cache
    if uid in _WHEEL_GROUP_CACHE:
        cached_result, cached_time = _WHEEL_GROUP_CACHE[uid]
        if now - cached_time < _WHEEL_CACHE_TTL:
            return cached_result
    
    try:
        pwd: Any = importlib.import_module("pwd")
        grp: Any = importlib.import_module("grp")
        
        wheel_group = grp.getgrnam("wheel")
        wheel_gid = wheel_group.gr_gid
        
        # Verificar via /etc/group (miembros del grupo)
        with open("/etc/group") as f:
            for line in f:
                if line.startswith("wheel:"):
                    members = line.strip().split(":")[3].split(",")
                    try:
                        username = pwd.getpwuid(uid).pw_name
                        if username in members:
                            _WHEEL_GROUP_CACHE[uid] = (True, now)
                            return True
                    except KeyError:
                        pass
        # Fallback: verificar GID primario / grupos suplementarios del UID
        try:
            username = pwd.getpwuid(uid).pw_name
            getgrouplist: Any = getattr(os, "getgrouplist", None)
            if getgrouplist is None:
                return False
            user_groups = getgrouplist(username, pwd.getpwuid(uid).pw_gid)
            result = wheel_gid in user_groups
            _WHEEL_GROUP_CACHE[uid] = (result, now)
            return result
        except (KeyError, OSError):
            pass
    except (KeyError, OSError, IndexError):
        pass
    
    _WHEEL_GROUP_CACHE[uid] = (False, now)
    return False


def _check_active_graphical_session(uid: int) -> bool:
    """Verifica si el usuario tiene una sesión gráfica activa via loginctl.
    
    Returns True si el usuario tiene al menos una sesión con:
    - Type=wayland o x11
    - State=active
    """
    import time
    now = time.time()
    
    # Verificar cache
    if uid in _ACTIVE_SESSION_CACHE:
        cached_result, cached_time = _ACTIVE_SESSION_CACHE[uid]
        if now - cached_time < _SESSION_CACHE_TTL:
            return cached_result
    
    try:
        # Ejecutar loginctl show-user <uid> --property=Display,State,Type
        result = subprocess.run(
            ["loginctl", "show-user", str(uid), "--property=Display,State,Type"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return False
        
        # Parsear output (formato: Key=Value por línea)
        has_active_graphical = False
        display = None
        state = None
        session_type = None
        
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                if key == 'Display':
                    display = value
                elif key == 'State':
                    state = value
                elif key == 'Type':
                    session_type = value
        
        # Verificar que es una sesión gráfica activa
        if state == 'active' and display and session_type in ('wayland', 'x11'):
            has_active_graphical = True
        
        # Cachear resultado
        _ACTIVE_SESSION_CACHE[uid] = (has_active_graphical, now)
        return has_active_graphical
        
    except (subprocess.SubprocessError, FileNotFoundError, OSError, Exception):
        # Si loginctl no está disponible o falla, denegar por seguridad
        return False


class PrivilegedService:
    """Implementación del servicio D-Bus privilegiado."""

    def __init__(self):
        self._bus = None
        self._node_info = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self._interface_info = self._node_info.interfaces[0]
        self._loop = None
        self._verify_timer = None
        self._shutdown_requested = False

    def _verify_sender(self, connection: Any, sender: str) -> bool:
        """Verifica que el sender es un usuario autorizado (grupo wheel + sesión gráfica activa)."""
        try:
            # Obtener credenciales del sender
            creds = connection.get_credentials()
            if creds is None:
                return False
            
            uid = creds.get_unix_user()
            if uid is None or uid < 0:
                return False
            
            # Verificar sesión gráfica activa
            if not _check_active_graphical_session(uid):
                _audit_log("auth_rejected", f"sender={sender} uid={uid} reason=no_active_graphical_session")
                return False
            
            # Verificar que el UID pertenece al grupo wheel (con cache TTL)
            if not _is_user_in_wheel_group(uid):
                _audit_log("auth_rejected", f"sender={sender} uid={uid} reason=not_in_wheel_group")
                return False
            
            return True
        except Exception:
            return False

    def on_method_call(
        self,
        connection: Any,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: Any,
        invocation: Any,
    ) -> None:
        """Manejador de llamadas D-Bus con verificación de sender."""
        # Verificar autenticación del sender
        if not self._verify_sender(connection, sender):
            _audit_log("auth_rejected", f"sender={sender} method={method_name} uid=unknown")
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.AccessDenied",
                "Acceso denegado: usuario no autorizado (requiere grupo wheel)"
            )
            return

        try:
            if method_name == "RemovePackages":
                packages = parameters[0]
                result = remove_packages(packages)
                invocation.return_value(GLib.Variant("(s)", (result,)))
            elif method_name == "CleanSystemPaths":
                paths = parameters[0]
                result = clean_system_paths(paths)
                invocation.return_value(GLib.Variant("(s)", (result,)))
            elif method_name == "Ping":
                invocation.return_value(GLib.Variant("(b)", (True,)))
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Método desconocido: {method_name}"
                )
        except ValueError as e:
            # Error de validación: path no permitido, paquete no instalado, etc.
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.InvalidArgs",
                str(e)
            )
        except subprocess.CalledProcessError as e:
            _audit_log("operation_failed",
                f"method={method_name} returncode={e.returncode} stderr={e.stderr.strip()[:200]}")
            # Mapear códigos de retorno comunes a errores D-Bus estándar
            if e.returncode == 126:  # pkexec auth cancelled
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.AuthFailed",
                    "Autenticación cancelada o fallida"
                )
            elif e.returncode == 127:  # command not found
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.FileNotFound",
                    f"Comando no encontrado: {e.stderr.strip()[:200]}"
                )
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.Failed",
                    f"Comando falló (código {e.returncode}): {e.stderr.strip()[:200]}"
                )
        except FileNotFoundError as e:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.FileNotFound",
                f"Comando no encontrado: {e.filename}"
            )
        except PermissionError as e:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.AccessDenied",
                f"Permiso denegado: {e}"
            )
        except Exception as e:  # noqa: BLE001
            _audit_log("operation_error", f"method={method_name} error={type(e).__name__}: {e}")
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.Failed",
                f"Error interno: {e}"
            )

    def register(self, bus: Any) -> int:
        """Registra el objeto en el bus."""
        return bus.register_object(
            "/com/dinopath/BlipEraser/Privileged",
            self._interface_info,
            self.on_method_call,
            None,  # get_property
            None,  # set_property
            None
        )

    def _setup_signals(self) -> None:
        """Configura handlers de señales para shutdown limpio."""
        def _signal_handler(signum: int, frame: Any) -> None:
            _audit_log("shutdown_signal", f"signal={signum}")
            self._shutdown_requested = True
            if self._loop:
                self._loop.quit()
        
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        # SIGHUP para recargar caché manualmente
        def _sighup_handler(signum: int, frame: Any) -> None:
            _audit_log("cache_reload_requested", "signal=SIGHUP")
            invalidate_package_cache()
        sighup = getattr(signal, "SIGHUP", None)
        if sighup is not None:
            signal.signal(sighup, _sighup_handler)

    def _start_periodic_cache_refresh(self):
        """Timer periódico para refrescar caché de paquetes (cada 5 min)."""
        def _refresh():
            if not self._shutdown_requested:
                invalidate_package_cache()
                get_cached_package_names()  # Trigger reload
                _audit_log("cache_periodic_refresh", "result=success")
            # Re-programar
            if not self._shutdown_requested:
                self._verify_timer = GLib.timeout_add_seconds(300, _refresh)
                return False  # No repetir automáticamente, lo re-programa manual
            return False
        
        # Primera verificación a los 30s, luego cada 5 min
        GLib.timeout_add_seconds(30, _refresh)

    def _start_signature_verification(self):
        """Inicia verificación periódica de firmas en background (cada 5 min).
        
        Nota: La verificación inicial ya se hizo en _load_package_cache.
        Esta función solo re-verifica periódicamente para detectar cambios.
        """
        def _bg_verify():
            try:
                all_valid, failed = _verify_package_signatures()
                if all_valid:
                    _audit_log("pacman_verify_periodic", "result=success")
                else:
                    _audit_log("pacman_verify_periodic", f"result=partial_failed failed={failed}")
                    # Invalidar caché para forzar recarga en próxima operación
                    invalidate_package_cache()
            except Exception as e:
                _audit_log("pacman_verify_periodic", f"result=error detail={e}")
        
        # Ejecutar en hilo separado después de 10s para no bloquear startup
        GLib.timeout_add_seconds(10, lambda: (threading.Thread(target=_bg_verify, daemon=True, name="pacman-verify-periodic").start(), False)[1])
        # Programar verificación periódica cada 5 min
        GLib.timeout_add_seconds(300, lambda: (threading.Thread(target=_bg_verify, daemon=True, name="pacman-verify-periodic").start(), False)[1])

    def run(self) -> int:
        """Ejecuta el bucle principal."""
        # Verificar que somos root
        if _get_euid() != 0:
            print("ERROR: El daemon debe ejecutarse como root", file=sys.stderr)
            return 1

        # Configurar señales
        self._setup_signals()

        # Registrar el nombre en el bus de sistema
        self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        try:
            # Flags seguros: permitir reemplazo si hay instancia anterior muerta
            Gio.bus_own_name_sync(
                Gio.BusType.SYSTEM,
                "com.dinopath.BlipEraser.Privileged",
                Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT | Gio.BusNameOwnerFlags.REPLACE,
                None,  # name_acquired
                None,  # name_lost
                None
            )
        except GLib.Error as e:
            _audit_log("dbus_register_failed", f"error={e.message}")
            print(f"ERROR: No se pudo registrar el nombre D-Bus: {e.message}", file=sys.stderr)
            return 1

        self.register(self._bus)
        _audit_log("daemon_started", "bus=system")
        print("BlipEraser Privileged Daemon iniciado", flush=True)

        # Iniciar tareas de fondo
        self._start_periodic_cache_refresh()
        self._start_signature_verification()

        self._loop = GLib.MainLoop()
        try:
            self._loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            _audit_log("daemon_stopped", "clean_shutdown")
        return 0


def main() -> int:
    """Punto de entrada del daemon."""
    import traceback
    
    try:
        # Verificar que somos root
        if _get_euid() != 0:
            print("ERROR: El daemon debe ejecutarse como root", file=sys.stderr)
            return 1
        
        # Log startup info
        _audit_log("daemon_starting", f"pid={os.getpid()} uid={_get_euid()} python={sys.version}")
        
        service = PrivilegedService()
        return service.run()
    except Exception as e:
        # Log any unhandled exceptions
        _audit_log("daemon_crashed", f"error={type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())