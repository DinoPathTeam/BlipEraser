"""Página 'Ajustes de rendimiento': opciones seleccionables.

Por ahora es presentación con interruptores visibles; las acciones
efectivas llegarán en fases posteriores (solo estética, sin ejecutar nada
todavía). Cada opción muestra un ícono de ayuda (?) con tooltip explicativo
y un mini gráfico de vista previa del recurso que afecta (disco/RAM/red).
"""

from PyQt6.QtCore import QRectF, QTimer, Qt
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
from blip_eraser.utils.config import load_prefs
from blip_eraser.utils.i18n import tr

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


class PerformancePage(BasePage):
    def __init__(self):
        super().__init__()
        self._rows: list[tuple[QCheckBox, str, QLabel, QToolButton, str, str, _EffectPreview, str]] = []
        self._previews: list[_EffectPreview] = []
        accent = theme_mod.THEMES[load_prefs().get("theme", "red")]["accent"]
        self._build_ui(accent)

    def _build_ui(self, accent: str):
        layout = QVBoxLayout(self)

        title = QLabel(tr("performance_title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel(tr("performance_hint"))
        hint.setObjectName("SubText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(16)

        for opt in _PERF_OPTIONS:
            block = QVBoxLayout()
            block.setSpacing(4)

            header_row = QHBoxLayout()
            header_row.setSpacing(10)

            box = QCheckBox(tr(opt["key"]))
            box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
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

            # Descripción breve visible bajo el nombre de la opción.
            desc = QLabel(tr(opt["desc"]))
            desc.setObjectName("SubText")
            desc.setWordWrap(True)
            desc.setContentsMargins(2, 0, 0, 0)
            block.addWidget(desc)

            layout.addLayout(block)
            self._rows.append((box, opt["key"], desc, help_btn, tip_key, desc_key, preview, opt["effect"]))

        layout.addStretch(1)

        # El timer solo avanza mientras la página es visible: se arranca en
        # showEvent y se detiene en hideEvent para no animar en segundo plano
        # cuando el usuario navega a otra sección del QStackedWidget.
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._animate_previews)

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
        for box, box_key, desc, help_btn, tip_key, desc_key, preview, effect_key in self._rows:
            box.setText(tr(box_key))
            desc.setText(tr(desc_key))
            help_btn.setToolTip(tr(tip_key))
            preview.set_label(tr(effect_key))