"""Page — per-tab widget loaded from page.ui.

Template-bound children: `view` (GtkSource.View), `map` (GtkSource.Map),
`scroller` (Gtk.ScrolledWindow). The Python side wires the page to a
Document and live-binds editor preferences onto the view.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ginext import GObject, Gtk, GtkSource, Pango

if TYPE_CHECKING:
    from examples.pyedit.document import Document
    from examples.pyedit.state import State


# Force-build the GtkSource classes referenced by the .ui so GtkBuilder
# can resolve them. Accessing the attribute triggers the lazy class
# build + the GType registration that GtkBuilder needs.
_ = (GtkSource.View, GtkSource.Map, GtkSource.Buffer)


_UI = (Path(__file__).resolve().parent / "resources" / "page.ui").read_text()


@Gtk.Template(string=_UI)
class Page(Gtk.Box, type_name="PyeditPage"):

    view: GtkSource.View
    map: GtkSource.Map  # type: ignore[assignment]  # template child shadows Gtk.Widget's inherited "map" signal
    scroller: Gtk.ScrolledWindow

    def __init__(self, document: Document, state: State) -> None:
        super().__init__()
        self.document = document
        self.state = state

        # Re-target the GtkSourceView at our document's buffer (the .ui
        # creates a fresh empty buffer).
        self.view.set_buffer(document.buffer)
        self.map.set_view(self.view)

        flags = GObject.BindingFlags.SYNC_CREATE
        state.bind_property("show-line-numbers", self.view, "show-line-numbers", flags)
        state.bind_property(
            "highlight-current-line", self.view, "highlight-current-line", flags
        )
        state.bind_property("show-right-margin", self.view, "show-right-margin", flags)
        state.bind_property(
            "right-margin-position", self.view, "right-margin-position", flags
        )
        state.bind_property("tab-width", self.view, "tab-width", flags)
        state.bind_property(
            "insert-spaces", self.view, "insert-spaces-instead-of-tabs", flags
        )
        state.bind_property("auto-indent", self.view, "auto-indent", flags)
        state.bind_property("show-map", self.map, "visible", flags)

        state.notify("wrap-text").connect(self._refresh_wrap)
        state.notify("font").connect(self._refresh_font)
        state.notify("use-system-font").connect(self._refresh_font)
        state.notify("style-scheme").connect(self._refresh_style_scheme)
        self._refresh_wrap()
        self._refresh_font()
        self._refresh_style_scheme()

    def _refresh_wrap(self, *_a: object) -> None:
        mode = Gtk.WrapMode.WORD_CHAR if self.state.wrap_text else Gtk.WrapMode.NONE
        self.view.set_wrap_mode(mode)

    def _refresh_font(self, *_a: object) -> None:
        provider = getattr(self, "_font_provider", None)
        if provider is None:
            provider = Gtk.CssProvider()
            self.view.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self._font_provider = provider
        font_desc = Pango.FontDescription.from_string(self.state.font)
        family = font_desc.get_family() or "Monospace"
        size_pts = max(6, (font_desc.get_size() // Pango.SCALE) or 11)
        css = f"textview {{ font-family: '{family}'; font-size: {size_pts}pt; }}"
        # GTK 4.12+ prefers load_from_string; fall back to load_from_data
        # for older runtimes (passing the str + length).
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(css)
        else:
            provider.load_from_data(css, len(css))

    def _refresh_style_scheme(self, *_a: object) -> None:
        sid = self.state.style_scheme or "Adwaita"
        mgr = GtkSource.StyleSchemeManager.get_default()
        scheme = (
            mgr.get_scheme(sid)
            or mgr.get_scheme("Adwaita")
            or mgr.get_scheme("classic")
        )
        if scheme is not None:
            self.document.buffer.set_style_scheme(scheme)

    def grab_editor_focus(self) -> None:
        self.view.grab_focus()

    def cursor_position(self) -> tuple[int, int]:
        mark = self.document.buffer.get_insert()
        it = self.document.buffer.get_iter_at_mark(mark)
        return it.get_line() + 1, it.get_line_offset() + 1

    def goto_line(self, line_1based: int) -> bool:
        buf = self.document.buffer
        n_lines = buf.get_line_count()
        line = max(0, min(line_1based - 1, n_lines - 1))
        result = buf.get_iter_at_line(line)
        if isinstance(result, tuple):
            ok, it = result
            if not ok:
                return False
        else:
            it = result
        buf.place_cursor(it)
        self.view.scroll_to_iter(it, 0.1, True, 0.0, 0.5)
        self.view.grab_focus()
        return True
