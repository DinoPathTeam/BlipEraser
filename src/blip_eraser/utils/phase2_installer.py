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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from blip_eraser.utils.log import write_diagnostic


# Rutas destino en el sistema
SYSTEMD_SERVICE_DEST = Path("/usr/lib/systemd/system/blip-eraser-privileged.service")
DBUS_CONF_DEST = Path("/usr/share/dbus-1/system.d/blip-eraser-privileged.conf")
DBUS_INTERFACE_DEST = Path("/usr/share/dbus-1/interfaces/com.dinopath.BlipEraser.Privileged.xml")
POLKIT_POLICY_DEST = Path("/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy")
APPARMOR_PROFILE_DEST = Path("/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged")
SCRIPT_DEST = Path("/usr/lib/blip-eraser/blip-eraser-privileged")
SCRIPT_DIR = Path("/usr/lib/blip-eraser")

# Rutas origen en el repo (relativas a la raíz del proyecto)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PACKAGING_DIR = REPO_ROOT / "packaging"

SYSTEMD_SERVICE_SRC = PACKAGING_DIR / "systemd" / "blip-eraser-privileged.service"
DBUS_CONF_SRC = PACKAGING_DIR / "dbus" / "blip-eraser-privileged.conf"
DBUS_INTERFACE_SRC = PACKAGING_DIR / "dbus" / "com.dinopath.BlipEraser.Privileged.xml"
POLKIT_POLICY_SRC = PACKAGING_DIR / "polkit" / "com.dinopath.blip-eraser.policy"
APPARMOR_PROFILE_SRC = PACKAGING_DIR / "apparmor" / "usr.lib.blip-eraser.blip-eraser-privileged"
SCRIPT_SRC = PACKAGING_DIR / "scripts" / "blip-eraser-privileged"


class InstallResult:
    """Resultado de una operación de instalación."""
    def __init__(self, success: bool, message: str = "", needs_restart: bool = False):
        self.success = success
        self.message = message
        self.needs_restart = needs_restart


def _run_pkexec(cmd: List[str], description: str) -> Tuple[bool, str]:
    """Ejecuta un comando con pkexec y retorna (success, message)."""
    cmd = ["pkexec"] + cmd
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, f"{description}: OK"
        else:
            return False, f"{description} falló: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout en {description}"
    except Exception as e:
        return False, f"Error en {description}: {e}"


def check_root() -> bool:
    """Verifica si estamos ejecutando como root."""
    return os.geteuid() == 0


def ensure_root_or_pkexec() -> bool:
    """Asegura que estamos en root o podemos usar pkexec."""
    if check_root():
        return True
    # Verificar si pkexec está disponible
    try:
        subprocess.run(["pkexec", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def install_file(src: Path, dest: Path, mode: int = 0o644) -> Tuple[bool, str]:
    """Instala un archivo con pkexec si es necesario."""
    try:
        # Crear directorio destino si no existe
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        if check_root():
            shutil.copy2(src, dest)
            os.chmod(dest, mode)
            return True, f"Instalado {dest.name}"
        else:
            # Usar pkexec para copiar y dar permisos
            cmd = ["pkexec", "cp", str(src), str(dest)]
            result = subprocess.run(["pkexec", "cp", str(src), str(dest)], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return False, f"Error copiando {src.name}: {result.stderr}"
            
            # Dar permisos
            subprocess.run(["pkexec", "chmod", str(mode), str(dest)], 
                          capture_output=True, timeout=10)
            return True, f"Instalado {dest.name} vía pkexec"
    except subprocess.TimeoutExpired:
        return False, f"Timeout instalando {dest.name}"
    except Exception as e:
        return False, f"Error instalando {dest.name}: {e}"


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
    missing = []
    
    # python-gobject (PyGObject)
    try:
        import gi
        gi.require_version("GLib", "2.0")
        gi.require_version("Gio", "2.0")
        from gi.repository import GLib, Gio
    except ImportError:
        missing.append("python-gobject")
    
    # gst-libav
    try:
        subprocess.run(["gst-inspect-1.0", "avdec_h264"], capture_output=True, timeout=5, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("gst-libav")
    
    # apparmor
    try:
        result = subprocess.run(["systemctl", "is-active", "apparmor"], capture_output=True, timeout=5)
        if result.returncode != 0 or result.stdout.strip() != "active":
            missing.append("apparmor (servicio inactivo)")
    except Exception:
        missing.append("apparmor")
    
    return missing


def check_daemon_installed() -> Tuple[bool, List[str]]:
    """Verifica si el daemon está completamente instalado."""
    missing = []
    
    checks = [
        (SYSTEMD_SERVICE_DEST, "Servicio systemd"),
        (DBUS_CONF_DEST, "Config D-Bus"),
        (DBUS_INTERFACE_DEST, "Interfaz D-Bus"),
        (POLKIT_POLICY_DEST, "Política Polkit"),
        (APPARMOR_PROFILE_DEST, "Perfil AppArmor"),
        (SCRIPT_DEST, "Script wrapper"),
    ]
    
    for path, name in checks:
        if not path.exists():
            missing.append(name)
    
    return len(missing) == 0, missing


def install_all_phase2() -> Tuple[bool, str, bool]:
    """
    Instala todo el stack Phase 2.
    
    Returns:
        (success, message, needs_restart)
    """
    if not ensure_root_or_pkexec():
        return False, "Se requieren privilegios de root (pkexec no disponible)", False
    
    results = []
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
    
    return True, "\n".join(results), True


# Funciones auxiliares que faltaban
def ensure_root_or_pkexec() -> bool:
    """Verifica si podemos ejecutar como root (directo o via pkexec)."""
    if os.geteuid() == 0:
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


def install_daemon_dependency(dep) -> Tuple[bool, str]:
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
    missing = []
    
    required = [
        ("/usr/lib/systemd/system/blip-eraser-privileged.service", "Servicio systemd"),
        ("/usr/share/dbus-1/system.d/blip-eraser-privileged.conf", "Config D-Bus"),
        ("/usr/share/dbus-1/interfaces/com.dinopath.BlipEraser.Privileged.xml", "Interfaz D-Bus"),
        ("/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy", "Política Polkit"),
        ("/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged", "Perfil AppArmor"),
        ("/usr/lib/blip-eraser/blip-eraser-privileged", "Script wrapper"),
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
    # Verificar si ya está instalado
    installed, missing = check_daemon_installed()
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