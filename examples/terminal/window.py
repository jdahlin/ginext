"""Main window — Adw.ApplicationWindow with an Adw.TabView of Vte.Terminals.

Each tab owns one Vte.Terminal spawned into the user's $SHELL. The window
listens to state changes (font, palette, …) and re-applies the prefs to
every open terminal.
"""

from __future__ import annotations

import os
from pathlib import Path

from goi.repository import Adw, Gio, GLib, Gtk, Pango, Vte

from . import palettes


_UI_DIR = Path(__file__).resolve().parent / "resources"
_WINDOW_UI = (_UI_DIR / "window.ui").read_text()
_MENUS_UI = str(_UI_DIR / "menus.ui")


_CURSOR_SHAPES = {
    "block": Vte.CursorShape.BLOCK,
    "ibeam": Vte.CursorShape.IBEAM,
    "underline": Vte.CursorShape.UNDERLINE,
}


def _user_shell() -> str:
    return os.environ.get("SHELL") or "/bin/sh"


@Gtk.Template(string=_WINDOW_UI)
class Window(Adw.ApplicationWindow):
    __gtype_name__ = "TerminalWindow"

    toast_overlay = Gtk.Template.Child()
    header_bar = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    new_tab_button = Gtk.Template.Child()
    primary_menu_button = Gtk.Template.Child()
    tab_view = Gtk.Template.Child()
    tab_bar = Gtk.Template.Child()

    def __init__(self, application, state):
        super().__init__(application=application)
        self.app = application
        self.state = state

        self.set_default_size(state.window_width, state.window_height)
        if state.window_maximized:
            self.maximize()

        builder = Gtk.Builder.new_from_file(_MENUS_UI)
        self.primary_menu_button.set_menu_model(builder.get_object("primary_menu"))

        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)
        self.tab_view.connect("close-page", self._on_close_page)

        self._install_actions()

        # Re-apply per-terminal prefs when any of them change.
        for key in (
            "font",
            "use-system-font",
            "palette",
            "scrollback-lines",
            "opacity",
            "cursor-shape",
            "audible-bell",
            "allow-bold",
            "scroll-on-output",
            "scroll-on-keystroke",
        ):
            state.connect(f"notify::{key}", self._on_prefs_changed)

        self.connect("close-request", self._on_close_request)
        self.connect("notify::default-width", self._on_geometry_changed)
        self.connect("notify::default-height", self._on_geometry_changed)
        self.connect("notify::maximized", self._on_geometry_changed)

    _WIN_ACTIONS = (
        ("new-tab", "_on_new_tab", ["<Primary><Shift>t"]),
        ("close-tab", "_on_close_tab", ["<Primary><Shift>w"]),
        ("copy", "_on_copy", ["<Primary><Shift>c"]),
        ("paste", "_on_paste", ["<Primary><Shift>v"]),
        ("select-all", "_on_select_all", ["<Primary><Shift>a"]),
        ("zoom-in", "_on_zoom_in", ["<Primary>plus", "<Primary>equal"]),
        ("zoom-out", "_on_zoom_out", ["<Primary>minus"]),
        ("zoom-reset", "_on_zoom_reset", ["<Primary>0"]),
        ("next-tab", "_on_next_tab", ["<Primary>Page_Down"]),
        ("prev-tab", "_on_prev_tab", ["<Primary>Page_Up"]),
        ("reset", "_on_reset", None),
    )

    def _install_actions(self):
        group = Gio.SimpleActionGroup()
        for name, handler, accels in self._WIN_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", getattr(self, handler))
            group.add_action(action)
            if accels:
                self.app.set_accels_for_action(f"win.{name}", list(accels))
        self.insert_action_group("win", group)

    # ------------------------------------------------------------------
    # Tab lifecycle
    # ------------------------------------------------------------------
    @property
    def current_terminal(self) -> Vte.Terminal | None:
        page = self.tab_view.get_selected_page()
        return page.get_child() if page is not None else None

    def _iter_terminals(self):
        n = self.tab_view.get_n_pages()
        for i in range(n):
            page = self.tab_view.get_nth_page(i)
            if page is not None:
                yield page.get_child()

    def new_tab(self) -> Vte.Terminal:
        term = Vte.Terminal()
        self._apply_prefs(term)
        term.connect("child-exited", self._on_child_exited)
        term.connect("window-title-changed", self._on_term_title_changed)
        term.connect("bell", self._on_bell)

        tab_page = self.tab_view.append(term)
        tab_page.set_title("Terminal")
        self.tab_view.set_selected_page(tab_page)

        shell = _user_shell()
        term.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.path.expanduser("~"),
            [shell],
            None,  # envv: inherit
            GLib.SpawnFlags.DEFAULT,
            None,  # child_setup
            -1,  # timeout: default
            None,  # cancellable
            None,  # callback
        )
        term.grab_focus()
        return term

    def _on_close_page(self, view, tab_page):
        # Vte cleans up its own PTY when the widget is unparented by
        # AdwTabView; don't poke set_pty(None) here — calling it after
        # the child has already exited has crashed inside libvte.
        view.close_page_finish(tab_page, True)
        if self.tab_view.get_n_pages() == 0:
            GLib.idle_add(self.close)
        # Return GDK_EVENT_STOP so the default handler doesn't also call
        # close_page_finish on a page we've already finished closing.
        return True

    def _on_selected_page_changed(self, *_a):
        page = self.tab_view.get_selected_page()
        title = page.get_title() if page is not None else "Terminal"
        self.set_title(f"{title} — Terminal")
        self.title_label.set_label(title or "Terminal")

    def _on_term_title_changed(self, term):
        title = term.get_window_title() or "Terminal"
        page = self.tab_view.get_page(term)
        if page is not None:
            page.set_title(title)
        if term is self.current_terminal:
            self.set_title(f"{title} — Terminal")
            self.title_label.set_label(title)

    def _on_child_exited(self, term, _status):
        page = self.tab_view.get_page(term)
        if page is not None:
            self.tab_view.close_page(page)

    def _on_bell(self, _term):
        # The audible bell is handled by Vte itself when enabled. We still
        # surface a toast so a muted terminal still has a visual cue.
        self._toast("Bell")

    # ------------------------------------------------------------------
    # Preferences sync
    # ------------------------------------------------------------------
    def _on_prefs_changed(self, *_a):
        for term in self._iter_terminals():
            self._apply_prefs(term)

    def _apply_prefs(self, term: Vte.Terminal) -> None:
        s = self.state

        # Font.
        if s.use_system_font:
            term.set_font(None)
        else:
            desc = Pango.FontDescription.from_string(s.font)
            term.set_font(desc)

        # Palette.
        bg, fg, ansi = palettes.resolve(s.palette)
        bg.alpha = max(0.0, min(1.0, float(s.opacity)))
        try:
            term.set_colors(fg, bg, ansi)
        except Exception:
            # Some Vte revisions want the ansi list length-checked or
            # the call to be split — fall back to the simpler form.
            term.set_color_background(bg)
            term.set_color_foreground(fg)

        # Scalars.
        term.set_scrollback_lines(int(s.scrollback_lines))
        term.set_audible_bell(bool(s.audible_bell))
        term.set_allow_bold(bool(s.allow_bold))
        term.set_scroll_on_output(bool(s.scroll_on_output))
        term.set_scroll_on_keystroke(bool(s.scroll_on_keystroke))
        term.set_cursor_shape(_CURSOR_SHAPES.get(s.cursor_shape, Vte.CursorShape.BLOCK))

    # ------------------------------------------------------------------
    # Window geometry persistence
    # ------------------------------------------------------------------
    def _on_geometry_changed(self, *_a):
        if self.is_maximized():
            self.state.window_maximized = True
            return
        self.state.window_maximized = False
        # goi returns a SimpleNamespace; PyGObject would return a tuple.
        size = self.get_default_size()
        w = getattr(size, "width", None)
        h = getattr(size, "height", None)
        if w and w > 0:
            self.state.window_width = w
        if h and h > 0:
            self.state.window_height = h

    def _on_close_request(self, *_a):
        return False

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _toast(self, text: str):
        self.toast_overlay.add_toast(Adw.Toast.new(text))

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def _on_new_tab(self, *_a):
        self.new_tab()

    def _on_close_tab(self, *_a):
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_copy(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.copy_clipboard_format(Vte.Format.TEXT)

    def _on_paste(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.paste_clipboard()

    def _on_select_all(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.select_all()

    def _on_zoom_in(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.set_font_scale(min(term.get_font_scale() * 1.1, 4.0))

    def _on_zoom_out(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.set_font_scale(max(term.get_font_scale() / 1.1, 0.25))

    def _on_zoom_reset(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.set_font_scale(1.0)

    def _on_next_tab(self, *_a):
        self.tab_view.select_next_page()

    def _on_prev_tab(self, *_a):
        self.tab_view.select_previous_page()

    def _on_reset(self, *_a):
        term = self.current_terminal
        if term is not None:
            term.reset(True, True)
