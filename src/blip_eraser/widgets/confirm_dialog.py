"""Diálogo compartido de confirmación para acciones destructivas.

Reutilizado por el Desinstalador, el Limpiador del sistema y la Vista general
(no duplican su propio confirm). Solo ofrece Sí/No: nunca un atajo de
"no volver a preguntar". Cuando el plan la marca como operación grande, el
total se resalta en color de advertencia. La ejecución del borrado (`remove`)
deja intacta la lógica real: este módulo solo la invoca y agrupa errores.
"""

from PyQt6.QtWidgets import QMessageBox

from blip_eraser.utils.confirm import ConfirmPlan
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer


def _plan_body(plan: ConfirmPlan) -> str:
    """HTML del cuerpo del diálogo: categorías + total (+ advertencia si es grande)."""
    lines = [tr("confirm_summary_intro")]
    for label, count, size in plan.category_lines:
        lines.append(f"&nbsp;&nbsp;<b>{label}</b> ({count}): {human_size(size)}")
    if plan.is_large:
        total = (
            f'<span style="color:#ff5555; font-weight:bold;">'
            f"⚠ {tr('confirm_large_size')}: {human_size(plan.total_bytes)}"
            f"</span>"
        )
        lines.append("")
        lines.append(total)
        lines.append(
            f'<span style="color:#ff5555; font-weight:bold;">'
            f"{tr('confirm_large_warning')}</span>"
        )
    else:
        lines.append("")
        lines.append(f"<b>{tr('confirm_total')}:</b> {human_size(plan.total_bytes)}")
    return "<br>".join(lines)


def ask_destructive_confirmation(parent, plan: ConfirmPlan, title: str) -> bool:
    """Pregunta Sí/No. Devuelve True solo con confirmación explícita.

    El diálogo no ofrece opciones para saltar la confirmación en el futuro:
    solo botones Sí y No, igual para cualquier cantidad seleccionada.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Warning if plan.is_large else QMessageBox.Icon.Question)
    box.setText(_plan_body(plan))
    yes = box.addButton(QMessageBox.StandardButton.Yes)
    box.addButton(QMessageBox.StandardButton.No)
    box.exec()
    return box.clickedButton() is yes


def run_destructive_action(
    parent,
    plan: ConfirmPlan,
    title: str,
    log_key: str = "log_destructive_removed",
) -> bool:
    """Confirma y ejecuta el plan: invoca el `remove` de cada ítem.

    Agrupa los errores individuales (las utilidades reales no se tocan) y
    muestra el resultado. Devuelve True si se eliminó al menos un elemento.
    """
    if not ask_destructive_confirmation(parent, plan, title):
        return False

    errors = []
    for item in plan.items:
        if item.remove is None:
            continue
        try:
            item.remove()
        except (OSError, PermissionError) as e:
            errors.append(f"{item.label}: {e}")

    removed = len(plan.items) - len(errors)
    if removed:
        log_buffer.add(tr(log_key).format(count=removed))
    if errors:
        QMessageBox.warning(parent, tr("some_errors_title"), "\n".join(errors))
    else:
        QMessageBox.information(parent, tr("done_title"), tr("items_deleted_ok"))
    return removed > 0