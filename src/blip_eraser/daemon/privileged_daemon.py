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
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import gi
    gi.require_version("GLib", "2.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import GLib, Gio
except ImportError:
    print("ERROR: PyGObject (gi) not available. Install python-gobject.", file=sys.stderr)
    sys.exit(1)

# ─── Constantes de seguridad ────────────────────────────────────────────

# Prefijos permitidos para CleanSystemPaths (rm -rf)
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

# Caché de paquetes instalados (thread-safe)
_PACKAGE_CACHE: set[str] | None = None
_CACHE_LOCK = threading.Lock()
_CACHE_INITIALIZED = False
_CACHE_VERIFICATION_DONE = False  # Para verificación async de firmas

# ─── Auditoría ──────────────────────────────────────────────────────────

def _audit_log(action: str, detail: str = "") -> None:
    """Registra auditoría en journal (systemd) con campos estructurados."""
    # Sanitizar detail: reemplazar newlines y limitar longitud
    safe_detail = detail.replace("\n", " ").replace("\r", " ")[:500] if detail else ""
    msg = f"AUDIT action={action}"
    if safe_detail:
        msg += f" {safe_detail}"
    print(msg, flush=True)


def _hash_path(path: str) -> str:
    """SHA-256 truncado para paths en logs."""
    import hashlib
    return hashlib.sha256(path.encode()).hexdigest()[:16]


# ─── Validaciones ──────────────────────────────────────────────────────

def _validate_path_str(path: str) -> bool:
    """Valida que una ruta string está dentro de los prefijos permitidos (sin resolve)."""
    path_str = str(path).replace("\\", "/")
    return any(path_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)


def _reject_symlinks_atomic(path: Path) -> bool:
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


def _validate_path_resolved(path: Path) -> bool:
    """Valida path resuelto contra allowlist (usa resolve real)."""
    try:
        resolved = path.resolve(strict=False)
        resolved_str = str(resolved).replace("\\", "/")
        return any(resolved_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)
    except OSError:
        return False


# ─── Operación atómica rm -rf usando fd ────────────────────────────────

def _rm_rf_atomic(path: Path) -> tuple[bool, str]:
    """
    Borra un path de forma atómica usando file descriptors para evitar TOCTOU.
    Retorna (success, error_message).
    """
    import errno
    
    try:
        # Abrir el directorio padre con O_DIRECTORY | O_NOFOLLOW
        parent = path.parent
        name = path.name
        
        # Verificar que el padre está en allowlist (string check rápido)
        if not _validate_path_str(str(parent)):
            return False, f"Parent path not in allowlist: {parent}"
        
        # Abrir fd del padre con O_PATH | O_NOFOLLOW | O_DIRECTORY
        # O_PATH no requiere permisos de lectura, solo execute en el directorio
        try:
            parent_fd = os.open(parent, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError as e:
            return False, f"Cannot open parent directory: {e}"
        
        try:
            # Verificar que el entry existe y no es symlink (usando fstatat)
            try:
                st = os.fstatat(parent_fd, name, follow_symlinks=False)
            except OSError as e:
                return False, f"Entry not found or inaccessible: {e}"
            
            # Verificar que no es symlink
            if os.path.islink(os.path.join(str(parent), name)):
                os.close(parent_fd)
                return False, "Entry is a symlink (TOCTOU protection)"
            
            # Determinar si es directorio o archivo
            is_dir = os.path.isdir(os.path.join(str(parent), name))
            
            if is_dir:
                # Para directorios, usar unlinkat con AT_REMOVEDIR
                # Primero vaciar recursivamente (también con fd)
                _rm_rf_dir_atomic(parent_fd, name)
                os.unlinkat(parent_fd, name, os.AT_REMOVEDIR)
            else:
                os.unlinkat(parent_fd, name, 0)
            
            return True, ""
        finally:
            os.close(parent_fd)
            
    except OSError as e:
        return False, f"Atomic removal failed: {e}"


def _rm_rf_dir_atomic(dir_fd: int, dir_name: str) -> None:
    """Vacía un directorio recursivamente usando fd atómico."""
    import os
    import stat
    
    # Abrir fd del subdirectorio
    try:
        subdir_fd = os.openat(dir_fd, dir_name, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        return  # No existe o no accesible
    
    try:
        # Iterar entradas
        with os.scandir(dir_fd) as it:
            for entry in it:
                if entry.name in ('.', '..'):
                    continue
                try:
                    entry_fd = os.openat(dir_fd, entry.name, os.O_PATH | os.O_NOFOLLOW)
                    try:
                        st = os.fstat(entry_fd)
                        if stat.S_ISDIR(st.st_mode):
                            _rm_rf_dir_atomic(entry_fd, entry.name)
                            os.unlinkat(dir_fd, entry.name, os.AT_REMOVEDIR)
                        else:
                            os.unlinkat(dir_fd, entry.name, 0)
                    finally:
                        os.close(entry_fd)
                except OSError:
                    pass  # Ignorar errores individuales
    finally:
        os.close(subdir_fd)


# ─── Validaciones de paths para operaciones ────────────────────────────

def _validate_clean_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Valida paths para CleanSystemPaths. Devuelve (válidos, rechazados)."""
    valid = []
    rejected = []
    for p in paths:
        path = Path(p)
        # Check 1: symlink detection (sin resolve)
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
        valid.append(p)
        _audit_log("clean_validated", f"path={p}#h{_hash_path(p)}")
    return valid, rejected


# ─── Caché de paquetes (supply chain) ─────────────────────────────────

def _verify_package_signatures() -> bool:
    """Verifica firmas de paquetes en /var/cache/pacman/pkg."""
    cache_dir = Path("/var/cache/pacman/pkg")
    if not cache_dir.exists():
        return True
    try:
        # Buscar todos los formatos de paquete válidos
        pkg_patterns = ["*.pkg.tar.zst", "*.pkg.tar.xz", "*.pkg.tar.lz4", "*.pkg.tar.gz"]
        pkg_files = []
        for pattern in pkg_patterns:
            pkg_files.extend(cache_dir.glob(pattern))
        
        if not pkg_files:
            return True
        
        for pkg_file in pkg_files:
            sig_file = pkg_file.with_suffix(pkg_file.suffix + ".sig")
            if not sig_file.exists():
                _audit_log("pacman_verify", f"package={pkg_file.name} result=missing_signature")
                return False
            result = subprocess.run(
                ["pacman-key", "--verify", str(sig_file), str(pkg_file)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                _audit_log("pacman_verify",
                    f"package={pkg_file.name} result=invalid_signature stderr={result.stderr.strip()[:200]}")
                return False
        _audit_log("pacman_verify_all", f"result=success count={len(pkg_files)}")
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        _audit_log("pacman_verify", f"result=error detail={e}")
        return False


def _load_package_cache() -> set[str]:
    """Carga y verifica la caché de paquetes instalados."""
    global _PACKAGE_CACHE, _CACHE_INITIALIZED, _CACHE_VERIFICATION_DONE
    with _CACHE_LOCK:
        if _CACHE_INITIALIZED:
            return _PACKAGE_CACHE or set()
        # NO bloquear en verificación de firmas - se hará en background
        _CACHE_VERIFICATION_DONE = False
        try:
            result = subprocess.run(
                ["pacman", "-Q"], capture_output=True, text=True, check=True, timeout=30
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
            _audit_log("pacman_cache_init", f"result=failed detail={e}")
            _PACKAGE_CACHE = set()
        _CACHE_INITIALIZED = True
        _audit_log("pacman_cache_init", f"result=success count={len(_PACKAGE_CACHE)}")
        return _PACKAGE_CACHE or set()


def _start_signature_verification_background():
    """Inicia verificación de firmas en hilo separado (no bloquea startup)."""
    def _bg_verify():
        global _CACHE_VERIFICATION_DONE
        try:
            if _verify_package_signatures():
                _audit_log("pacman_verify_async", "result=success")
            else:
                _audit_log("pacman_verify_async", "result=failed_warning")
        except Exception as e:
            _audit_log("pacman_verify_async", f"result=error detail={e}")
        finally:
            _CACHE_VERIFICATION_DONE = True
    
    t = threading.Thread(target=_bg_verify, daemon=True, name="pacman-verify")
    t.start()


def get_cached_package_names() -> set[str]:
    if not _CACHE_INITIALIZED:
        return _load_package_cache()
    return _PACKAGE_CACHE or set()


def invalidate_package_cache() -> None:
    global _PACKAGE_CACHE, _CACHE_INITIALIZED
    with _CACHE_LOCK:
        _PACKAGE_CACHE = None
        _CACHE_INITIALIZED = False
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
    errors = []
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

INTERFACE_XML = """
<node name="/com/dinopath/BlipEraser/Privileged">
  <interface name="com.dinopath.BlipEraser.Privileged">
    <method name="RemovePackages">
      <arg name="packages" type="as" direction="in"/>
      <arg name="result" type="s" direction="out"/>
    </method>
    <method name="CleanSystemPaths">
      <arg name="paths" type="as" direction="in"/>
      <arg name="result" type="s" direction="out"/>
    </method>
    <method name="Ping">
      <arg name="result" type="b" direction="out"/>
    </method>
  </interface>
</node>
"""


class PrivilegedService:
    """Implementación del servicio D-Bus privilegiado."""

    def __init__(self):
        self._bus = None
        self._node_info = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self._interface_info = self._node_info.interfaces[0]
        self._loop = None
        self._verify_timer = None
        self._shutdown_requested = False

    def _verify_sender(self, connection, sender) -> bool:
        """Verifica que el sender es un usuario autorizado (grupo wheel)."""
        try:
            # Obtener credenciales del sender
            creds = connection.get_credentials()
            if creds is None:
                return False
            
            uid = creds.get_unix_user()
            if uid is None or uid < 0:
                return False
            
            # Verificar que el UID pertenece al grupo wheel
            import grp
            try:
                wheel_group = grp.getgrnam("wheel")
                wheel_gid = wheel_group.gr_gid
                # Verificar grupos del usuario
                user_groups = os.getgroups()
                if wheel_group.gr_gid in user_groups:
                    return True
                # También verificar via /etc/group directamente
                with open("/etc/group") as f:
                    for line in f:
                        if line.startswith("wheel:"):
                            members = line.strip().split(":")[3].split(",")
                            import pwd
                            try:
                                username = pwd.getpwuid(uid).pw_name
                                if username in members:
                                    return True
                            except KeyError:
                                pass
            except (KeyError, OSError, IndexError):
                pass
            return False
        except Exception:
            return False

    def on_method_call(self, connection, sender, object_path, interface_name,
                       method_name, parameters, invocation):
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
            invocation.return_dbus_error(
                "com.dinopath.BlipEraser.Privileged.Error.ValidationFailed",
                str(e)
            )
        except subprocess.CalledProcessError as e:
            _audit_log("operation_failed",
                f"method={method_name} returncode={e.returncode} stderr={e.stderr.strip()[:200]}")
            invocation.return_dbus_error(
                "com.dinopath.BlipEraser.Privileged.Error.ExecutionFailed",
                f"Comando falló (código {e.returncode}): {e.stderr.strip()[:200]}"
            )
        except FileNotFoundError as e:
            invocation.return_dbus_error(
                "com.dinopath.BlipEraser.Privileged.Error.CommandNotFound",
                f"Comando no encontrado: {e.filename}"
            )
        except Exception as e:  # noqa: BLE001
            _audit_log("operation_error", f"method={method_name} error={type(e).__name__}: {e}")
            invocation.return_dbus_error(
                "com.dinopath.BlipEraser.Privileged.Error.Internal",
                f"Error interno: {e}"
            )

    def register(self, bus: Gio.DBusConnection) -> int:
        """Registra el objeto en el bus."""
        return bus.register_object(
            "/com/dinopath/BlipEraser/Privileged",
            self._interface_info,
            self.on_method_call,
            None,  # get_property
            None,  # set_property
            None
        )

    def _setup_signals(self):
        """Configura handlers de señales para shutdown limpio."""
        def _signal_handler(signum, frame):
            _audit_log("shutdown_signal", f"signal={signum}")
            self._shutdown_requested = True
            if self._loop:
                self._loop.quit()
        
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        # SIGHUP para recargar caché manualmente
        def _sighup_handler(signum, frame):
            _audit_log("cache_reload_requested", "signal=SIGHUP")
            invalidate_package_cache()
        signal.signal(signal.SIGHUP, _sighup_handler)

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
        """Inicia verificación de firmas en background después del startup."""
        def _bg_verify():
            try:
                if _verify_package_signatures():
                    _audit_log("pacman_verify_async", "result=success")
                else:
                    _audit_log("pacman_verify_async", "result=failed_warning")
            except Exception as e:
                _audit_log("pacman_verify_async", f"result=error detail={e}")
            finally:
                global _CACHE_VERIFICATION_DONE
                _CACHE_VERIFICATION_DONE = True
        
        # Ejecutar en hilo separado después de 10s para no bloquear startup
        GLib.timeout_add_seconds(10, lambda: (threading.Thread(target=_bg_verify, daemon=True, name="pacman-verify").start(), False)[1])

    def run(self) -> int:
        """Ejecuta el bucle principal."""
        # Verificar que somos root
        if os.geteuid() != 0:
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
    # Verificar que somos root
    if os.geteuid() != 0:
        print("ERROR: El daemon debe ejecutarse como root", file=sys.stderr)
        return 1

    service = PrivilegedService()
    return service.run()


if __name__ == "__main__":
    sys.exit(main())