"""Main window — Adw.ApplicationWindow with tab view, search bar, statusbar.

UI from window.ui; this module wires the action set, the tab lifecycle,
and the status bar updates. Each window keeps its own set of actions
under the `win.*` prefix; the `tab.*` action group is installed on
the active tab's Page and swapped on tab change.

Action groups:
  - `win.*`   — per-window (this class)
  - `app.*`   — app-level (App class), e.g. preferences, about
  - `tab.*`   — installed on the current page for tab-context actions
                (close, close-others, move-to-new-window)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from ginext import Adw, Gio, GLib, GObject, Gtk

from examples.pyedit.document import Document
from examples.pyedit.page import Page
from examples.pyedit.search_bar import SearchBar  # noqa: F401  (registered for .ui)

if TYPE_CHECKING:
    from collections.abc import Callable

    from examples.pyedit.app import App
    from examples.pyedit.state import State


_UI_DIR = Path(__file__).resolve().parent / "resources"
_WINDOW_UI = (_UI_DIR / "window.ui").read_text()
_MENUS_UI = str(_UI_DIR / "menus.ui")
_SHORTCUTS_UI = str(_UI_DIR / "shortcuts.ui")


@Gtk.Template(string=_WINDOW_UI)
class Window(Adw.ApplicationWindow, type_name="PyeditWindow"):

    toast_overlay: Adw.ToastOverlay
    header_bar: Adw.HeaderBar
    window_title: Adw.WindowTitle
    primary_menu_button: Gtk.MenuButton
    save_button: Gtk.Button
    search_button: Gtk.ToggleButton
    new_tab_button: Gtk.Button
    open_button: Gtk.Button
    tab_view: Adw.TabView
    tab_bar: Adw.TabBar
    content_stack: Gtk.Stack
    empty_state: Adw.StatusPage
    search_bar_slot: Gtk.Box
    status_position: Gtk.Label
    status_lang: Gtk.Label

    def __init__(self, application: App, state: State) -> None:
        super().__init__(application=application)
        self.app = application
        self.state = state

        # Restore geometry from prefs. Width/height only — Adw decides
        # maximize through its own state machine.
        if state.window_width > 200 and state.window_height > 200:
            self.set_default_size(state.window_width, state.window_height)
        if state.window_maximized:
            self.maximize()

        # Track resize/maximize so future launches restore.
        self.notify("default-width").connect(self._on_size_changed)
        self.notify("default-height").connect(self._on_size_changed)
        self.notify("maximized").connect(self._on_maximized_changed)

        # Menus: load primary + tab GMenu from menus.ui.
        builder = Gtk.Builder.new_from_file(_MENUS_UI)
        self.primary_menu_button.set_menu_model(
            cast("Gio.MenuModel", builder.get_object("primary_menu"))
        )
        self._tab_menu = cast("Gio.MenuModel", builder.get_object("tab_menu"))
        self.tab_view.set_menu_model(self._tab_menu)
        # Recent Files: section inside the primary menu's Open Recent
        # submenu. Rebuilt every time `state.recent_files_changed` fires.
        self._recent_section = cast(
            "Gio.Menu", builder.get_object("recent_files_section")
        )
        self.state.recent_files_changed.connect(self._rebuild_recent_menu)

        # Help overlay (Gtk.ShortcutsWindow) — built lazily via a
        # Gtk.Builder when the user triggers the win.show-help-overlay
        # action.
        self._help_overlay: Gtk.ShortcutsWindow | None = None

        # Tab view signals.
        self.tab_view.notify("selected-page").connect(self._on_selected_page_changed)
        self.tab_view.close_page.connect(self._on_close_page)
        self.tab_view.create_window.connect(self._on_create_window)

        # Build the search bar in Python (a nested @Gtk.Template inside the
        # window's template isn't auto-wired, so we instantiate the
        # SearchBar widget directly and graft it into the slot the .ui
        # reserved for it).
        self._search_bar = SearchBar()
        self.search_bar_slot.append(self._search_bar)

        self._install_actions()
        self._refresh_empty_state()

        # Mirror GtkSearchBar's search-mode-enabled ↔ the header toggle
        # button so opening the bar via Ctrl+F also lights the toolbar
        # toggle.
        self._search_bar.search_bar.bind_property(
            "search-mode-enabled",
            self.search_button,
            "active",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

    # ------------------------------------------------------------------
    # Action set
    # ------------------------------------------------------------------
    _WIN_ACTIONS: tuple[tuple[str, str, list[str] | None], ...] = (
        # (action-name, handler, accel)
        ("new-tab", "_on_new_tab", ["<Primary>n"]),
        ("open", "_on_open", ["<Primary>o"]),
        ("save", "_on_save", ["<Primary>s"]),
        ("save-as", "_on_save_as", ["<Primary><Shift>s"]),
        ("save-all", "_on_save_all", ["<Primary><Alt>s"]),
        ("close-tab", "_on_close_tab", ["<Primary>w"]),
        ("close-window", "_on_close_window", ["<Primary><Shift>w"]),
        ("find", "_on_find", ["<Primary>f"]),
        ("replace", "_on_replace", ["<Primary>h"]),
        ("find-next", "_on_find_next", ["<Primary>g"]),
        ("find-previous", "_on_find_previous", ["<Primary><Shift>g"]),
        ("goto-line", "_on_goto_line", ["<Primary>i"]),
        ("undo", "_on_undo", ["<Primary>z"]),
        ("redo", "_on_redo", ["<Primary><Shift>z"]),
        ("cut", "_on_cut", None),
        ("copy", "_on_copy", None),
        ("paste", "_on_paste", None),
        ("select-all", "_on_select_all", ["<Primary>a"]),
        ("toggle-line-numbers", "_on_toggle_line_numbers", None),
        ("toggle-highlight-line", "_on_toggle_highlight_line", None),
        ("toggle-right-margin", "_on_toggle_right_margin", None),
        ("toggle-wrap", "_on_toggle_wrap", None),
        ("toggle-map", "_on_toggle_map", None),
        ("toggle-fullscreen", "_on_toggle_fullscreen", ["F11"]),
        ("show-help-overlay", "_on_show_help_overlay", ["<Primary>question"]),
        ("next-tab", "_on_next_tab", ["<Primary>Tab", "<Primary>Page_Down"]),
        ("prev-tab", "_on_prev_tab", ["<Primary><Shift>Tab", "<Primary>Page_Up"]),
    )

    def _install_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        for name, handler, accels in self._WIN_ACTIONS:
            action = Gio.SimpleAction.new(name, None)
            action.activate.connect(getattr(self, handler))
            group.add_action(action)
            if accels:
                self.app.set_accels_for_action(f"win.{name}", list(accels))
        # Recent-files actions: `open-recent` is parameterized on the
        # URI string so one action serves every menu entry; `clear-
        # recents` is plain.
        open_recent = Gio.SimpleAction.new("open-recent", GLib.VariantType.new("s"))
        open_recent.activate.connect(self._on_open_recent)
        group.add_action(open_recent)
        clear_recents = Gio.SimpleAction.new("clear-recents", None)
        clear_recents.activate.connect(self._on_clear_recents)
        group.add_action(clear_recents)
        self.insert_action_group("win", group)
        # Seed the submenu with whatever was persisted across launches.
        self._rebuild_recent_menu()

    # ------------------------------------------------------------------
    # Tab lifecycle
    # ------------------------------------------------------------------
    @property
    def current_page(self) -> Page | None:
        page = self.tab_view.get_selected_page()
        return cast("Page", page.get_child()) if page is not None else None

    def add_document(self, document: Document, *, focus: bool = True) -> Page:
        page_widget: Page = Page(document, self.state)
        tab_page = self.tab_view.append(page_widget)
        self._bind_tab_page(tab_page, document)
        if focus:
            self.tab_view.set_selected_page(tab_page)
            page_widget.grab_editor_focus()
        self._refresh_empty_state()
        return page_widget

    def _bind_tab_page(self, tab_page: Adw.TabPage, document: Document) -> None:
        tab_page.set_title(document.display_name)
        tab_page.set_tooltip(document.uri or document.title)
        document.notify("title").connect(
            lambda *_a: tab_page.set_title(document.display_name),
            owner=tab_page,
        )
        document.notify("modified").connect(
            lambda *_a: tab_page.set_indicator_icon(
                Gio.ThemedIcon.new("document-modified-symbolic")
                if document.modified
                else None
            ),
            owner=tab_page,
        )

    def _on_selected_page_changed(self, *_a: object) -> None:
        page = self.current_page
        self._search_bar.attach_page(page)
        self._refresh_title()
        self._refresh_status()
        if page is not None:
            page.document.buffer.notify("cursor-position").connect(
                self._refresh_status
            )

    def _on_close_page(self, view: Adw.TabView, tab_page: Adw.TabPage) -> bool:
        page_widget = cast("Page", tab_page.get_child())
        doc = page_widget.document
        if doc.modified:
            self._confirm_close(tab_page, doc, page_widget)
            return True
        view.close_page_finish(tab_page, True)
        GLib.idle_add(self._refresh_empty_state)
        return False

    def _confirm_close(
        self, tab_page: Adw.TabPage, doc: Document, page_widget: Page
    ) -> None:
        dialog = Adw.MessageDialog.new(
            self,
            f"Save changes to “{doc.display_name}”?",
            "If you don't save, your changes will be lost.",
        )
        dialog.add_response("discard", "_Discard")
        dialog.add_response("cancel", "_Cancel")
        dialog.add_response("save", "_Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def respond(_d: Adw.MessageDialog, response: str) -> None:
            if response == "save":
                self._save_document(
                    doc,
                    on_done=lambda ok: self.tab_view.close_page_finish(tab_page, ok),
                )
            elif response == "discard":
                self.tab_view.close_page_finish(tab_page, True)
            else:
                self.tab_view.close_page_finish(tab_page, False)
            GLib.idle_add(self._refresh_empty_state)

        dialog.response.connect(respond)
        dialog.present()

    def _on_create_window(self, _view: Adw.TabView) -> Adw.TabView:
        new = self.app.spawn_window(present=True)
        return new.tab_view

    def _refresh_empty_state(self, *_a: object) -> None:
        n = self.tab_view.get_n_pages()
        self.content_stack.set_visible_child_name("tabs" if n else "empty")
        self.tab_bar.set_visible(bool(n))
        self.save_button.set_sensitive(bool(n))
        self.search_button.set_sensitive(bool(n))

    def _refresh_title(self) -> None:
        page = self.current_page
        if page is None:
            self.window_title.set_title("pyedit")
            self.window_title.set_subtitle("")
            self.set_title("pyedit")
            return
        doc = page.document
        suffix = " •" if doc.modified else ""
        self.window_title.set_title(f"{doc.display_name}{suffix}")
        self.window_title.set_subtitle(doc.subtitle)
        self.set_title(f"{doc.display_name} — pyedit")

    def _refresh_status(self, *_a: object) -> None:
        page = self.current_page
        if page is None:
            self.status_position.set_text("")
            self.status_lang.set_text("")
            return
        line, col = page.cursor_position()
        self.status_position.set_text(f"Ln {line}, Col {col}")
        lang = page.document.buffer.get_language()
        self.status_lang.set_text(lang.get_name() if lang is not None else "Plain Text")

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------
    def _on_new_tab(self, *_a: object) -> None:
        self.add_document(Document())

    def _on_open(self, *_a: object) -> None:
        chooser = Gtk.FileChooserNative.new(
            "Open File",
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )
        chooser.set_modal(True)
        chooser.response.connect(self._on_open_response)
        chooser.show()
        # Keep a reference so the native dialog isn't GC'd mid-flight.
        self._pending_chooser: Gtk.FileChooserNative | None = chooser

    def _on_open_response(
        self, chooser: Gtk.FileChooserNative, response: int
    ) -> None:
        try:
            if response == Gtk.ResponseType.ACCEPT:
                gfile = chooser.get_file()
                if gfile is not None:
                    self.open_file(gfile)
        finally:
            chooser.destroy()
            self._pending_chooser = None

    def open_file(self, gfile: Gio.File) -> Page:
        """Open `gfile` in a new tab, or focus the existing tab if it's
        already open in this window."""
        uri = gfile.get_uri() or ""
        for i in range(self.tab_view.get_n_pages()):
            tp = self.tab_view.get_nth_page(i)
            page = cast("Page", tp.get_child())
            if page.document.uri and page.document.uri == uri:
                self.tab_view.set_selected_page(tp)
                return page
        document = Document(gfile)
        if uri:
            self.state.push_recent(uri)
        return self.add_document(document)

    def open_path(self, path_str: str) -> Page | None:
        """Open a filesystem path — convenience wrapper used by argv
        handling. Routes through open_file(Gio.File)."""
        return self.open_file(Gio.file_new_for_path(path_str))

    def _on_save(self, *_a: object) -> None:
        page = self.current_page
        if page is None:
            return
        self._save_document(page.document)

    def _on_save_as(self, *_a: object) -> None:
        page = self.current_page
        if page is None:
            return
        self._save_document(page.document, force_dialog=True)

    def _on_save_all(self, *_a: object) -> None:
        for i in range(self.tab_view.get_n_pages()):
            page = cast("Page", self.tab_view.get_nth_page(i).get_child())
            if page.document.modified:
                self._save_document(page.document)

    def _save_document(
        self,
        doc: Document,
        *,
        force_dialog: bool = False,
        on_done: Callable[[bool], None] | None = None,
    ) -> None:
        if doc.file is None or force_dialog:
            chooser = Gtk.FileChooserNative.new(
                "Save As",
                self,
                Gtk.FileChooserAction.SAVE,
                "_Save",
                "_Cancel",
            )
            chooser.set_modal(True)
            chooser.set_current_name(doc.display_name)

            def respond(ch: Gtk.FileChooserNative, response: int) -> None:
                try:
                    if response != Gtk.ResponseType.ACCEPT:
                        if on_done is not None:
                            on_done(False)
                        return
                    gfile = ch.get_file()
                    if gfile is None:
                        if on_done is not None:
                            on_done(False)
                        return
                    ok = doc.save_to_file(gfile)
                    if ok:
                        # get_uri() is a pure accessor; doesn't raise.
                        self.state.push_recent(gfile.get_uri() or "")
                    self._toast(f"Saved {doc.display_name}" if ok else "Save failed")
                    if on_done is not None:
                        on_done(ok)
                    self._refresh_title()
                finally:
                    ch.destroy()

            chooser.response.connect(respond)
            chooser.show()
            self._pending_chooser = chooser
        else:
            ok = doc.save_to_file()
            self._toast(f"Saved {doc.display_name}" if ok else "Save failed")
            if on_done is not None:
                on_done(ok)
            self._refresh_title()

    def _toast(self, text: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(text))

    def _on_close_tab(self, *_a: object) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_close_window(self, *_a: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------
    def _rebuild_recent_menu(self, *_a: object) -> None:
        section = self._recent_section
        # Gio.Menu has remove_all(); fall back to popping items if the
        # binding is missing on older GIO.
        if hasattr(section, "remove_all"):
            section.remove_all()
        else:
            while section.get_n_items() > 0:
                section.remove(0)
        seen = set()
        for uri in self.state.recent_files:
            if not uri or uri in seen:
                continue
            seen.add(uri)
            gfile = Gio.file_new_for_uri(uri)
            basename = gfile.get_basename() or uri
            parent = gfile.get_parent()
            parent_str = parent.get_parse_name() if parent is not None else ""
            label = f"{basename}  —  {parent_str}" if parent_str else basename
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(
                "win.open-recent", GLib.Variant.new_string(uri)
            )
            section.append_item(item)

    def _on_open_recent(
        self, _action: Gio.SimpleAction, param: GLib.Variant | None
    ) -> None:
        uri = param.get_string() if param is not None else ""
        if not uri:
            return
        gfile = Gio.file_new_for_uri(uri)
        # If the file's gone, surface a toast and drop it from the list
        # instead of letting load_contents spew a stack trace.
        if not gfile.query_exists(None):
            self._toast(f"Not found: {gfile.get_basename() or uri}")
            self._drop_recent(uri)
            return
        self.open_file(gfile)

    def _on_clear_recents(self, *_a: object) -> None:
        self.state.clear_recents()
        self._toast("Recent files cleared")

    def _drop_recent(self, uri: str) -> None:
        # State doesn't expose a single-item remove; clear & restore the
        # surviving entries (small list, recent-limit is 20 by default).
        keep = [u for u in self.state.recent_files if u != uri]
        self.state.clear_recents()
        for u in reversed(keep):
            self.state.push_recent(u)

    # ------------------------------------------------------------------
    # Edit actions — delegate to the current view
    # ------------------------------------------------------------------
    def _on_undo(self, *_a: object) -> None:
        page = self.current_page
        if page is not None and page.document.buffer.can_undo():  # type: ignore[operator]  # stub models can_undo as bool prop; GtkSource.Buffer exposes it as a method
            page.document.buffer.undo()

    def _on_redo(self, *_a: object) -> None:
        page = self.current_page
        if page is not None and page.document.buffer.can_redo():  # type: ignore[operator]  # stub models can_redo as bool prop; GtkSource.Buffer exposes it as a method
            page.document.buffer.redo()

    def _on_cut(self, *_a: object) -> None:
        page = self.current_page
        if page is not None:
            page.view.cut_clipboard.emit()

    def _on_copy(self, *_a: object) -> None:
        page = self.current_page
        if page is not None:
            page.view.copy_clipboard.emit()

    def _on_paste(self, *_a: object) -> None:
        page = self.current_page
        if page is not None:
            page.view.paste_clipboard.emit()

    def _on_select_all(self, *_a: object) -> None:
        page = self.current_page
        if page is not None:
            page.view.select_all.emit(True)

    # ------------------------------------------------------------------
    # Search actions
    # ------------------------------------------------------------------
    def _on_find(self, *_a: object) -> None:
        page = self.current_page
        if page is None:
            return
        # Seed with current selection if any.
        buf = page.document.buffer
        seed = ""
        ok, start, end = buf.get_selection_bounds()
        if ok:
            seed = buf.get_text(start, end, True)
        self._search_bar.focus_find(seed or None)

    def _on_replace(self, *_a: object) -> None:
        if self.current_page is None:
            return
        self._search_bar.focus_replace()

    def _on_find_next(self, *_a: object) -> None:
        self._search_bar._on_next()

    def _on_find_previous(self, *_a: object) -> None:
        self._search_bar._on_previous()

    def _on_goto_line(self, *_a: object) -> None:
        page = self.current_page
        if page is None:
            return
        dialog = Adw.MessageDialog.new(self, "Go to Line", None)
        entry = Gtk.SpinButton.new_with_range(
            1, max(1, page.document.buffer.get_line_count()), 1
        )
        entry.set_value(page.cursor_position()[0])
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "_Cancel")
        dialog.add_response("ok", "_Go")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def respond(_d: Adw.MessageDialog, response: str) -> None:
            if response == "ok":
                page.goto_line(int(entry.get_value()))

        dialog.response.connect(respond)
        dialog.present()

    # ------------------------------------------------------------------
    # View toggles
    # ------------------------------------------------------------------
    def _on_toggle_line_numbers(self, *_a: object) -> None:
        self.state.show_line_numbers = not self.state.show_line_numbers

    def _on_toggle_highlight_line(self, *_a: object) -> None:
        self.state.highlight_current_line = not self.state.highlight_current_line

    def _on_toggle_right_margin(self, *_a: object) -> None:
        self.state.show_right_margin = not self.state.show_right_margin

    def _on_toggle_wrap(self, *_a: object) -> None:
        self.state.wrap_text = not self.state.wrap_text

    def _on_toggle_map(self, *_a: object) -> None:
        self.state.show_map = not self.state.show_map

    def _on_toggle_fullscreen(self, *_a: object) -> None:
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    # ------------------------------------------------------------------
    # Tab nav
    # ------------------------------------------------------------------
    def _on_next_tab(self, *_a: object) -> None:
        self.tab_view.select_next_page()

    def _on_prev_tab(self, *_a: object) -> None:
        self.tab_view.select_previous_page()

    # ------------------------------------------------------------------
    # Help overlay
    # ------------------------------------------------------------------
    def _on_show_help_overlay(self, *_a: object) -> None:
        if self._help_overlay is None:
            builder = Gtk.Builder.new_from_file(_SHORTCUTS_UI)
            self._help_overlay = cast(
                "Gtk.ShortcutsWindow", builder.get_object("help_overlay")
            )
            self._help_overlay.set_transient_for(self)
        self._help_overlay.present()

    # ------------------------------------------------------------------
    # Persistence sinks
    # ------------------------------------------------------------------
    def _on_size_changed(self, *_a: object) -> None:
        size = self.get_default_size()
        # ginext returns a SimpleNamespace; PyGObject would return a tuple.
        w = getattr(size, "width", None)
        h = getattr(size, "height", None)
        # Filter out the transient (-1, -1) GTK emits before realize.
        if w and h and w > 0 and h > 0:
            self.state.window_width = w
            self.state.window_height = h

    def _on_maximized_changed(self, *_a: object) -> None:
        self.state.window_maximized = self.is_maximized()
