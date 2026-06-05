"""Adw.Application subclass — owns the shared State + windows.

App-level actions:
  - app.new-window     (Ctrl+Shift+N): spawn another Window
  - app.preferences    (Ctrl+,):       open the preferences window
  - app.about:                         open AdwAboutWindow
  - app.quit           (Ctrl+Q):       close all windows
"""

from __future__ import annotations

# `import goi` then alias as gi so handler strings the GtkBuilder
# expects (which use the `gi`-style module shape internally) resolve.
import goi as _gir

_gir.install_as_gi()

# Versions: load before any submodule imports the namespaces.
_gir.require_versions(
    {
        "Gtk": "4.0",
        "Adw": "1",
        "GtkSource": "5",
    }
)

import signal
import sys

from goi.repository import Adw, Gio, GLib, Gtk

from examples.pyedit.document import Document
from examples.pyedit.state import State
from examples.pyedit.window import Window
from examples.pyedit.preferences import Preferences


_APP_ID = "org.goi.Pyedit"


class App(Gtk.Application):
    """Plain Gtk.Application (not Adw.Application) — Adw.init() runs from
    do_startup so libadwaita is set up exactly once. Going through
    Gtk.Application keeps the surface narrow to what goi already
    proves out in the test suite, and lets the example work even when
    libadwaita's app lifecycle hooks aren't fully wired through goi
    yet."""

    __gtype_name__ = "PyeditApp"

    def __init__(self):
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.state = State()
        self._prefs = None
        self._sigint_handle = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def do_startup(self):
        # goi's vfunc chain-up wants the explicit-class form with
        # `self`, not super(), to find the parent vfunc slot.
        Gtk.Application.do_startup(self)
        Adw.init()
        self._install_actions()
        self._install_sigint_handler()

    def _install_sigint_handler(self):
        """Ctrl+C in the controlling terminal cleanly quits the app —
        GLib.unix_signal_add wakes the main loop on SIGINT and routes
        to a Python callback. Falls back to Python's signal module on
        platforms that lack the GLib unix signal helper."""
        try:
            self._sigint_handle = GLib.unix_signal_add(
                GLib.PRIORITY_DEFAULT,
                signal.SIGINT,
                self._on_sigint,
            )
        except AttributeError:
            # Non-Unix or older GLib — fall back to Python's handler,
            # which fires once the interpreter regains control between
            # GTK iterations.
            signal.signal(signal.SIGINT, lambda *_: self.quit())

    def _on_sigint(self, *_):
        print("\n[pyedit] caught SIGINT, quitting", file=sys.stderr)
        self.quit()
        return False  # one-shot

    def do_activate(self):
        existing = self.get_active_window()
        if existing is None:
            win = self.spawn_window(present=True)
            # No files specified — open a draft so the user lands on
            # something they can type into.
            if win.tab_view.get_n_pages() == 0:
                win.add_document(Document())
        else:
            existing.present()

    def do_open(self, files, *_rest):
        """HANDLES_OPEN path — `gio open file://...` and cmdline file
        args route here. Each `Gio.File` opens in the active (or a new)
        window's tab view. *_rest absorbs whatever extra GApplication
        passes (n_files / hint can come through differently across
        goi/pygobject versions)."""
        win = self.get_active_window() or self.spawn_window(present=False)
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
    _APP_ACTIONS = (
        ("new-window", "_on_new_window", ["<Primary><Shift>n"]),
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
        self.spawn_window(present=True)

    def _on_preferences(self, *_a):
        if self._prefs is None:
            self._prefs = Preferences(self.state)
        win = self.get_active_window()
        if win is not None:
            self._prefs.set_transient_for(win)
        self._prefs.present()

    def _on_about(self, *_a):
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name="Pyedit",
            application_icon="document-edit-symbolic",
            developer_name="goi",
            version="0.0.0",
            comments="A small gnome-text-editor-shaped showcase for goi.",
            website="https://github.com/anthropics/goi",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _on_quit(self, *_a):
        for w in list(self.get_windows()):
            w.close()
