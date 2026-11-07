"""Tests de GUI para widgets/sidebar_activity.py (requieren PyQt6)."""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.utils.log import LogBuffer
from blip_eraser.widgets.sidebar_activity import MAX_CHARS, MAX_ROWS, SidebarActivity, shorten


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _make(app, buffer):
    widget = SidebarActivity(buffer=buffer)
    widget.show()  # sin show(), isVisible() es siempre False en los hijos
    return widget


def _visible_messages(widget):
    return [r.message.text() for r in widget._rows if not r.isHidden()]


def test_shorten_keeps_short_and_trims_long():
    assert shorten("hola") == "hola"
    long = "x" * 200
    out = shorten(long)
    assert len(out) == MAX_CHARS and out.endswith("…")


def test_empty_state_visible_without_entries(app):
    widget = _make(app, LogBuffer())
    assert not widget.empty.isHidden()
    assert _visible_messages(widget) == []
    widget.detach()


def test_shows_newest_first_and_hides_empty_state(app):
    buf = LogBuffer()
    widget = _make(app, buf)
    buf.add("uno")
    buf.add("dos")
    assert widget.empty.isHidden()
    assert _visible_messages(widget) == ["dos", "uno"]
    assert widget._rows[0].property("latest") is True
    assert widget._rows[1].property("latest") is False
    widget.detach()


def test_limits_rows_to_max(app):
    buf = LogBuffer()
    widget = _make(app, buf)
    for i in range(MAX_ROWS + 4):
        buf.add(f"evento {i}")
    shown = _visible_messages(widget)
    assert len(shown) == MAX_ROWS
    assert shown[0] == f"evento {MAX_ROWS + 3}"
    widget.detach()


def test_clearing_buffer_restores_empty_state(app):
    buf = LogBuffer()
    widget = _make(app, buf)
    buf.add("algo")
    buf.clear()
    assert not widget.empty.isHidden()
    assert _visible_messages(widget) == []
    widget.detach()


def test_tooltip_keeps_full_message(app):
    buf = LogBuffer()
    widget = _make(app, buf)
    full = "mensaje " * 30
    buf.add(full)
    assert widget._rows[0].toolTip() == full
    assert widget._rows[0].message.text().endswith("…")
    widget.detach()


def test_destroyed_widget_is_dropped_by_buffer(app):
    from PyQt6 import sip

    buf = LogBuffer()
    widget = _make(app, buf)
    sip.delete(widget)
    buf.add("tras destruir")  # no debe lanzar
    assert buf._listeners == []


def test_sidebar_list_fits_content(app):
    from blip_eraser.widgets.sidebar import Sidebar

    sidebar = Sidebar()
    assert sidebar.minimumHeight() == sidebar.maximumHeight()
    assert sidebar.height() >= 0 and sidebar.maximumHeight() > 5 * 76
