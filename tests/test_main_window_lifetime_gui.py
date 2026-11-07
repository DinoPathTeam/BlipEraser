"""La ventana principal debe tener un dueño estable durante toda la sesión.

Regresión: `main()` creaba `window` como variable local de un slot y solo la
sostenía un ciclo ventana → página → callback → ventana. Sin dueño externo, el
recolector de Python podía destruirla (DeferredDelete sobre la MainWindow sin
closeEvent) y la app se cerraba sola al abrir el Desinstalador.

La destrucción por GC no es determinista bajo pytest, así que aquí se fija el
contrato: existe el ancla y `main()` la usa justo al crear la ventana.
"""

from __future__ import annotations

import inspect

from blip_eraser import main as main_module


class _FakeApp:
    pass


def test_retain_main_window_ancla_la_ventana_a_la_app():
    app, window = _FakeApp(), object()
    main_module.retain_main_window(app, window)
    assert app._blip_main_window is window


def test_main_ancla_la_ventana_al_crearla():
    src = inspect.getsource(main_module.main)
    assert src.index("window = MainWindow()") < src.index("retain_main_window(app, window)")
    assert src.index("retain_main_window(app, window)") < src.index("window.show()")
