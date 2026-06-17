# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import gc
import os
import uuid
import time
from collections.abc import Callable

import pytest

try:
    from ginext import Adw, GLib, Gio, Gtk
except ImportError:
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)


def _spin_until(predicate: Callable[[], bool], *, timeout_ms: int = 1000) -> bool:
    context = GLib.MainContext.default()
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if predicate():
            return True
        context.iteration(False)
        time.sleep(0.01)
    return bool(predicate())


def test_close_page_method_signal_collision(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    view = Adw.TabView()
    page = view.append(Gtk.Label(label="Terminal"))
    seen: list[Adw.TabPage] = []

    def on_close_page(tab_view: Adw.TabView, tab_page: Adw.TabPage) -> bool:
        seen.append(tab_page)
        tab_view.close_page_finish(tab_page, True)
        return True

    view.close_page.connect(on_close_page, owner=view)
    view.close_page(page)

    assert seen == [page]
    assert view.get_n_pages() == 0


def test_tab_view_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    view = Adw.TabView()
    first = view.append(Gtk.Label(label="One"))
    second = view.append(Gtk.Label(label="Two"))

    assert len(view) == 2
    assert list(view) == [first, second]
    assert view[0] is first
    assert view[-1] is second
    assert view[:] == [first, second]


def test_bound_method_signal_handler_survives_window_rewrap(
    require_gtk4_display: object,
) -> None:
    _ = require_gtk4_display

    class Window(Gtk.ApplicationWindow):
        def __init__(self, application: Gio.Application) -> None:
            super().__init__(application=application)
            self.tab_view = Adw.TabView()
            self.set_child(self.tab_view)
            self.page = self.tab_view.append(Gtk.Label(label="Terminal"))
            self.close_count = 0
            self.tab_view.close_page.connect(self._on_close_page)

        def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
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


def test_public_close_button_survives_window_rewrap(
    require_gtk4_display: object,
) -> None:
    _ = require_gtk4_display

    class Window(Gtk.ApplicationWindow):
        def __init__(self, application: Gio.Application) -> None:
            super().__init__(application=application)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.tab_view = Adw.TabView()
            self.close_button = Gtk.Button(label="Close")
            self.close_button.clicked.connect(self._on_close_button_clicked)
            box.append(self.close_button)
            box.append(self.tab_view)
            self.set_child(box)
            self.button_count = 0
            self.close_count = 0
            self.tab_view.close_page.connect(self._on_close_page)
            self.tab_view.append(Gtk.Label(label="One"))
            self.tab_view.append(Gtk.Label(label="Two"))

        def _on_close_button_clicked(self, button: Gtk.Button) -> None:
            self.button_count += 1
            page = self.tab_view.get_nth_page(self.tab_view.get_n_pages() - 1)
            self.tab_view.close_page(page)

        def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
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

    del window
    gc.collect()

    active = app.get_active_window()

    assert active is not None
    active.close_button.clicked()
    assert _spin_until(
        lambda: (
            active.button_count == 1
            and active.close_count == 1
            and active.tab_view.get_n_pages() == 1
        )
    )
    assert active.button_count == 1
    assert active.close_count == 1
    assert active.tab_view.get_n_pages() == 1
