# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import importlib
import os
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, cast

from ginext import Gdk, GLib, Gtk

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class WidgetLike(Protocol):
    def get_first_child(self) -> Gtk.Widget | None: ...
    def get_next_sibling(self) -> Gtk.Widget | None: ...


class TerminalLike(WidgetLike, Protocol):
    pass


class TabViewLike(Protocol):
    def get_n_pages(self) -> int: ...


class TabBarLike(WidgetLike, Protocol):
    pass


class TerminalWindowLike(Protocol):
    current_terminal: TerminalLike | None
    tab_view: TabViewLike
    tab_bar: TabBarLike


class TerminalAppLike(Protocol):
    def get_active_window(self) -> TerminalWindowLike | None: ...
    def activate(self) -> None: ...
    def quit(self) -> None: ...
    def run(self, argv: list[str]) -> int: ...


def _spin_main_context(
    predicate: Callable[[], bool], *, timeout_ms: int = 1000
) -> bool:
    context = GLib.MainContext.default()
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if predicate():
            return True
        context.iteration(False)
        time.sleep(0.01)
    return predicate()


def _require_gtk4_display(wayland: object) -> None:
    ok = Gtk.init_check()
    if isinstance(ok, tuple):
        ok = ok[0]
    assert ok
    assert Gdk.Display.get_default() is not None


def test_terminal_runtime_activation_opens_real_tabs(
    monkeypatch: MonkeyPatch,
    tmp_path: object,
    wayland: object,
) -> None:
    _require_gtk4_display(wayland)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/sh")

    terminal_app = importlib.import_module("examples.terminal.app")
    app_cls = terminal_app.TerminalApp

    monkeypatch.setattr(
        terminal_app,
        "_APP_ID",
        f"org.ginext.TerminalRuntimeTest{os.getpid()}.t{uuid.uuid4().hex}",
    )

    app = cast("TerminalAppLike", app_cls())
    observed: dict[str, int] = {}

    def drive_activations() -> bool:
        window = app.get_active_window()
        if window is None:
            return True
        terminal = window.current_terminal
        if terminal is None:
            return True

        observed["initial_pages"] = window.tab_view.get_n_pages()
        Gtk.NamedAction.new("win.new-tab").activate(
            0, cast("Gtk.Widget", terminal), None
        )
        observed["after_shortcut_pages"] = window.tab_view.get_n_pages()
        return False

    def record_and_quit() -> bool:
        window = app.get_active_window()
        if window is not None:
            if window.tab_view.get_n_pages() != 2:
                return True
            observed["final_pages"] = window.tab_view.get_n_pages()
        app.quit()
        return False

    GLib.timeout_add(100, drive_activations)
    GLib.timeout_add(300, record_and_quit)

    assert app.run(["terminal-test"]) == 0
    assert _spin_main_context(lambda: observed.get("final_pages") == 2)
    assert observed == {
        "initial_pages": 1,
        "after_shortcut_pages": 2,
        "final_pages": 2,
    }
