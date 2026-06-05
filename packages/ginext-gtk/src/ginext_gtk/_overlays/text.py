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

"""Overlay for TreePath, TextBuffer, and TextIter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ginext import Gtk

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

overlay = Gtk.overlay


def _check_text(text: object) -> None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")


def _tree_path_indices(path: Gtk.TreePath) -> tuple[int, ...]:
    indices: object = path.get_indices()
    if isinstance(indices, tuple):
        indices = indices[0]
    if indices is None:
        return ()
    if isinstance(indices, list):
        return tuple(int(index) for index in indices)
    if isinstance(indices, int):
        return (indices,)
    raise TypeError("TreePath indices must be a list or int")


# ---------------------------------------------------------------------------
# TreePath
# ---------------------------------------------------------------------------


@overlay.method("TreePath")
def __str__(self: Gtk.TreePath) -> str:
    s = self.to_string()
    return s if s is not None else ""


@overlay.method("TreePath")
def __len__(self: Gtk.TreePath) -> int:
    return int(self.get_depth())


@overlay.method("TreePath")
def __iter__(self: Gtk.TreePath) -> Iterator[int]:
    return iter(_tree_path_indices(self))


@overlay.method("TreePath")
def __getitem__(self: Gtk.TreePath, index: int) -> int:
    return _tree_path_indices(self)[index]


# ---------------------------------------------------------------------------
# TextBuffer
# ---------------------------------------------------------------------------


@overlay.method("TextBuffer")
def create_tag(
    self: Gtk.TextBuffer, tag_name: str | None = None, **properties: object
) -> Gtk.TextTag:
    tag = Gtk.TextTag(name=tag_name) if tag_name is not None else Gtk.TextTag()
    for name, value in properties.items():
        tag.set_property(name.replace("_", "-"), value)
    self.get_tag_table().add(tag)
    return tag


@overlay.method("TextBuffer")
def create_mark(
    fn: Callable[[Gtk.TextBuffer, str, Gtk.TextIter, bool], Gtk.TextMark],
    self: Gtk.TextBuffer,
    mark_name: str,
    where: Gtk.TextIter,
    left_gravity: bool = False,
) -> Gtk.TextMark:
    return fn(self, mark_name, where, left_gravity)


@overlay.method("TextBuffer")
def set_text(
    fn: Callable[[Gtk.TextBuffer, str, int], None],
    self: Gtk.TextBuffer,
    text: str,
    length: int = -1,
) -> None:
    _check_text(text)
    fn(self, text, length)


@overlay.method("TextBuffer")
def insert(
    fn: Callable[[Gtk.TextBuffer, Gtk.TextIter, str, int], None],
    self: Gtk.TextBuffer,
    iter_: Gtk.TextIter,
    text: str,
    length: int = -1,
) -> None:
    _check_text(text)
    fn(self, iter_, text, length)


@overlay.method("TextBuffer")
def insert_at_cursor(
    fn: Callable[[Gtk.TextBuffer, str, int], None],
    self: Gtk.TextBuffer,
    text: str,
    length: int = -1,
) -> None:
    _check_text(text)
    fn(self, text, length)


@overlay.method("TextBuffer")
def get_selection_bounds(
    fn: Callable[[Gtk.TextBuffer], tuple[bool, Gtk.TextIter, Gtk.TextIter]],
    self: Gtk.TextBuffer,
) -> tuple[Gtk.TextIter, Gtk.TextIter] | tuple[()]:
    ok, start, end = fn(self)
    return () if not ok else (start, end)


if Gtk.__version__[0] == 3:

    @overlay.method("TextBuffer")
    def get_iter_at_line(
        fn: Callable[[Gtk.TextBuffer, int], Gtk.TextIter],
        self: Gtk.TextBuffer,
        line_number: int,
    ) -> tuple[bool, Gtk.TextIter]:
        return (True, fn(self, line_number))


@overlay.method("TextBuffer")
def insert_with_tags(
    self: Gtk.TextBuffer, iter_: Gtk.TextIter, text: str, *tags: Gtk.TextTag
) -> None:
    start_offset = iter_.get_offset()
    self.insert(iter_, text, -1)
    start = self.get_iter_at_offset(start_offset)
    end = self.get_iter_at_offset(start_offset + len(text))
    for tag in tags:
        self.apply_tag(tag, start, end)


@overlay.method("TextBuffer")
def insert_with_tags_by_name(
    self: Gtk.TextBuffer, iter_: Gtk.TextIter, text: str, *tag_names: str
) -> None:
    tags = []
    table = self.get_tag_table()
    for tag_name in tag_names:
        tag = table.lookup(tag_name)
        if tag is None:
            raise ValueError(f"unknown text tag: {tag_name}")
        tags.append(tag)
    self.insert_with_tags(iter_, text, *tags)


# ---------------------------------------------------------------------------
# TextIter
# ---------------------------------------------------------------------------


@overlay.method("TextIter")
def forward_search(
    fn: Callable[
        [Gtk.TextIter, str, Gtk.TextSearchFlags, Gtk.TextIter | None],
        tuple[bool, Gtk.TextIter, Gtk.TextIter],
    ],
    self: Gtk.TextIter,
    str_: str,
    flags: Gtk.TextSearchFlags,
    limit: Gtk.TextIter | None = None,
) -> tuple[Gtk.TextIter, Gtk.TextIter] | None:
    ok, start, end = fn(self, str_, flags, limit)
    return (start, end) if ok else None


@overlay.method("TextIter")
def forward_find_char(
    fn: Callable[
        [Gtk.TextIter, Gtk.TextCharPredicate, object, Gtk.TextIter | None], bool
    ],
    self: Gtk.TextIter,
    pred: Gtk.TextCharPredicate,
    user_data: object = None,
    limit: Gtk.TextIter | None = None,
) -> bool:
    return bool(fn(self, pred, user_data, limit))


@overlay.method("TextIter")
def backward_find_char(
    fn: Callable[
        [Gtk.TextIter, Gtk.TextCharPredicate, object, Gtk.TextIter | None], bool
    ],
    self: Gtk.TextIter,
    pred: Gtk.TextCharPredicate,
    user_data: object = None,
    limit: Gtk.TextIter | None = None,
) -> bool:
    return bool(fn(self, pred, user_data, limit))
