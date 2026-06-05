from __future__ import annotations

from dataclasses import dataclass

from ginext import Gtk, Pango

PANGO_SCALE = 1024
GTK_XFT_DPI_BASE = 96 * 1024


@dataclass(frozen=True)
class TextMetrics:
    font_description: Pango.FontDescription
    char_width: int
    columns_width: int
    line_height: int
    padding_top: int
    padding_right: int
    padding_bottom: int
    padding_left: int

    @property
    def content_width(self) -> int:
        return self.padding_left + self.columns_width + self.padding_right


def scaled_font_description(
    description: Pango.FontDescription,
    *,
    scale: float | None = None,
) -> Pango.FontDescription:
    copied = description.copy()
    assert copied is not None
    description = copied
    scale = xft_scale() if scale is None else scale
    size = description.get_size()
    if size <= 0:
        return description
    if description.get_size_is_absolute():
        description.set_absolute_size(int(size * scale))
    else:
        description.set_size(int(size * scale))
    return description


def css_font_description(layout: Pango.Layout) -> Pango.FontDescription:
    font_description = layout.get_context().get_font_description()
    assert font_description is not None
    return font_description


def xft_scale() -> float:
    settings = Gtk.Settings.get_default()
    if settings is None:
        return 1.0
    xft_dpi: int = settings.get_property("gtk-xft-dpi")
    if xft_dpi <= 0:
        return 1.0
    return xft_dpi / GTK_XFT_DPI_BASE


def measure_text_metrics(
    widget: Gtk.Widget,
    layout: Pango.Layout,
    *,
    columns: int,
    line_gap: int = 1,
) -> TextMetrics:
    padding = widget.get_style_context().get_padding()
    font_description = scaled_font_description(css_font_description(layout))
    layout.set_font_description(font_description)
    layout.set_single_paragraph_mode(True)

    layout.set_text("Agjpqy|_[]{}", -1)
    ink, logical = layout.get_pixel_extents()
    line_height = max(logical.height, ink.y + ink.height - min(0, ink.y))

    layout.set_text("M", -1)
    _ink, logical = layout.get_pixel_extents()
    char_width = logical.width

    if char_width <= 0 or line_height <= 0:
        _ink, logical = layout.get_extents()
        char_width = logical.width // PANGO_SCALE
        line_height = logical.height // PANGO_SCALE

    columns_width = _measure_columns_width(layout, columns)
    return TextMetrics(
        font_description=font_description,
        char_width=max(1, char_width),
        columns_width=columns_width,
        line_height=max(1, line_height + line_gap),
        padding_top=padding.top,
        padding_right=padding.right,
        padding_bottom=padding.bottom,
        padding_left=padding.left,
    )


def _measure_columns_width(layout: Pango.Layout, columns: int) -> int:
    layout.set_text("M" * columns, -1)
    _ink, logical = layout.get_pixel_extents()
    if logical.width > 0:
        return logical.width
    _ink, logical = layout.get_extents()
    return max(1, logical.width // PANGO_SCALE)
