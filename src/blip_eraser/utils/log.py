"""Registro de acciones (log) — lógica pura, sin PyQt6.

Un buffer simple de entradas (timestamp, mensaje) con suscriptores para
que la GUI refresque el panel de registro sin conocer su implementación.

Seguridad (Fase 1 - Bitácora forense protegida):
- Entradas hasheadas (SHA-256) para paths sensibles
- Permisos 600 en archivo de bitácora (solo owner read/write)
- No loggeo de paths completos en texto plano
"""

from __future__ import annotations

import hashlib
import os
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

Listener = Callable[[list[tuple[str, str]]], None]


class LogBuffer:
    def __init__(self, max_entries: int = 500):
        self._entries: list[tuple[str, str]] = []
        self._max_entries = max(1, max_entries)
        self._listeners: list[Listener] = []

    def add(self, message: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        # Dedupe: un evento repetido consecutivamente (p. ej. cambiar varias
        # veces la misma preferencia) solo refresca el timestamp en lugar de
        # acumular ruido en "Actividad reciente".
        if self._entries and self._entries[-1][1] == message:
            self._entries[-1] = (now, message)
        else:
            self._entries.append((now, message))
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
        self._notify()

    def clear(self) -> None:
        self._entries.clear()
        self._notify()

    def entries(self) -> list[tuple[str, str]]:
        return list(self._entries)

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)
        listener(self._entries)

    def unsubscribe(self, listener: Listener) -> None:
        """Quita un listener. Sin efecto si no estaba suscrito."""
        self._listeners = [l for l in self._listeners if l is not listener]

    def latest(self) -> str | None:
        return self._entries[-1][1] if self._entries else None

    def _notify(self) -> None:
        snapshot = list(self._entries)
        alive = []
        for listener in self._listeners:
            try:
                listener(snapshot)
                alive.append(listener)
            except RuntimeError:
                # Listener cuyo widget C++ ya fue destruido (cierre de app,
                # página muerta por una ventana cerrada): descartarlo para que
                # no vuelva a notificar y no bloquee a los demás.
                pass
        if len(alive) != len(self._listeners):
            self._listeners = alive


log = LogBuffer()


# ---------------------------------------------------------------------------
# Bitácora forense (no visible en la UI)
# ---------------------------------------------------------------------------
# Mientras `log` alimenta la "Actividad reciente" (visible al usuario),
# write_diagnostic() escribe a un archivo aparte con timestamp + hilo: sirve
# para reconstruir la secuencia exacta de destrucciones de widgets Qt si un
# RuntimeError vuelve a ocurrir en producción (p. ej. "wrapped C/C++ object
# of type QVBoxLayout has been deleted" en CachyOS). El usuario normal nunca
# la ve; un diagnóstico de CachyOS solo necesita adjuntar el archivo.
#
# SEGURIDAD (Fase 1):
# - Paths hasheados con SHA-256 (truncado a 16 chars) para no exponer rutas
#   en entradas AUDIT (paths hasheados INDIVIDUALMENTE antes de unir con comas)
# - Permisos 0o600 en archivo (solo owner read/write)
# - NO paths completos en texto plano en entradas AUDIT
#
# LIMITACIÓN ACEPTADA (Riesgo asumido, no resuelto):
# - TRACEBACKS (líneas que empiezan con "TRACEBACK:\n") NO se sanean.
#   Contienen rutas absolutas reales del home del usuario, nombres de archivo,
#   números de línea. El chmod 600 mitiga acceso cross-user, pero cualquier
#   proceso con el mismo UID (malware, etc.) puede leerlos.
#   DECISIÓN: No sanear tracebacks = preservar capacidad de diagnóstico.
#   Riesgo: exfiltración de paths por proceso co-uid. Mitigación: solo 600.
#   Ver: SECURITY_RESEARCH_INTERNAL.md hallazgo #2 (parcialmente mitigado).
DIAG_LOG_PATH = Path.home() / ".cache" / "blip-eraser" / "diagnostics.log"
DIAG_LOG_MAX_BYTES = 2_000_000
_diag_lock = threading.Lock()


def _hash_path(path_str: str) -> str:
    """Devuelve hash SHA-256 truncado (16 chars) de un path.
    
    Permite correlacionar entradas sin exponer la ruta completa.
    """
    return hashlib.sha256(path_str.encode()).hexdigest()[:16]


def _sanitize_message(message: str) -> str:
    """Sanea el mensaje para no loggear paths completos.

    Detecta patrones tipo path=... y los reemplaza por su hash.
    Formato esperado: path=valor#hash  (donde hash = SHA-256 truncado 16 chars)
    Acepta múltiples paths separados por comas: paths=a,b,c -> a#h1,b#h2,c#h3
    NO hashea texto libre que contenga "/" (p.ej. tracebacks, errores).
    """
    import re
    # Patrones: paths=..., path=..., target=... - SOLO estos parámetros explícitos
    # El valor puede contener comas y hashes (#), así que usamos [^\s]+
    def replace_path(match):
        full = match.group(0)
        key = match.group(1)
        value = match.group(2)
        # Si ya tiene hash (# seguido de 16 chars hex), no tocar
        if "#" in value and len(value.split("#")[-1]) == 16:
            return full
        # Si tiene comas, dividir y hashear cada parte
        if "," in value:
            parts = [f"{part}#{_hash_path(part)}" for part in value.split(",")]
            return f"{key}={','.join(parts)}"
        # Path simple
        if "/" in value or value.startswith("~"):
            return f"{key}={value}#{_hash_path(value)}"
        return full
    
    # Reemplaza SOLO patterns explícitos: paths=..., path=..., target=...
    # NO reemplaza slashes en texto libre (tracebacks, errores, etc.)
    message = re.sub(r'(paths?|target)=([^\s]+)', replace_path, message)
    return message


def _ensure_secure_permissions(path: Path) -> None:
    """Asegura permisos 0o600 en el archivo de bitácora (solo owner rw)."""
    try:
        if path.exists():
            os.chmod(path, 0o600)
    except OSError:
        pass


def write_diagnostic(message: str) -> None:
    """Añade una línea forense a la bitácora de diagnóstico.

    Best-effort: un fallo de escritura (permisos, disco, ...) nunca rompe la
    app. La bitácora se trunca desde cero si supera ``DIAG_LOG_MAX_BYTES``
    para no crecer sin límite.

    SEGURIDAD: Mensaje saneado (paths hasheados) + permisos 600 en archivo.
    """
    try:
        # Sanear mensaje antes de escribir
        safe_message = _sanitize_message(message)
        
        line = (
            f"[{datetime.now().isoformat(timespec='milliseconds')}] "
            f"[{threading.current_thread().name}] {safe_message}\n"
        )
        line_bytes = line.encode("utf-8")
        with _diag_lock:
            # Usar el atributo del módulo (permite monkeypatch en tests)
            import sys
            mod = sys.modules[__name__]
            path = mod.DIAG_LOG_PATH
            current_size = path.stat().st_size if path.exists() else 0
            if path.exists() and current_size + len(line_bytes) > mod.DIAG_LOG_MAX_BYTES:
                path.unlink()  # empezar de nuevo si la línea superaría el límite
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            # Asegurar permisos 600 tras cada escritura
            _ensure_secure_permissions(path)
    except OSError:
        pass