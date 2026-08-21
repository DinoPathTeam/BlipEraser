"""Registro de acciones (log) — lógica pura, sin PyQt6.

Un buffer simple de entradas (timestamp, mensaje) con suscriptores para
que la GUI refresque el panel de registro sin conocer su implementación.
"""

from __future__ import annotations

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
DIAG_LOG_PATH = Path.home() / ".cache" / "blip-eraser" / "diagnostics.log"
DIAG_LOG_MAX_BYTES = 2_000_000
_diag_lock = threading.Lock()


def write_diagnostic(message: str) -> None:
    """Añade una línea forense a la bitácora de diagnóstico.

    Best-effort: un fallo de escritura (permisos, disco, ...) nunca rompe la
    app. La bitácora se trunca desde cero si supera ``DIAG_LOG_MAX_BYTES``
    para no crecer sin límite.
    """
    try:
        line = (
            f"[{datetime.now().isoformat(timespec='milliseconds')}] "
            f"[{threading.current_thread().name}] {message}\n"
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
    except OSError:
        pass
