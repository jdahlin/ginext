from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ginext import Adw, Gtk

from commander.components.settings.settingsstore import (
    STYLE_LEVEL_MAX,
    STYLE_LEVEL_MIN,
    STYLE_LEVELS,
    CommanderSettings,
)

_UI = (Path(__file__).resolve().parent / "preferences.ui").read_text()


@Gtk.Template(string=_UI)
class CommanderPreferencesDialog(
    Adw.PreferencesDialog, type_name="GoiCommanderPreferencesDialog"
):

    style_row: Adw.ActionRow
    style_scale: Gtk.Scale

    def __init__(
        self,
        settings: CommanderSettings,
        on_style_level_changed: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_style_level_changed = on_style_level_changed
        self._style_level = settings.style_level

        self.style_scale.set_round_digits(0)
        self.style_scale.set_digits(0)
        self.style_scale.set_draw_value(False)
        self.style_scale.set_value(float(self._style_level))
        self.style_scale.set_increments(1.0, 1.0)
        self.style_scale.set_range(float(STYLE_LEVEL_MIN), float(STYLE_LEVEL_MAX))
        self.style_scale.set_has_origin(False)
        self._install_style_marks()
        self._sync_style_row()
        self.style_scale.value_changed.connect(self._on_style_scale_changed)

    def _install_style_marks(self) -> None:
        self.style_scale.clear_marks()
        for index, label in enumerate(STYLE_LEVELS):
            mark_label = None
            if index == STYLE_LEVEL_MIN or index == STYLE_LEVEL_MAX:
                mark_label = label
            self.style_scale.add_mark(float(index), Gtk.PositionType.BOTTOM, mark_label)

    def _on_style_scale_changed(self, scale: Gtk.Scale) -> None:
        rounded = int(round(scale.get_value()))
        if rounded != self._style_level:
            self._style_level = rounded
            self._settings.set_style_level(rounded)
            if self._on_style_level_changed is not None:
                self._on_style_level_changed(rounded)
            self._sync_style_row()
        if abs(scale.get_value() - rounded) > 0.01:
            scale.set_value(float(rounded))

    def _sync_style_row(self) -> None:
        self.style_row.set_subtitle(STYLE_LEVELS[self._style_level])
