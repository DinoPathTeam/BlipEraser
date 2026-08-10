"""Plan de confirmación de acciones destructivas — lógica pura, sin PyQt6.

Centraliza cómo se categoriza lo que se va a borrar (por tipo: aplicación,
dependencia, carpeta suelta; o por categoría de limpieza: basura/caché/registros),
cuánto suman y si es una operación de gran tamaño. La GUI
(widgets/confirm_dialog) reutiliza este plan para el Desinstalador, el
Limpiador del sistema y el botón de limpieza de la Vista general.

Regla de seguridad: toda acción destructiva pide confirmación SIEMPRE.
No existe opción de "no volver a preguntar": ConfirmPlan no contempla saltar
el diálogo ni este módulo persiste ningún estado de confirmación.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# Operaciones con un total igual o mayor a esto se destacan visualmente.
LARGE_DELETE_THRESHOLD_BYTES: int = 5 * 1024**3  # 5 GiB

# Política de la app: confirmación obligatoria, sin excepción.
ALWAYS_CONFIRM_DESTRUCTIVE: bool = True


@dataclass
class ConfirmItem:
    """Un elemento concreto que la acción destructiva va a eliminar.

    - `label`: nombre visible (paquete, carpeta suelta, elemento de caché...).
    - `category_label`: etiqueta localizada de la categoría a la que pertenece
      ("Carpeta suelta", "Basura", ...). Se usa para agrupar el resumen.
    - `size_bytes`: espacio que se liberaría al eliminarlo.
    - `remove`: callable sin argumentos que ejecuta el borrado real
      (p. ej. un cierre sobre `delete_path` o `uninstall_packages`).
    """
    label: str
    category_label: str
    size_bytes: int = 0
    remove: Callable[[], None] | None = None


@dataclass
class ConfirmPlan:
    """Resultado estructurado de `build_confirmation_plan`: qué se agrupa y cuánto."""
    items: list[ConfirmItem]
    category_lines: list[tuple[str, int, int]]  # (categoría, cantidad, bytes)
    total_bytes: int
    is_large: bool


def is_large_operation(total_bytes: int) -> bool:
    """True si el total a liberar alcanza (o supera) el umbral de gran tamaño."""
    return total_bytes >= LARGE_DELETE_THRESHOLD_BYTES


def build_category_summary(
    items: list[ConfirmItem],
) -> list[tuple[str, int, int]]:
    """Agrupa los ítems por categoría: (categoría, cantidad, bytes totales).

    Ordenado de mayor a menor espacio para que lo más pesado encabece el
    resumen; dentro de una misma categoría se suma el tamaño de sus ítems.
    """
    buckets: dict[str, list[int]] = {}
    for item in items:
        buckets.setdefault(item.category_label, []).append(item.size_bytes)
    summary = [(label, len(sizes), sum(sizes)) for label, sizes in buckets.items()]
    summary.sort(key=lambda row: row[2], reverse=True)
    return summary


def build_confirmation_plan(items: list[ConfirmItem]) -> ConfirmPlan:
    """Construye el plan de confirmación a partir de los ítems seleccionados.

    El plan es neutro en idioma: la GUI lo traduce y lo destaca. `is_large`
    sale de `is_large_operation(total_bytes)`, que es donde vive el umbral.
    """
    category_lines = build_category_summary(items)
    total_bytes = sum(item.size_bytes for item in items)
    return ConfirmPlan(
        items=items,
        category_lines=category_lines,
        total_bytes=total_bytes,
        is_large=is_large_operation(total_bytes),
    )