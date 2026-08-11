"""Diálogo compartido de confirmación para acciones destructivas.

Reutilizado por el Desinstalador, el Limpiador del sistema y la Vista general
(no duplican su propio confirm). Solo ofrece Sí/No: nunca un atajo de
"no volver a preguntar". Cuando el plan la marca como operación grande, el
total se resalta en color de advertencia.

La ejecución del borrado delega en `utils.privileges` (capa de privilegios):
las rutas del lote se agrupan en UNA llamada a pkexec cuando corresponda, y
los fallos se traducen a mensajes claros y localizados — sin tracebacks ni
rutas técnicas crudas. La lógica de qué comando correr vive en utils/.
"""

import subprocess

from PyQt6.QtWidgets import QMessageBox

from blip_eraser.utils.confirm import ConfirmPlan
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.privileges import RemovalError, remove_paths


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


def _friendly_error_message(error: RemovalError) -> str:
    """Traduce un RemovalError estructurado a un mensaje claro y localizado."""
    detail = error.detail.strip() if error.detail else ""
    first_path = str(error.paths[0]) if error.paths else ""
    if error.code == "cancelled":
        return tr("priv_error_cancelled")
    if error.code == "pkexec_missing":
        return tr("priv_error_missing")
    if error.code == "denied":
        return tr("priv_error_denied").format(path=first_path)
    # "failed" genérico: se muestra la ruta del lote sin el stderr crudo.
    return tr("priv_error_failed").format(path=first_path or "(?)")


def run_destructive_action(
    parent,
    plan: ConfirmPlan,
    title: str,
    log_key: str = "log_destructive_removed",
) -> bool:
    """Confirma y ejecuta el plan, agrupando el borrado de rutas.

    - Los ítems con `paths` se borran mediante `remove_paths` (ONE pkexec
      para todo el lote de sistema; rutas de $HOME directamente).
    - Los ítems con `remove` (pacman) se ejecutan por su cuenta.
    - Los fallos de privilegios se presentan como mensajes claros, nunca
      como tracebacks ni rutas técnicas crudas.
    Devuelve True si se eliminó al menos un elemento.
    """
    if not ask_destructive_confirmation(parent, plan, title):
        return False

    errors: list[str] = []
    removed = 0

    # 1) Borrado agrupado de rutas (una sola autenticación por lote).
    path_items = [item for item in plan.items if item.paths]
    batch_paths = [p for item in path_items for p in item.paths]
    if batch_paths:
        outcome = remove_paths(batch_paths)
        removed += outcome.removed
        errors.extend(_friendly_error_message(err) for err in outcome.errors)

    # 2) Acciones con `remove` (desinstalación vía pacman/pkexec, etc.).
    for item in plan.items:
        if item.remove is None or item.paths:
            continue
        try:
            item.remove()
            removed += 1
        except subprocess.CalledProcessError as e:
            if e.returncode == 126:  # automática cancelada en pkexec
                errors.append(tr("priv_error_cancelled"))
            else:
                errors.append(tr("priv_error_failed").format(path=item.label))
        except FileNotFoundError:
            errors.append(tr("priv_error_missing"))
        except (OSError, PermissionError) as e:
            errors.append(tr("priv_error_failed").format(path=item.label))
        except Exception as e:  # noqa: BLE001 - límite de la capa GUI
            errors.append(tr("priv_error_failed").format(path=item.label))

    if removed:
        log_buffer.add(tr(log_key).format(count=removed))
    if errors:
        QMessageBox.warning(parent, tr("some_errors_title"), "\n".join(errors))
    elif removed:
        QMessageBox.information(parent, tr("done_title"), tr("items_deleted_ok"))
    return removed > 0