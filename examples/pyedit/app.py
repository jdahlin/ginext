"""Adw.Application subclass — owns the shared State + windows.

App-level actions:
  - app.new-window     (Ctrl+Shift+N): spawn another Window
  - app.preferences    (Ctrl+,):       open the preferences window
  - app.about:                         open AdwAboutWindow
  - app.quit           (Ctrl+Q):       close all windows
"""

from __future__ import annotations

import signal
import sys
from typing import cast

from ginext import Adw, Gio, GLib, GLibUnix, Gtk, defaults

# Several GtkSource typelibs (300/3.0/4/5) are usually installed; pin the
# GTK 4 series (5) before any submodule imports the namespace.
defaults.require("GtkSource", "5")

from examples.pyedit.document import Document
from examples.pyedit.state import State
from examples.pyedit.window import Window
from examples.pyedit.preferences import Preferences


_APP_ID = "org.ginext.Pyedit"


class App(Gtk.Application, type_name="PyeditApp"):
    """Plain Gtk.Application (not Adw.Application) — Adw.init() runs from
    do_startup so libadwaita is set up exactly once. Going through
    Gtk.Application keeps the surface narrow to what ginext already
    proves out in the test suite, and lets the example work even when
    libadwaita's app lifecycle hooks aren't fully wired through ginext
    yet."""

    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.state = State()
        self._prefs: Preferences | None = None
        self._sigint_handle = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def do_startup(self) -> None:
        # vfunc chain-up wants the explicit-class form with `self`, not
        # super(), to find the parent vfunc slot.
        Gtk.Application.do_startup(self)
        Adw.init()
        self._install_actions()
        self._install_sigint_handler()

    def _install_sigint_handler(self) -> None:
        """Ctrl+C in the controlling terminal cleanly quits the app —
        GLibUnix.signal_add wakes the main loop on SIGINT and routes
        to a Python callback. Falls back to Python's signal module on
        platforms that lack the GLib unix signal helper."""
        try:
            self._sigint_handle = GLibUnix.signal_add(
                GLib.PRIORITY_DEFAULT,
                signal.SIGINT,
                self._on_sigint,
            )
        except AttributeError:
            # Non-Unix or older GLib — fall back to Python's handler,
            # which fires once the interpreter regains control between
            # GTK iterations.
            signal.signal(signal.SIGINT, lambda *_: self.quit())

    def _on_sigint(self, *_args: object) -> bool:
        print("\n[pyedit] caught SIGINT, quitting", file=sys.stderr)
        self.quit()
        return False  # one-shot

    def do_activate(self) -> None:
        existing = self.get_active_window()
        if existing is None:
            win = self.spawn_window(present=True)
            # No files specified — open a draft so the user lands on
            # something they can type into.
            if win.tab_view.get_n_pages() == 0:
                win.add_document(Document())
        else:
            existing.present()

    def do_open(self, files: list[Gio.File], *_rest: object) -> None:
        """HANDLES_OPEN path — `gio open file://...` and cmdline file
        args route here. Each `Gio.File` opens in the active (or a new)
        window's tab view. *_rest absorbs whatever extra GApplication
        passes (n_files / hint can come through differently across
        binding versions)."""
        win = cast("Window | None", self.get_active_window()) or self.spawn_window(
            present=False
        )
        for gfile in files:
            win.open_file(gfile)
        win.present()

    # ------------------------------------------------------------------
    # Window factory
    # ------------------------------------------------------------------
    def spawn_window(self, *, present: bool) -> Window:
        win = Window(application=self, state=self.state)
        if present:
            win.present()
        return win

    # ------------------------------------------------------------------
    # App actions
    # ------------------------------------------------------------------
    _APP_ACTIONS: tuple[tuple[str, str, list[str] | None], ...] = (
        ("new-window", "_on_new_window", ["<Primary><Shift>n"]),
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
        self.spawn_window(present=True)

    def _on_preferences(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        if self._prefs is None:
            self._prefs = Preferences(self.state)
        win = self.get_active_window()
        if win is not None:
            self._prefs.set_transient_for(win)
        self._prefs.present()

    def _on_about(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name="Pyedit",
            application_icon="document-edit-symbolic",
            developer_name="ginext",
            version="0.0.0",
            comments="A small gnome-text-editor-shaped showcase for ginext.",
            website="https://github.com/jdahlin/ginext",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _on_quit(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        for w in list(self.get_windows()):
            w.close()
