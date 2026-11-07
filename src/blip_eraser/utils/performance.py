"""Ejecución real de ajustes de rendimiento (Tweaks) — capa de sistema.

Cada tweak tiene: check_state(), apply(enable: bool), install_deps_if_needed().
Todas las operaciones privilegiadas usan la API unificada (daemon/pkexec).
"""

from __future__ import annotations

import shlex
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


@dataclass(frozen=True)
class TweakBlock:
    """Motivo por el que un tweak no debe aplicarse en este sistema."""
    code: str
    message: str
    # True: solo impide ACTIVAR; el usuario aún puede desactivar lo que activó.
    enable_only: bool = False


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


def _q(value: object) -> str:
    """Cita un valor para el shell (los paths y contenidos van siempre citados)."""
    return shlex.quote(str(value))


def _sh_install_pkg(pkg: str) -> str:
    return f"pacman -S --needed --noconfirm {_q(pkg)}"


def _sh_write_file(path: Path, content: str) -> str:
    """Escribe un archivo root; copia `.blip-bak` previa si existe (D4).

    La copia solo se hace la primera vez (la primera escritura manda).
    """
    p, bak = _q(path), _q(f"{path}.blip-bak")
    return (
        f"if [ -f {p} ] && [ ! -e {bak} ]; then cp -p {p} {bak}; fi\n"
        f"printf %s {_q(content)} > {p}"
    )


def _sh_remove_file(path: Path) -> str:
    """Quita un archivo root; restaura `.blip-bak` si existe (D4)."""
    p, bak = _q(path), _q(f"{path}.blip-bak")
    return f"if [ -f {bak} ]; then mv -f {bak} {p}; else rm -f {p}; fi"


def _run_privileged(steps: list[str]) -> subprocess.CompletedProcess:
    """Ejecuta todos los pasos con UN solo `pkexec sh -c` (una autorización).

    `set -e`: el primer paso que falle aborta el resto. Todo valor interpolado
    en los pasos debe pasar por `_q`.
    """
    script = "set -e\n" + "\n".join(steps)
    return _run_cmd(["pkexec", "sh", "-c", script], check=True)


def _failure_text(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        return (exc.stderr or "").strip() or f"código {exc.returncode}"
    return str(exc)


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

def _zram_device_present() -> bool:
    """True si el kernel tiene algún dispositivo zram (/sys/block/zram*)."""
    return any(Path("/sys/block").glob("zram*"))


def _blip_zram_config_exists() -> bool:
    """True si el zram actual lo configuró BlipEraser (su archivo existe)."""
    return ZRAM_CONFIG_PATH.exists()


def _zram_block() -> TweakBlock | None:
    if _zram_device_present() and not _blip_zram_config_exists():
        return TweakBlock(
            "system_zram",
            "Tu sistema ya gestiona su propio zram (por ejemplo CachyOS). "
            "BlipEraser no lo sobrescribe para no reducir su tamaño.",
        )
    return None


def tweak_zram_check_state() -> bool:
    """True solo si el zram activo es el configurado por BlipEraser."""
    return (
        _blip_zram_config_exists()
        and _systemctl_is_enabled(ZRAM_UNIT)
        and _systemctl_is_active(ZRAM_UNIT)
    )


def tweak_zram_apply(enable: bool) -> TweakResult:
    """Habilita/deshabilita zram-generator (una sola autorización)."""
    needs_pkg = enable and not _pkg_installed("zram-generator")
    if enable:
        steps = [_sh_install_pkg("zram-generator")] if needs_pkg else []
        steps += [
            _sh_write_file(ZRAM_CONFIG_PATH, ZRAM_CONFIG_CONTENT),
            "systemctl daemon-reload",
            f"systemctl enable --now {_q(ZRAM_UNIT)}",
        ]
    else:
        steps = [
            f"systemctl disable --now {_q(ZRAM_UNIT)}",
            _sh_remove_file(ZRAM_CONFIG_PATH),
            "systemctl daemon-reload",
        ]
    try:
        _run_privileged(steps)
    except (subprocess.CalledProcessError, OSError) as e:
        write_diagnostic(f"AUDIT action=tweak_zram enable={enable} result=failed error={_failure_text(e)}")
        verb = "activando" if enable else "desactivando"
        return TweakResult(
            success=False,
            message=f"Error {verb} zram: {_failure_text(e)}",
            installed_deps=needs_pkg and _pkg_installed("zram-generator"),
        )
    write_diagnostic(f"AUDIT action=tweak_zram {'enable' if enable else 'disable'} result=success")
    return TweakResult(
        success=True,
        message="Compresión RAM (zram) activada" if enable else "Compresión RAM (zram) desactivada",
        installed_deps=needs_pkg,
    )


# ─── Tweak: zswap (caché de compresión del kernel) ────────────────────────

ZSWAP_PARAM_DIR = Path("/sys/module/zswap/parameters")
ZSWAP_CONFIG_PATH = Path("/etc/tmpfiles.d/blip-eraser-zswap.conf")
ZSWAP_CONFIG_CONTENT = """# BlipEraser: activa zswap en cada arranque (sin tocar el bootloader)
w /sys/module/zswap/parameters/enabled - - - - 1
"""
_PROC_SWAPS = Path("/proc/swaps")


def _zswap_supported() -> bool:
    return ZSWAP_PARAM_DIR.is_dir()


def _zswap_enabled() -> bool:
    try:
        return (ZSWAP_PARAM_DIR / "enabled").read_text().strip() in ("Y", "1")
    except OSError:
        return False


def _blip_zswap_config_exists() -> bool:
    return ZSWAP_CONFIG_PATH.exists()


def _swap_devices() -> list[str]:
    """Dispositivos/archivos de swap activos (/proc/swaps)."""
    try:
        lines = _PROC_SWAPS.read_text().splitlines()[1:]
    except OSError:
        return []
    return [ln.split()[0] for ln in lines if ln.strip()]


def _zswap_block() -> TweakBlock | None:
    if not _zswap_supported():
        return TweakBlock("zswap_unsupported", "Tu kernel no incluye zswap.")
    if _zswap_enabled() and not _blip_zswap_config_exists():
        return TweakBlock(
            "system_zswap",
            "zswap ya está activado por tu sistema (parámetro del kernel). "
            "BlipEraser no lo gestiona.",
        )
    devices = _swap_devices()
    if any(d.startswith("/dev/zram") for d in devices):
        return TweakBlock(
            "zram_swap",
            "Tu swap es zram: zswap sería redundante (comprimiría dos veces).",
            enable_only=True,
        )
    if not devices:
        return TweakBlock(
            "no_swap",
            "zswap necesita una partición o archivo de swap en disco.",
            enable_only=True,
        )
    return None


def tweak_zswap_check_state() -> bool:
    """True solo si zswap está activo y lo configuró BlipEraser."""
    return _blip_zswap_config_exists() and _zswap_enabled()


def tweak_zswap_apply(enable: bool) -> TweakResult:
    """Activa/desactiva zswap de forma persistente (tmpfiles.d) y al instante."""
    if enable:
        # Si tmpfiles falla, el propio script deshace la config (sin 2.º pkexec).
        steps = [
            _sh_write_file(ZSWAP_CONFIG_PATH, ZSWAP_CONFIG_CONTENT),
            f"systemd-tmpfiles --create {_q(ZSWAP_CONFIG_PATH)} || "
            f"{{ {_sh_remove_file(ZSWAP_CONFIG_PATH)}; exit 1; }}",
        ]
    else:
        steps = [
            _sh_remove_file(ZSWAP_CONFIG_PATH),
            "echo 0 > /sys/module/zswap/parameters/enabled",
        ]
    try:
        _run_privileged(steps)
    except (subprocess.CalledProcessError, OSError) as e:
        write_diagnostic(f"AUDIT action=tweak_zswap enable={enable} result=failed error={_failure_text(e)}")
        verb = "activando" if enable else "desactivando"
        return TweakResult(success=False, message=f"Error {verb} zswap: {_failure_text(e)}")
    write_diagnostic(f"AUDIT action=tweak_zswap {'enable' if enable else 'disable'} result=success")
    return TweakResult(success=True, message="zswap activado" if enable else "zswap desactivado")


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

_MIRROR_TOOL_MARKERS = ("rate-mirrors", "started at:")


def _read_mirrorlist() -> str:
    try:
        return Path("/etc/pacman.d/mirrorlist").read_text()
    except OSError:
        return ""


def _mirrors_block() -> TweakBlock | None:
    head = "\n".join(_read_mirrorlist().splitlines()[:15]).lower()
    if any(marker in head for marker in _MIRROR_TOOL_MARKERS):
        return TweakBlock(
            "system_mirrors",
            "Tu lista de espejos la gestiona otra herramienta (por ejemplo "
            "cachyos-rate-mirrors). BlipEraser no la sobrescribe.",
        )
    return None


def tweak_reflector_check_state() -> bool:
    """True si reflector.timer está enabled."""
    return _systemctl_is_enabled(REFLECTOR_UNIT)


def tweak_reflector_apply(enable: bool) -> TweakResult:
    """Habilita/deshabilita reflector.timer (una sola autorización)."""
    needs_pkg = enable and not _pkg_installed("reflector")
    if enable:
        steps = [_sh_install_pkg("reflector")] if needs_pkg else []
        steps += [
            f"mkdir -p {_q(REFLECTOR_CONFIG_DIR)}",
            _sh_write_file(REFLECTOR_CONFIG_PATH, REFLECTOR_CONFIG_CONTENT),
            f"systemctl enable --now {_q(REFLECTOR_UNIT)}",
        ]
    else:
        steps = [
            f"systemctl disable --now {_q(REFLECTOR_UNIT)}",
            _sh_remove_file(REFLECTOR_CONFIG_PATH),
            # Borra el directorio solo si quedó vacío.
            f"rmdir {_q(REFLECTOR_CONFIG_DIR)} 2>/dev/null || true",
        ]
    try:
        _run_privileged(steps)
    except (subprocess.CalledProcessError, OSError) as e:
        write_diagnostic(f"AUDIT action=tweak_reflector enable={enable} result=failed error={_failure_text(e)}")
        verb = "activando" if enable else "desactivando"
        return TweakResult(
            success=False,
            message=f"Error {verb} reflector: {_failure_text(e)}",
            installed_deps=needs_pkg and _pkg_installed("reflector"),
        )
    write_diagnostic(f"AUDIT action=tweak_reflector {'enable' if enable else 'disable'} result=success")
    return TweakResult(
        success=True,
        message="Espejos optimizados (reflector) activado" if enable else "Espejos optimizados (reflector) desactivado",
        installed_deps=needs_pkg,
    )


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
    "perf_zswap": {
        "check": tweak_zswap_check_state,
        "apply": tweak_zswap_apply,
        "deps": [],
        "friendly_name": "zswap (caché de compresión en RAM)",
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


_BLOCKS = {
    "perf_compress_ram": _zram_block,
    "perf_zswap": _zswap_block,
    "perf_mirror_sort": _mirrors_block,
}


def get_tweak_block_reason(key: str) -> TweakBlock | None:
    """Motivo de bloqueo del tweak en este sistema, o None si es aplicable."""
    check = _BLOCKS.get(key)
    return check() if check else None


def apply_tweak(key: str, enable: bool) -> TweakResult:
    """Aplica (habilita/deshabilita) un tweak, salvo que pisaría config del sistema."""
    info = get_tweak_info(key)
    if not info:
        return TweakResult(success=False, message=f"Tweak desconocido: {key}")
    block = get_tweak_block_reason(key)
    if block is not None and (enable or not block.enable_only):
        write_diagnostic(f"AUDIT action=tweak_blocked key={key} reason={block.code}")
        return TweakResult(success=False, message=block.message)
    return info["apply"](enable)


@dataclass(frozen=True)
class Reconciliation:
    """Diferencias entre lo que el usuario eligió y lo que hay en el sistema."""
    drifted: list[str]        # elegido ON pero el sistema está OFF (no se pisa la elección)
    adopt: dict[str, bool]    # activo en el sistema y no registrado: se anota en prefs


def reconcile_tweaks(prefs: dict, states: dict, blocked: set[str]) -> Reconciliation:
    """La preferencia guardada es la intención del usuario y no se sobrescribe.

    Si el usuario dejó un tweak activado y el sistema ya no lo tiene (otra
    herramienta lo deshizo), es una divergencia que se avisa y se ofrece
    reaplicar. Los tweaks bloqueados se ignoran.
    """
    drifted: list[str] = []
    adopt: dict[str, bool] = {}
    for key in TWEAKS:
        if key in blocked:
            continue
        wanted = bool(prefs.get(key, False))
        actual = bool(states.get(key, False))
        if wanted and not actual:
            drifted.append(key)
        elif actual and not wanted:
            adopt[key] = True
    return Reconciliation(drifted=drifted, adopt=adopt)


def get_all_tweak_states() -> dict[str, bool]:
    """Retorna dict {key: estado_actual} para todos los tweaks."""
    return {key: check_tweak_state(key) for key in TWEAKS}