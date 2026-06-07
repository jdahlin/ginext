"""Search/replace bar.

Layout comes from search-bar.ui. The Python side wires the entries to
a GtkSource.SearchContext that lives per-page (rebuilt on tab switch),
plus a shared GtkSource.SearchSettings so the user's regex/case
toggles persist as they page through documents.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ginext import Gio, GLib, Gtk, GtkSource

if TYPE_CHECKING:
    from examples.pyedit.page import Page


_UI = (Path(__file__).resolve().parent / "resources" / "search-bar.ui").read_text()


@Gtk.Template(string=_UI)
class SearchBar(Gtk.Box, type_name="PyeditSearchBar"):

    search_bar: Gtk.SearchBar
    search_entry: Gtk.SearchEntry
    prev_button: Gtk.Button
    next_button: Gtk.Button
    case_button: Gtk.ToggleButton
    regex_button: Gtk.ToggleButton
    word_button: Gtk.ToggleButton
    replace_toggle: Gtk.ToggleButton
    replace_row: Gtk.Box
    replace_entry: Gtk.Entry
    replace_button: Gtk.Button
    replace_all_button: Gtk.Button
    close_button: Gtk.Button

    def __init__(self) -> None:
        super().__init__()
        self.settings = GtkSource.SearchSettings()
        self.settings.set_wrap_around(True)
        self.search_bar.connect_entry(self.search_entry)
        self._current_page: Page | None = None
        self._context: GtkSource.SearchContext | None = None

        # Signal wiring (kept out of the .ui; the layout stays declarative).
        self.search_entry.search_changed.connect(self._on_search_changed)
        self.search_entry.next_match.connect(self._on_next)
        self.search_entry.previous_match.connect(self._on_previous)
        self.search_entry.activate.connect(self._on_next)
        self.search_entry.stop_search.connect(self._on_stop)
        self.prev_button.clicked.connect(self._on_previous)
        self.next_button.clicked.connect(self._on_next)
        self.case_button.toggled.connect(self._on_case_toggled)
        self.regex_button.toggled.connect(self._on_regex_toggled)
        self.word_button.toggled.connect(self._on_word_toggled)
        self.replace_toggle.toggled.connect(self._on_replace_toggled)
        self.close_button.clicked.connect(self._on_stop)
        self.replace_button.clicked.connect(self._on_replace_one)
        self.replace_all_button.clicked.connect(self._on_replace_all)

    # --- page wiring --------------------------------------------------
    def attach_page(self, page: Page | None) -> None:
        self._current_page = page
        if page is None:
            self._context = None
            return
        self._context = GtkSource.SearchContext.new(page.document.buffer, self.settings)
        self._context.set_highlight(True)

    def set_revealed(self, on: bool, *, replace_visible: bool | None = None) -> None:
        self.search_bar.set_search_mode(on)
        if replace_visible is not None:
            self.replace_toggle.set_active(replace_visible)
            self.replace_row.set_visible(replace_visible)
        if on:
            target = (
                self.replace_entry
                if self.replace_row.get_visible()
                else self.search_entry
            )
            target.grab_focus()

    def revealed(self) -> bool:
        return self.search_bar.get_search_mode()

    def focus_find(self, text: str | None = None) -> None:
        if text:
            self.search_entry.set_text(text)
        self.set_revealed(True, replace_visible=False)

    def focus_replace(self) -> None:
        self.set_revealed(True, replace_visible=True)

    # --- signal handlers ---------------------------------------------
    def _on_search_changed(self, entry: Gtk.SearchEntry, *_a: object) -> None:
        self.settings.set_search_text(entry.get_text())

    def _on_stop(self, *_a: object) -> None:
        self.set_revealed(False)
        if self._current_page is not None:
            self._current_page.grab_editor_focus()

    def _on_case_toggled(self, button: Gtk.ToggleButton, *_a: object) -> None:
        self.settings.set_case_sensitive(button.get_active())

    def _on_regex_toggled(self, button: Gtk.ToggleButton, *_a: object) -> None:
        self.settings.set_regex_enabled(button.get_active())

    def _on_word_toggled(self, button: Gtk.ToggleButton, *_a: object) -> None:
        self.settings.set_at_word_boundaries(button.get_active())

    def _on_replace_toggled(self, button: Gtk.ToggleButton, *_a: object) -> None:
        self.replace_row.set_visible(button.get_active())
        if button.get_active():
            self.replace_entry.grab_focus()

    def _on_next(self, *_a: object) -> None:
        if self._context is None or self._current_page is None:
            return
        buf = self._current_page.document.buffer
        # get_selection_bounds returns (has_selection, start, end).
        ok, _start, end = buf.get_selection_bounds()
        start = end if ok else buf.get_iter_at_mark(buf.get_insert())
        self._context.forward_async(start, None, self._on_forward_done)  # type: ignore[arg-type]  # stub uses generic GAsyncReadyCallback (source: Object|None); runtime source is the SearchContext

    def _on_previous(self, *_a: object) -> None:
        if self._context is None or self._current_page is None:
            return
        buf = self._current_page.document.buffer
        ok, start, _end = buf.get_selection_bounds()
        if not ok:
            start = buf.get_iter_at_mark(buf.get_insert())
        self._context.backward_async(start, None, self._on_backward_done)  # type: ignore[arg-type]  # stub uses generic GAsyncReadyCallback (source: Object|None); runtime source is the SearchContext

    def _on_forward_done(
        self, ctx: GtkSource.SearchContext, result: Gio.AsyncResult, *_: object
    ) -> None:
        # The async finish returns a tuple — either `(ok, start, end)` (no
        # wrap-around flag) or `(ok, start, end, wrapped)`. Accept both.
        try:
            res = ctx.forward_finish(result)
        except GLib.Error as e:
            print(
                f"[pyedit] forward search failed: {e.domain}/{e.code}: {e.message}",
                file=sys.stderr,
            )
            return
        self._apply_match(res)

    def _on_backward_done(
        self, ctx: GtkSource.SearchContext, result: Gio.AsyncResult, *_: object
    ) -> None:
        try:
            res = ctx.backward_finish(result)
        except GLib.Error as e:
            print(
                f"[pyedit] backward search failed: {e.domain}/{e.code}: {e.message}",
                file=sys.stderr,
            )
            return
        self._apply_match(res)

    def _apply_match(self, res: object) -> None:
        # GtkSource.SearchContext.{forward,backward}_finish returns
        # `(ok, match_start, match_end, has_wrapped)`.
        #
        #   - GLib.Error: an error occurred (cancelled, invalid regex, …).
        #     Caller in {_on_forward_done, _on_backward_done} already
        #     swallowed it.
        #   - ok=False: completed without a match. The iter OUTs were
        #     never written by gtk_source_search_context_*_finish, so
        #     they hold whatever the caller-allocated buffer was
        #     initialised to — zeros, which means tree=NULL on the
        #     underlying GtkTextIter. Touching them (get_buffer,
        #     select_range, …) walks a null btree and crashes.
        #   - ok=True: iters are real, dispatch.
        if not isinstance(res, tuple) or len(res) < 3 or self._current_page is None:
            return
        ok = res[0]
        if not ok:
            return
        match_start, match_end = res[1], res[2]
        buf = self._current_page.document.buffer
        # Defensive: a tab switch mid-search can race the async callback,
        # delivering iters from the prior page's buffer; passing them to
        # a different buffer's select_range also crashes in
        # _gtk_text_btree_select_range with tree=NULL.
        if match_start.get_buffer() is not buf or match_end.get_buffer() is not buf:
            print(
                "[pyedit] search match dropped: iter buffer != current "
                "page buffer (likely a tab switch during the async)",
                file=sys.stderr,
            )
            return
        buf.select_range(match_start, match_end)
        self._current_page.view.scroll_to_iter(match_start, 0.1, True, 0.0, 0.5)

    def _on_replace_one(self, *_a: object) -> None:
        if self._context is None or self._current_page is None:
            return
        buf = self._current_page.document.buffer
        if not buf.get_has_selection():
            self._on_next()
            return
        _ok, start, end = buf.get_selection_bounds()
        new = self.replace_entry.get_text()
        try:
            self._context.replace(start, end, new, len(new.encode("utf-8")))
        except GLib.Error as e:
            print(
                f"[pyedit] replace failed: {e.domain}/{e.code}: {e.message}",
                file=sys.stderr,
            )
        self._on_next()

    def _on_replace_all(self, *_a: object) -> None:
        if self._context is None:
            return
        new = self.replace_entry.get_text()
        try:
            self._context.replace_all(new, len(new.encode("utf-8")))
        except GLib.Error as e:
            print(
                f"[pyedit] replace_all failed: {e.domain}/{e.code}: {e.message}",
                file=sys.stderr,
            )
