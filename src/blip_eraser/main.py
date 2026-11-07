"""Punto de entrada de BlipEraser.

Flujo:
  1. Nivel 1 (dependency_check): si falta PyQt6 se avisa por consola y
     se sale con código distinto de cero, porque sin PyQt6 no hay GUI.
     Por eso el import de PyQt6 se hace AQUÍ, una vez verificado.
  2. Idioma: si no hay preferencia guardada, el primer arranque pregunta
     (Español / English); si el usuario cierra sin elegir, se detecta del
     sistema. El resultado se guarda con set_language() ANTES de construir
     cualquier widget, para que todo se genere ya en el idioma correcto.
  3. Splash (widgets.splash_screen): logo + mensajes de progreso que
     StartupWorker (QThread) emite mientras hace comprobaciones REALES:
     binarios requeridos (pacman, pkexec) y dependencias del daemon.
     Nada bloqueante corre antes del splash.
  4. Al terminar el worker se construye la ventana principal
     (renderer.MainWindow), se muestra y se oculta el splash. Tras el primer
     escaneo se muestran los avisos con los resultados ya calculados (binarios
     faltantes y dependencias del daemon), sin repetir el trabajo. El diálogo
     de permisos solo está en Configuración.
"""

import sys

from blip_eraser.utils.dependency_check import (
    PYQT6_MISSING_MESSAGE,
    check_pyqt6_available,
)
from blip_eraser.utils.i18n import (
    load_saved_language,
    set_language,
    tr,
)
from blip_eraser.utils.ui_text import (
    resolve_initial_language,
    should_ask_for_language,
)

EXIT_PYQT6_MISSING = 2

__all__ = ["main"]


def _prompt_initial_language() -> str | None:
    """Diálogo de primer arranque con dos botones directos.

    Devuelve "es"/"en" según el botón pulsado, o None si el usuario
    cierra el diálogo sin elegir (la X).
    """
    from PyQt6.QtWidgets import QMessageBox

    box = QMessageBox()
    box.setWindowTitle(tr("language_first_run_title"))
    box.setText(tr("language_first_run_text"))
    es_button = box.addButton(
        tr("lang_name_es"), QMessageBox.ButtonRole.AcceptRole
    )
    en_button = box.addButton(
        tr("lang_name_en"), QMessageBox.ButtonRole.AcceptRole
    )
    box.exec()

    clicked = box.clickedButton()
    if clicked is es_button:
        return "es"
    if clicked is en_button:
        return "en"
    return None


def _warn_missing_dependencies(window, lines: list[str]) -> None:
    """Aviso de binarios faltantes, ya calculados durante el splash."""
    if not lines:
        return
    from PyQt6.QtWidgets import QMessageBox

    QMessageBox.warning(
        window,
        tr("missing_deps_title"),
        tr("missing_deps_intro").format(lines="\n\n".join(lines)),
    )


def _offer_daemon_deps(window, missing: list) -> tuple[bool, list[str]]:
    """Ofrece instalar las dependencias del daemon que faltan (Fase 2).

    `missing` lo calcula StartupWorker durante el splash: aquí no se ejecuta
    ningún subproceso de comprobación, solo se pregunta e instala.

    Returns:
        (restart_required, installed_list)
    """
    if not missing:
        return False, []

    from PyQt6.QtWidgets import QMessageBox
    from blip_eraser.utils.dependency_check import invalidate_daemon_deps_cache
    from blip_eraser.utils.phase2_installer import install_daemon_dependency

    lines = []
    for dep in missing:
        status = "no instalada" if not dep.check_cmd else "no activa"
        lines.append(f"• {dep.name}: {status}")

    msg = (
        f"El daemon privilegiado (Fase 2) requiere las siguientes dependencias:\n\n"
        f"{chr(10).join(lines)}\n\n"
        f"¿Desea instalarlas ahora? Se pedirá contraseña de administrador (pkexec)."
    )

    box = QMessageBox(window)
    box.setWindowTitle("Dependencias del daemon privilegiado")
    box.setText(msg)
    box.setIcon(QMessageBox.Icon.Question)
    yes_btn = box.addButton("Instalar", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    box.exec()

    if box.clickedButton() is not yes_btn:
        return False, []

    installed = []
    restart_required = False

    for dep in missing:
        success, detail = install_daemon_dependency(dep)
        if success:
            installed.append(dep.name)
            if dep.requires_restart:
                restart_required = True
        else:
            # Mostrar error pero continuar
            QMessageBox.warning(window, "Error", f"Error instalando {dep.name}: {detail}")

    invalidate_daemon_deps_cache()  # el estado cambió: la próxima lectura es real
    return restart_required, installed


def main() -> int:
    """Entry point. Devuelve el código de salida de la app."""
    if not check_pyqt6_available():
        print(PYQT6_MISSING_MESSAGE, file=sys.stderr)
        return EXIT_PYQT6_MISSING

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # Ícono de la aplicación (barra de tareas/dock). Fallback silencioso a
    # QIcon() vacío si el asset no existe (ver widgets/logo.py).
    from blip_eraser.widgets.logo import app_icon

    app.setWindowIcon(app_icon())

    saved = load_saved_language()
    if should_ask_for_language(saved):
        set_language(resolve_initial_language(_prompt_initial_language()))
    else:
        set_language(saved)

    from blip_eraser.renderer import MainWindow
    from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker

    splash = SplashScreen()
    splash.show()

    worker = StartupWorker()
    cancel_requested = {"value": False}

    def _on_splash_closed() -> None:
        # El usuario cerró el splash a mitad: se pide al worker parar en el
        # siguiente paso y se sale limpiamente cuando termine.
        cancel_requested["value"] = True
        worker.requestInterruption()

    def _on_worker_finished() -> None:
        if cancel_requested["value"]:
            app.quit()
            return

        window = MainWindow()
        window.show()
        # Aviso de versión nueva: hilo aparte + caché de 24 h; nunca bloquea.
        window.start_update_check()
        # Ocultar (no cerrar) el splash: hide() no dispara closeEvent, así
        # que `closed` solo se emite cuando el USUARIO lo cierra a mitad, no
        # en el cierre programático del camino de éxito.
        splash.hide()

        # Orden invertido: PRIMERO escaneo, LUEGO refresh_appearance().
        # Esto evita que _apply_appearance() (unpolish/polish global) deje
        # widgets en estado inconsistente antes de que el escaneo entregue
        # su resultado. El refresco de apariencia corre SOLO tras completar
        # el primer escaneo, encadenado vía callback.
        def _post_scan():
            window.refresh_appearance()

            # Aviso de binarios faltantes, calculado durante el splash.
            if worker.missing_lines:
                _warn_missing_dependencies(window, worker.missing_lines)

            # Dependencias del daemon (calculadas durante el splash): se
            # pregunta aquí, con la ventana ya visible, nunca antes del splash.
            restart_required, installed = _offer_daemon_deps(
                window, worker.missing_daemon_deps
            )
            if installed:
                from PyQt6.QtWidgets import QMessageBox

                text = "Se instalaron las siguientes dependencias:\n" + "\n".join(
                    f"• {d}" for d in installed
                )
                if restart_required:
                    text += "\n\nSe recomienda reiniciar el sistema para que AppArmor funcione correctamente."
                QMessageBox.information(window, "Dependencias instaladas", text)

        # Disparar escaneo PRIMERO, encadenar refresh_appearance() al final
        window._overview.start_initial_scan(on_finished=_post_scan)

    splash.closed.connect(_on_splash_closed)
    worker.message.connect(splash.set_message)
    worker.finished.connect(_on_worker_finished)
    worker.start()
    
    # Asegurar que el worker termine antes de que la app se cierre
    def _cleanup() -> None:
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(3000)  # Esperar hasta 3 segundos
    
    app.aboutToQuit.connect(_cleanup)
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())