# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_font_description_getters_setters_and_string_forms() -> None:
    desc = Pango.FontDescription.new()
    desc.set_family("Sans")
    desc.set_style(Pango.Style.ITALIC)
    desc.set_weight(Pango.Weight.BOLD)
    desc.set_size(12 * Pango.SCALE)
    desc.set_stretch(Pango.Stretch.CONDENSED)
    desc.set_variant(Pango.Variant.SMALL_CAPS)

    assert desc.get_family() == "Sans"
    assert desc.get_style() == Pango.Style.ITALIC
    assert desc.get_weight() == Pango.Weight.BOLD
    assert desc.get_size() == 12 * Pango.SCALE
    assert desc.get_size_is_absolute() is False
    assert desc.get_stretch() == Pango.Stretch.CONDENSED
    assert desc.get_variant() == Pango.Variant.SMALL_CAPS
    assert desc.to_string() == "Sans Bold Italic Condensed Small-Caps 12"
    assert desc.to_filename() == "sans_bold_italic_condensed_small-caps_12"
    assert str(desc) == "Sans Bold Italic Condensed Small-Caps 12"
    assert (
        repr(desc)
        == "Pango.FontDescription('Sans Bold Italic Condensed Small-Caps 12')"
    )


def test_font_description_copy_hash_and_better_match() -> None:
    desc = Pango.FontDescription.from_string("Sans 12")
    copy = desc.copy()
    assert copy is not None
    other = Pango.FontDescription.from_string("Sans 14")

    assert desc.equal(copy) is True
    assert desc.hash() > 0
    assert isinstance(desc.better_match(other, copy), bool)
