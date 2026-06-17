# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_glyph_item_accepts_item_and_glyph_string_fields() -> None:
    glyph_item = Pango.GlyphItem()
    glyph_item.item = Pango.Item.new()
    glyph_item.glyphs = Pango.GlyphString.new()

    assert glyph_item.item is not None
    assert glyph_item.glyphs is not None
