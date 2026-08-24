"""Filtros y ordenamiento de tablas — lógica pura, sin PyQt6.

Centraliza la lógica de filtrado y ordenamiento para que sea testeable
sin GUI. Las páginas aplican los filtros antes de renderizar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal


class SortOrder(Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class WeightFilterMode(Enum):
    """Modos de filtro por peso/tamaño."""
    ALL = "all"                    # Sin filtro
    HEAVIEST_FIRST = "heaviest"    # Orden: mayor a menor
    LIGHTEST_FIRST = "lightest"    # Orden: menor a mayor
    ONLY_HEAVY = "only_heavy"      # Solo los más pesados (umbral)
    ONLY_LIGHT = "only_light"      # Solo los menos pesados (umbral)


class DateFilterMode(Enum):
    """Modos de filtro/orden por fecha."""
    ALL = "all"
    NEWEST_FIRST = "newest"        # Más nuevos primero
    OLDEST_FIRST = "oldest"        # Más viejos primero
    CUSTOM_RANGE = "custom"        # Rango personalizado


class TypeFilterMode(Enum):
    """Modos de filtro por tipo."""
    ALL = "all"
    SELECTED = "selected"  # Solo tipos seleccionados (multi-selección)


@dataclass
class FilterState:
    """Estado completo de filtros para una tabla."""
    # Filtro de texto (búsqueda general)
    search_text: str = ""
    
    # Tipo: multi-selección de tipos permitidos
    type_filter: set[str] | None = None  # None = todos
    
    # Peso: modo de filtro/orden
    weight_mode: WeightFilterMode = WeightFilterMode.ALL
    weight_threshold_bytes: int | None = None  # Umbral para ONLY_HEAVY/ONLY_LIGHT
    
    # Fecha: modo de filtro/orden
    date_mode: DateFilterMode = DateFilterMode.ALL
    date_range_start: str | None = None  # YYYY-MM-DD
    date_range_end: str | None = None    # YYYY-MM-DD
    # Formato de fecha elegido por el usuario en la UI (manda sobre auto-detección)
    date_format: Literal["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD", "DD-MM-YYYY", "AUTO"] = "AUTO"
    
    # Categoría (para Limpiador)
    category_filter: set[str] | None = None  # None = todas

    def is_filtering(self) -> bool:
        """True si hay algún filtro activo (distinto de 'todo')."""
        return (
            self.search_text != ""
            or self.type_filter is not None
            or self.weight_mode != WeightFilterMode.ALL
            or self.date_mode != DateFilterMode.ALL
            or self.category_filter is not None
        )

    def copy(self) -> "FilterState":
        return FilterState(
            search_text=self.search_text,
            type_filter=self.type_filter.copy() if self.type_filter else None,
            weight_mode=self.weight_mode,
            weight_threshold_bytes=self.weight_threshold_bytes,
            date_mode=self.date_mode,
            date_range_start=self.date_range_start,
            date_range_end=self.date_range_end,
            date_format=self.date_format,
            category_filter=self.category_filter.copy() if self.category_filter else None,
        )


def parse_date_flexible(date_str: str, preferred_format: str | None = None) -> datetime | None:
    """Parsea fecha aceptando DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, MM/DD/YYYY.
    
    Retorna datetime si parsea, None si no puede.
    
    Si se proporciona `preferred_format` (distinto de "AUTO" y None),
    se usa EXCLUSIVAMENTE ese formato — el selector de la UI manda.
    Solo si es "AUTO" o None se hace auto-detección por patrón.
    """
    if not date_str:
        return None
    
    s = date_str.strip()
    
    # Si el usuario eligió un formato explícito, usarlo SIN fallback a otros
    if preferred_format and preferred_format != "AUTO":
        fmt_map = {
            "DD/MM/YYYY": "%d/%m/%Y",
            "MM/DD/YYYY": "%m/%d/%Y",
            "YYYY-MM-DD": "%Y-%m-%d",
            "DD-MM-YYYY": "%d-%m-%Y",
        }
        fmt = fmt_map.get(preferred_format)
        if fmt:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                return None
        return None
    
    # Auto-detección (comportamiento original): orden de prioridad fijo
    patterns = [
        ("%d/%m/%Y", r"^\d{2}/\d{2}/\d{4}$"),      # DD/MM/YYYY
        ("%d-%m-%Y", r"^\d{2}-\d{2}-\d{4}$"),      # DD-MM-YYYY
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),      # YYYY-MM-DD
        ("%m/%d/%Y", r"^\d{2}/\d{2}/\d{4}$"),      # MM/DD/YYYY
    ]
    
    import re
    for fmt, pattern in patterns:
        if re.match(pattern, s):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


def parse_date_range(date_str: str, preferred_format: str | None = None) -> tuple[datetime | None, datetime | None]:
    """Parsea un rango de fechas tipo 'DD/MM/YYYY - DD/MM/YYYY' o 'DD/MM/YYYY to DD/MM/YYYY'.
    
    Retorna (inicio, fin) como datetime, o (None, None) si falla.
    """
    if not date_str or "-" not in date_str and "to" not in date_str.lower():
        return None, None
    
    parts = None
    if " - " in date_str:
        parts = date_str.split(" - ")
    elif " to " in date_str.lower():
        parts = date_str.lower().split(" to ")
    
    if not parts or len(parts) != 2:
        return None, None
    
    start = parse_date_flexible(parts[0].strip(), preferred_format)
    end = parse_date_flexible(parts[1].strip(), preferred_format)
    
    # Para el final del día, ajustar a 23:59:59
    if end:
        end = end.replace(hour=23, minute=59, second=59)
    
    return start, end


def detect_date_format(date_str: str) -> str:
    """Detecta el formato de una fecha para mostrar al usuario cuál se está interpretando.
    
    Retorna descripción legible: "DD/MM/AAAA", "MM/DD/AAAA", "YYYY-MM-DD", o "desconocido".
    """
    if not date_str:
        return "desconocido"
    
    import re
    s = date_str.strip()
    
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return "YYYY-MM-DD"
    if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
        # Podría ser DD/MM/YYYY o MM/DD/YYYY - ambigüedad real
        day = int(s[:2])
        month = int(s[3:5])
        if day > 12:
            return "DD/MM/AAAA (día > 12)"
        if month > 12:
            return "MM/DD/AAAA (mes > 12)"
        return "DD/MM/AAAA o MM/DD/AAAA (ambiguo)"
    if re.match(r"^\d{2}-\d{2}-\d{4}$", s):
        day = int(s[:2])
        month = int(s[3:5])
        if day > 12:
            return "DD-MM-AAAA"
        if month > 12:
            return "MM-DD-AAAA"
        return "DD-MM-AAAA o MM-DD-AAAA (ambiguo)"
    
    return "desconocido"


def filter_apps(
    apps: list[Any],
    filter_state: FilterState,
    get_type: callable,
    get_size_bytes: callable,
    get_date: callable,
    get_category: callable | None = None,
) -> list[Any]:
    """Filtra y ordena una lista de apps/entradas según FilterState.
    
    Args:
        apps: Lista de objetos a filtrar
        filter_state: Estado de filtros
        get_type: fn(item) -> str (tipo: "app", "dependency", "folder", etc.)
        get_size_bytes: fn(item) -> int (tamaño en bytes)
        get_date: fn(item) -> str (fecha string)
        get_category: fn(item) -> str (categoría, opcional)
    
    Returns:
        Lista filtrada y ordenada
    """
    result = []
    
    for item in apps:
        # Filtro de búsqueda (texto libre)
        if filter_state.search_text:
            # Se asume que el llamador ya filtró por nombre, o se hace aquí
            # Para no duplicar lógica, asumimos que el nombre ya pasó filtro
            pass
        
        # Filtro por tipo
        if filter_state.type_filter is not None:
            item_type = get_type(item)
            if item_type not in filter_state.type_filter:
                continue
        
        # Filtro por categoría (Limpiador)
        if filter_state.category_filter is not None and get_category:
            item_cat = get_category(item)
            if item_cat not in filter_state.category_filter:
                continue
        
        # Filtro por peso (umbral)
        if filter_state.weight_mode in (WeightFilterMode.ONLY_HEAVY, WeightFilterMode.ONLY_LIGHT):
            size = get_size_bytes(item)
            threshold = filter_state.weight_threshold_bytes or 0
            if filter_state.weight_mode == WeightFilterMode.ONLY_HEAVY:
                if size < threshold:
                    continue
            elif filter_state.weight_mode == WeightFilterMode.ONLY_LIGHT:
                if size > threshold:
                    continue
        
        # Filtro por fecha (rango personalizado)
        if filter_state.date_mode == DateFilterMode.CUSTOM_RANGE:
            date_str = get_date(item)
            dt = parse_date_flexible(date_str, filter_state.date_format)
            if dt is None:
                continue
            if filter_state.date_range_start:
                start_dt = parse_date_flexible(filter_state.date_range_start, filter_state.date_format)
                if start_dt and dt < start_dt:
                    continue
            if filter_state.date_range_end:
                end_dt = parse_date_flexible(filter_state.date_range_end, filter_state.date_format)
                if end_dt and dt > end_dt:
                    continue
        
        result.append(item)
    
    # Ordenamiento
    if filter_state.weight_mode == WeightFilterMode.HEAVIEST_FIRST:
        result.sort(key=lambda x: get_size_bytes(x), reverse=True)
    elif filter_state.weight_mode == WeightFilterMode.LIGHTEST_FIRST:
        result.sort(key=lambda x: get_size_bytes(x))
    elif filter_state.date_mode == DateFilterMode.NEWEST_FIRST:
        result.sort(key=lambda x: parse_date_flexible(get_date(x), filter_state.date_format) or datetime.min, reverse=True)
    elif filter_state.date_mode == DateFilterMode.OLDEST_FIRST:
        result.sort(key=lambda x: parse_date_flexible(get_date(x), filter_state.date_format) or datetime.max)
    
    return result


def get_type_display_name(kind: str) -> str:
    """Mapea kind interno a nombre legible para UI."""
    mapping = {
        "app": "Aplicación",
        "dependency": "Dependencia",
        "folder": "Carpeta suelta",
    }
    return mapping.get(kind, kind)


def get_available_types() -> list[str]:
    """Tipos disponibles para el filtro multi-selección."""
    return ["app", "dependency", "folder"]


def get_type_display_names(types: list[str]) -> dict[str, str]:
    """Mapea lista de tipos a nombres legibles."""
    return {t: get_type_display_name(t) for t in types}


# =========================================================================
# Utilidades de UI para filtros (helpers para construir controles)
# =========================================================================

def format_size_threshold(bytes_val: int) -> str:
    """Formatea umbral de tamaño para UI (ej. '100 MB')."""
    if bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.1f} GB"
    elif bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val} B"


def parse_size_threshold(text: str) -> int | None:
    """Parsea texto tipo '100 MB', '1 GB', '500 KB' a bytes.
    
    Retorna None si no puede parsear.
    """
    if not text:
        return None
    text = text.strip().upper().replace(" ", "")
    multipliers = {
        "GB": 1024**3,
        "MB": 1024**2,
        "KB": 1024,
        "B": 1,
    }
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                val = float(text[:-len(suffix)])
                return int(val * mult)
            except ValueError:
                return None
    # Sin sufijo = bytes
    try:
        return int(text)
    except ValueError:
        return None


# =========================================================================
# Helpers para Cleaner (Categoría)
# =========================================================================

from blip_eraser.utils.scan import CLEANUP_CATEGORY_LABEL_KEYS

def get_cleanup_categories() -> list[str]:
    """Categorías disponibles en Limpiador (claves internas)."""
    return list(CLEANUP_CATEGORY_LABEL_KEYS.keys())


def get_category_display_name(cat_key: str) -> str:
    """Nombre legible de categoría para UI (usa i18n key)."""
    from blip_eraser.utils.i18n import tr
    return tr(CLEANUP_CATEGORY_LABEL_KEYS.get(cat_key, "col_name"))