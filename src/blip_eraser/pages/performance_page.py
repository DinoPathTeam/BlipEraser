"""Página 'Ajustes de rendimiento': opciones seleccionables.

Por ahora es presentación con interruptores visibles; las acciones
efectivas llegarán en fases posteriores (solo estética, sin ejecutar nada
todavía). Cada opción muestra un ícono de ayuda (?) con tooltip explicativo
y un mini gráfico de vista previa del recurso que afecta (disco/RAM/red).

Al activar cualquiera de las opciones, se muestra un aviso informativo
recomendando reiniciar para que el cambio tome efecto completo.
"""

from PyQt6.QtCore import QRectF, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils import theme as theme_mod
from blip_eraser.utils.config import load_prefs, save_prefs
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.performance import (
    check_tweak_state,
    apply_tweak,
    get_all_tweak_states,
    TweakResult,
)

_PERF_OPTIONS = [
    {
        "key": "perf_trim_mounts",
        "desc": "perf_trim_mounts_help",
        "tip": "perf_trim_mounts_tip",
        "effect": "perf_effect_disk",
        "level": 0.70,
    },
    {
        "key": "perf_compress_ram",
        "desc": "perf_compress_ram_help",
        "tip": "perf_compress_ram_tip",
        "effect": "perf_effect_ram",
        "level": 0.62,
    },
    {
        "key": "perf_mirror_sort",
        "desc": "perf_mirror_sort_help",
        "tip": "perf_mirror_sort_tip",
        "effect": "perf_effect_network",
        "level": 0.80,
    },
]


class _EffectPreview(QWidget):
    """Mini gráfico de vista previa: recurso afectado + barra de impacto.

    Puramente decorativo (no lee métricas reales): muestra el recurso que
    toca cada ajuste y una barra con un brillo sutil que recorre el relleno.
    """

    def __init__(self, label: str = "", level: float = 0.65, accent: str = "#E53935", parent=None):
        super().__init__(parent)
        self._label = label
        self._level = max(0.0, min(1.0, level))
        self._accent = QColor(accent)
        self._phase = 0.0
        self.setFixedHeight(28)
        self.setMinimumWidth(150)

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def set_accent(self, accent: str) -> None:
        self._accent = QColor(accent)
        self.update()

    def tick(self) -> None:
        self._phase = (self._phase + 0.05) % 1.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        height = self.height()
        width = self.width()

        # Etiqueta del recurso (Disco / RAM / Red)
        label_font = QFont(self.font())
        label_font.setPointSize(8)
        painter.setFont(label_font)
        painter.setPen(QColor(154, 154, 162))
        painter.drawText(
            QRectF(0, 0, 58, height),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._label,
        )

        track_x = 64.0
        track_w = width - track_x - 24.0
        track_y = (height - 8) / 2.0
        fill_w = max(8.0, track_w * self._level)

        # Pista
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._accent)
        painter.setOpacity(0.18)
        painter.drawRoundedRect(QRectF(track_x, track_y, track_w, 8), 4, 4)

        # Relleno (impacto estimado)
        painter.setOpacity(0.95)
        painter.setBrush(self._accent)
        painter.drawRoundedRect(QRectF(track_x, track_y, fill_w, 8), 4, 4)

        # Brillo sutil que recorre el relleno (animación decorativa)
        if fill_w > 14:
            sweep_x = track_x + (fill_w - 14) * self._phase
            glow = QLinearGradient(sweep_x - 8, 0, sweep_x + 8, 0)
            glow.setColorAt(0.0, QColor(255, 255, 255, 0))
            glow.setColorAt(0.5, QColor(255, 255, 255, 130))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setOpacity(1.0)
            painter.setBrush(glow)
            painter.drawRoundedRect(QRectF(sweep_x - 8, track_y - 2, 16, 12), 6, 6)

        painter.end()


class _TweakWorker(QThread):
    """Aplica un tweak en fondo (systemd/pkexec pueden tardar). Una sola definición
    a nivel de módulo: antes se redefinía en cada toggle."""

    finished = pyqtSignal(object)  # TweakResult

    def __init__(self, k: str, enable: bool):
        super().__init__()
        self._key = k
        self._enable = enable

    def run(self):
        self.finished.emit(apply_tweak(self._key, self._enable))


class PerformancePage(BasePage):
    # Si pkexec/systemd cuelga, no dejar la fila bloqueada para siempre.
    _TWEAK_TIMEOUT_MS = 120_000

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []
        self._previews: list[_EffectPreview] = []
        self._reboot_banner: QLabel | None = None
        self._applying: set[str] = set()  # keys being applied (prevent re-entry)
        self._workers: dict[str, QThread] = {}  # vivos mientras aplican (anti-GC)
        accent = theme_mod.THEMES[load_prefs().get("theme", "red")]["accent"]
        self._build_ui(accent)
        # Cargar estado persistido y sincronizar con sistema real
        self._sync_initial_state()

    def _build_ui(self, accent: str):
        layout = QVBoxLayout(self)

        title = QLabel(tr("performance_title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel(tr("performance_hint"))
        hint.setObjectName("SubText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Banner de aviso (inicialmente oculto)
        self._reboot_banner = QLabel(tr("perf_reboot_recommended"))
        self._reboot_banner.setObjectName("RebootBanner")
        self._reboot_banner.setWordWrap(True)
        self._reboot_banner.setVisible(False)
        layout.addWidget(self._reboot_banner)

        layout.addSpacing(16)

        for opt in _PERF_OPTIONS:
            block = QVBoxLayout()
            block.setSpacing(4)

            header_row = QHBoxLayout()
            header_row.setSpacing(10)

            box = QCheckBox(tr(opt["key"]))
            box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            # Conectar cambio de estado real (usuario hace clic)
            box.toggled.connect(lambda checked, k=opt["key"]: self._on_tweak_toggled(k, checked))
            header_row.addWidget(box, 1)

            preview = _EffectPreview(tr(opt["effect"]), opt["level"], accent)
            self._previews.append(preview)
            header_row.addWidget(preview, 0, Qt.AlignmentFlag.AlignVCenter)

            help_btn = QToolButton()
            help_btn.setObjectName("HelpIcon")
            help_btn.setText("?")
            help_btn.setToolTip(tr(opt["tip"]))
            help_btn.setCursor(Qt.CursorShape.WhatsThisCursor)
            tip_key = opt["tip"]
            desc_key = opt["desc"]
            help_btn.clicked.connect(
                lambda _checked=False, b=help_btn, k=tip_key: self._show_tip(b, tr(k))
            )
            header_row.addWidget(help_btn, 0, Qt.AlignmentFlag.AlignVCenter)

            block.addLayout(header_row)

            desc = QLabel(tr(opt["desc"]))
            desc.setObjectName("SubText")
            desc.setWordWrap(True)
            desc.setContentsMargins(2, 0, 0, 0)
            block.addWidget(desc)

            layout.addLayout(block)
            self._rows.append({
                "key": opt["key"],
                "checkbox": box,
                "desc": desc,
                "help_btn": help_btn,
                "tip_key": tip_key,
                "desc_key": desc_key,
                "preview": preview,
                "effect_key": opt["effect"],
            })

        layout.addStretch(1)

        self._anim = QTimer(self)
        self._anim.timeout.connect(self._animate_previews)

    def _sync_initial_state(self) -> None:
        """Carga estado persistido y verifica estado real en el sistema."""
        prefs = load_prefs()
        system_states = get_all_tweak_states()

        for row in self._rows:
            key = row["key"]
            checkbox = row["checkbox"]
            
            # Estado persistido en config
            persisted = prefs.get(key, False)
            # Estado real en el sistema
            actual = system_states.get(key, False)
            
            # Usar estado real como fuente de verdad, pero persistir la intención del usuario
            checkbox.blockSignals(True)
            checkbox.setChecked(actual)
            checkbox.blockSignals(False)
            
            # Si config dice True pero sistema dice False, sincronizar config
            if persisted != actual:
                save_prefs({key: actual})

        self._update_reboot_banner()

    def _on_tweak_toggled(self, key: str, checked: bool) -> None:
        """Maneja toggle de checkbox: aplica tweak real y actualiza UI/config."""
        if key in self._applying:
            return  # Evitar re-entrada si la operación tarda
        
        self._applying.add(key)
        
        # Encontrar row
        row = next((r for r in self._rows if r["key"] == key), None)
        if not row:
            self._applying.discard(key)
            return
        
        checkbox = row["checkbox"]
        
        # Deshabilitar checkbox durante la operación
        checkbox.setEnabled(False)

        # Ejecutar en hilo para no bloquear UI (operaciones systemd/pkexec pueden tardar)
        def on_finished(result: TweakResult):
            if self._workers.pop(key, None) is None:
                return  # ya gestionado por el timeout
            self._applying.discard(key)
            checkbox.setEnabled(True)

            if result.success:
                # Guardar intención del usuario en config
                save_prefs({key: checked})
                # Verificar estado real post-operación
                actual = check_tweak_state(key)
                checkbox.blockSignals(True)
                checkbox.setChecked(actual)
                checkbox.blockSignals(False)

                # Mostrar mensaje de éxito
                msg = result.message
                if result.installed_deps:
                    msg += " (dependencias instaladas)"
                if result.needs_reboot:
                    msg += " — " + tr("perf_reboot_required")
                self._show_status(msg, success=True)
            else:
                # Revertir checkbox si falló
                checkbox.blockSignals(True)
                checkbox.setChecked(not checked)
                checkbox.blockSignals(False)
                self._show_status(f"Error: {result.message}", success=False)

            self._update_reboot_banner()
            worker.deleteLater()

        def on_timeout():
            worker = self._workers.pop(key, None)
            if worker is None:
                return  # terminó a tiempo
            worker.terminate()
            worker.wait(3000)
            worker.deleteLater()
            self._applying.discard(key)
            checkbox.blockSignals(True)
            checkbox.setChecked(not checked)
            checkbox.blockSignals(False)
            checkbox.setEnabled(True)
            self._show_status(tr("perf_timeout"), success=False)
            self._update_reboot_banner()

        worker = _TweakWorker(key, checked)
        self._workers[key] = worker
        worker.finished.connect(on_finished)
        worker.start()
        QTimer.singleShot(self._TWEAK_TIMEOUT_MS, on_timeout)

    def _show_status(self, message: str, success: bool) -> None:
        """Muestra mensaje temporal en el banner (reusa reboot_banner)."""
        if self._reboot_banner is None:
            return
        self._reboot_banner.setText(message)
        self._reboot_banner.setObjectName("StatusBanner" if success else "ErrorBanner")
        self._reboot_banner.setVisible(True)
        # Volver al estado normal tras 5s
        QTimer.singleShot(5000, self._update_reboot_banner)

    def _update_reboot_banner(self) -> None:
        """Muestra u oculta el banner según checkboxes marcados."""
        if self._reboot_banner is None:
            return
        any_checked = any(r["checkbox"].isChecked() for r in self._rows)
        if any_checked:
            self._reboot_banner.setText(tr("perf_reboot_recommended"))
            self._reboot_banner.setObjectName("RebootBanner")
            self._reboot_banner.setVisible(True)
        else:
            self._reboot_banner.setVisible(False)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_anim"):
            self._anim.start(80)

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_anim"):
            self._anim.stop()

    @staticmethod
    def _show_tip(button: QToolButton, text: str) -> None:
        QToolTip.showText(button.mapToGlobal(button.rect().bottomLeft()), text)

    def _animate_previews(self) -> None:
        for preview in self._previews:
            preview.tick()

    def retranslate(self):
        for row in self._rows:
            row["checkbox"].setText(tr(row["key"]))
            row["desc"].setText(tr(row["desc_key"]))
            row["help_btn"].setToolTip(tr(row["tip_key"]))
            row["preview"].set_label(tr(row["effect_key"]))
        if self._reboot_banner is not None:
            self._reboot_banner.setText(tr("perf_reboot_recommended"))