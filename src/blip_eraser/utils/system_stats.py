"""Estado del sistema (CPU/RAM/disco) — lógica pura, sin PyQt6.

En Linux lee /proc/stat y /proc/meminfo (Arch/CachyOS). En entornos sin
/proc (p. ej. Windows para desarrollo) las lecturas devuelven None y la
GUI muestra "N/D". `_read_lines` se mockea en tests.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_CPU_STAT = Path("/proc/stat")
_MEMINFO = Path("/proc/meminfo")
_CPUINFO = Path("/proc/cpuinfo")


def _read_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None


# ----------------------------------------------------------------------
# CPU
# ----------------------------------------------------------------------
def read_cpu_sample() -> tuple[int, int] | None:
    """(total, idle) de la primera línea de /proc/stat; None si no hay."""
    lines = _read_lines(_CPU_STAT)
    if not lines:
        return None
    parts = lines[0].split()
    if not parts or parts[0] != "cpu" or len(parts) < 5:
        return None
    try:
        numbers = [int(x) for x in parts[1:]]
    except ValueError:
        return None
    total = sum(numbers)
    idle = numbers[3] + numbers[4]
    return total, idle


def cpu_usage_percent(
    prev: tuple[int, int] | None,
    curr: tuple[int, int] | None,
) -> int | None:
    """% de uso entre dos muestras (0-100)."""
    if prev is None or curr is None:
        return None
    total_delta = curr[0] - prev[0]
    idle_delta = curr[1] - prev[1]
    if total_delta <= 0:
        return None
    usage = (1 - idle_delta / total_delta) * 100
    return max(0, min(100, int(round(usage))))


# ----------------------------------------------------------------------
# Memoria
# ----------------------------------------------------------------------
def memory_usage_percent() -> int | None:
    """% de RAM usada desde /proc/meminfo."""
    lines = _read_lines(_MEMINFO)
    if not lines:
        return None
    values: dict[str, int] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        tokens = rest.split()
        if not tokens:
            continue
        try:
            values[key] = int(tokens[0])
        except ValueError:
            continue
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    usage = (1 - available / total) * 100
    return max(0, min(100, int(round(usage))))


# ----------------------------------------------------------------------
# Disco
# ----------------------------------------------------------------------
def disk_usage_percent(path: str = "/") -> int | None:
    """% de disco usado en `path` (shutil.disk_usage)."""
    try:
        usage = shutil.disk_usage(path)
    except (OSError, PermissionError):
        return None
    if usage.total == 0:
        return None
    return max(0, min(100, int(round(usage.used / usage.total * 100))))


# ----------------------------------------------------------------------
# Identificación de hardware (solo lectura)
# ----------------------------------------------------------------------
def cpu_model() -> str | None:
    """Nombre del procesador desde /proc/cpuinfo."""
    lines = _read_lines(_CPUINFO)
    if not lines:
        return None
    for line in lines:
        if line.lower().startswith("model name"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def gpu_model() -> str | None:
    """GPU principal desde `lspci`. None si lspci no existe o no devuelve nada.

    Es una consulta de solo lectura; sin privilegios y sin efectos.
    """
    try:
        out = subprocess.run(
            ["lspci"], capture_output=True, text=True, check=False, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if "vga" in line.lower() or "3d controller" in line.lower():
            # lspci: "00:02.0 VGA compatible controller: Intel UHD"
            # la dirección BDF lleva ":", así que la descripción va tras el
            # tercer campo al separar por ":".
            parts = line.split(":", 2)
            return parts[2].strip() if len(parts) >= 3 else line.strip()
    return None


def ram_total_bytes() -> int | None:
    """RAM total en bytes desde /proc/meminfo (MemTotal)."""
    lines = _read_lines(_MEMINFO)
    if not lines:
        return None
    for line in lines:
        if line.startswith("MemTotal:"):
            tokens = line.split()
            if len(tokens) >= 2 and tokens[1].isdigit():
                return int(tokens[1]) * 1024
    return None


def disk_total_bytes(path: str = "/") -> int | None:
    """Capacidad total de disco en `path` en bytes."""
    try:
        return shutil.disk_usage(path).total
    except (OSError, PermissionError):
        return None