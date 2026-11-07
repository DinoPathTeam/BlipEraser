"""Icono de bandeja de BlipEraser (proceso aparte de la ventana principal).

Consumo en reposo nulo: nada se calcula hasta que se abre el menú. Una única
comprobación al iniciar (con la caché de 24 h de `check_for_updates`) decide si
hay que avisar de una versión nueva o de mucho espacio recuperable.

Clic izquierdo: ventanita con el tema de la app (estado, escanear, limpiar,
abrir). Limpiar usa exactamente el mismo flujo que la app: lista lo que se va
a borrar, pide confirmación y la autorización (contraseña) la pide el borrado
con privilegios. Clic derecho: ajustes de la bandeja.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from blip_eraser import __version__
from blip_eraser.tray import launcher, logic
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
WAIT_LOCK_FLAG = "--wait-lock"  # el relanzado espera a que la instancia vieja suelte el bloqueo
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


_applied_appearance: dict[int, tuple[str, str]] = {}


def apply_app_appearance() -> str:
    """Tema y fuente elegidos en la app principal, aplicados a toda la bandeja.

    Cubre también los diálogos de confirmación/progreso de la limpieza. Devuelve
    la clave de tema aplicada.
    """
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    from blip_eraser.utils import theme as theme_mod

    prefs = load_prefs()
    key = prefs.get("theme")
    if key not in theme_mod.THEMES:
        key = "red"
    app = QApplication.instance()
    font_id = prefs.get("font", "system")
    # Re-aplicar una hoja de estilos global repule todos los widgets: solo si cambió.
    if app is not None and _applied_appearance.get(id(app)) != (key, font_id):
        app.setStyleSheet(theme_mod.build_qss(key))
        family = theme_mod.font_family(font_id)
        app.setFont(QFont(family) if family else QFont())
        _applied_appearance.clear()
        _applied_appearance[id(app)] = (key, font_id)
    return key


def build_controller(app: Any = None) -> Any:
    """Construye el controlador de la bandeja (importa PyQt6 de forma perezosa)."""
    from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
    from PyQt6.QtGui import QAction, QCursor, QDesktopServices, QGuiApplication
    from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

    from blip_eraser.tray.popup import TrayPopup
    from blip_eraser.utils.confirm import build_confirmation_plan, cleanup_confirm_items
    from blip_eraser.utils import scan as scan_mod
    from blip_eraser.widgets.confirm_dialog import run_destructive_action
    from blip_eraser.widgets.logo import app_icon

    class _Bridge(QObject):
        stats_ready = pyqtSignal(object)
        startup_ready = pyqtSignal(object)
        items_ready = pyqtSignal(object)

    class TrayController(QObject):
        def __init__(self) -> None:
            super().__init__()
            self._bridge = _Bridge()
            self._bridge.stats_ready.connect(self._on_stats)
            self._bridge.startup_ready.connect(self._on_startup)
            self._bridge.items_ready.connect(self._on_cleanup_items)
            self._gathering = False
            self._last_open = 0.0
            self._notice_kind: str | None = None

            self.tray = QSystemTrayIcon(app_icon())
            self.tray.setToolTip(f"BlipEraser {__version__}")

            self.popup = TrayPopup()
            self.popup.scan_requested.connect(self.refresh_stats)
            self.popup.clean_requested.connect(self.clean)
            self.popup.open_requested.connect(self._open_from_popup)
            self.popup.dragged_to.connect(self._save_dragged_position)

            # Clic derecho: ajustes de la bandeja. El clic izquierdo abre la ventanita.
            self.menu = QMenu()
            self.open_action = QAction(tr("tray_open"), self.menu)
            self.autostart_action = QAction(tr("tray_autostart"), self.menu)
            self.autostart_action.setCheckable(True)
            self.autostart_action.setChecked(logic.autostart_enabled())
            self.notify_action = QAction(tr("tray_notifications"), self.menu)
            self.notify_action.setCheckable(True)
            self.notify_action.setChecked(
                load_prefs().get("tray_notifications", True) is not False
            )
            self.restart_action = QAction(tr("tray_restart"), self.menu)
            self.quit_action = QAction(tr("tray_quit"), self.menu)
            self.menu.addAction(self.open_action)
            self.menu.addSeparator()
            self.menu.addAction(self.autostart_action)
            self.menu.addAction(self.notify_action)
            self.menu.addSeparator()
            self.menu.addAction(self.restart_action)
            self.menu.addAction(self.quit_action)
            self.tray.setContextMenu(self.menu)

            self.open_action.triggered.connect(lambda: self.open_app())
            self.autostart_action.toggled.connect(self._toggle_autostart)
            self.notify_action.toggled.connect(
                lambda on: save_prefs({"tray_notifications": bool(on)})
            )
            self.restart_action.triggered.connect(lambda: QTimer.singleShot(0, self.restart))
            self.quit_action.triggered.connect(lambda: QTimer.singleShot(0, self._quit))
            self.tray.activated.connect(self._on_activated)
            self.tray.messageClicked.connect(self._on_message_clicked)

        # -- ventanita ------------------------------------------------------
        def toggle_popup(self) -> None:
            if self.popup.isVisible():
                self.popup.hide()
            elif not self.popup.recently_closed():
                self.show_popup()

        def show_popup(self) -> None:
            import os

            geometry = self.tray.geometry()
            if not geometry.isEmpty():
                anchor = geometry.center()
            elif QGuiApplication.platformName() == "xcb" and not os.environ.get("WAYLAND_DISPLAY"):
                anchor = QCursor.pos()  # X11 real: el cursor está sobre el icono al pulsarlo
            else:
                anchor = None  # Wayland/XWayland: no hay forma fiable de saberlo
            screen = (
                (QGuiApplication.screenAt(anchor) if anchor is not None else None)
                or QGuiApplication.primaryScreen()
            )
            area = screen.availableGeometry()
            full = screen.geometry()
            apply_app_appearance()
            self.popup.apply_theme()
            self.popup.adjustSize()
            pos = logic.resolve_position(
                load_prefs(),
                (anchor.x(), anchor.y()) if anchor is not None else None,
                (self.popup.width(), self.popup.height()),
                (area.x(), area.y(), area.width(), area.height()),
                tray_corner=logic.guess_tray_corner(
                    (full.x(), full.y(), full.width(), full.height()),
                    (area.x(), area.y(), area.width(), area.height()),
                ),
            )
            self.popup.show_at(pos)
            self.refresh_stats()

        def _save_dragged_position(self, x: int, y: int) -> None:
            save_prefs({logic.PREF_POSITION: logic.POS_CUSTOM, logic.PREF_CUSTOM: [x, y]})

        def _open_from_popup(self) -> None:
            self.popup.hide()
            self.open_app()

        def _on_activated(self, reason: Any) -> None:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.toggle_popup()

        # -- datos --------------------------------------------------------
        def refresh_stats(self) -> None:
            """Escanea CPU/RAM/disco y espacio recuperable en un hilo."""
            if self._gathering:
                return
            self._gathering = True
            self.popup.set_busy(True)
            self.popup.set_calculating()
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
            self.popup.set_stats(
                data.get("cpu"), data.get("ram"), data.get("disk"), data.get("recoverable")
            )
            self.popup.set_busy(False)

        # -- limpieza (mismo flujo y misma autorización que la app) -----------
        def clean(self) -> None:
            """Lista lo recuperable y pide confirmación; borrar pide contraseña."""
            self.popup.hide()
            bridge = self._bridge

            def worker() -> None:
                try:
                    entries = scan_mod.scan_cleanup_items()
                except Exception as exc:  # noqa: BLE001
                    write_diagnostic(f"tray scan_cleanup_items failed: {exc}")
                    entries = []
                try:
                    bridge.items_ready.emit(entries)
                except RuntimeError:
                    pass

            threading.Thread(target=worker, daemon=True, name="tray-clean").start()

        def _on_cleanup_items(self, entries: list) -> None:
            apply_app_appearance()
            if not entries:
                QMessageBox.information(None, tr("done_title"), tr("tray_nothing_to_clean"))
                return
            items = cleanup_confirm_items(
                entries,
                lambda key: tr(scan_mod.CLEANUP_CATEGORY_LABEL_KEYS.get(key, "col_name")),
            )
            run_destructive_action(
                None,
                build_confirmation_plan(items),
                tr("cleanup_confirm_title"),
                on_finished=lambda _ok: self.refresh_stats(),
            )

        # -- abrir la app -----------------------------------------------------
        def open_app(self) -> bool:
            """Abre la ventana principal. Ignora clics repetidos en pocos segundos."""
            now = time.monotonic()
            if now - self._last_open < OPEN_DEBOUNCE_SECONDS:
                return False
            self._last_open = now
            from PyQt6.QtCore import QProcess

            cmd = logic.app_command()
            ok = QProcess.startDetached(cmd[0], cmd[1:])
            if not ok:
                write_diagnostic(f"tray: no se pudo lanzar {logic.shell_preview(cmd)}")
            return bool(ok)

        def _toggle_autostart(self, enabled: bool) -> None:
            if not logic.set_autostart(enabled):
                # No se pudo escribir: el check vuelve al estado real.
                self.autostart_action.blockSignals(True)
                self.autostart_action.setChecked(logic.autostart_enabled())
                self.autostart_action.blockSignals(False)

        # -- avisos -----------------------------------------------------------
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
                self.show_popup()
            self._notice_kind = None

        def restart(self) -> None:
            """Relanza la bandeja (p. ej. para aplicar una posición fija en Wayland)."""
            from PyQt6.QtCore import QProcess

            cmd = logic.tray_command() + [WAIT_LOCK_FLAG]
            if QProcess.startDetached(cmd[0], cmd[1:]):
                self._quit()
            else:
                write_diagnostic(f"tray: no se pudo reiniciar {logic.shell_preview(cmd)}")

        def _quit(self) -> None:
            self.popup.hide()
            self.tray.hide()
            from PyQt6.QtWidgets import QApplication

            QApplication.quit()

    return TrayController()


def main() -> int:
    """Entry point de la bandeja. 0 si sale bien (incluida otra instancia ya activa)."""
    if not check_pyqt6_available():
        print("PyQt6 no está instalado.", file=sys.stderr)
        return 1

    import os

    # Wayland no deja que una app elija dónde se abre su ventana: se usa
    # XWayland si existe (y Wayland nativo como respaldo si falla).
    if logic.should_force_xcb(dict(os.environ)):
        os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"

    from PyQt6.QtCore import QLockFile
    from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

    sys.setswitchinterval(0.001)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    set_language(load_saved_language() or detect_system_language())
    apply_app_appearance()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(tr("tray_unavailable"), file=sys.stderr)
        return 1

    lock = QLockFile(launcher.lock_path())
    lock.setStaleLockTime(0)
    if not lock.tryLock(6000 if WAIT_LOCK_FLAG in sys.argv[1:] else 100):
        return 0  # ya hay una bandeja activa

    controller = build_controller(app)
    controller.tray.show()
    controller.schedule_startup_check()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
