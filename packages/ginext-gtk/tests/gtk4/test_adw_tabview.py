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


def _tab_bar_close_buttons(tab_bar: Gtk.Widget) -> list[Gtk.Button]:
    buttons: list[Gtk.Button] = []

    def walk(widget: Gtk.Widget) -> None:
        if (
            isinstance(widget, Gtk.Button)
            and widget.get_icon_name() == "window-close-symbolic"
        ):
            buttons.append(widget)
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(tab_bar)
    return buttons


def _button_is_interactable(button: Gtk.Button) -> bool:
    return button.get_visible() and button.get_sensitive() and button.get_mapped()


def _spin_until(predicate: Callable[[], bool], *, timeout_ms: int = 1000) -> bool:
    context = GLib.MainContext.default()
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if predicate():
            return True
        context.iteration(False)
        time.sleep(0.01)
    return bool(predicate())


def _click_any_close_button(
    tab_bar: Gtk.Widget,
    predicate: Callable[[], bool],
    *,
    timeout_ms: int = 1000,
) -> bool:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        buttons = [
            button
            for button in _tab_bar_close_buttons(tab_bar)
            if _button_is_interactable(button)
        ]
        for button in reversed(buttons):
            button.clicked()
            if _spin_until(predicate, timeout_ms=100):
                return True
            if button.activate() and _spin_until(predicate, timeout_ms=100):
                return True
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_close_page_method_signal_collision(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    view = Adw.TabView()
    page = view.append(Gtk.Label(label="Terminal"))
    seen: list[Adw.TabPage] = []

    def on_close_page(tab_view: Adw.TabView, tab_page: Adw.TabPage) -> bool:
        seen.append(tab_page)
        tab_view.close_page_finish(tab_page, True)
        return True

    view.close_page.connect(on_close_page)
    view.close_page(page)

    assert seen == [page]
    assert view.get_n_pages() == 0


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


def test_tab_bar_close_button_survives_window_rewrap(
    require_gtk4_display: object,
) -> None:
    _ = require_gtk4_display

    class Window(Gtk.ApplicationWindow):
        def __init__(self, application: Gio.Application) -> None:
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

    assert _spin_until(
        lambda: any(
            _button_is_interactable(button)
            for button in _tab_bar_close_buttons(window.tab_bar)
        )
    )

    del window
    gc.collect()

    active = app.get_active_window()

    assert active is not None
    assert _spin_until(
        lambda: any(
            _button_is_interactable(button)
            for button in _tab_bar_close_buttons(active.tab_bar)
        )
    )
    assert _click_any_close_button(
        active.tab_bar,
        lambda: active.close_count == 1 and active.tab_view.get_n_pages() == 1,
        timeout_ms=2000,
    )
    assert active.close_count == 1
    assert active.tab_view.get_n_pages() == 1
