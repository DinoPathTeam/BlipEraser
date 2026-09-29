"""Ejecución real de ajustes de rendimiento (Tweaks) — capa de sistema.

Cada tweak tiene: check_state(), apply(enable: bool), install_deps_if_needed().
Todas las operaciones privilegiadas usan la API unificada (daemon/pkexec).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from blip_eraser.utils.host_cmd import host_cmd
from blip_eraser.utils.log import write_diagnostic


@dataclass
class TweakResult:
    """Resultado de una operación de tweak."""
    success: bool
    message: str = ""
    needs_reboot: bool = False
    installed_deps: bool = False


# ─── Utilidades ────────────────────────────────────────────────────────────

def _run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta comando y retorna CompletedProcess (en el host si Flatpak)."""
    return subprocess.run(host_cmd(cmd), capture_output=True, text=True, check=check)


def _pkg_installed(pkg: str) -> bool:
    """True si el paquete está instalado (pacman -Q)."""
    try:
        _run_cmd(["pacman", "-Q", pkg], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _systemctl_is_enabled(unit: str) -> bool:
    """True si el unit systemd está enabled."""
    try:
        _run_cmd(["systemctl", "is-enabled", unit], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _systemctl_is_active(unit: str) -> bool:
    """True si el unit systemd está active."""
    try:
        _run_cmd(["systemctl", "is-active", unit], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _install_pkg_via_pkexec(pkg: str) -> bool:
    """Instala paquete via pkexec pacman. Retorna True si éxito."""
    try:
        _run_cmd(["pkexec", "pacman", "-S", "--needed", "--noconfirm", pkg], check=True)
        write_diagnostic(f"AUDIT action=install_pkg pkg={pkg} result=success")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
        write_diagnostic(f"AUDIT action=install_pkg pkg={pkg} result=failed error={e}")
        return False


def _write_root_file(path: Path, content: str) -> bool:
    """Escribe archivo root via pkexec tee."""
    try:
        # Usar tee con pkexec para escribir archivo root
        subprocess.run(
            ["pkexec", "tee", str(path)],
            input=content,
            capture_output=True,
            text=True,
            check=True
        )
        write_diagnostic(f"AUDIT action=write_root_file path={path} result=success")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
        write_diagnostic(f"AUDIT action=write_root_file path={path} result=failed error={e}")
        return False


def _remove_root_file(path: Path) -> bool:
    """Borra archivo root via pkexec rm."""
    try:
        _run_cmd(["pkexec", "rm", "-f", str(path)], check=True)
        write_diagnostic(f"AUDIT action=remove_root_file path={path} result=success")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
        write_diagnostic(f"AUDIT action=remove_root_file path={path} result=failed error={e}")
        return False


# ─── Tweak: TRIM periódico (fstrim.timer) ──────────────────────────────────

TRIM_UNIT = "fstrim.timer"

def tweak_trim_check_state() -> bool:
    """True si fstrim.timer está enabled."""
    return _systemctl_is_enabled(TRIM_UNIT)


def tweak_trim_apply(enable: bool) -> TweakResult:
    """Habilita/deshabilita fstrim.timer."""
    try:
        if enable:
            _run_cmd(["pkexec", "systemctl", "enable", "--now", TRIM_UNIT], check=True)
            write_diagnostic("AUDIT action=tweak_trim enable result=success")
            return TweakResult(success=True, message="TRIM periódico activado")
        else:
            _run_cmd(["pkexec", "systemctl", "disable", "--now", TRIM_UNIT], check=True)
            write_diagnostic("AUDIT action=tweak_trim disable result=success")
            return TweakResult(success=True, message="TRIM periódico desactivado")
    except subprocess.CalledProcessError as e:
        return TweakResult(success=False, message=f"Error systemctl: {e.stderr.strip()}")


# ─── Tweak: Compresión RAM (zram-generator) ────────────────────────────────

ZRAM_UNIT = "systemd-zram-setup@zram0.service"
ZRAM_CONFIG_PATH = Path("/etc/systemd/zram-generator.conf")
ZRAM_CONFIG_CONTENT = """[zram0]
zram-size = min(ram / 2, 4096)
compression-algorithm = zstd
swap-priority = 100
"""

def tweak_zram_check_state() -> bool:
    """True si zram0 está enabled y activo."""
    return _systemctl_is_enabled(ZRAM_UNIT) and _systemctl_is_active(ZRAM_UNIT)


def tweak_zram_apply(enable: bool) -> TweakResult:
    """Habilita/deshabilita zram-generator."""
    installed_deps = False
    
    if enable:
        # Instalar zram-generator si no está
        if not _pkg_installed("zram-generator"):
            if not _install_pkg_via_pkexec("zram-generator"):
                return TweakResult(success=False, message="No se pudo instalar zram-generator")
            installed_deps = True
        
        # Escribir config
        if not _write_root_file(ZRAM_CONFIG_PATH, ZRAM_CONFIG_CONTENT):
            return TweakResult(success=False, message="No se pudo escribir config zram-generator", installed_deps=installed_deps)
        
        # Recargar daemon y habilitar
        try:
            _run_cmd(["pkexec", "systemctl", "daemon-reload"], check=True)
            _run_cmd(["pkexec", "systemctl", "enable", "--now", ZRAM_UNIT], check=True)
            write_diagnostic("AUDIT action=tweak_zram enable result=success")
            return TweakResult(success=True, message="Compresión RAM (zram) activada", installed_deps=installed_deps)
        except subprocess.CalledProcessError as e:
            return TweakResult(success=False, message=f"Error activando zram: {e.stderr.strip()}", installed_deps=installed_deps)
    else:
        # Deshabilitar y limpiar
        try:
            _run_cmd(["pkexec", "systemctl", "disable", "--now", ZRAM_UNIT], check=True)
            _remove_root_file(ZRAM_CONFIG_PATH)
            _run_cmd(["pkexec", "systemctl", "daemon-reload"], check=True)
            write_diagnostic("AUDIT action=tweak_zram disable result=success")
            return TweakResult(success=True, message="Compresión RAM (zram) desactivada", installed_deps=installed_deps)
        except subprocess.CalledProcessError as e:
            return TweakResult(success=False, message=f"Error desactivando zram: {e.stderr.strip()}", installed_deps=installed_deps)


# ─── Tweak: Ordenar espejos (reflector) ────────────────────────────────────

REFLECTOR_UNIT = "reflector.timer"
REFLECTOR_CONFIG_DIR = Path("/etc/xdg/reflector")
REFLECTOR_CONFIG_PATH = REFLECTOR_CONFIG_DIR / "reflector.conf"
REFLECTOR_CONFIG_CONTENT = """--protocol https
--latest 20
--sort rate
--fastest 10
--save /etc/pacman.d/mirrorlist
"""

def tweak_reflector_check_state() -> bool:
    """True si reflector.timer está enabled y mirrorlist fue generado por reflector."""
    if not _systemctl_is_enabled(REFLECTOR_UNIT):
        return False
    try:
        mirrorlist = Path("/etc/pacman.d/mirrorlist").read_text()
        return "Generated by reflector" in mirrorlist
    except Exception:
        return False


def tweak_reflector_apply(enable: bool) -> TweakResult:
    """Habilita/deshabilita reflector.timer."""
    installed_deps = False
    
    if enable:
        # Instalar reflector si no está
        if not _pkg_installed("reflector"):
            if not _install_pkg_via_pkexec("reflector"):
                return TweakResult(success=False, message="No se pudo instalar reflector")
            installed_deps = True
        
        # Crear directorio config
        try:
            _run_cmd(["pkexec", "mkdir", "-p", str(REFLECTOR_CONFIG_DIR)], check=True)
        except subprocess.CalledProcessError:
            pass  # puede que ya exista
        
        # Escribir config
        if not _write_root_file(REFLECTOR_CONFIG_PATH, REFLECTOR_CONFIG_CONTENT):
            return TweakResult(success=False, message="No se pudo escribir config reflector", installed_deps=installed_deps)
        
        # Habilitar timer
        try:
            _run_cmd(["pkexec", "systemctl", "enable", "--now", REFLECTOR_UNIT], check=True)
            write_diagnostic("AUDIT action=tweak_reflector enable result=success")
            return TweakResult(success=True, message="Espejos optimizados (reflector) activado", installed_deps=installed_deps)
        except subprocess.CalledProcessError as e:
            return TweakResult(success=False, message=f"Error activando reflector: {e.stderr.strip()}", installed_deps=installed_deps)
    else:
        # Deshabilitar y limpiar
        try:
            _run_cmd(["pkexec", "systemctl", "disable", "--now", REFLECTOR_UNIT], check=True)
            _remove_root_file(REFLECTOR_CONFIG_PATH)
            # Intentar borrar directorio si quedó vacío
            try:
                _run_cmd(["pkexec", "rmdir", str(REFLECTOR_CONFIG_DIR)], check=False)
            except Exception:
                pass
            write_diagnostic("AUDIT action=tweak_reflector disable result=success")
            return TweakResult(success=True, message="Espejos optimizados (reflector) desactivado", installed_deps=installed_deps)
        except subprocess.CalledProcessError as e:
            return TweakResult(success=False, message=f"Error desactivando reflector: {e.stderr.strip()}", installed_deps=installed_deps)


# ─── Registro de tweaks ────────────────────────────────────────────────────

TWEAKS = {
    "perf_trim_mounts": {
        "check": tweak_trim_check_state,
        "apply": tweak_trim_apply,
        "deps": ["util-linux"],  # base, siempre presente
        "friendly_name": "TRIM periódico (SSD/NVMe)",
    },
    "perf_compress_ram": {
        "check": tweak_zram_check_state,
        "apply": tweak_zram_apply,
        "deps": ["zram-generator"],
        "friendly_name": "Compresión de RAM (zram)",
    },
    "perf_mirror_sort": {
        "check": tweak_reflector_check_state,
        "apply": tweak_reflector_apply,
        "deps": ["reflector"],
        "friendly_name": "Espejos más rápidos (reflector)",
    },
}


def get_tweak_info(key: str) -> dict | None:
    """Obtiene info de un tweak por key."""
    return TWEAKS.get(key)


def check_tweak_state(key: str) -> bool:
    """Verifica estado actual de un tweak en el sistema."""
    info = get_tweak_info(key)
    if not info:
        return False
    try:
        return info["check"]()
    except Exception:
        return False


def apply_tweak(key: str, enable: bool) -> TweakResult:
    """Aplica (habilita/deshabilita) un tweak."""
    info = get_tweak_info(key)
    if not info:
        return TweakResult(success=False, message=f"Tweak desconocido: {key}")
    return info["apply"](enable)


def get_all_tweak_states() -> dict[str, bool]:
    """Retorna dict {key: estado_actual} para todos los tweaks."""
    return {key: check_tweak_state(key) for key in TWEAKS}