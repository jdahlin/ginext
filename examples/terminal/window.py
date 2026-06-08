"""Main window — Adw.ApplicationWindow with an Adw.TabView of Vte.Terminals.

Each tab owns one Vte.Terminal spawned into the user's $SHELL. The window
listens to state changes (font, palette, …) and re-applies the prefs to
every open terminal.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ginext import Adw, Gio, GLib, GObject, Gtk, Pango, Vte

from . import palettes

if TYPE_CHECKING:
    from .app import TerminalApp
    from .state import TerminalState


_UI_DIR = Path(__file__).resolve().parent / "resources"
_WINDOW_UI = (_UI_DIR / "window.ui").read_text()
_MENUS_UI = str(_UI_DIR / "menus.ui")


_CURSOR_SHAPES: dict[str, Vte.CursorShape] = {
    "block": Vte.CursorShape.BLOCK,
    "ibeam": Vte.CursorShape.IBEAM,
    "underline": Vte.CursorShape.UNDERLINE,
}


def _user_shell() -> str:
    return os.environ.get("SHELL") or "/bin/sh"


@Gtk.Template(string=_WINDOW_UI)
class Window(Adw.ApplicationWindow, type_name="GinextTerminalWindow"):

    toast_overlay: Adw.ToastOverlay
    header_bar: Adw.HeaderBar
    title_label: Gtk.Label
    new_tab_button: Gtk.Button
    primary_menu_button: Gtk.MenuButton
    tab_view: Adw.TabView
    tab_bar: Adw.TabBar

    def __init__(self, application: TerminalApp, state: TerminalState) -> None:
        super().__init__(application=application)
        self.app = application
        self.state = state

        self.set_default_size(state.window_width, state.window_height)
        if state.window_maximized:
            self.maximize()

        builder = Gtk.Builder.new_from_file(_MENUS_UI)
        self.primary_menu_button.set_menu_model(
            cast("Gio.MenuModel", builder.get_object("primary_menu"))
        )

        self.tab_view.notify("selected-page").connect(self._on_selected_page_changed)
        self.tab_view.close_page.connect(self._on_close_page)
        self._tab_close_buttons: list[Gtk.Button] = []
        self._tab_close_button_pages: dict[Gtk.Button, Adw.TabPage] = {}
        self._terminal_pages: dict[Vte.Terminal, Adw.TabPage] = {}

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
            state.notify(key).connect(self._on_prefs_changed)

        self.close_request.connect(self._on_close_request)
        self.notify("default-width").connect(self._on_geometry_changed)
        self.notify("default-height").connect(self._on_geometry_changed)
        self.notify("maximized").connect(self._on_geometry_changed)

    _WIN_ACTIONS: tuple[tuple[str, str, list[str] | None], ...] = (
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

    def _install_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        for name, handler, accels in self._WIN_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.activate.connect(getattr(self, handler))
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
        if page is None:
            return None
        return cast("Vte.Terminal", page.get_child())

    def _iter_terminals(self) -> Iterator[Vte.Terminal]:
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            if page is not None:
                yield cast("Vte.Terminal", page.get_child())

    def new_tab(self) -> Vte.Terminal:
        term = Vte.Terminal()
        self._apply_prefs(term)
        term.child_exited.connect(self._on_child_exited)
        term.window_title_changed.connect(self._on_term_title_changed)
        term.bell.connect(self._on_bell)

        tab_page = self.tab_view.append(term)
        self._terminal_pages[term] = tab_page
        tab_page.set_title("Terminal")
        self.tab_view.set_selected_page(tab_page)
        GLib.idle_add(self._sync_tab_close_buttons)

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

    def _on_close_page(self, view: Adw.TabView, tab_page: Adw.TabPage) -> bool:
        # Vte cleans up its own PTY when the widget is unparented by
        # AdwTabView; don't poke set_pty(None) here — calling it after
        # the child has already exited has crashed inside libvte.
        child = tab_page.get_child()
        if isinstance(child, Vte.Terminal):
            self._terminal_pages.pop(child, None)
        view.close_page_finish(tab_page, True)
        GLib.idle_add(self._sync_tab_close_buttons)
        if self.tab_view.get_n_pages() == 0:
            GLib.idle_add(self.close)
        # Return GDK_EVENT_STOP so the default handler doesn't also call
        # close_page_finish on a page we've already finished closing.
        return True

    def _sync_tab_close_buttons(self) -> bool:
        buttons = self._tab_bar_close_buttons()
        self._tab_close_button_pages = {}
        n_pages = self.tab_view.get_n_pages()
        for index, button in enumerate(buttons):
            if index >= n_pages:
                break
            page = self.tab_view.get_nth_page(index)
            if page is not None:
                self._tab_close_button_pages[button] = page
        for button in buttons:
            if button not in self._tab_close_buttons:
                button.clicked.connect(self._on_tab_bar_close_button_clicked, owner=self)
        self._tab_close_buttons = buttons
        return False

    def _tab_bar_close_buttons(self) -> list[Gtk.Button]:
        buttons: list[Gtk.Button] = []

        def walk(widget: Gtk.Widget) -> None:
            if isinstance(widget, Gtk.Button):
                icon_name = widget.get_icon_name()
                if icon_name == "window-close-symbolic":
                    buttons.append(widget)
            child = widget.get_first_child()
            while child is not None:
                walk(child)
                child = child.get_next_sibling()

        walk(self.tab_bar)
        return buttons

    def _on_tab_bar_close_button_clicked(self, button: Gtk.Button) -> None:
        page = self._tab_close_button_pages.get(button)
        if page is None or not self._page_is_open(page):
            return
        self.tab_view.close_page(page)

    def _page_is_open(self, page: Adw.TabPage) -> bool:
        for index in range(self.tab_view.get_n_pages()):
            if self.tab_view.get_nth_page(index) is page:
                return True
        return False

    def _on_selected_page_changed(
        self, _view: Adw.TabView, _pspec: GObject.ParamSpec
    ) -> None:
        page = self.tab_view.get_selected_page()
        title = page.get_title() if page is not None else "Terminal"
        self.set_title(f"{title} — Terminal")
        self.title_label.set_label(title or "Terminal")

    def _on_term_title_changed(self, term: Vte.Terminal) -> None:
        title = term.get_window_title() or "Terminal"
        page = self._terminal_pages.get(term)
        if page is not None:
            page.set_title(title)
        if term is self.current_terminal:
            self.set_title(f"{title} — Terminal")
            self.title_label.set_label(title)

    def _on_child_exited(self, term: Vte.Terminal, _status: int) -> None:
        page = self._terminal_pages.get(term)
        if page is not None:
            self.tab_view.close_page(page)

    def _on_bell(self, _term: Vte.Terminal) -> None:
        # The audible bell is handled by Vte itself when enabled. We still
        # surface a toast so a muted terminal still has a visual cue.
        self._toast("Bell")

    # ------------------------------------------------------------------
    # Preferences sync
    # ------------------------------------------------------------------
    def _on_prefs_changed(self, _state: TerminalState, _pspec: GObject.ParamSpec) -> None:
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
    def _on_geometry_changed(self) -> None:
        if self.is_maximized():
            self.state.window_maximized = True
            return
        self.state.window_maximized = False
        # ginext returns a SimpleNamespace; PyGObject would return a tuple.
        size = self.get_default_size()
        w = getattr(size, "width", None)
        h = getattr(size, "height", None)
        if w and w > 0:
            self.state.window_width = w
        if h and h > 0:
            self.state.window_height = h

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        return False

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _toast(self, text: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(text))

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def _on_new_tab(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        self.new_tab()

    def _on_close_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_copy(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        term = self.current_terminal
        if term is not None:
            term.copy_clipboard_format(Vte.Format.TEXT)

    def _on_paste(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        term = self.current_terminal
        if term is not None:
            term.paste_clipboard()

    def _on_select_all(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        term = self.current_terminal
        if term is not None:
            term.select_all()

    def _on_zoom_in(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        term = self.current_terminal
        if term is not None:
            term.set_font_scale(min(term.get_font_scale() * 1.1, 4.0))

    def _on_zoom_out(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        term = self.current_terminal
        if term is not None:
            term.set_font_scale(max(term.get_font_scale() / 1.1, 0.25))

    def _on_zoom_reset(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        term = self.current_terminal
        if term is not None:
            term.set_font_scale(1.0)

    def _on_next_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.tab_view.select_next_page()

    def _on_prev_tab(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.tab_view.select_previous_page()

    def _on_reset(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        term = self.current_terminal
        if term is not None:
            term.reset(True, True)
