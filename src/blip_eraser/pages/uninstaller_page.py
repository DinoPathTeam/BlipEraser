"""Página 'Desinstalador': aplicaciones instaladas con desinstalación.

Lista las aplicaciones detectadas (utils.apps.list_installed_apps) y
desinstala con privilegios según la fuente: pacman o borrado manual.
Presentación únicamente; la lógica vive en utils. La confirmación usa el
diálogo compartido (widgets/confirm_dialog, basado en utils.confirm), el
mismo que el Limpiador del sistema.
"""

from pathlib import Path
from typing import Any, Literal, cast

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from blip_eraser.pages.base import BasePage
from blip_eraser.utils.apps import (
    KIND_APP,
    KIND_FOLDER,
    InstalledApp,
    kind_label_key,
    list_installed_apps,
)
from blip_eraser.utils.confirm import ConfirmItem, build_confirmation_plan
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.log import write_diagnostic
from blip_eraser.utils.scan_cache import SECTION_UNINSTALLER, is_stale, mark_scanned
from blip_eraser.utils.table_filters import (
    DateFilterMode,
    FilterState,
    WeightFilterMode,
    filter_apps,
    get_available_types,
    get_type_display_names,
    parse_size_threshold,
)
from blip_eraser.widgets.check_table import CheckTable
from blip_eraser.widgets.confirm_dialog import run_destructive_action
from blip_eraser.widgets.scan_worker import BackgroundScanMixin

_COLUMNS = 6  # Sel | Nombre | Tipo | Detalle | Peso | Fecha


def _manual_target(app: InstalledApp) -> Path:
    """Ruta real a borrar para una app manual (carpeta suelta/AppImage)."""
    return Path(app.detail) if app.detail else Path.home() / app.name


class UninstallerPage(BasePage, BackgroundScanMixin):
    def __init__(self):
        super().__init__()
        self._apps: list[InstalledApp] = []
        self._visible: list[InstalledApp] = []
        self._filter = ""
        self._filter_state = FilterState()
        self._build_ui()
        self._init_scan_buttons([self.refresh_btn, self.uninstall_btn])

        write_diagnostic(
            f"UninstallerPage CREATED id={id(self)} table_id={id(self.table)}"
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(tr("uninstaller_info"))
        layout.addWidget(self.info_label)

        # Toolbar de filtros
        filter_bar = self._build_filter_toolbar()
        layout.addWidget(filter_bar)

        # Sin checkbox de "seleccionar todo" en el encabezado: el
        # Desinstalador solo permite selección manual (una a una o
        # arrastrando) para evitar desinstalaciones masivas accidentales.
        self.table = CheckTable(_COLUMNS, show_select_all=False)
        cast(Any, self.table).setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_type"), tr("col_detail"), tr("col_weight"), tr("col_date")]
        )
        header = cast(QHeaderView, self.table.horizontalHeader())
        # Columnas redimensionables arrastrando el borde (Interactive).
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        for idx, width in ((1, 200), (2, 130), (3, 320), (4, 90), (5, 130)):
            self.table.setColumnWidth(idx, width)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("refresh_button"))
        cast(Any, self.refresh_btn.clicked).connect(self.load_apps)
        btn_row.addWidget(self.refresh_btn)

        self.uninstall_btn = QPushButton(tr("uninstall_button_count").format(n=0))
        self.uninstall_btn.setEnabled(False)
        cast(Any, self.uninstall_btn.clicked).connect(self.uninstall_selected)
        btn_row.addWidget(self.uninstall_btn)

        layout.addLayout(btn_row)

        cast(Any, self.table.itemChanged).connect(self._update_uninstall_btn)

    def _build_filter_toolbar(self) -> QWidget:
        """Construye la barra de filtros: Tipo / Peso / Fecha / Limpiar."""
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        # --- Tipo (multi-selección) ---
        self.filter_type_label = QLabel(tr("filter_type_label"))
        row.addWidget(self.filter_type_label)

        self.filter_type_button = QToolButton()
        self.filter_type_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.filter_type_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.filter_type_button.setMinimumWidth(140)
        self.filter_type_button.setToolTip(tr("filter_type_all"))
        self._populate_type_button()
        row.addWidget(self.filter_type_button)

        # --- Peso ---
        self.filter_weight_label = QLabel(tr("filter_weight_label"))
        row.addWidget(self.filter_weight_label)

        self.filter_weight_combo = QComboBox()
        self._populate_weight_combo()
        row.addWidget(self.filter_weight_combo)

        self.filter_weight_threshold = QLineEdit()
        self.filter_weight_threshold.setPlaceholderText(tr("filter_weight_threshold"))
        self.filter_weight_threshold.setMaximumWidth(120)
        self.filter_weight_threshold.setVisible(False)
        row.addWidget(self.filter_weight_threshold)

        # --- Fecha ---
        self.filter_date_label = QLabel(tr("filter_date_label"))
        row.addWidget(self.filter_date_label)

        self.filter_date_combo = QComboBox()
        self._populate_date_combo()
        row.addWidget(self.filter_date_combo)

        self.filter_date_format = QComboBox()
        cast(Any, self.filter_date_format).addItems(["AUTO", "DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD", "DD-MM-YYYY"])
        self.filter_date_format.setCurrentText(self._filter_state.date_format)
        self.filter_date_format.setToolTip(tr("filter_date_format_hint"))
        self.filter_date_format.setVisible(False)
        row.addWidget(self.filter_date_format)

        self.filter_date_from = QDateEdit()
        self.filter_date_from.setCalendarPopup(True)
        self.filter_date_from.setDisplayFormat("dd/MM/yyyy")
        self.filter_date_from.setVisible(False)
        row.addWidget(self.filter_date_from)

        self.filter_date_to_label = QLabel(tr("filter_date_to"))
        self.filter_date_to_label.setVisible(False)
        row.addWidget(self.filter_date_to_label)

        self.filter_date_to = QDateEdit()
        self.filter_date_to.setCalendarPopup(True)
        self.filter_date_to.setDisplayFormat("dd/MM/yyyy")
        self.filter_date_to.setVisible(False)
        row.addWidget(self.filter_date_to)

        # --- Limpiar filtros ---
        self.filter_clear_btn = QPushButton(tr("filter_clear"))
        row.addWidget(self.filter_clear_btn)

        row.addStretch(1)

        # Conexiones
        cast(Any, self.filter_weight_combo.currentIndexChanged).connect(self._on_weight_filter_changed)
        cast(Any, self.filter_weight_threshold.editingFinished).connect(self._on_weight_threshold_changed)
        cast(Any, self.filter_date_combo.currentIndexChanged).connect(self._on_date_filter_changed)
        cast(Any, self.filter_date_format.currentTextChanged).connect(self._on_date_format_changed)
        cast(Any, self.filter_date_from.dateChanged).connect(self._on_date_range_changed)
        cast(Any, self.filter_date_to.dateChanged).connect(self._on_date_range_changed)
        cast(Any, self.filter_clear_btn.clicked).connect(self._clear_filters)

        return bar

    def _populate_type_button(self):
        """Llena el botón de Tipo con menú de acciones checkeables (multi-selección)."""
        menu = QMenu(self.filter_type_button)
        self._type_actions: dict[str, QAction] = {}

        # Opción "Todos"
        all_action = cast(QAction, cast(Any, menu).addAction(tr("filter_type_all")))
        all_action.setCheckable(True)
        all_action.setChecked(True)
        cast(Any, all_action.toggled).connect(self._on_type_all_toggled)
        self._type_actions["all"] = all_action

        menu.addSeparator()

        type_names = get_type_display_names(get_available_types())
        for kind_key, display in type_names.items():
            action = cast(QAction, cast(Any, menu).addAction(display))
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(kind_key)
            cast(Any, action.toggled).connect(self._on_type_item_toggled)
            self._type_actions[kind_key] = action

        self.filter_type_button.setMenu(menu)
        self._update_type_button_text()

    def _populate_weight_combo(self):
        """Llena el combo de Peso."""
        self.filter_weight_combo.clear()
        modes = [
            (WeightFilterMode.ALL, tr("filter_weight_all")),
            (WeightFilterMode.HEAVIEST_FIRST, tr("filter_weight_heaviest")),
            (WeightFilterMode.LIGHTEST_FIRST, tr("filter_weight_lightest")),
            (WeightFilterMode.ONLY_HEAVY, tr("filter_weight_only_heavy")),
            (WeightFilterMode.ONLY_LIGHT, tr("filter_weight_only_light")),
        ]
        for mode, label in modes:
            self.filter_weight_combo.addItem(label, mode)
        self.filter_weight_combo.setCurrentIndex(0)

    def _populate_date_combo(self):
        """Llena el combo de Fecha."""
        self.filter_date_combo.clear()
        modes = [
            (DateFilterMode.ALL, tr("filter_date_all")),
            (DateFilterMode.NEWEST_FIRST, tr("filter_date_newest")),
            (DateFilterMode.OLDEST_FIRST, tr("filter_date_oldest")),
            (DateFilterMode.CUSTOM_RANGE, tr("filter_date_custom")),
        ]
        for mode, label in modes:
            self.filter_date_combo.addItem(label, mode)
        self.filter_date_combo.setCurrentIndex(0)

    def _update_type_button_text(self) -> None:
        """Actualiza el texto visible del botón de Tipo según selección."""
        checked = [k for k, a in self._type_actions.items() if k != "all" and a.isChecked()]
        if not checked:
            self.filter_type_button.setText(tr("filter_type_all"))
            self.filter_type_button.setToolTip(tr("filter_type_all"))
        elif len(checked) == len(self._type_actions) - 1:  # todos menos "all"
            self.filter_type_button.setText(tr("filter_type_all"))
            self.filter_type_button.setToolTip(tr("filter_type_all"))
        else:
            labels = [self._type_actions[k].text() for k in checked]
            self.filter_type_button.setText(", ".join(labels))
            self.filter_type_button.setToolTip(", ".join(labels))

    def _on_type_all_toggled(self, checked: bool):
        """Al marcar/desmarcar 'Todos', marca/desmarca todos los items."""
        for k, a in self._type_actions.items():
            if k != "all":
                a.blockSignals(True)
                a.setChecked(checked)
                a.blockSignals(False)
        self._update_type_button_text()
        self._apply_type_filter()

    def _on_type_item_toggled(self, _checked: bool):
        """Al cambiar un item individual, actualiza 'Todos' y filtro."""
        all_checked = all(a.isChecked() for k, a in self._type_actions.items() if k != "all")
        self._type_actions["all"].blockSignals(True)
        self._type_actions["all"].setChecked(all_checked)
        self._type_actions["all"].blockSignals(False)
        self._update_type_button_text()
        self._apply_type_filter()

    def _apply_type_filter(self):
        """Aplica el filtro de Tipo al FilterState y re-renderiza."""
        checked = {k for k, a in self._type_actions.items() if k != "all" and a.isChecked()}
        if len(checked) == len(self._type_actions) - 1 or not checked:
            self._filter_state.type_filter = None
        else:
            self._filter_state.type_filter = checked
        self._render()

    def _on_weight_filter_changed(self, _index: int):
        """Aplica el filtro de Peso al cambiar el combo."""
        mode = self.filter_weight_combo.currentData()
        self._filter_state.weight_mode = mode
        show_threshold = mode in (WeightFilterMode.ONLY_HEAVY, WeightFilterMode.ONLY_LIGHT)
        self.filter_weight_threshold.setVisible(show_threshold)
        self._render()

    def _on_weight_threshold_changed(self):
        """Aplica el umbral de peso al terminar de editar."""
        text = self.filter_weight_threshold.text().strip()
        if not text:
            self._filter_state.weight_threshold_bytes = None
        else:
            self._filter_state.weight_threshold_bytes = parse_size_threshold(text)
        self._render()

    def _on_date_filter_changed(self, _index: int):
        """Aplica el filtro de Fecha al cambiar el combo."""
        mode = self.filter_date_combo.currentData()
        self._filter_state.date_mode = mode
        is_custom = mode == DateFilterMode.CUSTOM_RANGE
        self.filter_date_format.setVisible(is_custom)
        self.filter_date_from.setVisible(is_custom)
        self.filter_date_to_label.setVisible(is_custom)
        self.filter_date_to.setVisible(is_custom)
        self._render()

    def _on_date_format_changed(self, text: str):
        """Aplica el formato de fecha elegido."""
        if text in {"DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD", "DD-MM-YYYY", "AUTO"}:
            self._filter_state.date_format = cast(
                Literal["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD", "DD-MM-YYYY", "AUTO"],
                text,
            )
        self._render()

    def _on_date_range_changed(self):
        """Aplica el rango de fechas al cambiar los QDateEdit.

        Guarda el rango en el formato preferido por el usuario para que
        parse_date_flexible pueda parsearlo correctamente con el mismo formato.
        """
        if self._filter_state.date_mode == DateFilterMode.CUSTOM_RANGE:
            fmt_map = {
                "DD/MM/YYYY": "dd/MM/yyyy",
                "MM/DD/YYYY": "MM/dd/yyyy",
                "YYYY-MM-DD": "yyyy-MM-dd",
                "DD-MM-YYYY": "dd-MM-yyyy",
            }
            fmt = fmt_map.get(self._filter_state.date_format, "yyyy-MM-dd")
            self._filter_state.date_range_start = self.filter_date_from.date().toString(fmt)
            self._filter_state.date_range_end = self.filter_date_to.date().toString(fmt)
            self._render()

    def _clear_filters(self):
        """Resetea todos los filtros a valores por defecto."""
        # Tipo: todos seleccionados
        for _k, a in self._type_actions.items():
            a.blockSignals(True)
            a.setChecked(True)
            a.blockSignals(False)
        self._filter_state.type_filter = None
        self._update_type_button_text()

        # Peso: ALL
        self.filter_weight_combo.blockSignals(True)
        self.filter_weight_combo.setCurrentIndex(0)
        self.filter_weight_combo.blockSignals(False)
        self._filter_state.weight_mode = WeightFilterMode.ALL
        self._filter_state.weight_threshold_bytes = None
        self.filter_weight_threshold.clear()
        self.filter_weight_threshold.setVisible(False)

        # Fecha: ALL
        self.filter_date_combo.blockSignals(True)
        self.filter_date_combo.setCurrentIndex(0)
        self.filter_date_combo.blockSignals(False)
        self._filter_state.date_mode = DateFilterMode.ALL
        self._filter_state.date_range_start = None
        self._filter_state.date_range_end = None
        self._filter_state.date_format = "AUTO"
        self.filter_date_format.blockSignals(True)
        self.filter_date_format.setCurrentText("AUTO")
        self.filter_date_format.blockSignals(False)
        self.filter_date_format.setVisible(False)
        self.filter_date_from.setVisible(False)
        self.filter_date_to_label.setVisible(False)
        self.filter_date_to.setVisible(False)

        # Búsqueda: limpiar (se maneja desde el header)
        self._filter = ""

        self._render()

    def _update_uninstall_btn(self):
        """Contador dinámico 'Desinstalar seleccionados (N)' + estado del header."""
        count = len(self.table.checked_rows())
        self.uninstall_btn.setText(tr("uninstall_button_count").format(n=count))
        # Durante un escaneo en segundo plano el botón queda deshabilitado
        # (el mixin lo re-habilita al llegar el resultado).
        self.uninstall_btn.setEnabled(count > 0 and not self._scanning)
        self.table.refresh_header_state()

    # ------------------------------------------------------------------
    # BasePage
    # ------------------------------------------------------------------
    def retranslate(self):
        self.info_label.setText(tr("uninstaller_info"))
        self.refresh_btn.setText(tr("refresh_button"))
        self.uninstall_btn.setText(
            tr("uninstall_button_count").format(n=len(self.table.checked_rows()))
        )
        self.table.select_all_box.setToolTip(tr("select_all_tooltip"))
        cast(Any, self.table).setHorizontalHeaderLabels(
            ["", tr("col_name"), tr("col_type"), tr("col_detail"), tr("col_weight"), tr("col_date")]
        )

        # Actualizar etiquetas de la barra de filtros
        if hasattr(self, "filter_type_label"):
            self.filter_type_label.setText(tr("filter_type_label"))
        if hasattr(self, "filter_weight_label"):
            self.filter_weight_label.setText(tr("filter_weight_label"))
        if hasattr(self, "filter_date_label"):
            self.filter_date_label.setText(tr("filter_date_label"))
        if hasattr(self, "filter_clear_btn"):
            self.filter_clear_btn.setText(tr("filter_clear"))
        if hasattr(self, "filter_weight_threshold"):
            self.filter_weight_threshold.setPlaceholderText(tr("filter_weight_threshold"))
        if hasattr(self, "filter_date_to_label"):
            self.filter_date_to_label.setText(tr("filter_date_to"))
        if hasattr(self, "filter_type_button"):
            # Solo actualizar textos, NO repoblar (perdería selección actual)
            self._update_type_button_text()
        # NOTA: NO repoblar weight_combo ni date_combo aquí, o se pierde la selección del usuario

        # Refresca el texto de la columna de tipo si ya hay datos cargados.
        self._render()

    def set_search_filter(self, text: str):
        self._filter = text.strip().lower()
        self._render()

    def showEvent(self, a0: Any) -> None:
        super().showEvent(a0)
        # Escaneo automático al mostrar la página solo si el caché está
        # viciado (primera vez, timeout de 5 min, o invalidado tras una
        # desinstalación). El botón "Actualizar lista" escanea siempre.
        if is_stale(SECTION_UNINSTALLER):
            cast(Any, QTimer).singleShot(0, self.load_apps)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def load_apps(self):
        self._start_background_scan(list_installed_apps, self._on_apps_loaded)

    def _on_apps_loaded(self, apps: list[InstalledApp]):
        # Defensa dura de TODA la cadena del resultado: la tabla (o cualquier
        # otro widget de la página) puede morir en C++ y el handler completo
        # queda contenido en un solo lugar (la pila dice cuál falló).
        try:
            self._apps = apps
            self._render()
            mark_scanned(SECTION_UNINSTALLER)
        except RuntimeError as exc:
            self._render_failure(
                "uninstaller_page._on_apps_loaded",
                exc,
                table=self.table,
                extra={"apps_total": len(self._apps)},
            )

    def _render(self):
        # Aplicar filtros de columna (Tipo, Peso, Fecha) usando filter_apps
        filtered = filter_apps(
            self._apps,
            self._filter_state,
            get_type=lambda a: a.kind,
            get_size_bytes=lambda a: a.size_bytes,
            get_date=lambda a: a.install_date,
            get_category=None,
        )

        # Filtro de búsqueda (texto libre) — se aplica después de filter_apps
        if self._filter:
            search_lower = self._filter.lower()
            self._visible = [app for app in filtered if search_lower in app.name.lower()]
        else:
            self._visible = filtered

        try:
            self.table.setRowCount(0)
            for app in self._visible:
                row = self.table.add_check_row()
                self.table.setItem(row, 1, QTableWidgetItem(app.name))
                self.table.setItem(row, 2, QTableWidgetItem(tr(kind_label_key(app.kind))))
                self.table.setItem(row, 3, QTableWidgetItem(app.detail))
                self.table.setItem(
                    row, 4, QTableWidgetItem(human_size(app.size_bytes) if app.size_bytes else "")
                )
                self.table.setItem(row, 5, QTableWidgetItem(app.install_date))
            self._update_uninstall_btn()
        except RuntimeError as exc:
            # Defensa dura: la tabla (widget Qt) puede morir en C++ dejando la
            # página viva (mismo patrón que el crash de Overview en CachyOS).
            # No tumba la app: se deja evidencia forense y se avisa al usuario.
            self._render_failure(
                "uninstaller_page._render",
                exc,
                table=self.table,
                extra={"rows": len(self._visible)},
            )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def uninstall_selected(self):
        rows = self.table.checked_rows()
        if not rows:
            QMessageBox.information(
                self, tr("nothing_selected_title"), tr("pacman_nothing_selected")
            )
            return

        apps = [self._visible[row] for row in rows]
        items: list[ConfirmItem] = []

        pacman_names = [a.name for a in apps if a.source == "pacman"]
        manual_apps = [a for a in apps if a.source != "pacman"]

        if pacman_names:
            # Un solo `pkexec pacman -Rns` para todo el lote (una autenticación).
            # Usa operation="pacman_remove" (allowlist en privileges.py).
            items.append(
                ConfirmItem(
                    label=", ".join(pacman_names),
                    category_label=tr("kind_app"),
                    size_bytes=sum(
                        (a.size_bytes or 0) for a in apps if a.source == "pacman"
                    ),
                    operation="pacman_remove",
                )
            )
        for app in manual_apps:
            target = _manual_target(app)
            items.append(
                ConfirmItem(
                    label=app.name,
                    category_label=tr(kind_label_key(app.kind)),
                    size_bytes=app.size_bytes or 0,
                    paths=[target],
                )
            )

        plan = build_confirmation_plan(items)

        def _after_uninstall(ok: bool):
            if ok:
                log_buffer.add(
                    tr("log_uninstalled_packages").format(
                        packages=", ".join(a.name for a in apps)
                    )
                )
            self.load_apps()

        run_destructive_action(
            self, plan, tr("uninstaller_confirm_title"),
            invalidate_sections=(SECTION_UNINSTALLER,),
            on_finished=_after_uninstall,
        )

    def request_uninstall(self, name: str, source: str, detail: str = ""):
        """Desinstala por nombre+fuente+detalle (llamado desde Overview)."""
        kind = KIND_APP if source == "pacman" else KIND_FOLDER

        if source == "pacman":
            item = ConfirmItem(
                label=name,
                category_label=tr(kind_label_key(kind)),
                size_bytes=0,
                operation="pacman_remove",
            )
        else:
            target = Path(detail) if detail else Path.home() / name
            item = ConfirmItem(
                label=name,
                category_label=tr(kind_label_key(kind)),
                size_bytes=0,
                paths=[target],
            )

        plan = build_confirmation_plan([item])

        def _after_request(ok: bool):
            if ok:
                log_buffer.add(tr("log_uninstalled_packages").format(packages=name))
            self.load_apps()

        run_destructive_action(
            self, plan, tr("uninstaller_confirm_title"),
            invalidate_sections=(SECTION_UNINSTALLER,),
            on_finished=_after_request,
        )