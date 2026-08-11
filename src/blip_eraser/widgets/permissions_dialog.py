"""Diálogo informativo de permisos — GUI.

Muestra el contenido de permisos (keys i18n de utils/i18n) de forma única en
la primera ejecución y queda accesible de nuevo desde Configuración/Ayuda sin
duplicar el texto: aquí solo se maquetan las mismas cadenas. Al pulsar
'Entendido' marca la bandera de visto en utils.permissions y cierra.
"""

from PyQt6.QtWidgets import QMessageBox

from blip_eraser.utils.i18n import tr
from blip_eraser.utils.permissions import mark_permissions_notice_shown


def _permissions_body() -> str:
    """Reutiliza el contenido i18n; NO lo duplica en charcos."""
    return "\n\n".join(
        [
            tr("permissions_notice_intro"),
            tr("permissions_point_scan"),
            tr("permissions_point_actions"),
            tr("permissions_point_root"),
        ]
    )


def show_permissions_dialog(parent=None) -> bool:
    """Muestra el diálogo modal. True si el usuario pulsó 'Entendido'."""
    box = QMessageBox(parent)
    box.setWindowTitle(tr("permissions_notice_title"))
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(_permissions_body())
    understood = box.addButton(
        tr("permissions_understood"), QMessageBox.ButtonRole.AcceptRole
    )
    box.exec()
    if box.clickedButton() is understood:
        mark_permissions_notice_shown()
        return True
    return False