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

from typing import TYPE_CHECKING, Protocol, cast

import pytest

from ginext.namespace import Namespace

if TYPE_CHECKING:
    import types
    import ginext.Gtk as _Gtk
    from collections.abc import Generator

    class _TextIter(Protocol):
        def equal(self, other: object) -> bool: ...
        def forward_chars(self, count: int) -> bool: ...
        def backward_chars(self, count: int) -> bool: ...
        def copy(self) -> _TextIter: ...
        def has_tag(self, tag: object) -> bool: ...
        def ends_tag(self, tag: object = ...) -> bool: ...
        def toggles_tag(self, tag: object = ...) -> bool: ...
        def forward_search(
            self, text: str, flags: object, limit: object
        ) -> tuple[_TextIter, _TextIter] | None: ...
        def get_offset(self) -> int: ...
        def assign(self, other: object) -> None: ...

    class _TextTag(Protocol):
        def get_property_by_name(self, name: str) -> object: ...

    class _TextMark(Protocol):
        def get_left_gravity(self) -> bool: ...

    class _TextBuf(Protocol):
        def create_tag(self, name: str | None = ..., **props: object) -> _TextTag: ...
        def get_bounds(self) -> tuple[_TextIter, _TextIter]: ...
        def get_text(self, start: object, end: object, include_hidden: bool) -> str: ...
        def get_tag_table(self) -> object: ...
        def get_property_by_name(self, name: str) -> object: ...
        def create_mark(
            self, name: str | None, pos: object, left_gravity: bool = ...
        ) -> _TextMark: ...
        def set_text(self, text: str, length: int = ...) -> None: ...
        def insert(self, pos: object, text: object, length: int = ...) -> None: ...
        def place_cursor(self, pos: object) -> None: ...
        def insert_at_cursor(self, text: object, length: int = ...) -> None: ...
        def get_selection_bounds(self) -> tuple[()] | tuple[_TextIter, _TextIter]: ...
        def select_range(self, s: object, e: object) -> None: ...
        def insert_with_tags(self, pos: object, text: str, *tags: object) -> None: ...
        def get_start_iter(self) -> _TextIter: ...
        def insert_with_tags_by_name(
            self, pos: object, text: str, *names: str
        ) -> None: ...
        def get_iter_at_offset(self, offset: int) -> _TextIter: ...
        def apply_tag(self, tag: object, s: object, e: object) -> None: ...
        def get_iter_at_line(self, line: int) -> object: ...
        insert_text: object  # signal


class StartsTagFn(Protocol):
    def __call__(self, *args: object) -> object: ...


needs_display = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="Gtk.TextBuffer needs an initialized GTK runtime",
)


@pytest.fixture(scope="module")
def Gtk() -> Generator[types.ModuleType]:
    import ginext

    ginext.features.set_enabled(ginext.features.OLD_SIGNAL_API, True)
    Gtk = ginext.Gtk
    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    yield Gtk
    ginext.features.reset_for_test()


@pytest.fixture
def buf(Gtk: types.ModuleType) -> _TextBuf:
    return cast("_TextBuf", Gtk.TextBuffer())


@pytest.fixture
def tagged_buf(Gtk: Namespace, buf: _TextBuf) -> tuple[_TextBuf, _TextTag]:
    tag = buf.create_tag("title", font="Sans 18")
    return buf, tag


def _text(buf: _TextBuf) -> str:
    start, end = buf.get_bounds()
    return buf.get_text(start, end, False)


def _starts_tag(Gtk: Namespace) -> StartsTagFn:
    # GTK4 renamed begins_tag → starts_tag in some versions; pick whichever exists.
    fn: StartsTagFn | None = getattr(Gtk.TextIter, "starts_tag", None)
    if fn is not None:
        return fn
    begins: StartsTagFn = Gtk.TextIter.begins_tag
    return begins


# --------------------------------------------------------------------------
# Tag table + create_tag overlay
# --------------------------------------------------------------------------


@needs_display
def test_tag_table_present(buf: _TextBuf) -> None:
    assert buf.get_tag_table() is not None


@needs_display
def test_create_tag_sets_properties(tagged_buf: tuple[_TextBuf, _TextTag]) -> None:
    _, tag = tagged_buf
    assert tag.get_property_by_name("name") == "title"
    assert tag.get_property_by_name("font") == "Sans 18"


@needs_display
def test_create_tag_anonymous(buf: _TextBuf) -> None:
    tag = buf.create_tag(None, font="Sans 12")
    assert tag.get_property_by_name("name") is None
    assert tag.get_property_by_name("font") == "Sans 12"


# --------------------------------------------------------------------------
# create_mark default left_gravity (PyGObject-shaped default)
# --------------------------------------------------------------------------


@needs_display
def test_create_mark_default_gravity(buf: _TextBuf) -> None:
    start, _ = buf.get_bounds()
    mark = buf.create_mark(None, start)
    assert mark.get_left_gravity() is False


# --------------------------------------------------------------------------
# set_text / insert / insert_at_cursor — `length=-1` default
# --------------------------------------------------------------------------


@needs_display
@pytest.mark.parametrize("text", ["Hello Jane Hello Bob", "", "single line"])
def test_set_text_default_length(buf: _TextBuf, text: str) -> None:
    buf.set_text(text)
    assert _text(buf) == text


@needs_display
def test_insert_default_length(buf: _TextBuf) -> None:
    buf.set_text("")
    _, end = buf.get_bounds()
    buf.insert(end, "HelloHello")
    buf.insert(end, " Bob")
    assert _text(buf) == "HelloHello Bob"


@needs_display
def test_insert_at_cursor_default_length(buf: _TextBuf) -> None:
    buf.set_text("HelloHello Bob")
    _, end = buf.get_bounds()
    cursor_iter = end.copy()
    cursor_iter.backward_chars(9)
    buf.place_cursor(cursor_iter)
    buf.insert_at_cursor(" Jane ")
    assert _text(buf) == "Hello Jane Hello Bob"


# --------------------------------------------------------------------------
# Selection bounds — empty tuple when no selection, pair when selected
# --------------------------------------------------------------------------


@needs_display
def test_get_selection_bounds_empty(buf: _TextBuf) -> None:
    buf.set_text("Hello Jane Hello Bob")
    assert buf.get_selection_bounds() == ()


@needs_display
def test_get_selection_bounds_after_select_range(buf: _TextBuf) -> None:
    buf.set_text("Hello Jane Hello Bob")
    start, end = buf.get_bounds()
    buf.select_range(start, end)
    sel = buf.get_selection_bounds()
    assert len(sel) == 2
    sel_start, sel_end = sel
    assert sel_start.equal(start)
    assert sel_end.equal(end)


# --------------------------------------------------------------------------
# insert_with_tags / insert_with_tags_by_name overlays
# --------------------------------------------------------------------------


@needs_display
def test_insert_with_tags_no_tags(buf: _TextBuf) -> None:
    buf.insert_with_tags(buf.get_start_iter(), "HelloHello")
    assert _text(buf) == "HelloHello"


@needs_display
def test_insert_with_tags_by_name_no_tags(buf: _TextBuf) -> None:
    buf.insert_with_tags_by_name(buf.get_start_iter(), "HelloHello")
    assert _text(buf) == "HelloHello"


@needs_display
def test_insert_with_tags_applies_tag(
    Gtk: Namespace, tagged_buf: tuple[_TextBuf, _TextTag]
) -> None:
    buf, tag = tagged_buf
    buf.insert_with_tags(buf.get_start_iter(), "HelloHello", tag)
    start, _ = buf.get_bounds()
    starts_tag = _starts_tag(Gtk)
    assert starts_tag(start, tag)
    assert start.has_tag(tag)


@needs_display
def test_insert_with_tags_by_name_applies_tag(
    Gtk: Namespace, tagged_buf: tuple[_TextBuf, _TextTag]
) -> None:
    buf, tag = tagged_buf
    buf.insert_with_tags_by_name(buf.get_start_iter(), "HelloHello", "title")
    start, _ = buf.get_bounds()
    starts_tag = _starts_tag(Gtk)
    assert starts_tag(start, tag)
    assert start.has_tag(tag)


@needs_display
def test_insert_with_tags_by_name_unknown_raises(buf: _TextBuf) -> None:
    with pytest.raises(ValueError):
        buf.insert_with_tags_by_name(buf.get_start_iter(), "HelloHello", "nope")


# --------------------------------------------------------------------------
# insert / insert_at_cursor reject non-string text — PyGObject parity
# --------------------------------------------------------------------------


@needs_display
@pytest.mark.parametrize("bad", [42, 4.2, b"bytes", None, ["list"]])
def test_insert_rejects_non_string(buf: _TextBuf, bad: object) -> None:
    start, _ = buf.get_bounds()
    with pytest.raises(TypeError):
        buf.insert(start, bad)


@needs_display
@pytest.mark.parametrize("bad", [42, 4.2, b"bytes", None, ["list"]])
def test_insert_at_cursor_rejects_non_string(buf: _TextBuf, bad: object) -> None:
    with pytest.raises(TypeError):
        buf.insert_at_cursor(bad)


# --------------------------------------------------------------------------
# TextIter — tag boundary predicates, search
# --------------------------------------------------------------------------


@needs_display
def test_text_iter_tag_boundaries(
    Gtk: Namespace, tagged_buf: tuple[_TextBuf, _TextTag]
) -> None:
    buf, tag = tagged_buf
    buf.set_text("Hello Jane Hello Bob")
    start, end = buf.get_bounds()
    start.forward_chars(10)
    buf.apply_tag(tag, start, end)
    starts_tag = _starts_tag(Gtk)
    assert starts_tag(start)
    assert end.ends_tag()
    assert start.toggles_tag()
    assert end.toggles_tag()
    start.backward_chars(1)
    assert not starts_tag(start)
    assert not start.ends_tag()
    assert not start.toggles_tag()


@needs_display
def test_text_iter_forward_search_misses_case_sensitive(buf: _TextBuf) -> None:
    buf.set_text("Hello World Hello GNOME")
    it = buf.get_iter_at_offset(0)
    assert it.forward_search("world", 0, None) is None


@needs_display
def test_text_iter_forward_search_case_sensitive_hit(
    Gtk: Namespace, buf: _TextBuf
) -> None:
    buf.set_text("Hello World Hello GNOME")
    it = buf.get_iter_at_offset(0)
    assert isinstance(it, Gtk.TextIter)
    match = it.forward_search("World", 0, None)
    assert match is not None
    start, end = match
    assert start.get_offset() == 6
    assert end.get_offset() == 11


@needs_display
def test_text_iter_forward_search_case_insensitive(Gtk: Namespace, buf: _TextBuf) -> None:
    buf.set_text("Hello World Hello GNOME")
    it = buf.get_iter_at_offset(0)
    match = it.forward_search("world", Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
    assert match is not None
    start, end = match
    assert start.get_offset() == 6
    assert end.get_offset() == 11


# --------------------------------------------------------------------------
# insert-text signal — callback may relocate the insert iter.
# Regression: https://bugzilla.gnome.org/show_bug.cgi?id=736175
# --------------------------------------------------------------------------


@needs_display
def test_insert_text_signal_can_relocate_iter(buf: _TextBuf) -> None:
    def relocate_to_end(
        buffer: _Gtk.TextBuffer, location: _Gtk.TextIter, text: object, length: object
    ) -> None:
        location.assign(buffer.get_end_iter())

    buf.set_text("first line\n")
    buf.insert_text.connect(relocate_to_end)  # type: ignore[attr-defined]
    buf.place_cursor(buf.get_start_iter())
    buf.insert_at_cursor("second line\n")
    assert buf.get_property_by_name("text") == "first line\nsecond line\n"


# --------------------------------------------------------------------------
# backward_find_char — predicate sees chars in reverse, can stop early
# --------------------------------------------------------------------------


@needs_display
def test_backward_find_char_walks_in_reverse(buf: _TextBuf) -> None:
    buf.set_text("abc")
    end = buf.get_iter_at_line(99)
    if isinstance(end, tuple):  # goi sometimes returns (bool, iter)
        end = end[1]
    seen: list[str] = []

    def pred(ch: str, _user_data: object) -> bool:
        seen.append(ch)
        return ch == "a"

    assert end.backward_find_char(pred)  # type: ignore[attr-defined]
    assert seen == ["c", "b", "a"]


pytestmark = [
    pytest.mark.xdist_group("gtk3"),
]
