# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from collections.abc import Iterator

from ginext import Adw
from ginext import Gtk


overlay = Adw.overlay


def _normalize_position(index: int, length: int) -> int:
    if index < 0:
        index += length
    if index < 0 or index >= length:
        raise IndexError("index out of range")
    return index


def _widget_children(widget: Gtk.Widget) -> Iterator[Gtk.Widget]:
    child = widget.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()


def _sidebar_item_at(sidebar: Adw.Sidebar, index: int) -> Adw.SidebarItem:
    item = sidebar.get_item(index)
    if item is None:
        raise IndexError("index out of range")
    return item


def _sidebar_section_at(sidebar: Adw.Sidebar, index: int) -> Adw.SidebarSection:
    section = sidebar.get_section(index)
    if section is None:
        raise IndexError("index out of range")
    return section


def _sidebar_section_item_at(
    section: Adw.SidebarSection, index: int
) -> Adw.SidebarItem:
    item = section.get_item(index)
    if item is None:
        raise IndexError("index out of range")
    return item


def _squeezer_page_at(squeezer: Adw.Squeezer, index: int) -> Adw.SqueezerPage:
    for position, child in enumerate(_widget_children(squeezer)):
        if position == index:
            return squeezer.get_page(child)
    raise IndexError("index out of range")


def _view_stack_page_at(view_stack: Adw.ViewStack, index: int) -> Adw.ViewStackPage:
    for position, child in enumerate(_widget_children(view_stack)):
        if position == index:
            return view_stack.get_page(child)
    raise IndexError("index out of range")


@overlay.method("Carousel", name="__len__")
def carousel_len(self: Adw.Carousel) -> int:
    return int(self.get_n_pages())


@overlay.method("Carousel", name="__getitem__")
def carousel_getitem(self: Adw.Carousel, key: object) -> Gtk.Widget | list[Gtk.Widget]:
    length = len(self)
    match key:
        case slice():
            return [self.get_nth_page(i) for i in range(*key.indices(length))]
        case int():
            return self.get_nth_page(_normalize_position(key, length))
        case _:
            raise TypeError(
                f"carousel indices must be integers or slices, not {type(key).__name__}"
            )


@overlay.method("Carousel", name="__iter__")
def carousel_iter(self: Adw.Carousel) -> Iterator[Gtk.Widget]:
    for index in range(len(self)):
        yield self.get_nth_page(index)


@overlay.method("Sidebar", name="__len__")
def sidebar_len(self: Adw.Sidebar) -> int:
    return len(self.get_sections())


@overlay.method("Sidebar", name="__getitem__")
def sidebar_getitem(
    self: Adw.Sidebar, key: object
) -> Adw.SidebarSection | list[Adw.SidebarSection]:
    length = len(self)
    match key:
        case slice():
            return [_sidebar_section_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _sidebar_section_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                f"sidebar indices must be integers or slices, not {type(key).__name__}"
            )


@overlay.method("Sidebar", name="__iter__")
def sidebar_iter(self: Adw.Sidebar) -> Iterator[Adw.SidebarSection]:
    for index in range(len(self)):
        yield _sidebar_section_at(self, index)


@overlay.method("SidebarSection", name="__len__")
def sidebar_section_len(self: Adw.SidebarSection) -> int:
    return len(self.get_items())


@overlay.method("SidebarSection", name="__getitem__")
def sidebar_section_getitem(
    self: Adw.SidebarSection, key: object
) -> Adw.SidebarItem | list[Adw.SidebarItem]:
    length = len(self)
    match key:
        case slice():
            return [
                _sidebar_section_item_at(self, i) for i in range(*key.indices(length))
            ]
        case int():
            return _sidebar_section_item_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                "sidebar section indices must be integers or slices, not "
                f"{type(key).__name__}"
            )


@overlay.method("SidebarSection", name="__iter__")
def sidebar_section_iter(self: Adw.SidebarSection) -> Iterator[Adw.SidebarItem]:
    for index in range(len(self)):
        yield _sidebar_section_item_at(self, index)


@overlay.method("Squeezer", name="__len__")
def squeezer_len(self: Adw.Squeezer) -> int:
    return sum(1 for _child in _widget_children(self))


@overlay.method("Squeezer", name="__getitem__")
def squeezer_getitem(
    self: Adw.Squeezer, key: object
) -> Adw.SqueezerPage | list[Adw.SqueezerPage]:
    length = len(self)
    match key:
        case slice():
            return [_squeezer_page_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _squeezer_page_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                f"squeezer indices must be integers or slices, not {type(key).__name__}"
            )


@overlay.method("Squeezer", name="__iter__")
def squeezer_iter(self: Adw.Squeezer) -> Iterator[Adw.SqueezerPage]:
    for index in range(len(self)):
        yield _squeezer_page_at(self, index)


@overlay.method("TabView", name="__len__")
def tab_view_len(self: Adw.TabView) -> int:
    return int(self.get_n_pages())


@overlay.method("TabView", name="__getitem__")
def tab_view_getitem(self: Adw.TabView, key: object) -> Adw.TabPage | list[Adw.TabPage]:
    length = len(self)
    match key:
        case slice():
            return [self.get_nth_page(i) for i in range(*key.indices(length))]
        case int():
            return self.get_nth_page(_normalize_position(key, length))
        case _:
            raise TypeError(
                f"tab view indices must be integers or slices, not {type(key).__name__}"
            )


@overlay.method("TabView", name="__iter__")
def tab_view_iter(self: Adw.TabView) -> Iterator[Adw.TabPage]:
    for index in range(len(self)):
        yield self.get_nth_page(index)


@overlay.method("ViewStack", name="__len__")
def view_stack_len(self: Adw.ViewStack) -> int:
    return sum(1 for _child in _widget_children(self))


@overlay.method("ViewStack", name="__getitem__")
def view_stack_getitem(
    self: Adw.ViewStack, key: object
) -> Adw.ViewStackPage | list[Adw.ViewStackPage]:
    length = len(self)
    match key:
        case slice():
            return [_view_stack_page_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _view_stack_page_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                "view stack indices must be integers or slices, not "
                f"{type(key).__name__}"
            )


@overlay.method("ViewStack", name="__iter__")
def view_stack_iter(self: Adw.ViewStack) -> Iterator[Adw.ViewStackPage]:
    for index in range(len(self)):
        yield _view_stack_page_at(self, index)
