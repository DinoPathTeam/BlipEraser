"""Tests para table_filters.py — lógica pura, sin PyQt6.

Cubre:
- parse_date_flexible: ambos formatos DD/MM/YYYY y MM/DD/YYYY (punto crítico: confusión día/mes)
- parse_date_range: rangos con separadores ' - ' y ' to '
- detect_date_format: detección de formato para feedback al usuario
- filter_apps: filtrado y ordenamiento por peso, fecha, tipo, categoría
- utilidades de tamaño: format_size_threshold, parse_size_threshold
"""

from datetime import datetime

import pytest

from blip_eraser.utils.table_filters import (
    DateFilterMode,
    FilterState,
    WeightFilterMode,
    detect_date_format,
    filter_apps,
    format_size_threshold,
    parse_date_flexible,
    parse_date_range,
    parse_size_threshold,
)


class TestParseDateFlexible:
    """Tests críticos para parse_date_flexible — el punto donde más fácil se cuela
    un bug silencioso confundiendo día/mes."""

    # Formato DD/MM/YYYY (español/europeo) — día > 12 elimina ambigüedad
    def test_dd_mm_yyyy_day_gt_12(self):
        dt = parse_date_flexible("31/12/2023")
        assert dt == datetime(2023, 12, 31)

    def test_mm_dd_yyyy_month_gt_12_parsed_correctly(self):
        """12/31/2023 -> 31 diciembre (MM/DD/YYYY), mes=12 válido, día=31 válido."""
        dt = parse_date_flexible("12/31/2023")
        assert dt == datetime(2023, 12, 31)

    def test_dd_mm_yyyy_valid(self):
        dt = parse_date_flexible("15/06/2023")
        assert dt == datetime(2023, 6, 15)

    def test_dd_mm_yyyy_leading_zeros(self):
        dt = parse_date_flexible("01/02/2024")
        assert dt == datetime(2024, 2, 1)

    # Formato DD-MM-YYYY (con guiones)
    def test_dd_mm_yyyy_dashes(self):
        dt = parse_date_flexible("31-12-2023")
        assert dt == datetime(2023, 12, 31)

    def test_dd_mm_yyyy_dashes_valid(self):
        dt = parse_date_flexible("15-06-2023")
        assert dt == datetime(2023, 6, 15)

    # Formato YYYY-MM-DD (ISO) — sin ambigüedad
    def test_yyyy_mm_dd(self):
        dt = parse_date_flexible("2023-12-31")
        assert dt == datetime(2023, 12, 31)

    def test_yyyy_mm_dd_leading_zeros(self):
        dt = parse_date_flexible("2024-01-02")
        assert dt == datetime(2024, 1, 2)

    # Formato MM/DD/YYYY (EE. UU.) — mes > 12 elimina ambigüedad
    def test_mm_dd_yyyy_month_gt_12(self):
        dt = parse_date_flexible("12/31/2023")  # mes=12, día=31 -> MM/DD/YYYY
        assert dt == datetime(2023, 12, 31)

    def test_mm_dd_yyyy_valid(self):
        dt = parse_date_flexible("06/15/2023")
        assert dt == datetime(2023, 6, 15)

    # Ambigüedad real: día ≤ 12 Y mes ≤ 12 — el código intenta DD/MM/YYYY primero
    def test_ambiguous_dd_mm_first_match(self):
        """01/02/2024 -> 1 de febrero (DD/MM/YYYY), NO 2 de enero (MM/DD/YYYY)."""
        dt = parse_date_flexible("01/02/2024")
        assert dt == datetime(2024, 2, 1)  # DD/MM/YYYY tiene prioridad

    def test_ambiguous_12_12(self):
        """12/12/2024 -> 12 diciembre (ambos formatos coinciden, prioridad DD/MM)."""
        dt = parse_date_flexible("12/12/2024")
        assert dt == datetime(2024, 12, 12)

    # Tests para preferred_format explícito — EL SELECTOR DE LA UI MANDA
    def test_preferred_format_mm_dd_overrides_auto(self):
        """Con preferred_format='MM/DD/YYYY', 01/02/2024 -> 2 ene (NO 1 feb)."""
        dt = parse_date_flexible("01/02/2024", preferred_format="MM/DD/YYYY")
        assert dt == datetime(2024, 1, 2)

    def test_preferred_format_dd_mm_overrides_auto(self):
        """Con preferred_format='DD/MM/YYYY', 01/02/2024 -> 1 feb (explícito)."""
        dt = parse_date_flexible("01/02/2024", preferred_format="DD/MM/YYYY")
        assert dt == datetime(2024, 2, 1)

    def test_preferred_format_iso(self):
        """Con preferred_format='YYYY-MM-DD', 2024-01-02 -> 2 ene 2024."""
        dt = parse_date_flexible("2024-01-02", preferred_format="YYYY-MM-DD")
        assert dt == datetime(2024, 1, 2)

    def test_preferred_format_dd_mm_dashes(self):
        """Con preferred_format='DD-MM-YYYY', 01-02-2024 -> 1 feb 2024."""
        dt = parse_date_flexible("01-02-2024", preferred_format="DD-MM-YYYY")
        assert dt == datetime(2024, 2, 1)

    def test_preferred_format_invalid_for_date_returns_none(self):
        """Si el formato elegido no coincide con la fecha, retorna None (no fallback)."""
        dt = parse_date_flexible("31/12/2023", preferred_format="MM/DD/YYYY")
        # 31 no es mes válido en MM/DD -> None, NO fallback a DD/MM
        assert dt is None

    def test_preferred_format_none_uses_auto(self):
        """preferred_format=None usa auto-detección (compatibilidad)."""
        dt = parse_date_flexible("01/02/2024", preferred_format=None)
        assert dt == datetime(2024, 2, 1)  # Auto: DD/MM primero

    def test_preferred_format_auto_uses_auto(self):
        """preferred_format='AUTO' usa auto-detección."""
        dt = parse_date_flexible("01/02/2024", preferred_format="AUTO")
        assert dt == datetime(2024, 2, 1)  # Auto: DD/MM primero

    # Casos inválidos
    def test_invalid_day(self):
        dt = parse_date_flexible("32/01/2023")
        assert dt is None

    def test_invalid_month(self):
        # 13/13/2023 -> DD/MM falla (mes 13), MM/DD falla (mes 13)
        dt = parse_date_flexible("13/13/2023")
        assert dt is None

    def test_empty_string(self):
        assert parse_date_flexible("") is None

    def test_none_input(self):
        assert parse_date_flexible(None) is None  # type: ignore[arg-type]

    def test_whitespace_only(self):
        assert parse_date_flexible("   ") is None

    def test_random_text(self):
        assert parse_date_flexible("no es fecha") is None

    def test_partial_date(self):
        assert parse_date_flexible("2023-12") is None

    def test_wrong_separator(self):
        assert parse_date_flexible("31.12.2023") is None


class TestParseDateRange:
    """Tests para parse_date_range — rangos con ' - ' y ' to '."""

    def test_range_with_dash(self):
        start, end = parse_date_range("01/01/2023 - 31/12/2023")
        assert start == datetime(2023, 1, 1)
        assert end == datetime(2023, 12, 31, 23, 59, 59)

    def test_range_with_to(self):
        start, end = parse_date_range("01/01/2023 to 31/12/2023")
        assert start == datetime(2023, 1, 1)
        assert end == datetime(2023, 12, 31, 23, 59, 59)

    def test_range_with_TO_uppercase(self):
        start, end = parse_date_range("01/01/2023 TO 31/12/2023")
        assert start == datetime(2023, 1, 1)
        assert end == datetime(2023, 12, 31, 23, 59, 59)

    def test_range_iso_format(self):
        start, end = parse_date_range("2023-01-01 - 2023-12-31")
        assert start == datetime(2023, 1, 1)
        assert end == datetime(2023, 12, 31, 23, 59, 59)

    def test_range_mixed_formats(self):
        start, end = parse_date_range("01/01/2023 - 2023-12-31")
        assert start == datetime(2023, 1, 1)
        assert end == datetime(2023, 12, 31, 23, 59, 59)

    def test_invalid_no_separator(self):
        start, end = parse_date_range("01/01/2023")
        assert start is None
        assert end is None

    def test_invalid_empty(self):
        start, end = parse_date_range("")
        assert start is None
        assert end is None

    def test_invalid_malformed(self):
        # Segunda parte vacía -> start parseable, end = None
        start, end = parse_date_range("01/01/2023 - ")
        assert start == datetime(2023, 1, 1)
        assert end is None

    def test_invalid_both_unparseable(self):
        start, end = parse_date_range("no-fecha - tampoco")
        assert start is None
        assert end is None

    def test_invalid_unparseable_dates(self):
        start, end = parse_date_range("no-fecha - tampoco")
        assert start is None
        assert end is None

    # Tests para parse_date_range con preferred_format
    def test_parse_date_range_with_mm_dd_preferred(self):
        """Rango con preferred_format='MM/DD/YYYY'."""
        start, end = parse_date_range("01/02/2024 - 03/04/2024", preferred_format="MM/DD/YYYY")
        assert start == datetime(2024, 1, 2)
        assert end == datetime(2024, 3, 4, 23, 59, 59)

    def test_parse_date_range_with_dd_mm_preferred(self):
        """Rango con preferred_format='DD/MM/YYYY'."""
        start, end = parse_date_range("01/02/2024 - 03/04/2024", preferred_format="DD/MM/YYYY")
        assert start == datetime(2024, 2, 1)
        assert end == datetime(2024, 4, 3, 23, 59, 59)


class TestDetectDateFormat:
    """Tests para detect_date_format — feedback al usuario sobre formato detectado."""

    def test_iso_format(self):
        assert detect_date_format("2023-12-31") == "YYYY-MM-DD"

    def test_dd_mm_unambiguous_day_gt_12(self):
        assert detect_date_format("31/12/2023") == "DD/MM/AAAA (día > 12)"

    def test_mm_dd_unambiguous_month_gt_12(self):
        assert detect_date_format("12/31/2023") == "MM/DD/AAAA (mes > 12)"

    def test_dd_mm_unambiguous_day_gt_12_dashes(self):
        assert detect_date_format("31-12-2023") == "DD-MM-AAAA"

    def test_mm_dd_unambiguous_month_gt_12_dashes(self):
        assert detect_date_format("12-31-2023") == "MM-DD-AAAA"

    def test_ambiguous_slash(self):
        assert detect_date_format("01/02/2024") == "DD/MM/AAAA o MM/DD/AAAA (ambiguo)"

    def test_ambiguous_dash(self):
        assert detect_date_format("01-02-2024") == "DD-MM-AAAA o MM-DD-AAAA (ambiguo)"

    def test_empty(self):
        assert detect_date_format("") == "desconocido"

    def test_whitespace(self):
        assert detect_date_format("   ") == "desconocido"

    def test_unknown(self):
        assert detect_date_format("no-fecha") == "desconocido"


class TestFilterState:
    """Tests para FilterState dataclass."""

    def test_default_is_not_filtering(self):
        state = FilterState()
        assert state.is_filtering() is False

    def test_search_text_enables_filtering(self):
        state = FilterState(search_text="test")
        assert state.is_filtering() is True

    def test_type_filter_enables_filtering(self):
        state = FilterState(type_filter={"app"})
        assert state.is_filtering() is True

    def test_weight_mode_enables_filtering(self):
        state = FilterState(weight_mode=WeightFilterMode.HEAVIEST_FIRST)
        assert state.is_filtering() is True

    def test_date_mode_enables_filtering(self):
        state = FilterState(date_mode=DateFilterMode.NEWEST_FIRST)
        assert state.is_filtering() is True

    def test_category_filter_enables_filtering(self):
        state = FilterState(category_filter={"cache"})
        assert state.is_filtering() is True

    def test_copy_preserves_values(self):
        state = FilterState(
            search_text="test",
            type_filter={"app", "dependency"},
            weight_mode=WeightFilterMode.ONLY_HEAVY,
            weight_threshold_bytes=1024,
            date_mode=DateFilterMode.CUSTOM_RANGE,
            date_range_start="2023-01-01",
            date_range_end="2023-12-31",
            date_format="MM/DD/YYYY",
            category_filter={"cache"},
        )
        copied = state.copy()
        assert copied.search_text == "test"
        assert copied.type_filter == {"app", "dependency"}
        assert copied.weight_mode == WeightFilterMode.ONLY_HEAVY
        assert copied.weight_threshold_bytes == 1024
        assert copied.date_mode == DateFilterMode.CUSTOM_RANGE
        assert copied.date_range_start == "2023-01-01"
        assert copied.date_range_end == "2023-12-31"
        assert copied.date_format == "MM/DD/YYYY"
        assert copied.category_filter == {"cache"}

    def test_copy_is_independent(self):
        state = FilterState(type_filter={"app"})
        copied = state.copy()
        copied.type_filter.add("dependency")
        assert "dependency" not in state.type_filter

    def test_default_date_format_is_auto(self):
        """Por defecto date_format es 'AUTO' (auto-detección)."""
        state = FilterState()
        assert state.date_format == "AUTO"

    def test_date_format_can_be_set_explicitly(self):
        """El usuario puede elegir formato explícito en la UI."""
        state = FilterState(date_format="MM/DD/YYYY")
        assert state.date_format == "MM/DD/YYYY"
        state2 = FilterState(date_format="DD/MM/YYYY")
        assert state2.date_format == "DD/MM/YYYY"
        state3 = FilterState(date_format="YYYY-MM-DD")
        assert state3.date_format == "YYYY-MM-DD"


class TestFilterApps:
    """Tests para filter_apps — filtrado y ordenamiento combinados."""

    def _make_items(self):
        """Items mock con get_type, get_size_bytes, get_date, get_category."""
        return [
            {"name": "app1", "kind": "app", "size": 1024**3, "date": "15/06/2023", "cat": "cache"},
            {"name": "app2", "kind": "dependency", "size": 512 * 1024**2, "date": "01/01/2023", "cat": "logs"},
            {"name": "app3", "kind": "folder", "size": 100 * 1024**2, "date": "31/12/2023", "cat": "cache"},
            {"name": "app4", "kind": "app", "size": 10 * 1024**3, "date": "15/03/2023", "cat": "temp"},
        ]

    def test_no_filters_returns_all(self):
        items = self._make_items()
        state = FilterState()
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result) == 4

    def test_type_filter(self):
        items = self._make_items()
        state = FilterState(type_filter={"app"})
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result) == 2
        assert all(r["kind"] == "app" for r in result)

    def test_category_filter(self):
        items = self._make_items()
        state = FilterState(category_filter={"cache"})
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result) == 2
        assert all(r["cat"] == "cache" for r in result)

    def test_weight_only_heavy(self):
        items = self._make_items()
        # app1=1GB, app2=512MB, app3=100MB, app4=10GB
        # Umbral 600MB -> app1, app4 pasan (app2=512MB < 600MB)
        state = FilterState(weight_mode=WeightFilterMode.ONLY_HEAVY, weight_threshold_bytes=600 * 1024**2)
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result) == 2  # app1 (1GB) y app4 (10GB)
        assert all(r["size"] >= 600 * 1024**2 for r in result)

    def test_weight_only_light(self):
        items = self._make_items()
        # app1=1GB, app2=512MB, app3=100MB, app4=10GB
        # Umbral 600MB -> app2 (512MB), app3 (100MB) pasan
        state = FilterState(weight_mode=WeightFilterMode.ONLY_LIGHT, weight_threshold_bytes=600 * 1024**2)
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result) == 2  # app2 (512MB) y app3 (100MB)
        assert all(r["size"] <= 600 * 1024**2 for r in result)

    def test_weight_heaviest_first_sort(self):
        items = self._make_items()
        state = FilterState(weight_mode=WeightFilterMode.HEAVIEST_FIRST)
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        sizes = [r["size"] for r in result]
        assert sizes == sorted(sizes, reverse=True)

    def test_weight_lightest_first_sort(self):
        items = self._make_items()
        state = FilterState(weight_mode=WeightFilterMode.LIGHTEST_FIRST)
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        sizes = [r["size"] for r in result]
        assert sizes == sorted(sizes)

    def test_date_newest_first_sort(self):
        items = self._make_items()
        state = FilterState(date_mode=DateFilterMode.NEWEST_FIRST)
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        dates = [parse_date_flexible(r["date"]) for r in result]
        assert dates == sorted(dates, reverse=True)

    def test_date_oldest_first_sort(self):
        items = self._make_items()
        state = FilterState(date_mode=DateFilterMode.OLDEST_FIRST)
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        dates = [parse_date_flexible(r["date"]) for r in result]
        assert dates == sorted(dates)

    def test_date_custom_range_filters(self):
        items = self._make_items()
        state = FilterState(
            date_mode=DateFilterMode.CUSTOM_RANGE,
            date_range_start="01/01/2023",
            date_range_end="30/06/2023",  # hasta 30 junio
        )
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        # app1 (15/06), app2 (01/01), app4 (15/03) pasan; app3 (31/12) NO
        assert len(result) == 3
        assert all(parse_date_flexible(r["date"]) <= datetime(2023, 6, 30, 23, 59, 59) for r in result)

    def test_date_custom_range_with_invalid_date_skips(self):
        """Items con fecha inválida se excluyen en modo CUSTOM_RANGE."""
        items = self._make_items() + [{"name": "bad", "kind": "app", "size": 100, "date": "no-fecha", "cat": "cache"}]
        state = FilterState(
            date_mode=DateFilterMode.CUSTOM_RANGE,
            date_range_start="2023-01-01",
            date_range_end="2023-12-31",
        )
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result) == 4  # el item con fecha inválida se salta

    def test_combined_filters(self):
        items = self._make_items()
        state = FilterState(
            type_filter={"app", "folder"},
            weight_mode=WeightFilterMode.HEAVIEST_FIRST,
            category_filter={"cache"},
        )
        result = filter_apps(
            items, state,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        # Solo app1 y app3 son (app o folder) Y cache, ordenados por peso descendente
        assert len(result) == 2
        assert result[0]["name"] == "app1"  # 1GB
        assert result[1]["name"] == "app3"  # 100MB

    # Tests para filter_apps con preferred_format explícito
    def test_filter_apps_uses_preferred_format_for_sorting(self):
        """El ordenamiento por fecha usa el formato elegido por el usuario."""
        items = [
            {"name": "a", "kind": "app", "size": 100, "date": "01/02/2024", "cat": "cache"},  # 1 feb o 2 ene
            {"name": "b", "kind": "app", "size": 100, "date": "02/03/2024", "cat": "cache"},  # 2 mar o 3 feb
            {"name": "c", "kind": "app", "size": 100, "date": "03/04/2024", "cat": "cache"},  # 3 abr o 4 mar
        ]
        # Con MM/DD/YYYY: fechas son 2 ene, 3 feb, 4 mar -> OLDEST_FIRST = a, b, c
        state_mm_dd = FilterState(date_mode=DateFilterMode.OLDEST_FIRST, date_format="MM/DD/YYYY")
        result_mm_dd = filter_apps(
            items, state_mm_dd,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert [r["name"] for r in result_mm_dd] == ["a", "b", "c"]

        # Con DD/MM/YYYY: fechas son 1 feb, 2 mar, 3 abr -> OLDEST_FIRST = a, b, c (mismo orden por casualidad)
        # Cambiemos las fechas para que el orden sea DISTINTO
        items2 = [
            {"name": "a", "kind": "app", "size": 100, "date": "02/01/2024", "cat": "cache"},  # 2 ene (MM/DD) vs 1 feb (DD/MM)
            {"name": "b", "kind": "app", "size": 100, "date": "03/01/2024", "cat": "cache"},  # 3 ene vs 1 mar
        ]
        # MM/DD: 2 ene, 3 ene -> a, b
        state_mm_dd2 = FilterState(date_mode=DateFilterMode.OLDEST_FIRST, date_format="MM/DD/YYYY")
        result_mm_dd2 = filter_apps(
            items2, state_mm_dd2,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert [r["name"] for r in result_mm_dd2] == ["a", "b"]

        # DD/MM: 1 feb, 1 mar -> a, b (a es 1 feb, b es 1 mar -> a antes que b)
        state_dd_mm2 = FilterState(date_mode=DateFilterMode.OLDEST_FIRST, date_format="DD/MM/YYYY")
        result_dd_mm2 = filter_apps(
            items2, state_dd_mm2,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert [r["name"] for r in result_dd_mm2] == ["a", "b"]

    def test_filter_apps_uses_preferred_format_for_range_filter(self):
        """El filtro por rango de fechas usa el formato elegido por el usuario."""
        items2 = [
            {"name": "in_dd_mm", "kind": "app", "size": 100, "date": "05/03/2024", "cat": "cache"},  # 5 mar (DD/MM) vs 3 may (MM/DD)
            {"name": "in_mm_dd", "kind": "app", "size": 100, "date": "03/05/2024", "cat": "cache"},  # 3 may (DD/MM) vs 5 mar (MM/DD)
        ]
        # Rango: 01/03/2024 - 15/03/2024 (marzo)
        # DD/MM: rango = 1 mar - 15 mar -> "in_dd_mm" (5 mar) DENTRO, "in_mm_dd" (3 may) FUERA
        state_dd_mm = FilterState(
            date_mode=DateFilterMode.CUSTOM_RANGE,
            date_format="DD/MM/YYYY",
            date_range_start="01/03/2024",
            date_range_end="15/03/2024",
        )
        result_dd_mm = filter_apps(
            items2, state_dd_mm,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result_dd_mm) == 1
        assert result_dd_mm[0]["name"] == "in_dd_mm"

        # MM/DD: rango = 3 ene - 15 mar -> "in_mm_dd" (5 mar) DENTRO, "in_dd_mm" (3 may) FUERA
        # Usar formato MM/DD para el rango: 01/03/2024 = 3 ene, 03/15/2024 = 15 mar
        state_mm_dd = FilterState(
            date_mode=DateFilterMode.CUSTOM_RANGE,
            date_format="MM/DD/YYYY",
            date_range_start="01/03/2024",
            date_range_end="03/15/2024",
        )
        result_mm_dd = filter_apps(
            items2, state_mm_dd,
            get_type=lambda x: x["kind"],
            get_size_bytes=lambda x: x["size"],
            get_date=lambda x: x["date"],
            get_category=lambda x: x["cat"],
        )
        assert len(result_mm_dd) == 1
        assert result_mm_dd[0]["name"] == "in_mm_dd"


class TestSizeThresholdUtils:
    """Tests para format_size_threshold y parse_size_threshold."""

    def test_format_bytes(self):
        assert format_size_threshold(500) == "500 B"
        assert format_size_threshold(1023) == "1023 B"

    def test_format_kb(self):
        assert format_size_threshold(1024) == "1.0 KB"
        assert format_size_threshold(1536) == "1.5 KB"
        # 1024**2 - 1 = 1048575 bytes = 1023.999... KB -> redondea a 1024.0 KB
        assert format_size_threshold(1024**2 - 1) == "1024.0 KB"

    def test_format_mb(self):
        assert format_size_threshold(1024**2) == "1.0 MB"
        assert format_size_threshold(100 * 1024**2) == "100.0 MB"

    def test_format_gb(self):
        assert format_size_threshold(1024**3) == "1.0 GB"
        assert format_size_threshold(2 * 1024**3) == "2.0 GB"

    def test_parse_bytes(self):
        assert parse_size_threshold("500") == 500
        assert parse_size_threshold("500 B") == 500

    def test_parse_kb(self):
        assert parse_size_threshold("1 KB") == 1024
        assert parse_size_threshold("1.5 KB") == 1536
        assert parse_size_threshold("1KB") == 1024

    def test_parse_mb(self):
        assert parse_size_threshold("1 MB") == 1024**2
        assert parse_size_threshold("100 MB") == 100 * 1024**2

    def test_parse_gb(self):
        assert parse_size_threshold("1 GB") == 1024**3
        assert parse_size_threshold("2 GB") == 2 * 1024**3

    def test_parse_case_insensitive(self):
        assert parse_size_threshold("1 mb") == 1024**2
        assert parse_size_threshold("1 Mb") == 1024**2
        assert parse_size_threshold("1 MB") == 1024**2

    def test_parse_with_spaces(self):
        assert parse_size_threshold("  100  MB  ") == 100 * 1024**2

    def test_parse_invalid(self):
        assert parse_size_threshold("") is None
        assert parse_size_threshold("abc") is None
        assert parse_size_threshold("100 XB") is None