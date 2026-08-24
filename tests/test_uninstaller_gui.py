"""Tests de GUI para pages/uninstaller_page.py (requieren PyQt6).

Este archivo necesita PyQt6. `pytest.importorskip("PyQt6")` al inicio
hace que el módulo entero se reporte como *skipped* en entornos sin PyQt6.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")

from blip_eraser.pages.uninstaller_page import UninstallerPage
from blip_eraser.utils.table_filters import (
    DateFilterMode,
    WeightFilterMode,
    FilterState,
)
from blip_eraser.utils.apps import KIND_APP, KIND_DEPENDENCY, KIND_FOLDER


@pytest.fixture(scope="module")
def app():
    """QApplication compartida: necesaria para construir QWidgets."""
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture
def page(app, monkeypatch):
    """UninstallerPage con datos mockeados."""
    # Mockear el escaneo para no depender de pacman real
    mock_apps = [
        _make_app("Firefox", KIND_APP, "pacman", 100_000_000, "2024-01-15"),
        _make_app("libfoo", KIND_DEPENDENCY, "pacman", 10_000_000, "2024-02-20"),
        _make_app("MyApp.AppImage", KIND_FOLDER, "manual", 500_000_000, "2024-03-10"),
        _make_app("VLC", KIND_APP, "pacman", 200_000_000, "2024-04-05"),
        _make_app("libbar", KIND_DEPENDENCY, "pacman", 5_000_000, "2024-05-01"),
    ]
    monkeypatch.setattr(
        "blip_eraser.pages.uninstaller_page.list_installed_apps",
        lambda: mock_apps,
    )
    p = UninstallerPage()
    # Cargar apps directamente en lugar de esperar al background scan
    p._on_apps_loaded(mock_apps)
    QtWidgets.QApplication.processEvents()
    return p


def _make_app(name, kind, source, size, date):
    from types import SimpleNamespace
    return SimpleNamespace(
        name=name,
        kind=kind,
        source=source,
        size_bytes=size,
        install_date=date,
        detail="/fake/path",
    )


class TestUninstallerFilters:
    """Tests para los controles de filtro del Desinstalador."""

    def test_page_has_filter_toolbar(self, page):
        """La página tiene la barra de filtros con todos los controles."""
        assert hasattr(page, "filter_type_label")
        assert hasattr(page, "filter_type_button")
        assert hasattr(page, "filter_weight_label")
        assert hasattr(page, "filter_weight_combo")
        assert hasattr(page, "filter_weight_threshold")
        assert hasattr(page, "filter_date_label")
        assert hasattr(page, "filter_date_combo")
        assert hasattr(page, "filter_date_format")
        assert hasattr(page, "filter_date_from")
        assert hasattr(page, "filter_date_to")
        assert hasattr(page, "filter_clear_btn")

    def test_type_filter_multi_select(self, page):
        """El filtro de Tipo permite multi-selección y filtra filas."""
        # Inicialmente 5 apps
        assert len(page._visible) == 5

        # Desmarcar "Dependencia" -> solo App y Folder
        dep_action = page._type_actions[KIND_DEPENDENCY]
        dep_action.setChecked(False)
        QtWidgets.QApplication.processEvents()

        # Deben quedar 3 (Firefox, VLC, MyApp.AppImage)
        assert len(page._visible) == 3
        names = {a.name for a in page._visible}
        assert names == {"Firefox", "VLC", "MyApp.AppImage"}

        # Marcar solo "Dependencia"
        for k, a in page._type_actions.items():
            if k != "all":
                a.blockSignals(True)
                a.setChecked(k == KIND_DEPENDENCY)
                a.blockSignals(False)
        page._update_type_button_text()
        page._apply_type_filter()
        QtWidgets.QApplication.processEvents()

        assert len(page._visible) == 2
        names = {a.name for a in page._visible}
        assert names == {"libfoo", "libbar"}

    def test_weight_filter_heaviest_first(self, page):
        """Peso: 'Más pesados primero' reordena descendente."""
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.HEAVIEST_FIRST)
        )
        QtWidgets.QApplication.processEvents()

        sizes = [a.size_bytes for a in page._visible]
        assert sizes == sorted(sizes, reverse=True)

    def test_weight_filter_lightest_first(self, page):
        """Peso: 'Menos pesados primero' reordena ascendente."""
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.LIGHTEST_FIRST)
        )
        QtWidgets.QApplication.processEvents()

        sizes = [a.size_bytes for a in page._visible]
        assert sizes == sorted(sizes)

    def test_weight_filter_only_heavy(self, page):
        """Peso: 'Solo > umbral' filtra por umbral."""
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.ONLY_HEAVY)
        )
        QtWidgets.QApplication.processEvents()
        assert page.filter_weight_threshold.isVisible()

        # Umbral 150 MB -> solo Firefox (100M), VLC (200M), MyApp (500M) pasan
        page.filter_weight_threshold.setText("150 MB")
        page.filter_weight_threshold.editingFinished.emit()
        QtWidgets.QApplication.processEvents()

        assert len(page._visible) == 3
        names = {a.name for a in page._visible}
        assert names == {"Firefox", "VLC", "MyApp.AppImage"}

    def test_weight_filter_only_light(self, page):
        """Peso: 'Solo < umbral' filtra por umbral."""
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.ONLY_LIGHT)
        )
        QtWidgets.QApplication.processEvents()
        assert page.filter_weight_threshold.isVisible()

        # Umbral 50 MB -> solo libfoo (10M), libbar (5M) pasan
        page.filter_weight_threshold.setText("50 MB")
        page.filter_weight_threshold.editingFinished.emit()
        QtWidgets.QApplication.processEvents()

        assert len(page._visible) == 2
        names = {a.name for a in page._visible}
        assert names == {"libfoo", "libbar"}

    def test_date_filter_newest_first(self, page):
        """Fecha: 'Más nuevos primero' reordena descendente."""
        page.filter_date_combo.setCurrentIndex(
            page.filter_date_combo.findData(DateFilterMode.NEWEST_FIRST)
        )
        QtWidgets.QApplication.processEvents()

        dates = [a.install_date for a in page._visible]
        assert dates == sorted(dates, reverse=True)

    def test_date_filter_oldest_first(self, page):
        """Fecha: 'Más viejos primero' reordena ascendente."""
        page.filter_date_combo.setCurrentIndex(
            page.filter_date_combo.findData(DateFilterMode.OLDEST_FIRST)
        )
        QtWidgets.QApplication.processEvents()

        dates = [a.install_date for a in page._visible]
        assert dates == sorted(dates)

    def test_date_filter_custom_range_with_format(self, page):
        """Fecha: Rango personalizado con selector de formato MM/DD/YYYY."""
        page.filter_date_combo.setCurrentIndex(
            page.filter_date_combo.findData(DateFilterMode.CUSTOM_RANGE)
        )
        QtWidgets.QApplication.processEvents()

        # Verificar que aparecen controles de formato y rango
        assert page.filter_date_format.isVisible()
        assert page.filter_date_from.isVisible()
        assert page.filter_date_to.isVisible()

        # Seleccionar formato MM/DD/YYYY
        page.filter_date_format.setCurrentText("MM/DD/YYYY")
        QtWidgets.QApplication.processEvents()

        # Rango: 01/01/2024 - 02/28/2024 (enero-febrero en MM/DD)
        from PyQt6.QtCore import QDate
        page.filter_date_from.setDate(QDate(2024, 1, 1))
        page.filter_date_to.setDate(QDate(2024, 2, 28))
        QtWidgets.QApplication.processEvents()

        # Con MM/DD: libfoo (02/20/2024 = 20 feb) pasa, libbar (05/01/2024 = 1 may) NO
        # Firefox (01/15/2024 = 15 ene) pasa, VLC (04/05/2024 = 5 abr) NO, MyApp (03/10/2024 = 10 mar) NO
        assert len(page._visible) == 2
        names = {a.name for a in page._visible}
        assert names == {"Firefox", "libfoo"}

    def test_date_filter_custom_range_dd_mm_yyyy(self, page):
        """Fecha: Rango personalizado con formato DD/MM/YYYY (distinto resultado)."""
        page.filter_date_combo.setCurrentIndex(
            page.filter_date_combo.findData(DateFilterMode.CUSTOM_RANGE)
        )
        QtWidgets.QApplication.processEvents()

        page.filter_date_format.setCurrentText("DD/MM/YYYY")
        QtWidgets.QApplication.processEvents()

        # Mismo rango 01/01/2024 - 02/28/2024 pero DD/MM = 1 ene - 28 feb
        from PyQt6.QtCore import QDate
        page.filter_date_from.setDate(QDate(2024, 1, 1))
        page.filter_date_to.setDate(QDate(2024, 2, 28))
        QtWidgets.QApplication.processEvents()

        # Con DD/MM: Firefox (15/01 = 15 ene) pasa, libfoo (20/02 = 20 feb) pasa
        # VLC (05/04 = 5 abr) NO, MyApp (10/03 = 10 mar) NO, libbar (01/05 = 1 may) NO
        assert len(page._visible) == 2
        names = {a.name for a in page._visible}
        assert names == {"Firefox", "libfoo"}

    def test_clear_filters_resets_everything(self, page):
        """Botón 'Limpiar filtros' resetea todos los controles."""
        # Aplicar algunos filtros
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.HEAVIEST_FIRST)
        )
        page.filter_date_combo.setCurrentIndex(
            page.filter_date_combo.findData(DateFilterMode.NEWEST_FIRST)
        )
        page._type_actions[KIND_DEPENDENCY].setChecked(False)
        page._apply_type_filter()
        QtWidgets.QApplication.processEvents()

        # Verificar que hay filtros activos
        assert page._filter_state.weight_mode == WeightFilterMode.HEAVIEST_FIRST
        assert page._filter_state.date_mode == DateFilterMode.NEWEST_FIRST
        assert page._filter_state.type_filter is not None

        # Limpiar
        page.filter_clear_btn.click()
        QtWidgets.QApplication.processEvents()

        # Verificar reset
        assert page._filter_state.weight_mode == WeightFilterMode.ALL
        assert page._filter_state.date_mode == DateFilterMode.ALL
        assert page._filter_state.type_filter is None
        assert page._filter_state.date_format == "AUTO"
        assert not page.filter_weight_threshold.isVisible()
        assert not page.filter_date_format.isVisible()
        assert not page.filter_date_from.isVisible()

        # Todas las apps visibles de nuevo
        assert len(page._visible) == 5

    def test_search_filter_combined_with_column_filters(self, page):
        """Filtro de búsqueda (texto) funciona junto con filtros de columna."""
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.HEAVIEST_FIRST)
        )
        page.set_search_filter("Fire")
        QtWidgets.QApplication.processEvents()

        # Solo Firefox coincide con "Fire" y está en los resultados
        assert len(page._visible) == 1
        assert page._visible[0].name == "Firefox"

    def test_filter_state_persists_across_render(self, page):
        """FilterState se mantiene al re-renderizar (ej. cambio de idioma)."""
        page.filter_weight_combo.setCurrentIndex(
            page.filter_weight_combo.findData(WeightFilterMode.ONLY_HEAVY)
        )
        page.filter_weight_threshold.setText("50 MB")
        page.filter_weight_threshold.editingFinished.emit()
        QtWidgets.QApplication.processEvents()

        original_state = page._filter_state.copy()
        page.retranslate()
        QtWidgets.QApplication.processEvents()

        assert page._filter_state.weight_mode == original_state.weight_mode
        assert page._filter_state.weight_threshold_bytes == original_state.weight_threshold_bytes