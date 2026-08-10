"""Página 'Vista general' (Overview): escaneo real + panel de tres columnas.

- Panel izquierdo: gauge radial "SYSTEM HEALTH" (con estado GOOD/FAIR/POOR),
  métricas (basura, huérfanos, entradas sueltas) y botón pastilla
  "SCAN NOW".
- Panel central: "SYSTEM INFORMATION" (CPU/GPU/RAM/DISK) + actividad reciente.
- Panel derecho: "INSTALLED APPLICATIONS" (icono, nombre, versión/fuente,
  botón UNINSTALL, contador) + "SYSTEM CLEANUP RECOMMENDED".

SCAN NOW ejecuta un escaneo real (utils.scan + utils.apps) en segundo plano
y actualiza el gauge, las métricas, la lista de apps y el resumen de
limpieza con datos reales. Toda la lógica es pura y testeable.
"""

import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.utils import theme as theme_mod
from blip_eraser.utils.apps import health_score, kind_label_key, list_installed_apps
from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.confirm import ConfirmItem, build_confirmation_plan
from blip_eraser.utils.file_utils import delete_path, human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.scan import (
    CLEANUP_CATEGORY_LABEL_KEYS,
    scan_cleanup,
    scan_cleanup_items,
)
from blip_eraser.utils.system_stats import (
    cpu_model,
    cpu_usage_percent,
    disk_total_bytes,
    disk_usage_percent,
    gpu_model,
    memory_usage_percent,
    ram_total_bytes,
    read_cpu_sample,
)
from blip_eraser.widgets.confirm_dialog import run_destructive_action
from blip_eraser.widgets.health_gauge import HealthGauge
from blip_eraser.widgets.scan_button import ScanNowButton

_ICON_FALLBACK = "application-x-executable"


class OverviewPage(QWidget):
    uninstall_requested = pyqtSignal(str, str, str)  # (nombre, fuente, detalle)
    _scan_result = pyqtSignal(dict)
    _cleanup_items_ready = pyqtSignal(list)  # entries de scan_cleanup_items()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prev_cpu: tuple[int, int] | None = None
        self._scanning = False
        self._accent = theme_mod.THEMES[load_prefs().get("theme", "red")]["accent"]
        self._apps: list = []
        self._scan_result.connect(self._on_scan_done)
        self._cleanup_items_ready.connect(self._on_cleanup_items_ready)
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        self.refresh()
        log_buffer.subscribe(self._on_log)
        self._scan()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 16)
        outer.setSpacing(12)

        # Header "Overview"
        self.section_header = QLabel(tr("nav_overview"))
        self.section_header.setObjectName("PageTitle")
        outer.addWidget(self.section_header)

        layout = QHBoxLayout()
        layout.setSpacing(16)

        # --- Panel izquierdo: salud + métricas + SCAN NOW ---
        left = QWidget()
        left.setObjectName("PanelCard")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(8)

        self.health_title = QLabel(tr("overview_health_title"))
        self.health_title.setObjectName("PanelTitle")
        self.health_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.health_title)

        self.gauge = HealthGauge()
        self.gauge.set_accent(self._accent)
        left_layout.addWidget(self.gauge)

        # Métricas dentro del gauge (estilo imagen)
        self.metric_junk = QLabel()
        self.metric_orphans = QLabel()
        self.metric_loose = QLabel()
        for metric in (self.metric_junk, self.metric_orphans, self.metric_loose):
            metric.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metric.setStyleSheet("color: #ff5555; font-weight: bold;")
            left_layout.addWidget(metric)

        left_layout.addSpacing(8)

        # Botón SCAN NOW (pastilla con glow e icono)
        accent = theme_mod.THEMES[load_prefs().get("theme", "red")]["accent"]
        self.scan_btn = ScanNowButton(tr("overview_erase_button"), tr("overview_erase_subtitle"))
        self.scan_btn.set_accent(accent)
        self.scan_btn.clicked.connect(self._scan)
        left_layout.addWidget(self.scan_btn)

        left_layout.addStretch(1)

        # --- Panel central: información del sistema ---
        center = QWidget()
        center.setObjectName("PanelCard")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(20, 20, 20, 20)
        center_layout.setSpacing(6)

        self.info_title = QLabel(tr("system_info_title"))
        self.info_title.setObjectName("PanelTitle")
        center_layout.addWidget(self.info_title)

        self.cpu_row = QLabel()
        self.gpu_row = QLabel()
        self.ram_row = QLabel()
        self.disk_row = QLabel()
        for row in (self.cpu_row, self.gpu_row, self.ram_row, self.disk_row):
            row.setWordWrap(True)
            center_layout.addWidget(row)

        center_layout.addSpacing(12)
        self.activity_title = QLabel(tr("recent_activity_title"))
        self.activity_title.setObjectName("PanelTitle")
        center_layout.addWidget(self.activity_title)

        self.activity_list = QLabel(tr("list_empty_subtext"))
        self.activity_list.setWordWrap(True)
        self.activity_list.setObjectName("SubText")
        center_layout.addWidget(self.activity_list)

        center_layout.addStretch(1)

        # --- Panel derecho: apps instaladas + limpieza recomendada ---
        right = QWidget()
        right.setObjectName("PanelCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(8)

        apps_header = QHBoxLayout()
        self.apps_title = QLabel(tr("installed_apps_title"))
        self.apps_title.setObjectName("PanelTitle")
        apps_header.addWidget(self.apps_title)
        self.apps_count = QLabel()
        self.apps_count.setObjectName("AppsBadge")
        apps_header.addStretch(1)
        apps_header.addWidget(self.apps_count)
        right_layout.addLayout(apps_header)

        self._apps_widget = QWidget()
        self._apps_layout = QVBoxLayout(self._apps_widget)
        self._apps_layout.setContentsMargins(0, 0, 0, 0)
        self._apps_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._apps_widget)
        right_layout.addWidget(scroll, 1)

        right_layout.addSpacing(8)
        self.cleanup_title = QLabel(tr("cleanup_recommended_title"))
        self.cleanup_title.setObjectName("PanelTitle")
        right_layout.addWidget(self.cleanup_title)
        self.cleanup_junk_label = QLabel()
        self.cleanup_cache_label = QLabel()
        self.cleanup_logs_label = QLabel()
        for label in (self.cleanup_junk_label, self.cleanup_cache_label, self.cleanup_logs_label):
            label.setStyleSheet("color: #ff5555; font-weight: bold;")
            right_layout.addWidget(label)

        # Acción real conectada al resumen: limpia basura + caché + registros
        # con el mismo flujo (confirmación y borrado) que el Limpiador.
        self.cleanup_btn = QPushButton(tr("cleanup_run_button"))
        self.cleanup_btn.clicked.connect(self._cleanup_now)
        right_layout.addWidget(self.cleanup_btn)
        right_layout.addStretch(0)

        layout.addWidget(left, 3)
        layout.addWidget(center, 4)
        layout.addWidget(right, 4)

        outer.addLayout(layout, 1)

    # ------------------------------------------------------------------
    # Escaneo (SCAN NOW) — en segundo plano para no bloquear la GUI
    # ------------------------------------------------------------------
    def _scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.scan_btn.set_texts(tr("overview_scanning"), tr("overview_erase_subtitle"))
        self.scan_btn.setEnabled(False)

        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        apps = list_installed_apps()
        cleanup = scan_cleanup()
        self._scan_result.emit({"apps": apps, "cleanup": cleanup})

    def _cleanup_now(self):
        """Botón del resumen: limpia basura + caché + registros (fondo, no bloquea)."""
        if self._scanning:
            return
        self.cleanup_btn.setEnabled(False)
        threading.Thread(target=self._cleanup_worker, daemon=True).start()

    def _cleanup_worker(self):
        self._cleanup_items_ready.emit(scan_cleanup_items())

    def _on_cleanup_items_ready(self, entries: list):
        self.cleanup_btn.setEnabled(True)
        if not entries:
            QMessageBox.information(self, tr("done_title"), tr("cleanup_list_empty"))
            return

        items = [
            ConfirmItem(
                label=str(path),
                category_label=tr(
                    CLEANUP_CATEGORY_LABEL_KEYS.get(cat_key, "col_name")
                ),
                size_bytes=size,
                remove=lambda p=path: delete_path(p),
            )
            for cat_key, path, size in entries
        ]
        # Mismo flujo compartido que la sección "Limpieza recomendada".
        run_destructive_action(
            self, build_confirmation_plan(items), tr("cleanup_confirm_title")
        )

    def _on_scan_done(self, result: dict):
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self.scan_btn.set_texts(tr("overview_erase_button"), tr("overview_erase_subtitle"))

        self._apps = result["apps"]
        self._rebuild_apps()

        cleanup = result["cleanup"]
        self.cleanup_junk_label.setText(
            f"{tr('cleanup_junk')}: {human_size(cleanup['junk_bytes'])}"
        )
        self.cleanup_cache_label.setText(
            f"{tr('cleanup_cache')}: {human_size(cleanup['pacman_cache_bytes'])}"
        )
        self.cleanup_logs_label.setText(
            f"{tr('cleanup_logs')}: {human_size(cleanup['logs_bytes'])}"
        )

        total_space = sum(a.size_bytes for a in self._apps)
        log_buffer.add(
            tr("log_scan_completed").format(count=len(self._apps), space=human_size(total_space))
        )

        self.metric_junk.setText(f"{tr('metric_junk')}: {human_size(cleanup['junk_bytes'])}")
        self.metric_orphans.setText(f"{tr('metric_orphans')}: {cleanup['orphan_count']}")
        self.metric_loose.setText(
            f"{tr('metric_loose')}: {sum(1 for a in self._apps if a.source == 'manual')}"
        )
        self.refresh()

    def _rebuild_apps(self):
        while self._apps_layout.count():
            item = self._apps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._apps:
            empty = QLabel(tr("apps_empty"))
            empty.setObjectName("SubText")
            empty.setWordWrap(True)
            self._apps_layout.addWidget(empty)
            self.apps_count.setText(tr("apps_count_label").format(count=0))
            return

        self.apps_count.setText(tr("apps_count_label").format(count=len(self._apps)))
        for app in self._apps:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(8)

            # Icono de la app (por nombre, con respaldo genérico)
            icon = QIcon.fromTheme(app.name.lower(), QIcon.fromTheme(_ICON_FALLBACK))
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(20, 20))
            row_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

            meta = QVBoxLayout()
            meta.setSpacing(0)

            name_row = QHBoxLayout()
            name_row.setSpacing(6)
            name_label = QLabel(app.name)
            name_row.addWidget(name_label)

            # Etiqueta del tipo: aplicación / dependencia / carpeta suelta
            kind_key = kind_label_key(app.kind)
            kind_obj = {
                "app": "KindTagApp",
                "dependency": "KindTagDep",
                "folder": "KindTagFolder",
            }.get(app.kind, "KindTagFolder")
            kind_tag = QLabel(tr(kind_key))
            kind_tag.setObjectName(kind_obj)
            name_row.addWidget(kind_tag)
            name_row.addStretch(1)
            meta.addLayout(name_row)

            sub_label = QLabel(
                f"{app.detail}  |  {human_size(app.size_bytes)}"
                if app.size_bytes
                else app.detail
            )
            sub_label.setObjectName("SubText")
            sub_label.setWordWrap(True)
            meta.addWidget(sub_label)
            row_layout.addLayout(meta, 1)

            uninstall_btn = QPushButton(tr("uninstall_short"))
            uninstall_btn.setObjectName("DangerButton")
            uninstall_btn.clicked.connect(
                lambda _=False, n=app.name, s=app.source, d=app.detail: self.uninstall_requested.emit(n, s, d)
            )
            row_layout.addWidget(uninstall_btn)
            self._apps_layout.addWidget(row)

    # ------------------------------------------------------------------
    # Refresco de métricas del sistema
    # ------------------------------------------------------------------
    def refresh(self):
        sample = read_cpu_sample()
        cpu = cpu_usage_percent(self._prev_cpu, sample)
        self._prev_cpu = sample if sample is not None else self._prev_cpu

        ram = memory_usage_percent()
        disk = disk_usage_percent("/")

        health = health_score(cpu, ram, disk)
        if health is None:
            health = 0
        self.gauge.set_value(health)
        self.gauge.set_status(
            tr("overview_status_good")
            if health >= 70
            else tr("overview_status_fair") if health >= 40 else tr("overview_status_poor")
        )

        na = tr("status_na")
        cpu_model_text = cpu_model() or na
        gpu_model_text = gpu_model() or na
        ram_total = human_size(ram_total_bytes()) if ram_total_bytes() else na
        disk_total = human_size(disk_total_bytes()) if disk_total_bytes() else na

        self.cpu_row.setText(f"{tr('status_cpu')}: {cpu_model_text}  ({cpu}%)" if cpu is not None else f"{tr('status_cpu')}: {cpu_model_text}  ({na})")
        self.gpu_row.setText(f"{tr('gpu_label')}: {gpu_model_text}")
        self.ram_row.setText(f"{tr('status_ram')}: {ram_total}  ({ram}%)" if ram is not None else f"{tr('status_ram')}: {ram_total}  ({na})")
        self.disk_row.setText(f"{tr('status_disk')}: {disk_total}  ({disk}%)" if disk is not None else f"{tr('status_disk')}: {disk_total}  ({na})")

    def _on_log(self, entries: list[tuple[str, str]]):
        recent = entries[-6:]
        if not recent:
            self.activity_list.setText(tr("list_empty_subtext"))
            return
        lines = [f"• {msg}" for _ts, msg in recent]
        self.activity_list.setText("\n".join(lines))

    def retranslate(self):
        self.section_header.setText(tr("nav_overview"))
        self.health_title.setText(tr("overview_health_title"))
        self.scan_btn.set_texts(
            tr("overview_scanning") if self._scanning else tr("overview_erase_button"),
            tr("overview_erase_subtitle"),
        )
        self.info_title.setText(tr("system_info_title"))
        self.activity_title.setText(tr("recent_activity_title"))
        self.apps_title.setText(tr("installed_apps_title"))
        self.cleanup_title.setText(tr("cleanup_recommended_title"))
        if self._apps:
            self._rebuild_apps()
        self.refresh()

    def set_accent(self, color: str):
        self._accent = color
        self.gauge.set_accent(color)
        self.scan_btn.set_accent(color)