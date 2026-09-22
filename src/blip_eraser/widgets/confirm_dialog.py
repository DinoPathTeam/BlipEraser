"""Diálogo compartido de confirmación para acciones destructivas.

Reutilizado por el Desinstalador, el Limpiador del sistema y la Vista general
(no duplican su propio confirm). Solo ofrece Sí/No: nunca un atajo de
"no volver a preguntar". Cuando el plan la marca como operación grande, el
total se resalta en color de advertencia.

La ejecución del borrado delega en `utils.privileges` (capa de privilegios):
las rutas del lote se agrupan en UNA llamada a pkexec cuando corresponda, y
los fallos se traducen a mensajes claros y localizados — sin tracebacks ni
rutas técnicas crudas. La lógica de qué comando correr vive en utils/.

SEGURIDAD: Las operaciones se despachan vía allowlist en `privileges.py`
(ALLOWED_OPERATIONS). ConfirmItem.operation debe ser un ID en esa allowlist.
NO se ejecutan callables arbitrarios (elimina vector RCE).
"""

import subprocess
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from blip_eraser.utils.confirm import ConfirmPlan
from blip_eraser.utils.file_utils import human_size
from blip_eraser.utils.i18n import tr
from blip_eraser.utils.log import log as log_buffer
from blip_eraser.utils.privileges import (
    RemovalError,
    remove_paths,
    get_allowed_operation,
)
from blip_eraser.utils.pacman import PackageIdentityUntrustedError
from blip_eraser.utils.scan_cache import invalidate


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


def ask_destructive_confirmation(parent: QWidget | None, plan: ConfirmPlan, title: str) -> bool:
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
    parent: QWidget | None,
    plan: ConfirmPlan,
    title: str,
    log_key: str = "log_destructive_removed",
    invalidate_sections: tuple[str, ...] = (),
    on_finished=None,
) -> None:
    """Confirma y ejecuta el plan en segundo plano con diálogo de progreso.

    - La confirmación Sí/No sigue siendo modal y síncrona.
    - El borrado corre en un QThread: la UI no se congela ("No responde").
    - El diálogo de progreso es modal SIN botón de cancelar: un borrado a
      medias no se puede interrumpir de forma segura. Se cierra solo al
      terminar. Modal también evita navegar a otra pestaña a mitad del
      borrado (los widgets pueden morir en C++ durante rescans).
    - `on_finished(success: bool)` se llama en el hilo GUI al terminar
      (para re-escanear, loguear, etc.). Ya no hay valor de retorno útil.
    """
    if not ask_destructive_confirmation(parent, plan, title):
        if on_finished is not None:
            on_finished(False)
        return

    path_items = [item for item in plan.items if item.paths]
    batch_paths = [p for item in path_items for p in item.paths]
    op_items = [item for item in plan.items if item.operation is not None and not item.paths]
    total = len(batch_paths) + len(op_items)

    dlg = QProgressDialog(
        _progress_text(plan.items[0].label if plan.items else "", 0, total),
        None, 0, max(total, 1), parent,
    )
    dlg.setWindowTitle(title)
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setCancelButton(None)
    dlg.show()

    worker = _DeleteWorker(batch_paths, op_items)
    worker.progress.connect(
        lambda done, _total, label: (
            dlg.setValue(done),
            dlg.setLabelText(_progress_text(label, done, total)),
        )
    )

    def _done(result: _DeleteResult):
        dlg.close()
        worker.deleteLater()
        if result.untrusted:
            QMessageBox.critical(
                parent,
                "Identidad no reconocida",
                "La identidad de los paquetes no pudo verificarse. "
                "La desinstalación fue bloqueada y la aplicación se cerrará.",
            )
            from PyQt6.QtWidgets import QApplication

            QApplication.quit()
            return
        if result.removed:
            log_buffer.add(tr(log_key).format(count=result.removed))
            for section in invalidate_sections:
                invalidate(section)
        if result.errors:
            QMessageBox.warning(parent, tr("some_errors_title"), "\n".join(result.errors))
        elif result.removed:
            QMessageBox.information(parent, tr("done_title"), tr("items_deleted_ok"))
        if on_finished is not None:
            on_finished(result.removed > 0)

    worker.finished.connect(_done)
    # Keeper anti-GC: el diálogo (que vive hasta el final) retiene al worker.
    dlg._delete_worker = worker
    worker.start()


def _progress_text(label: str, done: int, total: int) -> str:
    """'Eliminando <label>… (85/150)'. El % lo pinta el propio diálogo."""
    base = tr("delete_progress_label")
    if label:
        base = f"{base} {label}"
    if total > 0:
        return f"{base}… ({done}/{total})"
    return f"{base}…"


@dataclass
class _DeleteResult:
    removed: int = 0
    errors: list[str] = field(default_factory=list)
    untrusted: bool = False


class _DeleteWorker(QThread):
    """Ejecuta el borrado fuera del hilo GUI (mismo flujo que antes, con progreso)."""

    progress = pyqtSignal(int, int, str)  # done, total, label
    finished = pyqtSignal(object)  # _DeleteResult

    def __init__(self, batch_paths, op_items):
        super().__init__()
        self._batch_paths = batch_paths
        self._op_items = op_items

    def run(self):
        total = len(self._batch_paths) + len(self._op_items)
        done = 0
        result = _DeleteResult()

        def _tick(label: str = "", step: int = 1):
            nonlocal done
            done += step
            self.progress.emit(done, total, label)

        # 1) Borrado agrupado de rutas (una sola autenticación por lote).
        if self._batch_paths:
            outcome = remove_paths(
                self._batch_paths,
                on_progress=lambda d, _t: self.progress.emit(
                    d, total, str(self._batch_paths[min(d, len(self._batch_paths)) - 1])
                    if d > 0 else "",
                ),
            )
            done += len(self._batch_paths)
            result.removed += outcome.removed
            result.errors.extend(_friendly_error_message(err) for err in outcome.errors)

        # 2) Acciones con `operation` (desinstalación vía pacman, etc.).
        for item in self._op_items:
            op_func = get_allowed_operation(item.operation)
            if op_func is None:
                result.errors.append(tr("priv_error_failed").format(path=item.label))
                _tick(item.label)
                continue
            try:
                op_func(item.paths if item.operation == "rm_rf" else [item.label])
                result.removed += 1
            except subprocess.CalledProcessError as e:
                if e.returncode == 126:  # automática cancelada en pkexec
                    result.errors.append(tr("priv_error_cancelled"))
                else:
                    result.errors.append(tr("priv_error_failed").format(path=item.label))
            except FileNotFoundError:
                result.errors.append(tr("priv_error_missing"))
            except (OSError, PermissionError):
                result.errors.append(tr("priv_error_failed").format(path=item.label))
            except ValueError as e:
                # Paquetes no válidos (rechazados por validación en pacman.py)
                result.errors.append(str(e))
            except PackageIdentityUntrustedError:
                result.untrusted = True
                self.finished.emit(result)
                return
            except Exception:  # noqa: BLE001 - límite de la capa GUI
                result.errors.append(tr("priv_error_failed").format(path=item.label))
            _tick(item.label)

        self.finished.emit(result)