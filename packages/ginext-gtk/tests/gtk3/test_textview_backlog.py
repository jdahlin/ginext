# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

"""TextBuffer overlay coverage, ported from PyGObject.

Source: pygobject/tests/test_overrides_gtk.py::TestTextBuffer. Adapted
to pytest style (fixtures + parametrize) and targeted at the Gtk-4.0
overlay at src/goi/_goi/overlays/Gtk-4.0/TextBuffer.py — which wraps the
variadic C entry points (`create_tag`, `insert_with_tags[_by_name]`)
that GIR can't expose, and adds the `length=-1` default that callers
expect on `set_text` / `insert` / `insert_at_cursor`.

Module-scoped Gtk-4.0 requirement so all tests share one toolkit init.
"""

from __future__ import annotations

import os
import types
from typing import TYPE_CHECKING, Protocol

import pytest

from ginext.namespace import Namespace

if TYPE_CHECKING:
    from collections.abc import Generator


class _StartsTagFn(Protocol):
    def __call__(self, *args: object) -> object: ...


needs_display = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="Gtk.TextBuffer needs an initialized GTK runtime",
)


@pytest.fixture(scope="module")
def Gtk() -> Generator[types.ModuleType, None, None]:
    import ginext

    ginext.features.set_enabled(ginext.features.OLD_SIGNAL_API, True)
    Gtk = ginext.Gtk
    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    yield Gtk
    ginext.features.reset_for_test()


@pytest.fixture
def buf(Gtk: types.ModuleType) -> object:
    return Gtk.TextBuffer()


@pytest.fixture
def tagged_buf(Gtk: Namespace, buf: object) -> tuple[object, object]:
    tag = getattr(buf, "create_tag")("title", font="Sans 18")
    return buf, tag


def _text(buf: object) -> object:
    start, end = getattr(buf, "get_bounds")()
    return getattr(buf, "get_text")(start, end, False)


def _starts_tag(Gtk: Namespace) -> _StartsTagFn:
    # GTK4 renamed begins_tag → starts_tag in some versions; pick whichever exists.
    fn: _StartsTagFn | None = getattr(Gtk.TextIter, "starts_tag", None)
    if fn is not None:
        return fn
    begins: _StartsTagFn = getattr(Gtk.TextIter, "begins_tag")
    return begins


# --------------------------------------------------------------------------
# Tag table + create_tag overlay
# --------------------------------------------------------------------------


@needs_display
def test_tag_table_present(buf: object) -> None:
    assert getattr(buf, "get_tag_table")() is not None


@needs_display
def test_create_tag_sets_properties(tagged_buf: tuple[object, object]) -> None:
    _, tag = tagged_buf
    assert getattr(tag, "get_property_by_name")("name") == "title"
    assert getattr(tag, "get_property_by_name")("font") == "Sans 18"


@needs_display
def test_create_tag_anonymous(buf: object) -> None:
    tag = getattr(buf, "create_tag")(None, font="Sans 12")
    assert getattr(tag, "get_property_by_name")("name") is None
    assert getattr(tag, "get_property_by_name")("font") == "Sans 12"


# --------------------------------------------------------------------------
# create_mark default left_gravity (PyGObject-shaped default)
# --------------------------------------------------------------------------


@needs_display
def test_create_mark_default_gravity(buf: object) -> None:
    start, _ = getattr(buf, "get_bounds")()
    mark = getattr(buf, "create_mark")(None, start)
    assert getattr(mark, "get_left_gravity")() is False


# --------------------------------------------------------------------------
# set_text / insert / insert_at_cursor — `length=-1` default
# --------------------------------------------------------------------------


@needs_display
@pytest.mark.parametrize("text", ["Hello Jane Hello Bob", "", "single line"])
def test_set_text_default_length(buf: object, text: str) -> None:
    getattr(buf, "set_text")(text)
    assert _text(buf) == text


@needs_display
def test_insert_default_length(buf: object) -> None:
    getattr(buf, "set_text")("")
    _, end = getattr(buf, "get_bounds")()
    getattr(buf, "insert")(end, "HelloHello")
    getattr(buf, "insert")(end, " Bob")
    assert _text(buf) == "HelloHello Bob"


@needs_display
def test_insert_at_cursor_default_length(buf: object) -> None:
    getattr(buf, "set_text")("HelloHello Bob")
    _, end = getattr(buf, "get_bounds")()
    cursor_iter = getattr(end, "copy")()
    getattr(cursor_iter, "backward_chars")(9)
    getattr(buf, "place_cursor")(cursor_iter)
    getattr(buf, "insert_at_cursor")(" Jane ")
    assert _text(buf) == "Hello Jane Hello Bob"


# --------------------------------------------------------------------------
# Selection bounds — empty tuple when no selection, pair when selected
# --------------------------------------------------------------------------


@needs_display
def test_get_selection_bounds_empty(buf: object) -> None:
    getattr(buf, "set_text")("Hello Jane Hello Bob")
    assert getattr(buf, "get_selection_bounds")() == ()


@needs_display
def test_get_selection_bounds_after_select_range(buf: object) -> None:
    getattr(buf, "set_text")("Hello Jane Hello Bob")
    start, end = getattr(buf, "get_bounds")()
    getattr(buf, "select_range")(start, end)
    sel = getattr(buf, "get_selection_bounds")()
    assert len(sel) == 2
    sel_start, sel_end = sel
    assert getattr(sel_start, "equal")(start)
    assert getattr(sel_end, "equal")(end)


# --------------------------------------------------------------------------
# insert_with_tags / insert_with_tags_by_name overlays
# --------------------------------------------------------------------------


@needs_display
def test_insert_with_tags_no_tags(buf: object) -> None:
    getattr(buf, "insert_with_tags")(getattr(buf, "get_start_iter")(), "HelloHello")
    assert _text(buf) == "HelloHello"


@needs_display
def test_insert_with_tags_by_name_no_tags(buf: object) -> None:
    getattr(buf, "insert_with_tags_by_name")(getattr(buf, "get_start_iter")(), "HelloHello")
    assert _text(buf) == "HelloHello"


@needs_display
def test_insert_with_tags_applies_tag(Gtk: Namespace, tagged_buf: tuple[object, object]) -> None:
    buf, tag = tagged_buf
    getattr(buf, "insert_with_tags")(getattr(buf, "get_start_iter")(), "HelloHello", tag)
    start, _ = getattr(buf, "get_bounds")()
    starts_tag = _starts_tag(Gtk)
    assert starts_tag(start, tag)
    assert getattr(start, "has_tag")(tag)


@needs_display
def test_insert_with_tags_by_name_applies_tag(Gtk: Namespace, tagged_buf: tuple[object, object]) -> None:
    buf, tag = tagged_buf
    getattr(buf, "insert_with_tags_by_name")(getattr(buf, "get_start_iter")(), "HelloHello", "title")
    start, _ = getattr(buf, "get_bounds")()
    starts_tag = _starts_tag(Gtk)
    assert starts_tag(start, tag)
    assert getattr(start, "has_tag")(tag)


@needs_display
def test_insert_with_tags_by_name_unknown_raises(buf: object) -> None:
    with pytest.raises(ValueError):
        getattr(buf, "insert_with_tags_by_name")(getattr(buf, "get_start_iter")(), "HelloHello", "nope")


# --------------------------------------------------------------------------
# insert / insert_at_cursor reject non-string text — PyGObject parity
# --------------------------------------------------------------------------


@needs_display
@pytest.mark.parametrize("bad", [42, 4.2, b"bytes", None, ["list"]])
def test_insert_rejects_non_string(buf: object, bad: object) -> None:
    start, _ = getattr(buf, "get_bounds")()
    with pytest.raises(TypeError):
        getattr(buf, "insert")(start, bad)


@needs_display
@pytest.mark.parametrize("bad", [42, 4.2, b"bytes", None, ["list"]])
def test_insert_at_cursor_rejects_non_string(buf: object, bad: object) -> None:
    with pytest.raises(TypeError):
        getattr(buf, "insert_at_cursor")(bad)


# --------------------------------------------------------------------------
# TextIter — tag boundary predicates, search
# --------------------------------------------------------------------------


@needs_display
def test_text_iter_tag_boundaries(Gtk: Namespace, tagged_buf: tuple[object, object]) -> None:
    buf, tag = tagged_buf
    getattr(buf, "set_text")("Hello Jane Hello Bob")
    start, end = getattr(buf, "get_bounds")()
    getattr(start, "forward_chars")(10)
    getattr(buf, "apply_tag")(tag, start, end)
    starts_tag = _starts_tag(Gtk)
    assert starts_tag(start)
    assert getattr(end, "ends_tag")()
    assert getattr(start, "toggles_tag")()
    assert getattr(end, "toggles_tag")()
    getattr(start, "backward_chars")(1)
    assert not starts_tag(start)
    assert not getattr(start, "ends_tag")()
    assert not getattr(start, "toggles_tag")()


@needs_display
def test_text_iter_forward_search_misses_case_sensitive(buf: object) -> None:
    getattr(buf, "set_text")("Hello World Hello GNOME")
    it = getattr(buf, "get_iter_at_offset")(0)
    assert getattr(it, "forward_search")("world", 0, None) is None


@needs_display
def test_text_iter_forward_search_case_sensitive_hit(Gtk: Namespace, buf: object) -> None:
    getattr(buf, "set_text")("Hello World Hello GNOME")
    it = getattr(buf, "get_iter_at_offset")(0)
    assert isinstance(it, Gtk.TextIter)
    match = getattr(it, "forward_search")("World", 0, None)
    assert match is not None
    start, end = match
    assert getattr(start, "get_offset")() == 6
    assert getattr(end, "get_offset")() == 11


@needs_display
def test_text_iter_forward_search_case_insensitive(Gtk: Namespace, buf: object) -> None:
    getattr(buf, "set_text")("Hello World Hello GNOME")
    it = getattr(buf, "get_iter_at_offset")(0)
    match = getattr(it, "forward_search")("world", Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
    assert match is not None
    start, end = match
    assert getattr(start, "get_offset")() == 6
    assert getattr(end, "get_offset")() == 11


# --------------------------------------------------------------------------
# insert-text signal — callback may relocate the insert iter.
# Regression: https://bugzilla.gnome.org/show_bug.cgi?id=736175
# --------------------------------------------------------------------------


@needs_display
def test_insert_text_signal_can_relocate_iter(buf: object) -> None:
    def relocate_to_end(buffer: object, location: object, text: object, length: object) -> None:
        getattr(location, "assign")(getattr(buffer, "get_end_iter")())

    getattr(buf, "set_text")("first line\n")
    getattr(buf, "signal_for_name")("insert-text").connect(relocate_to_end)
    getattr(buf, "place_cursor")(getattr(buf, "get_start_iter")())
    getattr(buf, "insert_at_cursor")("second line\n")
    assert getattr(buf, "get_property_by_name")("text") == "first line\nsecond line\n"


# --------------------------------------------------------------------------
# backward_find_char — predicate sees chars in reverse, can stop early
# --------------------------------------------------------------------------


@needs_display
def test_backward_find_char_walks_in_reverse(buf: object) -> None:
    getattr(buf, "set_text")("abc")
    end = getattr(buf, "get_iter_at_line")(99)
    if isinstance(end, tuple):  # goi sometimes returns (bool, iter)
        end = end[1]
    seen: list[str] = []

    def pred(ch: str, _user_data: object) -> bool:
        seen.append(ch)
        return ch == "a"

    assert getattr(end, "backward_find_char")(pred)
    assert seen == ["c", "b", "a"]


pytestmark = [
    pytest.mark.xdist_group("gtk3"),
]
