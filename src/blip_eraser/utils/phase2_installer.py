"""Instalador automático de componentes Phase 2 (daemon privilegiado).

Este módulo se encarga de instalar automáticamente todos los archivos
necesarios para el daemon privilegiado (Fase 2) cuando el usuario lo autoriza.

Incluye:
- Políticas Polkit
- Configuración D-Bus
- Servicio systemd
- Perfil AppArmor
- Script wrapper del daemon
"""

from __future__ import annotations

import os
import importlib
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Tuple

from blip_eraser.utils.dependency_check import DaemonDependency
from blip_eraser.utils.host_cmd import is_flatpak

#: En Flatpak los archivos del sandbox son invisibles al host y los
#: destinos (/usr, /etc) no existen: el daemon SOLO se instala con
#: scripts/install-daemon.sh ejecutado fuera del sandbox.
FLATPAK_DAEMON_MSG = (
    "En Flatpak el daemon se instala en el host: ejecuta "
    "'./scripts/install-daemon.sh' fuera del sandbox y reinicia la app."
)


# Rutas destino en el sistema
SYSTEMD_SERVICE_DEST = Path("/usr/lib/systemd/system/blip-eraser-privileged.service")
DBUS_CONF_DEST = Path("/usr/share/dbus-1/system.d/blip-eraser-privileged.conf")
DBUS_INTERFACE_DEST = Path("/usr/share/dbus-1/interfaces/com.dinopath.BlipEraser.Privileged.xml")
POLKIT_POLICY_DEST = Path("/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy")
APPARMOR_PROFILE_DEST = Path("/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged")
SCRIPT_DEST = Path("/usr/lib/blip-eraser/blip-eraser-privileged")
SCRIPT_DIR = Path("/usr/lib/blip-eraser")
DAEMON_PACKAGE_DEST = SCRIPT_DIR / "blip_eraser"

# Rutas origen en el repo (relativas a la raíz del proyecto)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PACKAGING_DIR = REPO_ROOT / "packaging"

SYSTEMD_SERVICE_SRC = PACKAGING_DIR / "systemd" / "blip-eraser-privileged.service"
DBUS_CONF_SRC = PACKAGING_DIR / "dbus" / "blip-eraser-privileged.conf"
DBUS_INTERFACE_SRC = PACKAGING_DIR / "dbus" / "com.dinopath.BlipEraser.Privileged.xml"
POLKIT_POLICY_SRC = PACKAGING_DIR / "polkit" / "com.dinopath.blip-eraser.policy"
APPARMOR_PROFILE_SRC = PACKAGING_DIR / "apparmor" / "usr.lib.blip-eraser.blip-eraser-privileged"
SCRIPT_SRC = PACKAGING_DIR / "scripts" / "blip-eraser-privileged"
DAEMON_PACKAGE_SRC = Path(__file__).resolve().parent.parent


def check_root() -> bool:
    """Verifica si estamos ejecutando como root."""
    get_euid = getattr(os, "geteuid", None)
    return callable(get_euid) and get_euid() == 0


def install_systemd_service() -> Tuple[bool, str]:
    """Instala el servicio systemd."""
    # Crear directorio
    dest_dir = SYSTEMD_SERVICE_DEST.parent
    try:
        if check_root():
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SYSTEMD_SERVICE_SRC, SYSTEMD_SERVICE_DEST)
        else:
            subprocess.run(["pkexec", "mkdir", "-p", str(dest_dir)], check=True, timeout=10)
            subprocess.run(["pkexec", "cp", str(SYSTEMD_SERVICE_SRC), str(SYSTEMD_SERVICE_DEST)], check=True, timeout=10)
        
        # Recargar systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=10)
        return True, "Servicio systemd instalado"
    except Exception as e:
        return False, f"Error instalando servicio systemd: {e}"


def install_dbus_config() -> Tuple[bool, str]:
    """Instala configuración D-Bus."""
    try:
        # Config D-Bus
        if check_root():
            DBUS_CONF_DEST.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DBUS_CONF_SRC, DBUS_CONF_DEST)
            DBUS_INTERFACE_DEST.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DBUS_INTERFACE_SRC, DBUS_INTERFACE_DEST)
        else:
            subprocess.run(["pkexec", "mkdir", "-p", "/usr/share/dbus-1/system.d"], check=True, timeout=10)
            subprocess.run(["pkexec", "mkdir", "-p", "/usr/share/dbus-1/interfaces"], check=True, timeout=10)
            subprocess.run(["pkexec", "cp", str(DBUS_CONF_SRC), str(DBUS_CONF_DEST)], check=True, timeout=10)
            subprocess.run(["pkexec", "cp", str(DBUS_INTERFACE_SRC), str(DBUS_INTERFACE_DEST)], check=True, timeout=10)
        
        return True, "Configuración D-Bus instalada"
    except Exception as e:
        return False, f"Error instalando configuración D-Bus: {e}"


def install_polkit_policy() -> Tuple[bool, str]:
    """Instala política Polkit."""
    try:
        if check_root():
            POLKIT_POLICY_DEST.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(POLKIT_POLICY_SRC, POLKIT_POLICY_DEST)
        else:
            subprocess.run(["pkexec", "mkdir", "-p", "/usr/share/polkit-1/actions"], check=True, timeout=10)
            subprocess.run(["pkexec", "cp", str(POLKIT_POLICY_SRC), str(POLKIT_POLICY_DEST)], check=True, timeout=10)
        
        return True, "Política Polkit instalada"
    except Exception as e:
        return False, f"Error instalando política Polkit: {e}"


def install_apparmor_profile() -> Tuple[bool, str]:
    """Instala y carga perfil AppArmor."""
    try:
        # Copiar perfil
        if check_root():
            APPARMOR_PROFILE_DEST.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(APPARMOR_PROFILE_SRC, APPARMOR_PROFILE_DEST)
        else:
            subprocess.run(["pkexec", "mkdir", "-p", "/etc/apparmor.d"], check=True, timeout=10)
            subprocess.run(["pkexec", "cp", str(APPARMOR_PROFILE_SRC), str(APPARMOR_PROFILE_DEST)], check=True, timeout=10)
        
        # Cargar perfil
        if check_root():
            subprocess.run(["apparmor_parser", "-r", "/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged"], check=True, timeout=10)
        else:
            subprocess.run(["pkexec", "apparmor_parser", "-r", "/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged"], check=True, timeout=10)
        
        return True, "Perfil AppArmor instalado y cargado"
    except Exception as e:
        return False, f"Error instalando perfil AppArmor: {e}"


def install_script() -> Tuple[bool, str]:
    """Instala script wrapper del daemon."""
    try:
        if check_root():
            SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPT_SRC, SCRIPT_DEST)
            os.chmod(SCRIPT_DEST, 0o755)
        else:
            subprocess.run(["pkexec", "mkdir", "-p", "/usr/lib/blip-eraser"], check=True, timeout=10)
            subprocess.run(["pkexec", "cp", str(SCRIPT_SRC), str(SCRIPT_DEST)], check=True, timeout=10)
            subprocess.run(["pkexec", "chmod", "+x", str(SCRIPT_DEST)], check=True, timeout=10)
        
        return True, "Script wrapper instalado"
    except Exception as e:
        return False, f"Error instalando script wrapper: {e}"


def install_daemon_package() -> Tuple[bool, str]:
    """Instala el paquete Python del daemon en una ruta del sistema."""
    try:
        if not DAEMON_PACKAGE_SRC.is_dir():
            return False, f"No se encontró el paquete fuente: {DAEMON_PACKAGE_SRC}"

        if check_root():
            SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                DAEMON_PACKAGE_SRC,
                DAEMON_PACKAGE_DEST,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            subprocess.run(
                ["pkexec", "mkdir", "-p", str(SCRIPT_DIR)],
                check=True,
                timeout=10,
            )
            subprocess.run(
                ["pkexec", "cp", "-R", str(DAEMON_PACKAGE_SRC), str(SCRIPT_DIR)],
                check=True,
                timeout=30,
            )

        return True, "Paquete Python del daemon instalado"
    except Exception as e:
        return False, f"Error instalando paquete Python del daemon: {e}"


def _service_is_current() -> bool:
    """Comprueba que la unidad usa el runtime autónomo del daemon."""
    try:
        content = SYSTEMD_SERVICE_DEST.read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        "ExecStart=/usr/bin/python3 /usr/lib/blip-eraser/"
        "blip-eraser-privileged" in content
        and "Environment=PYTHONPATH=/usr/lib/blip-eraser" in content
    )


def _daemon_package_is_current() -> bool:
    """Comprueba que el código instalado del daemon no quedó obsoleto."""
    source = DAEMON_PACKAGE_SRC / "daemon" / "privileged_daemon.py"
    installed = DAEMON_PACKAGE_DEST / "daemon" / "privileged_daemon.py"
    if not source.is_file():
        return True
    try:
        return installed.is_file() and source.read_bytes() == installed.read_bytes()
    except OSError:
        return False


def reload_daemons() -> Tuple[bool, str]:
    """Recarga daemon systemd y AppArmor."""
    try:
        if check_root():
            subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=10)
        else:
            subprocess.run(["pkexec", "systemctl", "daemon-reload"], check=True, timeout=10)
        return True, "Daemons recargados"
    except Exception as e:
        return False, f"Error recargando daemons: {e}"


def enable_and_start_service() -> Tuple[bool, str]:
    """Habilita e inicia el servicio systemd."""
    try:
        if check_root():
            subprocess.run(["systemctl", "enable", "--now", "blip-eraser-privileged.service"], check=True, timeout=30)
        else:
            subprocess.run(["pkexec", "systemctl", "enable", "--now", "blip-eraser-privileged.service"], check=True, timeout=30)
        return True, "Servicio habilitado e iniciado"
    except subprocess.CalledProcessError as e:
        return False, f"Error habilitando servicio: {e.stderr}"
    except Exception as e:
        return False, f"Error habilitando servicio: {e}"


def check_dependencies_installed() -> List[str]:
    """Verifica qué dependencias del sistema faltan."""
    missing: list[str] = []
    
    # python-gobject (PyGObject)
    try:
        gi: Any = importlib.import_module("gi")
        gi.require_version("GLib", "2.0")
        gi.require_version("Gio", "2.0")
        importlib.import_module("gi.repository.GLib")
        importlib.import_module("gi.repository.Gio")
    except ImportError:
        missing.append("python-gobject")
    
    # gst-libav
    try:
        subprocess.run(["gst-inspect-1.0", "avdec_h264"], capture_output=True, timeout=5, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("gst-libav")
    
    # apparmor
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "apparmor"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            missing.append("apparmor (servicio inactivo)")
    except Exception:
        missing.append("apparmor")
    
    return missing


def check_daemon_installed() -> Tuple[bool, List[str]]:
    """Verifica si el daemon está completamente instalado."""
    missing: list[str] = []
    
    checks = [
        (SYSTEMD_SERVICE_DEST, "Servicio systemd"),
        (DBUS_CONF_DEST, "Config D-Bus"),
        (DBUS_INTERFACE_DEST, "Interfaz D-Bus"),
        (POLKIT_POLICY_DEST, "Política Polkit"),
        (APPARMOR_PROFILE_DEST, "Perfil AppArmor"),
        (SCRIPT_DEST, "Script wrapper"),
        (DAEMON_PACKAGE_DEST / "__init__.py", "Paquete Python del daemon"),
    ]
    
    for path, name in checks:
        if not path.exists():
            missing.append(name)

    if not _service_is_current():
        missing.append("Servicio systemd desactualizado")
    if not _daemon_package_is_current():
        missing.append("Paquete Python del daemon desactualizado")
    
    return len(missing) == 0, missing


def install_all_phase2() -> Tuple[bool, str, bool]:
    """
    Instala todo el stack Phase 2.
    
    Returns:
        (success, message, needs_restart)
    """
    if is_flatpak():
        return False, FLATPAK_DAEMON_MSG, False
    if not ensure_root_or_pkexec():
        return False, "Se requieren privilegios de root (pkexec no disponible)", False
    
    results: list[str] = []
    needs_restart = False
    
    # 1. Instalar servicio systemd
    success, msg = install_systemd_service()
    results.append(f"Systemd: {msg}")
    if not success:
        return False, f"Error instalando systemd: {msg}", False
    
    # 2. Config D-Bus
    success, msg = install_dbus_config()
    results.append(f"D-Bus: {msg}")
    if not success:
        return False, f"Error instalando D-Bus: {msg}", False
    
    # 3. Polkit policy
    success, msg = install_polkit_policy()
    results.append(f"Polkit: {msg}")
    if not success:
        return False, f"Error instalando Polkit: {msg}", False
    
    # 4. AppArmor
    success, msg = install_apparmor_profile()
    results.append(f"AppArmor: {msg}")
    if not success:
        return False, f"Error instalando AppArmor: {msg}", True  # necesita reinicio
    if "instalado" in msg.lower() and "cargado" in msg.lower():
        needs_restart = True
    
    # 5. Script wrapper
    success, msg = install_script()
    results.append(f"Script: {msg}")
    if not success:
        return False, f"Error instalando script: {msg}", False

    # 5a. Código Python importable fuera del entorno virtual del usuario
    success, msg = install_daemon_package()
    results.append(f"Paquete Python: {msg}")
    if not success:
        return False, f"Error instalando paquete Python: {msg}", False
    
    # 5b. Polkit policy
    success, msg = install_polkit_policy()
    results.append(f"Polkit: {msg}")
    if not success:
        return False, f"Error instalando Polkit: {msg}", False
    
    # 6. Recargar daemons
    success, msg = reload_daemons()
    results.append(f"Daemons: {msg}")
    if not success:
        return False, f"Error recargando daemons: {msg}", False
    
    # 7. Habilitar e iniciar servicio
    success, msg = enable_and_start_service()
    results.append(f"Servicio: {msg}")
    if not success:
        return False, f"Error habilitando servicio: {msg}", False
    
    return True, "\n".join(results), needs_restart


# Funciones auxiliares que faltaban
def ensure_root_or_pkexec() -> bool:
    """Verifica si podemos ejecutar como root (directo o via pkexec)."""
    if check_root():
        return True
    try:
        subprocess.run(["pkexec", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def run_with_pkexec(cmd: List[str]) -> Tuple[bool, str]:
    """Ejecuta comando con pkexec."""
    try:
        result = subprocess.run(["pkexec"] + cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, "OK"
        else:
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def install_daemon_dependency(dep: DaemonDependency) -> Tuple[bool, str]:
    """Instala una dependencia del daemon usando pkexec.
    
    Args:
        dep: DaemonDependency object with install_cmd attribute
        
    Returns:
        Tuple of (success, message)
    """
    if not dep.install_cmd:
        return False, f"No install command for {dep.name}"
    
    # Use pkexec to install the dependency
    success, msg = run_with_pkexec(dep.install_cmd.split())
    if success:
        return True, f"{dep.name} installed successfully"
    else:
        return False, f"Failed to install {dep.name}: {msg}"


def check_phase2_installed() -> Tuple[bool, List[str]]:
    """Verifica si Phase 2 está completamente instalado."""
    missing: list[str] = []
    
    required = [
        ("/usr/lib/systemd/system/blip-eraser-privileged.service", "Servicio systemd"),
        ("/usr/share/dbus-1/system.d/blip-eraser-privileged.conf", "Config D-Bus"),
        ("/usr/share/dbus-1/interfaces/com.dinopath.BlipEraser.Privileged.xml", "Interfaz D-Bus"),
        ("/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy", "Política Polkit"),
        ("/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged", "Perfil AppArmor"),
        ("/usr/lib/blip-eraser/blip-eraser-privileged", "Script wrapper"),
        ("/usr/lib/blip-eraser/blip_eraser/__init__.py", "Paquete Python del daemon"),
    ]
    
    for path, name in required:
        if not Path(path).exists():
            missing.append(name)
    
    return len(missing) == 0, missing


def install_phase2_if_needed() -> Tuple[bool, str]:
    """
    Función principal para instalar Phase 2 si es necesario.
    Se llama al inicio de la aplicación.
    
    Returns:
        (success, message)
    """
    if is_flatpak():
        return False, FLATPAK_DAEMON_MSG
    # Verificar si ya está instalado
    installed, _missing = check_daemon_installed()
    if installed:
        return True, "Phase 2 ya instalado"
    
    # Verificar si podemos usar pkexec
    if not shutil.which("pkexec"):
        return False, "pkexec no disponible. Instale 'polkit' para continuar."
    
    # Intentar instalar
    print("Instalando componentes Phase 2...")
    success, msg, needs_restart = install_all_phase2()
    
    if success:
        msg = "Phase 2 instalado correctamente."
        if needs_restart:
            msg += "\n⚠ Se recomienda reiniciar el sistema para AppArmor."
        return True, msg
    else:
        return False, f"Error instalando Phase 2: {msg}"


if __name__ == "__main__":
    # Para testing manual
    success, msg = install_phase2_if_needed()
    print(f"Resultado: {success} - {msg}")