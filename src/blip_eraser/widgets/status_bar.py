"""Barra de estado del sistema: CPU / RAM / disco, refrescada por QTimer.

Las métricas vienen de utils.system_stats (lógica pura y testable);
aquí solo se muestran y se localizan con tr().
"""

import html

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QStatusBar

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.system_stats import (
    cpu_usage_percent,
    disk_usage_percent,
    memory_usage_percent,
    read_cpu_sample,
)


RELEASES_URL = "https://github.com/DinoPathTeam/BlipEraser/releases/latest"


class SystemStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._prev_cpu: tuple[int, int] | None = None
        self._update_version: str | None = None
        self._update_label: QLabel | None = None

        self._cpu_parts = {"label": tr("status_cpu"), "value": QLabel()}
        self._ram_parts = {"label": tr("status_ram"), "value": QLabel()}
        self._disk_parts = {"label": tr("status_disk"), "value": QLabel()}

        for part in (self._cpu_parts, self._ram_parts, self._disk_parts):
            part["value"].setObjectName("StatusValue")
            self.addPermanentWidget(part["value"])

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)

        self.refresh()

    def show_update_available(self, version: str) -> None:
        """Aviso discreto (sin diálogo) de que hay una versión nueva."""
        self._update_version = version
        if self._update_label is None:
            label = QLabel()
            label.setObjectName("UpdateNotice")
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setOpenExternalLinks(True)
            self.addWidget(label)
            self._update_label = label
        self._render_update_notice()

    def _render_update_notice(self) -> None:
        if self._update_label is None or self._update_version is None:
            return
        text = tr("update_available").format(version=html.escape(self._update_version))
        link = f'<a href="{RELEASES_URL}">{html.escape(tr("update_view"))}</a>'
        self._update_label.setText(f"{text} · {link}")

    def retranslate(self) -> None:
        self._render_update_notice()
        self._cpu_parts["label"] = tr("status_cpu")
        self._ram_parts["label"] = tr("status_ram")
        self._disk_parts["label"] = tr("status_disk")
        self.refresh()

    def refresh(self) -> None:
        sample = read_cpu_sample()
        cpu = cpu_usage_percent(self._prev_cpu, sample)
        self._prev_cpu = sample if sample is not None else self._prev_cpu

        ram = memory_usage_percent()
        disk = disk_usage_percent("/")

        na = tr("status_na")
        self._cpu_parts["value"].setText(
            f"{self._cpu_parts['label']}: {cpu}%" if cpu is not None else f"{self._cpu_parts['label']}: {na}"
        )
        self._ram_parts["value"].setText(
            f"{self._ram_parts['label']}: {ram}%" if ram is not None else f"{self._ram_parts['label']}: {na}"
        )
        self._disk_parts["value"].setText(
            f"{self._disk_parts['label']}: {disk}%" if disk is not None else f"{self._disk_parts['label']}: {na}"
        )