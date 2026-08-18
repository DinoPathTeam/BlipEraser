"""Repro fiel del flujo de arranque de main.py (splash + StartupWorker +
MainWindow) para observar cuándo muere self._apps_layout de OverviewPage.

Se imita el timing de CachyOS: escaneos que tardan ~0.8-1.5s, apps reales
(no vacías), y se bombea el event loop igual que lo haría app.exec() con un
QTimer que cierra a los 25s. Se instrumenta:
  - cada iteracion: sip.isdeleted(page._apps_layout)
  - _rebuild_apps: al entrar y antes de cada addWidget
Se instala sys.excepthook para capturar el RuntimeError con traceback real.
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "src")

from PyQt6 import sip
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import blip_eraser.utils.config as config_mod
config_mod.PREFS_FILE = Path("C:/Users/Adrian/AppData/Local/Temp/opencode/repro_prefs.json")

# --- escaneos lentos tipo CachyOS + datos reales ---
from blip_eraser.utils.apps import InstalledApp, KIND_APP, KIND_DEPENDENCY, KIND_FOLDER

_FAKE_APPS = []
for i in range(40):
    kind = KIND_APP if i % 3 else KIND_DEPENDENCY
    _FAKE_APPS.append(InstalledApp(
        name=f"paquete-{i}",
        source="pacman",
        detail=f"/usr/share/{i}",
        size_bytes=10_000_000 + i,
        kind=kind,
    ))


def slow_list(*a, **k):
    threading.Event().wait(1.2)
    return list(_FAKE_APPS)


def slow_cleanup(*a, **k):
    threading.Event().wait(0.6)
    return {"junk_bytes": 1000, "pacman_cache_bytes": 2000, "logs_bytes": 500, "orphan_count": 3}


import blip_eraser.utils.apps as apps_mod
import blip_eraser.utils.scan as scan_mod
apps_mod.list_installed_apps = slow_list
scan_mod.scan_cleanup = slow_cleanup
scan_mod.scan_cleanup_items = lambda *a, **k: []

# --- excepthook para capturar el RuntimeError real ---
def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("=" * 60, flush=True)
    print("EXCEPCION NO CAPTURADA:", flush=True)
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stdout)
    print("=" * 60, flush=True)
    sys.exit(3)


sys.excepthook = _excepthook

app = QApplication([])

# --- instrumentacion del layout de Overview ---
import blip_eraser.pages.overview_page as overview_mod

_orig_rebuild = overview_mod.OverviewPage._rebuild_apps

def traced_rebuild(self):
    print(f"[rebuild] entrando: sip.isdeleted(self)={sip.isdeleted(self)} "
          f"sip.isdeleted(self._apps_layout)={sip.isdeleted(self._apps_layout)} "
          f"layout={self._apps_layout!r} count="
          f"{self._apps_layout.count() if not sip.isdeleted(self._apps_layout) else 'DELETED'}", flush=True)
    _orig_rebuild(self)

overview_mod.OverviewPage._rebuild_apps = traced_rebuild

# --- monitor periodico del layout ---
_checked = {"n": 0}

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

t0 = time.monotonic()

# --- flujo de main() ---
import blip_eraser.main as main_mod
from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker
from blip_eraser.renderer import MainWindow

splash = SplashScreen()
splash.show()
app.processEvents()

worker = StartupWorker()
cancel_requested = {"value": False}
window_holder = {}


def _on_splash_closed():
    cancel_requested["value"] = True
    worker.requestInterruption()


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
    QTimer.singleShot(0, lambda: print(f"[flow] refresh_appearance t={time.monotonic()-t0:.2f}s", flush=True))


splash.closed.connect(_on_splash_closed)
worker.message.connect(lambda m: None)  # no imprimir cada paso
worker.finished.connect(_on_worker_finished)
worker.start()

print(f"[flow] splash+worker arrancado t={time.monotonic()-t0:.2f}s", flush=True)

# cerrar a los 25s
QTimer.singleShot(25000, app.quit)
QTimer.singleShot(26000, lambda: print("[flow] TIMEOUT sin crash", flush=True))

rc = app.exec()
page = app._ov_page if hasattr(app, "_ov_page") else None
if page is not None:
    print(f"[final] page_alive={not sip.isdeleted(page)} layout_alive={not sip.isdeleted(page._apps_layout)}", flush=True)
print("[flow] exit rc =", rc, flush=True)
sys.exit(rc)