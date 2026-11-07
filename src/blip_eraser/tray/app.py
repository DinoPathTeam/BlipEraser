"""Icono de bandeja de BlipEraser (proceso aparte de la ventana principal).

Consumo en reposo nulo: nada se calcula hasta que se abre el menú. Una única
comprobación al iniciar (con la caché de 24 h de `check_for_updates`) decide si
hay que avisar de una versión nueva o de mucho espacio recuperable.

La bandeja nunca borra nada: "Limpieza rápida" abre la app principal con
`--cleanup`, que reutiliza el flujo de confirmación de siempre.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from blip_eraser import __version__
from blip_eraser.tray import logic
from blip_eraser.utils.config import load_prefs, save_prefs
from blip_eraser.utils.dependency_check import check_pyqt6_available
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import (
    detect_system_language,
    load_saved_language,
    set_language,
    tr,
)
from blip_eraser.utils.log import write_diagnostic

STARTUP_CHECK_DELAY_MS = 10_000
OPEN_DEBOUNCE_SECONDS = 8.0
CPU_SAMPLE_GAP_SECONDS = 0.25
RELEASES_URL = "https://github.com/DinoPathTeam/BlipEraser/releases/latest"


def gather_stats() -> dict[str, Any]:
    """CPU/RAM/disco + espacio recuperable. Pensada para un hilo de fondo."""
    from blip_eraser.utils.scan import scan_cleanup
    from blip_eraser.utils.system_stats import (
        cpu_usage_percent,
        disk_usage_percent,
        memory_usage_percent,
        read_cpu_sample,
    )

    first = read_cpu_sample()
    time.sleep(CPU_SAMPLE_GAP_SECONDS)
    cpu = cpu_usage_percent(first, read_cpu_sample())
    cleanup = scan_cleanup()
    return {
        "cpu": cpu,
        "ram": memory_usage_percent(),
        "disk": disk_usage_percent("/"),
        "recoverable": logic.recoverable_bytes(cleanup),
    }


def startup_check() -> dict[str, Any]:
    """Versión nueva (caché 24 h) y espacio recuperable, en un hilo de fondo."""
    from blip_eraser.utils.scan import scan_cleanup
    from blip_eraser.utils.updates import check_for_updates

    update = check_for_updates()
    cleanup = scan_cleanup()
    return {
        "update_version": update.latest_version if update.has_update else None,
        "recoverable": logic.recoverable_bytes(cleanup),
    }


def build_controller(app: Any = None) -> Any:
    """Construye el controlador de la bandeja (importa PyQt6 de forma perezosa)."""
    from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
    from PyQt6.QtGui import QAction, QDesktopServices
    from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

    from blip_eraser.widgets.logo import app_icon

    class _Bridge(QObject):
        stats_ready = pyqtSignal(object)
        startup_ready = pyqtSignal(object)

    class TrayController(QObject):
        def __init__(self) -> None:
            super().__init__()
            self._bridge = _Bridge()
            self._bridge.stats_ready.connect(self._on_stats)
            self._bridge.startup_ready.connect(self._on_startup)
            self._gathering = False
            self._last_open = 0.0
            self._notice_kind: str | None = None

            self.tray = QSystemTrayIcon(app_icon())
            self.tray.setToolTip(f"BlipEraser {__version__}")
            self.menu = QMenu()

            self.title_action = QAction(f"BlipEraser {__version__}", self.menu)
            self.title_action.setEnabled(False)
            self.status_action = QAction(self.menu)
            self.status_action.setEnabled(False)
            self.recoverable_action = QAction(self.menu)
            self.recoverable_action.setEnabled(False)
            self.open_action = QAction(tr("tray_open"), self.menu)
            self.cleanup_action = QAction(tr("tray_cleanup"), self.menu)
            self.autostart_action = QAction(tr("tray_autostart"), self.menu)
            self.autostart_action.setCheckable(True)
            self.autostart_action.setChecked(logic.autostart_enabled())
            self.notify_action = QAction(tr("tray_notifications"), self.menu)
            self.notify_action.setCheckable(True)
            self.notify_action.setChecked(
                load_prefs().get("tray_notifications", True) is not False
            )
            self.quit_action = QAction(tr("tray_quit"), self.menu)

            for item in (self.title_action, self.status_action, self.recoverable_action):
                self.menu.addAction(item)
            self.menu.addSeparator()
            self.menu.addAction(self.open_action)
            self.menu.addAction(self.cleanup_action)
            self.menu.addSeparator()
            self.menu.addAction(self.autostart_action)
            self.menu.addAction(self.notify_action)
            self.menu.addSeparator()
            self.menu.addAction(self.quit_action)
            self.tray.setContextMenu(self.menu)

            self._set_placeholders()
            self.menu.aboutToShow.connect(self.refresh_stats)
            self.open_action.triggered.connect(lambda: self.open_app())
            self.cleanup_action.triggered.connect(lambda: self.open_app([logic.CLEANUP_FLAG]))
            self.autostart_action.toggled.connect(self._toggle_autostart)
            self.notify_action.toggled.connect(
                lambda on: save_prefs({"tray_notifications": bool(on)})
            )
            self.quit_action.triggered.connect(lambda: QTimer.singleShot(0, self._quit))
            self.tray.activated.connect(self._on_activated)
            self.tray.messageClicked.connect(self._on_message_clicked)

        # -- menú ---------------------------------------------------------
        def _set_placeholders(self) -> None:
            calc = tr("tray_calculating")
            self.status_action.setText(calc)
            self.recoverable_action.setText(
                tr("tray_recoverable").format(size=calc)
            )

        def refresh_stats(self) -> None:
            """Al abrir el menú: calcula en un hilo (sin bloquear el menú)."""
            if self._gathering:
                return
            self._gathering = True
            self._set_placeholders()
            bridge = self._bridge

            def worker() -> None:
                try:
                    result = gather_stats()
                except Exception as exc:  # noqa: BLE001 - nunca romper la bandeja
                    write_diagnostic(f"tray gather_stats failed: {exc}")
                    result = {"cpu": None, "ram": None, "disk": None, "recoverable": None}
                try:
                    bridge.stats_ready.emit(result)
                except RuntimeError:
                    pass  # el puente se destruyó (cierre)

            threading.Thread(target=worker, daemon=True, name="tray-stats").start()

        def _on_stats(self, data: dict) -> None:
            self._gathering = False
            na = tr("status_na")
            cpu, ram, disk = logic.status_values(
                data.get("cpu"), data.get("ram"), data.get("disk"), na
            )
            self.status_action.setText(
                tr("tray_status").format(cpu=cpu, ram=ram, disk=disk)
            )
            rec = data.get("recoverable")
            self.recoverable_action.setText(
                tr("tray_recoverable").format(size=human_size(rec) if rec is not None else na)
            )

        # -- abrir la app -------------------------------------------------
        def open_app(self, extra_args: list[str] | None = None) -> bool:
            """Abre la ventana principal. Ignora clics repetidos en pocos segundos."""
            now = time.monotonic()
            if now - self._last_open < OPEN_DEBOUNCE_SECONDS:
                return False
            self._last_open = now
            from PyQt6.QtCore import QProcess

            cmd = logic.app_command(extra_args)
            ok = QProcess.startDetached(cmd[0], cmd[1:])
            if not ok:
                write_diagnostic(f"tray: no se pudo lanzar {logic.shell_preview(cmd)}")
            return bool(ok)

        def _on_activated(self, reason: Any) -> None:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.open_app()

        def _toggle_autostart(self, enabled: bool) -> None:
            if not logic.set_autostart(enabled):
                # No se pudo escribir: el check vuelve al estado real.
                self.autostart_action.blockSignals(True)
                self.autostart_action.setChecked(logic.autostart_enabled())
                self.autostart_action.blockSignals(False)

        # -- avisos -------------------------------------------------------
        def schedule_startup_check(self, delay_ms: int = STARTUP_CHECK_DELAY_MS) -> None:
            QTimer.singleShot(delay_ms, self._start_startup_check)

        def _start_startup_check(self) -> None:
            bridge = self._bridge

            def worker() -> None:
                try:
                    result = startup_check()
                except Exception as exc:  # noqa: BLE001
                    write_diagnostic(f"tray startup_check failed: {exc}")
                    return
                try:
                    bridge.startup_ready.emit(result)
                except RuntimeError:
                    pass

            threading.Thread(target=worker, daemon=True, name="tray-startup").start()

        def _on_startup(self, data: dict) -> None:
            notices, updates = logic.decide_notices(
                load_prefs(),
                update_version=data.get("update_version"),
                recoverable=int(data.get("recoverable") or 0),
                now=time.time(),
            )
            if not notices:
                return
            save_prefs(updates)
            # Un aviso a la vez: la versión nueva tiene prioridad.
            notice = notices[0]
            self._notice_kind = notice.kind
            if notice.kind == logic.KIND_UPDATE:
                title = tr("tray_update_title")
                message = tr("update_available").format(version=notice.value)
            else:
                title = tr("tray_junk_title")
                message = tr("tray_junk_message").format(size=human_size(int(notice.value)))
            self.tray.showMessage(title, message, self.tray.icon(), 10_000)

        def _on_message_clicked(self) -> None:
            if self._notice_kind == logic.KIND_UPDATE:
                QDesktopServices.openUrl(QUrl(RELEASES_URL))
            elif self._notice_kind == logic.KIND_JUNK:
                self.open_app([logic.CLEANUP_FLAG])
            self._notice_kind = None

        def _quit(self) -> None:
            self.tray.hide()
            from PyQt6.QtWidgets import QApplication

            QApplication.quit()

    return TrayController()


def main() -> int:
    """Entry point de la bandeja. 0 si sale bien (incluida otra instancia ya activa)."""
    if not check_pyqt6_available():
        print("PyQt6 no está instalado.", file=sys.stderr)
        return 1

    from PyQt6.QtCore import QDir, QLockFile
    from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

    sys.setswitchinterval(0.001)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    set_language(load_saved_language() or detect_system_language())

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(tr("tray_unavailable"), file=sys.stderr)
        return 1

    lock = QLockFile(QDir.tempPath() + "/blip-eraser-tray.lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return 0  # ya hay una bandeja activa

    controller = build_controller(app)
    controller.tray.show()
    controller.schedule_startup_check()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
