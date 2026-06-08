# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import os
import uuid
from typing import Any


def _require_gtk4_display(wayland: object) -> object:
    from ginext import Gdk, Gtk

    ok = Gtk.init_check()
    if isinstance(ok, tuple):
        ok = ok[0]
    assert ok
    assert Gdk.Display.get_default() is not None
    return Gtk


def _tab_bar_close_buttons(Gtk: Any, window: Any) -> list[Any]:
    buttons: list[Any] = []

    def walk(widget: Any) -> None:
        if isinstance(widget, Gtk.Button) and widget.get_icon_name() == "window-close-symbolic":
            buttons.append(widget)
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(window.tab_bar)
    return buttons


def test_terminal_runtime_activation_opens_real_tabs(
    monkeypatch: Any,
    tmp_path: object,
    wayland: object,
) -> None:
    Gtk = _require_gtk4_display(wayland)
    from ginext import GLib

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/sh")

    from examples.terminal import app as terminal_app
    from examples.terminal.app import App

    monkeypatch.setattr(
        terminal_app,
        "_APP_ID",
        f"org.ginext.TerminalRuntimeTest{os.getpid()}.t{uuid.uuid4().hex}",
    )

    app = App()
    observed: dict[str, int] = {}

    def drive_activations() -> bool:
        window = app.get_active_window()
        if window is None:
            return True
        terminal = window.current_terminal
        if terminal is None:
            return True

        observed["initial_pages"] = window.tab_view.get_n_pages()
        Gtk.NamedAction.new("win.new-tab").activate(0, terminal, None)
        observed["after_shortcut_pages"] = window.tab_view.get_n_pages()
        app.activate()
        observed["after_app_activation_pages"] = window.tab_view.get_n_pages()
        GLib.idle_add(click_tab_bar_close_button)
        return False

    def click_tab_bar_close_button() -> bool:
        window = app.get_active_window()
        if window is None:
            return True
        buttons = _tab_bar_close_buttons(Gtk, window)
        if len(buttons) < 3:
            return True
        buttons[-1].clicked()
        observed["after_close_tab_pages"] = window.tab_view.get_n_pages()
        return False

    def record_and_quit() -> bool:
        window = app.get_active_window()
        if window is not None:
            observed["final_pages"] = window.tab_view.get_n_pages()
        app.quit()
        return False

    GLib.timeout_add(100, drive_activations)
    GLib.timeout_add(500, record_and_quit)

    assert app.run(["terminal-test"]) == 0
    assert observed == {
        "initial_pages": 1,
        "after_shortcut_pages": 2,
        "after_app_activation_pages": 3,
        "after_close_tab_pages": 2,
        "final_pages": 2,
    }
