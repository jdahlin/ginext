"""Gtk.Application subclass — owns the window factory and shared State.

App-level actions:
  - app.new-window     (Ctrl+N): spawn another Window
  - app.preferences    (Ctrl+,): open Preferences dialog
  - app.about:                   open AdwAboutWindow
  - app.quit           (Ctrl+Q): close all windows
"""

from __future__ import annotations

import signal
import sys
from typing import TYPE_CHECKING

from ginext import Adw, Gio, GLib, GLibUnix, Gtk, defaults

# Two Vte typelibs (2.91 / 3.91) are usually installed; pin the GTK 4 one
# before any module imports the namespace.
defaults.require("Vte", "3.91")

from .state import State
from .window import Window

if TYPE_CHECKING:
    from .preferences import Preferences


_APP_ID = "org.ginext.Terminal"


class App(Gtk.Application, type_name="TerminalApp"):

    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.state = State()
        self._sigint_handle = 0
        self._prefs_window: Preferences | None = None
        self._windows: list[Window] = []

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        Adw.init()
        self._install_actions()
        self._install_sigint_handler()

    def _install_sigint_handler(self) -> None:
        try:
            self._sigint_handle = GLibUnix.signal_add(
                GLib.PRIORITY_DEFAULT,
                signal.SIGINT,
                self._on_sigint,
            )
        except AttributeError:
            signal.signal(signal.SIGINT, lambda *_: self.quit())

    def _on_sigint(self, *_args: object) -> bool:
        print("\n[terminal] caught SIGINT, quitting", file=sys.stderr)
        self.quit()
        return False

    def do_activate(self) -> None:
        existing = self.get_active_window()
        if existing is None:
            win = self.spawn_window(present=True)
            win.new_tab()
        else:
            assert isinstance(existing, Window)
            existing.new_tab()
            existing.present()

    def do_command_line(self, _cmdline: Gio.ApplicationCommandLine) -> int:
        self.activate()
        return 0

    def spawn_window(self, *, present: bool) -> Window:
        win = Window(application=self, state=self.state)
        self._windows.append(win)
        win.close_request.connect(self._on_window_closed, owner=self)
        if present:
            win.present()
        return win

    def _on_window_closed(self, window: Window) -> bool:
        if window in self._windows:
            self._windows.remove(window)
        return False

    _APP_ACTIONS: tuple[tuple[str, str, list[str] | None], ...] = (
        ("new-window", "_on_new_window", ["<Primary>n"]),
        ("preferences", "_on_preferences", ["<Primary>comma"]),
        ("about", "_on_about", None),
        ("quit", "_on_quit", ["<Primary>q"]),
    )

    def _install_actions(self) -> None:
        for name, handler, accels in self._APP_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.activate.connect(getattr(self, handler))
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", list(accels))

    def _on_new_window(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        win = self.spawn_window(present=True)
        win.new_tab()

    def _on_preferences(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        from .preferences import Preferences

        if self._prefs_window is not None:
            self._prefs_window.present()
            return
        self._prefs_window = Preferences(self.state)
        self._prefs_window.set_transient_for(self.get_active_window())
        self._prefs_window.close_request.connect(self._on_prefs_closed)
        self._prefs_window.present()

    def _on_prefs_closed(self, _window: Adw.PreferencesWindow) -> bool:
        self._prefs_window = None
        return False

    def _on_about(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name="Terminal",
            application_icon="utilities-terminal-symbolic",
            developer_name="ginext",
            version="0.0.0",
            comments="A tabbed terminal showcase for ginext.",
            website="https://github.com/jdahlin/ginext",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _on_quit(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        for w in list(self.get_windows()):
            w.close()
