"""Repro fiel V2: incluye los QMessageBox modales del primer arranque
(avisos de permisos y de binarios faltantes) que main() dispara con
QTimer.singleShot(0) tras el primer pintado. Esos dialogs corren un event
loop ANIDADO (box.exec()) justo cuando el escaneo de Overview termina y
entrega su resultado. Se monitorea el layout de Overview continuamente y se
detecta el instante exacto en que muere.
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "src")

from PyQt6 import sip
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

import blip_eraser.utils.config as config_mod
config_mod.PREFS_FILE = Path("C:/Users/Adrian/AppData/Local/Temp/opencode/repro_prefs2.json")

from blip_eraser.utils.apps import InstalledApp, KIND_APP, KIND_DEPENDENCY

_FAKE_APPS = []
for i in range(40):
    kind = KIND_APP if i % 3 else KIND_DEPENDENCY
    _FAKE_APPS.append(InstalledApp(
        name=f"paquete-{i}", source="pacman",
        detail=f"/usr/share/{i}", size_bytes=10_000_000 + i, kind=kind,
    ))


def slow_list(*a, **k):
    threading.Event().wait(2.0)   # el escaneo termina DENTRO de los dialogs
    return list(_FAKE_APPS)


def slow_cleanup(*a, **k):
    threading.Event().wait(1.2)
    return {"junk_bytes": 1000, "pacman_cache_bytes": 2000, "logs_bytes": 500, "orphan_count": 3}


import blip_eraser.utils.apps as apps_mod
import blip_eraser.utils.scan as scan_mod
apps_mod.list_installed_apps = slow_list
scan_mod.scan_cleanup = slow_cleanup
scan_mod.scan_cleanup_items = lambda *a, **k: []


def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("=" * 60, flush=True)
    print("EXCEPCION NO CAPTURADA:", flush=True)
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stdout)
    print("=" * 60, flush=True)
    sys.exit(3)


sys.excepthook = _excepthook

app = QApplication([])

import blip_eraser.pages.overview_page as overview_mod

_orig_rebuild = overview_mod.OverviewPage._rebuild_apps

def traced_rebuild(self):
    print(f"[rebuild] entrando: page_dead={sip.isdeleted(self)} "
          f"layout_dead={sip.isdeleted(self._apps_layout)} "
          f"apps={len(self._apps)}", flush=True)
    _orig_rebuild(self)

overview_mod.OverviewPage._rebuild_apps = traced_rebuild

_checked = {"n": 0}
t0 = time.monotonic()

def monitor():
    page = getattr(app, "_ov_page", None)
    if page is not None:
        laid = not sip.isdeleted(page._apps_layout)
        alive = not sip.isdeleted(page)
        if _checked["n"] % 20 == 0:
            print(f"[monitor] t={time.monotonic()-t0:.2f}s page_alive={alive} layout_alive={laid}", flush=True)
        _checked["n"] += 1
        if not laid and alive:
            print(f"[monitor] *** LAYOUT MUERTO con pagina VIVA en t={time.monotonic()-t0:.2f}s ***", flush=True)


mon = QTimer()
mon.timeout.connect(monitor)
mon.start(50)

from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker
from blip_eraser.renderer import MainWindow

splash = SplashScreen()
splash.show()
app.processEvents()

worker = StartupWorker()
cancel_requested = {"value": False}
window_holder = {}


def _on_worker_finished():
    print(f"[flow] worker finished t={time.monotonic()-t0:.2f}s", flush=True)
    if cancel_requested["value"]:
        app.quit()
        return
    window = MainWindow()
    window_holder["w"] = window
    app._ov_page = window._pages["overview"]
    window.show()
    splash.hide()
    print(f"[flow] MainWindow mostrado t={time.monotonic()-t0:.2f}s", flush=True)
    QTimer.singleShot(0, window.refresh_appearance)
    # ==== Dialogs modales del primer arranque (como main.py) ====
    QTimer.singleShot(0, lambda: _warn_deps(window))
    QTimer.singleShot(0, lambda: _permissions(window))


def _warn_deps(window):
    print(f"[flow] abriendo dialog de deps t={time.monotonic()-t0:.2f}s", flush=True)
    # Simula _warn_missing_dependencies: modal -> event loop anidado.
    box = QMessageBox(window)
    box.setWindowTitle("deps")
    box.setText("pacman/pkexec faltantes (simulado)")
    box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    box.exec()
    print(f"[flow] dialog deps cerrado t={time.monotonic()-t0:.2f}s", flush=True)


def _permissions(window):
    print(f"[flow] abriendo dialog permisos t={time.monotonic()-t0:.2f}s", flush=True)
    from blip_eraser.widgets.permissions_dialog import show_permissions_dialog
    show_permissions_dialog(window)
    print(f"[flow] dialog permisos cerrado t={time.monotonic()-t0:.2f}s", flush=True)


splash.closed.connect(lambda: None)
worker.message.connect(lambda m: None)
worker.finished.connect(_on_worker_finished)
worker.start()

print(f"[flow] splash+worker arrancado t={time.monotonic()-t0:.2f}s", flush=True)

QTimer.singleShot(25000, app.quit)
QTimer.singleShot(26000, lambda: print("[flow] TIMEOUT sin crash", flush=True))

rc = app.exec()
page = app._ov_page if hasattr(app, "_ov_page") else None
if page is not None:
    print(f"[final] page_alive={not sip.isdeleted(page)} layout_alive={not sip.isdeleted(page._apps_layout)}", flush=True)
print("[flow] exit rc =", rc, flush=True)
sys.exit(rc)