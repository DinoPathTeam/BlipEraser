"""Registro de acciones (log) — lógica pura, sin PyQt6.

Un buffer simple de entradas (timestamp, mensaje) con suscriptores para
que la GUI refresque el panel de registro sin conocer su implementación.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

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

    def latest(self) -> str | None:
        return self._entries[-1][1] if self._entries else None

    def _notify(self) -> None:
        snapshot = list(self._entries)
        for listener in self._listeners:
            listener(snapshot)


log = LogBuffer()
