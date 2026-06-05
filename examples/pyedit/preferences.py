"""Preferences dialog (AdwPreferencesWindow + Adw rows).

UI from preferences.ui. The Python side wires each row's relevant
property to the matching State property via bind_property so the
prefs serialize automatically (State.notify → JSON flush)."""

from __future__ import annotations

from pathlib import Path

from goi.repository import Adw, GObject, Gtk, GtkSource, Pango


# Force-build Adw widget classes referenced by the .ui template so the
# GTypes are registered before GtkBuilder parses it.
Adw.init()
_ = (
    Adw.PreferencesWindow,
    Adw.PreferencesPage,
    Adw.PreferencesGroup,
    Adw.SwitchRow,
    Adw.ActionRow,
    Adw.SpinRow,
    Adw.ComboRow,
)


_UI = (Path(__file__).resolve().parent / "resources" / "preferences.ui").read_text()


@Gtk.Template(string=_UI)
class Preferences(Gtk.Window):
    # The .ui declares the template as AdwPreferencesWindow; we use
    # Gtk.Window as the Python parent because goi resolves the
    # parent class from the template at decoration time.
    __gtype_name__ = "PyeditPreferences"

    use_system_font_row = Gtk.Template.Child()
    font_button = Gtk.Template.Child()
    line_numbers_row = Gtk.Template.Child()
    highlight_line_row = Gtk.Template.Child()
    right_margin_row = Gtk.Template.Child()
    right_margin_position_row = Gtk.Template.Child()
    show_map_row = Gtk.Template.Child()
    tab_width_row = Gtk.Template.Child()
    insert_spaces_row = Gtk.Template.Child()
    auto_indent_row = Gtk.Template.Child()
    wrap_text_row = Gtk.Template.Child()
    scheme_row = Gtk.Template.Child()
    scheme_model = Gtk.Template.Child()
    restore_session_row = Gtk.Template.Child()
    font_row = Gtk.Template.Child()

    def __init__(self, state):
        super().__init__()
        self.state = state

        flags = GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL

        # AdwSwitchRow exposes the on/off via the "active" property.
        for st_key, row in (
            ("use-system-font", self.use_system_font_row),
            ("show-line-numbers", self.line_numbers_row),
            ("highlight-current-line", self.highlight_line_row),
            ("show-right-margin", self.right_margin_row),
            ("show-map", self.show_map_row),
            ("insert-spaces", self.insert_spaces_row),
            ("auto-indent", self.auto_indent_row),
            ("wrap-text", self.wrap_text_row),
            ("restore-session", self.restore_session_row),
        ):
            state.bind_property(st_key, row, "active", flags)

        # Spin rows use "value".
        state.bind_property(
            "right-margin-position", self.right_margin_position_row, "value", flags
        )
        state.bind_property("tab-width", self.tab_width_row, "value", flags)

        # Font: GtkFontDialogButton holds a Pango.FontDescription. Sync
        # in both directions through string round-trips.
        self._sync_font_to_button()
        self.font_button.connect("notify::font-desc", self._on_font_chosen)
        state.connect("notify::font", self._sync_font_to_button)

        # When "use-system-font" is on, the font row is insensitive —
        # the system font wins regardless. Bind via SYNC_CREATE so
        # initial state is right.
        state.bind_property(
            "use-system-font",
            self.font_row,
            "sensitive",
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )

        # Style scheme: populate combo from GtkSourceStyleSchemeManager
        # and bind selection ↔ state.style_scheme by id.
        self._populate_schemes()
        self.scheme_row.connect("notify::selected", self._on_scheme_selected)
        state.connect("notify::style-scheme", self._sync_scheme_selection)
        self._sync_scheme_selection()

    # --- font sync ----------------------------------------------------
    def _sync_font_to_button(self, *_a):
        # Pango.FontDescription.from_string parses leniently — bogus
        # input yields a default FontDescription rather than raising.
        desc = Pango.FontDescription.from_string(self.state.font)
        self.font_button.set_font_desc(desc)

    def _on_font_chosen(self, button, _pspec):
        desc = button.get_font_desc()
        if desc is not None:
            self.state.font = desc.to_string()

    # --- scheme sync --------------------------------------------------
    def _populate_schemes(self):
        mgr = GtkSource.StyleSchemeManager.get_default()
        ids = list(mgr.get_scheme_ids() or [])
        self._scheme_ids = sorted(ids)
        # Reset list to current ids; .splice rather than append-loop so
        # repeated open of prefs doesn't accrete duplicates.
        n = self.scheme_model.get_n_items()
        if n > 0:
            self.scheme_model.splice(0, n, None)
        for sid in self._scheme_ids:
            self.scheme_model.append(sid)

    def _sync_scheme_selection(self, *_a):
        current = self.state.style_scheme
        try:
            idx = self._scheme_ids.index(current)
        except ValueError:
            idx = 0
        if self.scheme_row.get_selected() != idx:
            self.scheme_row.set_selected(idx)

    def _on_scheme_selected(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(self._scheme_ids):
            self.state.style_scheme = self._scheme_ids[idx]
