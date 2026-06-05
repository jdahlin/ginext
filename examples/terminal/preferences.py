"""Preferences dialog (AdwPreferencesWindow + Adw rows).

UI from preferences.ui. The Python side wires each row's relevant
property to the matching State property via bind_property where the
shapes match, and a one-shot manual sync for the combo/font cases.
"""

from __future__ import annotations

from pathlib import Path

from goi.repository import Adw, GObject, Gtk, Pango

from . import palettes


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


_CURSOR_SHAPES = ["block", "ibeam", "underline"]


@Gtk.Template(string=_UI)
class Preferences(Adw.PreferencesWindow):
    __gtype_name__ = "TerminalPreferences"

    use_system_font_row = Gtk.Template.Child()
    font_row = Gtk.Template.Child()
    font_button = Gtk.Template.Child()
    palette_row = Gtk.Template.Child()
    palette_model = Gtk.Template.Child()
    cursor_shape_row = Gtk.Template.Child()
    cursor_shape_model = Gtk.Template.Child()
    scrollback_row = Gtk.Template.Child()
    opacity_row = Gtk.Template.Child()
    opacity_scale = Gtk.Template.Child()
    audible_bell_row = Gtk.Template.Child()
    allow_bold_row = Gtk.Template.Child()
    scroll_on_output_row = Gtk.Template.Child()
    scroll_on_keystroke_row = Gtk.Template.Child()

    def __init__(self, state):
        super().__init__()
        self.state = state

        flags = GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL

        for key, row in (
            ("use-system-font", self.use_system_font_row),
            ("audible-bell", self.audible_bell_row),
            ("allow-bold", self.allow_bold_row),
            ("scroll-on-output", self.scroll_on_output_row),
            ("scroll-on-keystroke", self.scroll_on_keystroke_row),
        ):
            state.bind_property(key, row, "active", flags)

        state.bind_property(
            "use-system-font",
            self.font_row,
            "sensitive",
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )

        state.bind_property("scrollback-lines", self.scrollback_row, "value", flags)

        # Opacity (0..1 in state, 0..100 on the scale).
        self._opacity_syncing = False
        self.opacity_scale.set_value(state.opacity * 100.0)
        self.opacity_scale.connect("value-changed", self._on_opacity_scale)
        state.connect("notify::opacity", self._sync_opacity_scale)

        # Font: GtkFontDialogButton holds a Pango.FontDescription.
        self._sync_font_to_button()
        self.font_button.connect("notify::font-desc", self._on_font_chosen)
        state.connect("notify::font", self._sync_font_to_button)

        # Palette combo.
        self._populate_palettes()
        self.palette_row.connect("notify::selected", self._on_palette_selected)
        state.connect("notify::palette", self._sync_palette_selection)
        self._sync_palette_selection()

        # Cursor-shape combo.
        self._populate_cursor_shapes()
        self.cursor_shape_row.connect("notify::selected", self._on_cursor_selected)
        state.connect("notify::cursor-shape", self._sync_cursor_selection)
        self._sync_cursor_selection()

    # --- opacity ------------------------------------------------------
    def _on_opacity_scale(self, scale):
        if self._opacity_syncing:
            return
        self.state.opacity = max(0.0, min(1.0, scale.get_value() / 100.0))

    def _sync_opacity_scale(self, *_a):
        self._opacity_syncing = True
        try:
            self.opacity_scale.set_value(self.state.opacity * 100.0)
        finally:
            self._opacity_syncing = False

    # --- font ---------------------------------------------------------
    def _sync_font_to_button(self, *_a):
        desc = Pango.FontDescription.from_string(self.state.font)
        self.font_button.set_font_desc(desc)

    def _on_font_chosen(self, button, _pspec):
        desc = button.get_font_desc()
        if desc is not None:
            self.state.font = desc.to_string()

    # --- palette ------------------------------------------------------
    def _populate_palettes(self):
        n = self.palette_model.get_n_items()
        if n > 0:
            self.palette_model.splice(0, n, None)
        for name in palettes.PALETTE_NAMES:
            self.palette_model.append(name)

    def _sync_palette_selection(self, *_a):
        try:
            idx = palettes.PALETTE_NAMES.index(self.state.palette)
        except ValueError:
            idx = 0
        if self.palette_row.get_selected() != idx:
            self.palette_row.set_selected(idx)

    def _on_palette_selected(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(palettes.PALETTE_NAMES):
            self.state.palette = palettes.PALETTE_NAMES[idx]

    # --- cursor shape -------------------------------------------------
    def _populate_cursor_shapes(self):
        n = self.cursor_shape_model.get_n_items()
        if n > 0:
            self.cursor_shape_model.splice(0, n, None)
        for label in ("Block", "I-Beam", "Underline"):
            self.cursor_shape_model.append(label)

    def _sync_cursor_selection(self, *_a):
        try:
            idx = _CURSOR_SHAPES.index(self.state.cursor_shape)
        except ValueError:
            idx = 0
        if self.cursor_shape_row.get_selected() != idx:
            self.cursor_shape_row.set_selected(idx)

    def _on_cursor_selected(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(_CURSOR_SHAPES):
            self.state.cursor_shape = _CURSOR_SHAPES[idx]
