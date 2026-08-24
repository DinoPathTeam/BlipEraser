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
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
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

# ─── Auditoría ─────────────────────────────────────────────────────────

def _audit_log(action: str, detail: str = "") -> None:
    """Registra auditoría en journal (systemd)."""
    msg = f"AUDIT action={action}"
    if detail:
        msg += f" {detail}"
    print(msg, flush=True)


def _hash_path(path: str) -> str:
    """SHA-256 truncado para paths en logs."""
    import hashlib
    return hashlib.sha256(path.encode()).hexdigest()[:16]


# ─── Validaciones ──────────────────────────────────────────────────────

def _validate_path(path: str) -> bool:
    """Valida que una ruta está dentro de los prefijos permitidos."""
    path_str = str(path).replace("\\", "/")
    if not any(path_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES):
        return False
    try:
        resolved = Path(path).resolve(strict=False)
        resolved_str = str(resolved).replace("\\", "/")
        return any(resolved_str.startswith(prefix) for prefix in ALLOWED_SYSTEM_PREFIXES)
    except OSError:
        return False


def _reject_symlinks(path: Path) -> bool:
    """True si la ruta o cualquiera de sus padres es un symlink."""
    if path.is_symlink():
        return True
    for parent in path.parents:
        if parent.is_symlink():
            return True
    return False


def _validate_clean_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Valida paths para CleanSystemPaths. Devuelve (válidos, rechazados)."""
    valid = []
    rejected = []
    for p in paths:
        path = Path(p)
        if _reject_symlinks(path):
            rejected.append(p)
            _audit_log("clean_rejected", f"path={p}#h{_hash_path(p)} reason=symlink_detected")
            continue
        if not _validate_path(path):
            rejected.append(p)
            _audit_log("clean_rejected", f"path={p}#h{_hash_path(p)} reason=path_not_in_allowlist")
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
        pkg_files = list(cache_dir.glob("*.pkg.tar.zst"))
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
    global _PACKAGE_CACHE, _CACHE_INITIALIZED
    with _CACHE_LOCK:
        if _CACHE_INITIALIZED:
            return _PACKAGE_CACHE or set()
        if not _verify_package_signatures():
            _audit_log("pacman_cache_init", "result=signature_verification_failed")
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
    """Borra rutas de sistema vía rm -rf. Devuelve resumen."""
    valid, rejected = _validate_clean_paths(paths)
    if not valid:
        if not rejected:
            return "Ninguna ruta válida para limpiar"
        raise ValueError(f"Todas las rutas rechazadas por validación: {', '.join(rejected)}")
    _audit_log("clean_started", f"paths={valid}")
    cmd = ["rm", "-rf", "--", *valid]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    _audit_log("clean_success", f"paths={valid}")
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

    def on_method_call(self, connection, sender, object_path, interface_name,
                       method_name, parameters, invocation):
        """Manejador de llamadas D-Bus."""
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

    def run(self) -> int:
        """Ejecuta el bucle principal."""
        # Registrar el nombre en el bus de sistema
        self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        try:
            Gio.bus_own_name_sync(
                Gio.BusType.SYSTEM,
                "com.dinopath.BlipEraser.Privileged",
                Gio.BusNameOwnerFlags.NONE,
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

        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
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