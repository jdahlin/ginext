# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import gc
import os
import uuid
from typing import Any

import pytest

try:
    from ginext import Adw
except ImportError:
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)


def _tab_bar_close_buttons(Gtk: Any, tab_bar: Any) -> list[Any]:
    buttons: list[Any] = []

    def walk(widget: Any) -> None:
        if isinstance(widget, Gtk.Button) and widget.get_icon_name() == "window-close-symbolic":
            buttons.append(widget)
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(tab_bar)
    return buttons


def test_close_page_method_signal_collision(require_gtk4_display: Any) -> None:
    Gtk = require_gtk4_display

    view = Adw.TabView()
    page = view.append(Gtk.Label(label="Terminal"))
    seen: list[Any] = []

    def on_close_page(tab_view: Any, tab_page: Any) -> bool:
        seen.append(tab_page)
        tab_view.close_page_finish(tab_page, True)
        return True

    view.close_page.connect(on_close_page)
    view.close_page(page)

    assert seen == [page]
    assert view.get_n_pages() == 0


def test_bound_method_signal_handler_survives_window_rewrap(
    require_gtk4_display: Any,
) -> None:
    from ginext import Gio

    Gtk = require_gtk4_display

    class Window(Gtk.ApplicationWindow):  # type: ignore[misc, name-defined]
        def __init__(self, application: Any) -> None:
            super().__init__(application=application)
            self.tab_view = Adw.TabView()
            self.set_child(self.tab_view)
            self.page = self.tab_view.append(Gtk.Label(label="Terminal"))
            self.close_count = 0
            self.tab_view.close_page.connect(self._on_close_page)

        def _on_close_page(self, view: Any, page: Any) -> bool:
            self.close_count += 1
            view.close_page_finish(page, True)
            return True

    app = Gtk.Application(
        application_id=f"org.ginext.TestAdwTabView{os.getpid()}.t{uuid.uuid4().hex}",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)

    window = Window(app)
    window.present()
    del window
    gc.collect()

    active = app.get_active_window()

    assert active is not None
    active.tab_view.close_page(active.page)
    assert active.close_count == 1
    assert active.tab_view.get_n_pages() == 0


def test_tab_bar_close_button_survives_window_rewrap(
    require_gtk4_display: Any,
) -> None:
    from ginext import Gio
    from ginext import GLib

    Gtk = require_gtk4_display

    class Window(Gtk.ApplicationWindow):  # type: ignore[misc, name-defined]
        def __init__(self, application: Any) -> None:
            super().__init__(application=application)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.tab_view = Adw.TabView()
            self.tab_bar = Adw.TabBar(view=self.tab_view, autohide=False)
            box.append(self.tab_bar)
            box.append(self.tab_view)
            self.set_child(box)
            self.close_count = 0
            self.tab_view.close_page.connect(self._on_close_page)
            self.tab_view.append(Gtk.Label(label="One"))
            self.tab_view.append(Gtk.Label(label="Two"))

        def _on_close_page(self, view: Any, page: Any) -> bool:
            self.close_count += 1
            view.close_page_finish(page, True)
            return True

    app = Gtk.Application(
        application_id=f"org.ginext.TestAdwTabBar{os.getpid()}.t{uuid.uuid4().hex}",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)

    window = Window(app)
    window.present()

    context = GLib.MainContext.default()
    for _ in range(10):
        context.iteration(False)

    del window
    gc.collect()

    active = app.get_active_window()

    assert active is not None
    buttons = _tab_bar_close_buttons(Gtk, active.tab_bar)
    assert buttons
    buttons[0].clicked()
    for _ in range(5):
        context.iteration(False)
    assert active.close_count == 1
    assert active.tab_view.get_n_pages() == 1
