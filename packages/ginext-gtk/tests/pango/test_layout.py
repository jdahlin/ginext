# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango

from .support import make_context


def test_layout_exposes_text_geometry_and_navigation() -> None:
    layout = Pango.Layout.new(make_context())
    tabs = Pango.TabArray.new(2, True)
    tabs.set_tab(0, Pango.TabAlign.LEFT, 10)
    tabs.set_tab(1, Pango.TabAlign.DECIMAL, 30)

    layout.set_text("Hello\tworld", -1)
    layout.set_tabs(tabs)
    layout.set_width(100 * Pango.SCALE)
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    layout.set_alignment(Pango.Alignment.CENTER)
    layout.set_ellipsize(Pango.EllipsizeMode.END)
    layout.set_indent(4)
    layout.set_spacing(2)
    layout.set_line_spacing(1.2)
    layout.set_justify(True)
    layout.set_justify_last_line(True)
    layout.set_single_paragraph_mode(True)

    assert layout.get_alignment() == Pango.Alignment.CENTER
    tabs_result = layout.get_tabs()
    assert tabs_result is not None
    assert tabs_result.to_string() == "10px\ndecimal:30px"
    assert layout.get_line_count() >= 1
    assert layout.get_unknown_glyphs_count() == 0
    assert layout.get_serial() >= 1
    assert layout.get_context() is not None
    assert layout.get_text() == "Hello\tworld"
    assert layout.get_pixel_size().height > 0
    assert layout.get_size().width == 100 * Pango.SCALE
    assert layout.xy_to_index(0, 0).index_ == 0
    assert layout.index_to_line_x(1, False).line == 0
    assert layout.move_cursor_visually(True, 0, 0, 1).new_index >= 0


def test_layout_serializes_deserializes_and_copies() -> None:
    context = make_context()
    layout = Pango.Layout.new(context)
    layout.set_text("Hello", -1)

    data = layout.serialize(Pango.LayoutSerializeFlags.DEFAULT)
    restored = Pango.Layout.deserialize(
        context, data, Pango.LayoutDeserializeFlags.DEFAULT
    )
    clone = layout.copy()

    assert restored is not None
    assert restored.get_text() == "Hello"
    assert clone.get_text() == "Hello"
