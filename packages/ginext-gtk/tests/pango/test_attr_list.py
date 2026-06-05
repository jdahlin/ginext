# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_attr_list_round_trips_and_iterates() -> None:
    attrs = Pango.AttrList.new()
    size = Pango.AttrSize.new(12 * Pango.SCALE)
    size.start_index = 0
    size.end_index = 5
    absolute = Pango.AttrSize.new_absolute(14 * Pango.SCALE)
    absolute.start_index = 6
    absolute.end_index = 10
    attrs.insert(size)
    attrs.insert_before(absolute)

    assert attrs.to_string() == "0 5 size 12288\n6 10 absolute-size 14336"
    assert len(attrs) == 2
    assert len(list(attrs)) == 2
    assert repr(attrs) == "Pango.AttrList('0 5 size 12288\\n6 10 absolute-size 14336')"

    copy = attrs.copy()
    assert copy is not None
    assert attrs.equal(copy) is True

    parsed = Pango.AttrList.from_string(attrs.to_string())
    assert parsed is not None
    assert parsed.to_string() == attrs.to_string()

    iterator = attrs.get_iterator()
    assert iterator.range() == (0, 5)
    assert len(iterator.get_attrs()) == 1
    size_attr = iterator.get(Pango.AttrType.SIZE)
    assert size_attr is not None
    assert iterator.next() is True
    assert iterator.range() == (5, 6)


def test_attr_list_filter_and_change_keep_string_surface() -> None:
    attrs = Pango.AttrList.new()
    size = Pango.AttrSize.new(12 * Pango.SCALE)
    size.start_index = 0
    size.end_index = 5
    attrs.insert(size)
    initial = attrs.to_string()

    filtered = attrs.filter(lambda attr: True)
    assert filtered is not None
    assert filtered.to_string() == initial

    replacement = Pango.AttrSize.new(15 * Pango.SCALE)
    replacement.start_index = 0
    replacement.end_index = 5
    attrs.change(replacement)
    assert "size 15360" in attrs.to_string()
    assert repr(attrs) == "Pango.AttrList('0 5 size 15360')"
