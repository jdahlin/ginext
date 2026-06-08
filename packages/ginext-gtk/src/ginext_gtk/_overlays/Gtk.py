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

"""Gtk namespace overlay — thin dispatcher.

Each concern lives in its own module; importing it runs the overlay
registrations.  The bootstrap calls `apply_to_namespace` if present, but all
registration here happens at import time via the decorator-based overlay API.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from ginext import Gtk
from ginext_gio._actions import action as _gio_action
from ginext_gtk._gtktemplate import Template
from ginext_gtk._overlays import (
    css,
    expression,
    gtk3_actions,
    gtk3_builder,
    gtk3_dialogs,
    gtk3_legacy,
    text,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


_P = ParamSpec("_P")
_R = TypeVar("_R")


def action(
    name: str, accels: Sequence[str] | None = None
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    return _gio_action(name, accels)


overlay = Gtk.overlay
overlay.constant("action", action)
overlay.constant("Template", Template)


def _widget_children(widget: Gtk.Widget) -> Iterator[Gtk.Widget]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()


def _normalize_position(index: int, length: int) -> int:
    if index < 0:
        index += length
    if index < 0 or index >= length:
        raise IndexError("index out of range")
    return index


def _notebook_page_at(notebook: Gtk.Notebook, index: int) -> Gtk.Widget:
    page = notebook.get_nth_page(index)
    if page is None:
        raise IndexError("index out of range")
    return page


def _assistant_page_at(assistant: Gtk.Assistant, index: int) -> Gtk.Widget:
    page = assistant.get_nth_page(index)
    if page is None:
        raise IndexError("index out of range")
    return page


def _stack_page_at(stack: Gtk.Stack, index: int) -> Gtk.StackPage:
    for position, child in enumerate(_widget_children(stack)):
        if position == index:
            return stack.get_page(child)
    raise IndexError("index out of range")


@overlay.method("Builder", name="__len__")
def builder_len(self: Gtk.Builder) -> int:
    return len(self.get_objects())


@overlay.method("Builder", name="__iter__")
def builder_iter(self: Gtk.Builder) -> Iterator[object]:
    yield from self.get_objects()


@overlay.method("Builder", name="__contains__")
def builder_contains(self: Gtk.Builder, item: object) -> bool:
    return item in self.get_objects()


@overlay.method("Assistant", name="__len__")
def assistant_len(self: Gtk.Assistant) -> int:
    return int(self.get_n_pages())


@overlay.method("Assistant", name="__getitem__")
def assistant_getitem(
    self: Gtk.Assistant, key: object
) -> Gtk.Widget | list[Gtk.Widget]:
    length = len(self)
    match key:
        case slice():
            return [_assistant_page_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _assistant_page_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                "assistant indices must be integers or slices, not "
                f"{type(key).__name__}"
            )


@overlay.method("Assistant", name="__iter__")
def assistant_iter(self: Gtk.Assistant) -> Iterator[Gtk.Widget]:
    for index in range(len(self)):
        yield _assistant_page_at(self, index)


@overlay.method("Widget", name="__iter__")
def widget_iter(self: Gtk.Widget) -> Iterator[Gtk.Widget]:
    yield from _widget_children(self)


@overlay.method("Box", name="__len__")
def box_len(self: Gtk.Box) -> int:
    return sum(1 for _child in _widget_children(self))


@overlay.method("Box", name="__iter__")
def box_iter(self: Gtk.Box) -> Iterator[Gtk.Widget]:
    yield from _widget_children(self)


@overlay.method("Notebook", name="__len__")
def notebook_len(self: Gtk.Notebook) -> int:
    return int(self.get_n_pages())


@overlay.method("Notebook", name="__getitem__")
def notebook_getitem(self: Gtk.Notebook, key: object) -> Gtk.Widget | list[Gtk.Widget]:
    length = len(self)
    match key:
        case slice():
            return [_notebook_page_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _notebook_page_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                "notebook indices must be integers or slices, not "
                f"{type(key).__name__}"
            )


@overlay.method("Notebook", name="__iter__")
def notebook_iter(self: Gtk.Notebook) -> Iterator[Gtk.Widget]:
    for index in range(len(self)):
        yield _notebook_page_at(self, index)


@overlay.method("Stack", name="__len__")
def stack_len(self: Gtk.Stack) -> int:
    return sum(1 for _child in _widget_children(self))


@overlay.method("Stack", name="__getitem__")
def stack_getitem(self: Gtk.Stack, key: object) -> Gtk.StackPage | list[Gtk.StackPage]:
    length = len(self)
    match key:
        case slice():
            return [_stack_page_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _stack_page_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                "stack indices must be integers or slices, not "
                f"{type(key).__name__}"
            )


@overlay.method("Stack", name="__iter__")
def stack_iter(self: Gtk.Stack) -> Iterator[Gtk.StackPage]:
    for index in range(len(self)):
        yield _stack_page_at(self, index)

__all__ = [
    "css",
    "expression",
    "gtk3_actions",
    "gtk3_builder",
    "gtk3_dialogs",
    "gtk3_legacy",
    "text",
]
