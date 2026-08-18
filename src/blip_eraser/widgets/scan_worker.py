"""Escaneos pesados fuera del hilo principal (patrón compartido).

Lleva las funciones de escaneo que tardan (list_installed_apps,
scan_cleanup_items, scan_manual_entries) a un hilo de fondo con el mismo
patrón que la Vista general: threading.Thread + pyqtSignal. El hilo emite el
resultado por señal, que Qt entrega de forma queued al hilo principal, y un
token de generación descarta resultados obsoletos (si se lanza un segundo
escaneo antes de que llegue el primero).
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.log import write_diagnostic


class _ScanBridge(QObject):
    """Puente QObject: único lugar donde vive la señal, emitida por el hilo.

    Al conectarla a un método de la página (un QObject que vive en el hilo
    principal), Qt entrega el resultado de forma queued en ese hilo, sin que
    el worker toque nunca un widget directamente.
    """

    result_ready = pyqtSignal(object)  # (token, resultado)
    failed = pyqtSignal(str)


class BackgroundScanMixin:
    """Ejecuta una función de escaneo en un hilo de fondo sin bloquear la GUI.

    La página que lo use debe:
    - construir sus botones y llamar ``_init_scan_buttons([...])`` después;
    - llamar ``_start_background_scan(fn, on_result)`` donde ``fn`` es la
      función pesada (callable sin argumentos) y ``on_result(result)`` recibe
      el resultado en el hilo principal.

    Garantías:
    - Los botones registrados se deshabilitan durante el escaneo y se
      re-habilitan cuando llega el resultado (o falla el worker).
    - Token por generación: si se lanza otro escaneo antes de que llegue el
      resultado anterior, el anterior se descarta (doble refresco, o navegar
      y volver mientras un escaneo corre).
    - Verificación de vida del widget: si la página fue destruida en C++
      (cierre de la app mientras el hilo corre), el resultado se descarta sin
      tocar ningún widget — el wrapper Python puede seguir vivo por la
      referencia del hilo, pero su C++ subyacente ya no existe.
    - El resultado se aplica aunque la página esté oculta: las páginas viven
      toda la sesión en el QStackedWidget (nunca se destruyen al navegar),
      así que es seguro y deja los datos listos para cuando el usuario vuelva.
    """

    def _init_scan_buttons(self, buttons: list) -> None:
        self._scan_buttons = list(buttons)
        self._scan_token = 0
        self._scanning = False
        self._scan_on_result: Callable[[object], None] | None = None
        self._scan_bridge = _ScanBridge()
        self._scan_bridge.result_ready.connect(self._on_scan_result_ready)
        self._scan_bridge.failed.connect(self._on_scan_failed)

    def _widget_is_alive(self) -> bool:
        """True si el QObject C++ subyacente de la página sigue existiendo.

        Un thread de fondo puede terminar después de que la app/ventana se
        cierre: el hilo mantiene viva la referencia al bound method, así que
        el wrapper Python sobrevive, pero Qt ya destruyó el C++ del widget y
        de sus layouts/hijos. Tocar cualquiera de ellos lanzaría RuntimeError
        ("wrapped C/C++ object ... has been deleted").
        """
        from PyQt6 import sip

        return not sip.isdeleted(self)

    def _forensic_debug(self, label: str, **widgets) -> str:
        """Línea forense de depuración (vida + identidad de widgets implicados).

        Va a la bitácora de diagnóstico (write_diagnostic), nunca a la UI del
        usuario. `id()` permite comparar si un widget cambia de identidad
        entre eventos (descarta/revela reasignaciones).
        """
        from PyQt6 import sip

        try:
            parts = [
                f"{label} page_alive={not sip.isdeleted(self)} "
                f"page_id={id(self)} thread={threading.current_thread().name}"
            ]
        except Exception:  # noqa: BLE001 - forense: nunca romper por el propio log
            parts = [f"{label} page=unreadable"]
        for name, widget in widgets.items():
            try:
                parts.append(f"{name}_alive={not sip.isdeleted(widget)} id={id(widget)}")
            except Exception:  # noqa: BLE001
                parts.append(f"{name}=unreadable")
        return " ".join(parts)

    def _render_failure(
        self,
        label: str,
        exc: BaseException,
        *,
        user_message: str | None = None,
        extra: dict | None = None,
        **widgets,
    ) -> None:
        """Contiene un RuntimeError de render/rebuild SIN tumbar la app.

        Aunque la causa raíz siga sin diagnosticarse, ninguna página puede
        derribar la app por widgets/layouts destruidos a mitad de ejecución:
        se deja evidencia forense en la bitácora de diagnóstico (vida e
        identidad de los widgets implicados + datos del instante del fallo),
        se avisa al usuario en el log con `user_message` (o el genérico
        ``table_render_failed``) y NO se relanza la excepción.
        """
        from PyQt6 import sip

        parts = [f"RENDER_FAILED {label}: {exc}"]
        try:
            parts += [
                f"page_alive={not sip.isdeleted(self)}",
                f"page_id={id(self)}",
                f"thread={threading.current_thread().name}",
            ]
        except Exception:  # noqa: BLE001
            parts.append("page=unreadable")
        for name, widget in widgets.items():
            try:
                parts.append(f"{name}_alive={not sip.isdeleted(widget)} id={id(widget)}")
            except Exception:  # noqa: BLE001
                parts.append(f"{name}=unreadable")
        for key, value in (extra or {}).items():
            parts.append(f"{key}={value}")
        write_diagnostic(" ".join(parts))
        log_buffer.add(user_message if user_message is not None else tr("table_render_failed"))

    def _start_background_scan(
        self, fn: Callable[[], object], on_result: Callable[[object], None]
    ) -> None:
        self._scan_token += 1
        token = self._scan_token
        self._scanning = True
        self._scan_on_result = on_result
        for btn in self._scan_buttons:
            btn.setEnabled(False)

        def worker() -> None:
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001 - el error viaja por señal
                self._scan_bridge.failed.emit(str(exc))
                return
            self._scan_bridge.result_ready.emit((token, result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_result_ready(self, payload: tuple) -> None:
        token, result = payload
        if token != self._scan_token:
            return  # resultado obsoleto: se lanzó otro escaneo después
        if not self._widget_is_alive():
            # La página ya no existe en C++ (cierre de app): descartar sin
            # tocar botones ni widgets, que lanzarían RuntimeError.
            return
        self._scanning = False
        for btn in self._scan_buttons:
            btn.setEnabled(True)
        if self._scan_on_result is not None:
            self._scan_on_result(result)

    def _on_scan_failed(self, message: str) -> None:
        if not self._widget_is_alive():
            return
        self._scanning = False
        for btn in self._scan_buttons:
            btn.setEnabled(True)
        log_buffer.add(f"Error de escaneo: {message}")