"""Comprobación de actualizaciones en segundo plano (nunca bloquea la UI).

`UpdateNotifier.start()` lanza un hilo daemon que llama a
`updates.check_for_updates()` (con caché de 24 h) y, solo si hay versión
nueva, emite `update_found(version)` hacia el hilo de la interfaz. Cualquier
fallo es silencioso: una comprobación de actualizaciones jamás debe molestar.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, pyqtSignal

from blip_eraser.utils import updates


class UpdateNotifier(QObject):
    update_found = pyqtSignal(str)

    def start(self) -> None:
        threading.Thread(target=self._run, name="update-check", daemon=True).start()

    def _run(self) -> None:
        try:
            result = updates.check_for_updates()
            if result.has_update and result.latest_version:
                self.update_found.emit(result.latest_version)
        except RuntimeError:
            pass  # el objeto Qt ya se destruyó (la app se cerró): nada que avisar
        except Exception:
            pass
