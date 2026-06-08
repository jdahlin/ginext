"""Gtk.Application subclass — owns the window factory and shared State.

App-level actions:
  - app.new-window     (Ctrl+N): spawn another Window
  - app.preferences    (Ctrl+,): open Preferences dialog
  - app.about:                   open AdwAboutWindow
  - app.quit           (Ctrl+Q): close all windows
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ginext import Adw, Gio, Gtk, defaults

# Two Vte typelibs (2.91 / 3.91) are usually installed; pin the GTK 4 one
# before any module imports the namespace.
defaults.require("Vte", "3.91")

from .state import TerminalState
from .window import Window

if TYPE_CHECKING:
    from .preferences import Preferences


_APP_ID = "org.ginext.Terminal"


class TerminalApp(Adw.Application):

    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.state = TerminalState()
        self._prefs_window: Preferences | None = None
        self._windows: list[Window] = []

    def do_activate(self) -> None:
        if active_window := self.get_active_window():
            active_window.present()
            if isinstance(active_window, Window):
                active_window.new_tab()
        else:
            self.spawn_window(present=True)

    def do_command_line(self, _cmdline: Gio.ApplicationCommandLine) -> int:
        self.activate()
        return 0

    def spawn_window(self, *, present: bool) -> Window:
        win = Window(application=self, state=self.state)
        self._windows.append(win)
        win.close_request.connect(self._on_window_closed)
        if present:
            win.present()
        win.new_tab()
        return win

    def _on_window_closed(self, window: Window) -> bool:
        if window in self._windows:
            self._windows.remove(window)
        return False

    @Gtk.action("new-window", ["<Primary>n"])
    def _on_new_window(self) -> None:
        self.spawn_window(present=True)

    @Gtk.action("preferences", ["<Primary>comma"])
    def _on_preferences(self) -> None:
        if not (prefs_window := self._prefs_window):
            from .preferences import Preferences
            prefs_window = Preferences(self.state)
            prefs_window.set_transient_for(self.get_active_window())
            prefs_window.close_request.connect(self._on_prefs_closed)
            self._prefs_window = prefs_window
        prefs_window.present()

    def _on_prefs_closed(self, _prefs_window: Preferences) -> bool:
        self._prefs_window = None
        return False

    @Gtk.action("about")
    def _on_about(self) -> None:
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

    @Gtk.action("quit")
    def _on_quit(self) -> None:
        for w in list(self.get_windows()):
            w.close()


App = TerminalApp
