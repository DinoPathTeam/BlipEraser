"""Ventanita de la bandeja: estado del sistema + escanear/limpiar/abrir.

Sigue el tema y la fuente elegidos en la app principal (se relee `prefs.json`
cada vez que se abre). No ejecuta nada por sí misma: solo emite señales; el
controlador decide qué hacer.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blip_eraser import __version__
from blip_eraser.utils import theme as theme_mod
from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import tr

POPUP_WIDTH = 300
# Un clic en el icono con la ventanita abierta la cierra (por ser Popup) y a
# continuación llega como "activado": se ignora si acaba de cerrarse.
REOPEN_GUARD_SECONDS = 0.35


def _bar_qss(theme_key: str) -> str:
    theme = theme_mod.THEMES.get(theme_key, theme_mod.THEMES["red"])
    accent, p = theme["accent"], theme["palette"]
    return (
        f"QWidget#TrayPopup {{ background-color: {p['bg']}; border: 1px solid {accent};"
        " border-radius: 10px; }"
        f"QProgressBar {{ background-color: {p['panel']}; border: 1px solid {p['border']};"
        f" border-radius: 5px; min-height: 14px; max-height: 14px; text-align: center;"
        f" color: {p['text']}; font-size: 10px; }}"
        f"QProgressBar::chunk {{ background-color: {accent}; border-radius: 4px; }}"
        f"QPushButton#TrayLink {{ background: transparent; color: {p['subtext']};"
        " border: none; padding: 6px; }"
        f"QPushButton#TrayLink:hover {{ color: {accent}; }}"
        f"QPushButton:disabled {{ color: {p['subtext']}; border-color: {p['border']};"
        f" background-color: {p['panel']}; }}"
    )


class TrayPopup(QWidget):
    scan_requested = pyqtSignal()
    clean_requested = pyqtSignal()
    open_requested = pyqtSignal()
    dragged_to = pyqtSignal(int, int)  # posición final tras arrastrar (no Wayland)

    def __init__(self) -> None:
        # NO es Qt.Popup: en Wayland un popup con "grab" exige una ventana padre
        # que haya recibido input, y la bandeja no la tiene ("Failed to create
        # grabbing popup"). Ventana normal sin marco; se cierra al perder el foco.
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("TrayPopup")
        self.setFixedWidth(POPUP_WIDTH)
        self._closed_at = 0.0
        self._was_active = False
        self._drag_offset: QPoint | None = None
        self._dragged = False
        self._busy = False
        self._recoverable: int | None = None
        self._theme_key = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        self.title = QLabel("BlipEraser")
        self.title.setObjectName("AppTitle")
        self.version = QLabel(f"v{__version__}")
        self.version.setObjectName("SubText")
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.version)
        root.addLayout(head)

        card = QWidget()
        card.setObjectName("PanelCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        self._labels: dict[str, QLabel] = {}
        self._bars: dict[str, QProgressBar] = {}
        for key in ("cpu", "ram", "disk"):
            row = QHBoxLayout()
            label = QLabel()
            label.setFixedWidth(48)
            bar = QProgressBar()
            bar.setRange(0, 100)
            row.addWidget(label)
            row.addWidget(bar, 1)
            card_layout.addLayout(row)
            self._labels[key] = label
            self._bars[key] = bar
        root.addWidget(card)

        rec = QHBoxLayout()
        self.recoverable_title = QLabel()
        self.recoverable_title.setObjectName("PanelTitle")
        self.recoverable_value = QLabel()
        rec.addWidget(self.recoverable_title)
        rec.addStretch(1)
        rec.addWidget(self.recoverable_value)
        root.addLayout(rec)

        buttons = QHBoxLayout()
        self.scan_btn = QPushButton()
        self.scan_btn.setObjectName("DangerButton")
        self.clean_btn = QPushButton()
        self.clean_btn.setObjectName("PrimaryButton")
        buttons.addWidget(self.scan_btn)
        buttons.addWidget(self.clean_btn)
        root.addLayout(buttons)

        self.open_btn = QPushButton()
        self.open_btn.setObjectName("TrayLink")
        root.addWidget(self.open_btn)

        self.scan_btn.clicked.connect(self.scan_requested.emit)
        self.clean_btn.clicked.connect(self.clean_requested.emit)
        self.open_btn.clicked.connect(self.open_requested.emit)

        self.retranslate()
        self.set_stats(None, None, None, None)
        self.set_busy(False)

    # -- texto y tema -----------------------------------------------------
    def retranslate(self) -> None:
        self._labels["cpu"].setText(tr("status_cpu"))
        self._labels["ram"].setText(tr("status_ram"))
        self._labels["disk"].setText(tr("status_disk"))
        self.recoverable_title.setText(tr("tray_recoverable_title"))
        self.clean_btn.setText(tr("tray_clean"))
        self.open_btn.setText(tr("tray_open"))
        self.scan_btn.setText(tr("tray_scanning") if self._busy else tr("tray_scan"))

    def apply_theme(self) -> None:
        """Relee el tema de la app principal; solo restila si cambió."""
        key = load_prefs().get("theme")
        if key not in theme_mod.THEMES:
            key = "red"
        if key == self._theme_key:
            return
        self._theme_key = key
        self.setStyleSheet(theme_mod.build_qss(key) + _bar_qss(key))

    # -- estado -----------------------------------------------------------
    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.scan_btn.setText(tr("tray_scanning") if busy else tr("tray_scan"))
        self.scan_btn.setEnabled(not busy)
        self._sync_clean_enabled()

    def _sync_clean_enabled(self) -> None:
        self.clean_btn.setEnabled(not self._busy and bool(self._recoverable))

    def set_stats(
        self,
        cpu: int | None,
        ram: int | None,
        disk: int | None,
        recoverable: int | None,
    ) -> None:
        na = tr("status_na")
        for key, value in (("cpu", cpu), ("ram", ram), ("disk", disk)):
            bar = self._bars[key]
            bar.setValue(value or 0)
            bar.setFormat(f"{value}%" if value is not None else na)
        self._recoverable = recoverable
        self.recoverable_value.setText(human_size(recoverable) if recoverable is not None else na)
        self._sync_clean_enabled()

    def set_calculating(self) -> None:
        self.recoverable_value.setText(tr("tray_calculating"))

    # -- mostrar ----------------------------------------------------------
    def recently_closed(self) -> bool:
        return time.monotonic() - self._closed_at < REOPEN_GUARD_SECONDS

    def hideEvent(self, event) -> None:  # noqa: N802 - API de Qt
        self._closed_at = time.monotonic()
        self._was_active = False
        if self._dragged:
            self._dragged = False
            # En Wayland la posición de la ventana no es legible ni respetada:
            # solo se recuerda donde la plataforma la controla (X11/XWayland).
            if QGuiApplication.platformName() != "wayland":
                self.dragged_to.emit(self.x(), self.y())
        super().hideEvent(event)

    def _try_system_move(self) -> bool:
        handle = self.windowHandle()
        return bool(handle is not None and handle.startSystemMove())

    # -- arrastrar la ventanita desde cualquier zona que no sea un botón ----
    def mousePressEvent(self, event) -> None:  # noqa: N802 - API de Qt
        if event.button() == Qt.MouseButton.LeftButton:
            # El propio compositor mueve la ventana (funciona también en Wayland).
            if self._try_system_move():
                self._dragged = True
                event.accept()
                return
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - API de Qt
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._dragged = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - API de Qt
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802 - API de Qt
        if event.type() == QEvent.Type.ActivationChange and self.isVisible():
            if self.isActiveWindow():
                self._was_active = True
            elif self._was_active:
                # Perdió el foco (clic fuera, otra ventana): se cierra.
                QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - API de Qt
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def show_at(self, pos: tuple[int, int]) -> None:
        self.apply_theme()
        self.retranslate()
        self.adjustSize()
        self.move(*pos)
        self.show()
        self.raise_()
        self.activateWindow()
