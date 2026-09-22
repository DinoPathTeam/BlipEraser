"""Tests GUI del borrado en segundo plano con diálogo de progreso.

Antes: run_destructive_action bloqueaba el hilo GUI (app "No responde").
Ahora: worker QThread + QProgressDialog modal sin cancelar + on_finished.
Requieren PyQt6; skipped sin él.
"""

import time

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

import blip_eraser.widgets.confirm_dialog as dlg_mod
from blip_eraser.utils.confirm import ConfirmItem, build_confirmation_plan
from blip_eraser.utils.privileges import RemovalOutcome


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _pump_until(app, cond, timeout_s=8.0):
    deadline = time.monotonic() + timeout_s
    while not cond() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert cond(), "timeout esperando fin del borrado"


class TestDeleteProgress:
    def test_runs_in_background_with_callback(self, app, monkeypatch, qtbot=None):
        """Progreso hasta el total, diálogo auto-cerrado y callback con True."""
        from pathlib import Path

        monkeypatch.setattr(dlg_mod, "ask_destructive_confirmation", lambda *a: True)
        monkeypatch.setattr(
            dlg_mod.QMessageBox, "information", lambda *a, **k: None
        )
        monkeypatch.setattr(dlg_mod.QMessageBox, "warning", lambda *a, **k: None)

        seen = []

        def fake_remove(paths, on_progress=None):
            out = RemovalOutcome()
            for i, _p in enumerate(paths, start=1):
                if on_progress:
                    on_progress(i, len(paths))
            out.removed = len(paths)
            return out

        monkeypatch.setattr(dlg_mod, "remove_paths", fake_remove)

        items = [
            ConfirmItem(label=f"f{i}", category_label="Basura", size_bytes=10, paths=[Path(f"/tmp/falso{i}")])
            for i in range(3)
        ]
        plan = build_confirmation_plan(items)
        done = []
        parent = QtWidgets.QWidget()
        dlg_mod.run_destructive_action(
            parent, plan, "t", on_finished=done.append
        )
        # El event loop bombea mientras el worker borra (antes se congelaba).
        _pump_until(app, lambda: len(done) == 1)
        assert done == [True]
        leftovers = [
            w for w in QtWidgets.QApplication.topLevelWidgets()
            if isinstance(w, QtWidgets.QProgressDialog) and w.isVisible()
        ]
        assert leftovers == []
        parent.close()

    def test_cancelled_confirm_calls_back_false(self, app, monkeypatch):
        """Sin confirmación: callback False y sin diálogo de progreso."""
        monkeypatch.setattr(dlg_mod, "ask_destructive_confirmation", lambda *a: False)
        plan = build_confirmation_plan([])
        done = []
        dlg_mod.run_destructive_action(
            QtWidgets.QWidget(), plan, "t", on_finished=done.append
        )
        assert done == [False]

    def test_theme_change_mid_delete_does_not_break(self, app, monkeypatch):
        """Un repolish (cambio de tema) con el diálogo abierto no tumba el borrado."""
        from pathlib import Path

        monkeypatch.setattr(dlg_mod, "ask_destructive_confirmation", lambda *a: True)
        monkeypatch.setattr(
            dlg_mod.QMessageBox, "information", lambda *a, **k: None
        )
        monkeypatch.setattr(dlg_mod.QMessageBox, "warning", lambda *a, **k: None)

        def slow_remove(paths, on_progress=None):
            import time as _time

            out = RemovalOutcome()
            for i, _p in enumerate(paths, start=1):
                _time.sleep(0.2)
                if on_progress:
                    on_progress(i, len(paths))
            out.removed = len(paths)
            return out

        monkeypatch.setattr(dlg_mod, "remove_paths", slow_remove)

        items = [
            ConfirmItem(label=f"g{i}", category_label="Basura", size_bytes=10, paths=[Path(f"/tmp/g{i}")])
            for i in range(4)
        ]
        done = []
        parent = QtWidgets.QWidget()
        dlg_mod.run_destructive_action(
            parent, build_confirmation_plan(items), "t", on_finished=done.append
        )
        # Cambio de tema a mitad: repolish global + eventos, como _apply_appearance.
        for _ in range(6):
            app.processEvents()
            app.setStyleSheet("QWidget { font-size: 10pt; }")
            for w in QtWidgets.QApplication.allWidgets():
                try:
                    w.style().unpolish(w)
                    w.style().polish(w)
                except RuntimeError:
                    pass  # widget muerto en C++: no debe tumbar el test
            time.sleep(0.15)
        _pump_until(app, lambda: len(done) == 1)
        assert done == [True]
        app.setStyleSheet("")
        parent.close()
