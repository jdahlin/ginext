"""Adw.Application subclass — owns the window factory and shared State.

App-level actions:
  - app.new-window     (Ctrl+N): spawn another Window
  - app.preferences    (Ctrl+,): open Preferences dialog
  - app.about:                   open AdwAboutWindow
  - app.quit           (Ctrl+Q): close all windows
"""

from __future__ import annotations

import goi as _gir

_gir.install_as_gi()

_gir.require_versions(
    {
        "Gtk": "4.0",
        "Adw": "1",
        "Vte": "3.91",
    }
)

import signal
import sys

from goi.repository import Adw, Gio, GLib, Gtk

from .state import State
from .window import Window


_APP_ID = "org.goi.Terminal"


class App(Gtk.Application):
    __gtype_name__ = "TerminalApp"

    def __init__(self):
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.state = State()
        self._sigint_handle = 0
        self._prefs_window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Adw.init()
        self._install_actions()
        self._install_sigint_handler()

    def _install_sigint_handler(self):
        try:
            self._sigint_handle = GLib.unix_signal_add(
                GLib.PRIORITY_DEFAULT,
                signal.SIGINT,
                self._on_sigint,
            )
        except AttributeError:
            signal.signal(signal.SIGINT, lambda *_: self.quit())

    def _on_sigint(self, *_):
        print("\n[terminal] caught SIGINT, quitting", file=sys.stderr)
        self.quit()
        return False

    def do_activate(self):
        existing = self.get_active_window()
        if existing is None:
            win = self.spawn_window(present=True)
            win.new_tab()
        else:
            existing.present()

    def do_command_line(self, _cmdline):
        self.activate()
        return 0

    def spawn_window(self, *, present: bool) -> Window:
        win = Window(application=self, state=self.state)
        if present:
            win.present()
        return win

    _APP_ACTIONS = (
        ("new-window", "_on_new_window", ["<Primary>n"]),
        ("preferences", "_on_preferences", ["<Primary>comma"]),
        ("about", "_on_about", None),
        ("quit", "_on_quit", ["<Primary>q"]),
    )

    def _install_actions(self):
        for name, handler, accels in self._APP_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", getattr(self, handler))
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", list(accels))

    def _on_new_window(self, *_a):
        win = self.spawn_window(present=True)
        win.new_tab()

    def _on_preferences(self, *_a):
        from .preferences import Preferences

        if self._prefs_window is not None:
            self._prefs_window.present()
            return
        self._prefs_window = Preferences(self.state)
        self._prefs_window.set_transient_for(self.get_active_window())
        self._prefs_window.connect("close-request", self._on_prefs_closed)
        self._prefs_window.present()

    def _on_prefs_closed(self, *_a):
        self._prefs_window = None
        return False

    def _on_about(self, *_a):
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name="Terminal",
            application_icon="utilities-terminal-symbolic",
            developer_name="goi",
            version="0.0.0",
            comments="A tabbed terminal showcase for goi.",
            website="https://github.com/anthropics/goi",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _on_quit(self, *_a):
        for w in list(self.get_windows()):
            w.close()
