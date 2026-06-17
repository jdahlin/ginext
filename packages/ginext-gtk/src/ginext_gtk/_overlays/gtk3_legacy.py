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

"""GTK 3 only: Container, Editable, Table, drag-and-drop, stock_lookup, stock constants."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from ginext import Gtk

if TYPE_CHECKING:
    import types
    from collections.abc import Callable, Iterable, Iterator


    class _Container(Protocol):
        def get_children(self) -> list[object] | None: ...

    class _Widget(Protocol):
        def thaw_child_notify(self) -> None: ...

    class _Editable(Protocol):
        def insert_text(self, text: str, n_chars: int, position: int) -> int: ...
        def get_selection_bounds(self) -> tuple[bool, int, int]: ...

overlay = Gtk.overlay

if Gtk.__version__[0] == 3:

    @overlay.replace
    def stock_lookup(
        fn: Callable[[str], tuple[bool, Gtk.StockItem]], stock_id: str
    ) -> object:
        ok, stock_item = fn(stock_id)
        if not ok:
            return None
        compat_item = Gtk.StockItem()
        compat_item.stock_id = stock_item.stock_id
        compat_item.label = stock_item.label
        compat_item.modifier = stock_item.modifier
        compat_item.keyval = stock_item.keyval
        compat_item.translation_domain = stock_item.translation_domain
        return compat_item


# ---------------------------------------------------------------------------
# Widget drag-and-drop helpers
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 3:

    class _FreezeChildNotifyContext:
        __slots__ = ("_obj",)

        def __init__(self, obj: _Widget) -> None:
            self._obj: _Widget = obj

        def __enter__(self) -> _FreezeChildNotifyContext:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            tb: types.TracebackType | None,
        ) -> Literal[False]:
            self._obj.thaw_child_notify()
            return False

    def _construct_target_list(targets: Iterable[object]) -> list[object]:
        target_entries: list[object] = []
        for entry in targets:
            if not isinstance(entry, Gtk.TargetEntry):
                entry_seq: Iterator[object] = iter(entry)  # type: ignore[call-overload]
                entry = Gtk.TargetEntry.new(*entry_seq)
            target_entries.append(entry)
        return target_entries

    overlay.add(_construct_target_list)

    @overlay.method("Widget")
    def freeze_child_notify(
        fn: Callable[[object], object], self: _Widget
    ) -> _FreezeChildNotifyContext:
        fn(self)
        return _FreezeChildNotifyContext(self)

    @overlay.method("Widget")
    def drag_dest_set_target_list(
        fn: Callable[[object, object], object],
        self: object,
        target_list: Iterable[object] | None,
    ) -> object:
        if target_list is not None and not isinstance(target_list, Gtk.TargetList):
            target_list = Gtk.TargetList.new(_construct_target_list(target_list))
        return fn(self, target_list)

    @overlay.method("Widget")
    def drag_source_set_target_list(
        fn: Callable[[object, object], object],
        self: object,
        target_list: Iterable[object] | None,
    ) -> object:
        if target_list is not None and not isinstance(target_list, Gtk.TargetList):
            target_list = Gtk.TargetList.new(_construct_target_list(target_list))
        return fn(self, target_list)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 3:

    @overlay.method("Container")
    def __contains__(self: _Container, child: object) -> bool:
        children = self.get_children()
        return child in ([] if children is None else list(children))

    @overlay.method("Container")
    def __iter__(self: _Container) -> object:
        children = self.get_children()
        return iter([] if children is None else children)

    @overlay.method("Container")
    def __len__(self: _Container) -> int:
        children = self.get_children()
        return 0 if children is None else len(children)

    @overlay.method("Container")
    def __bool__(self: _Container) -> bool:
        return True


# ---------------------------------------------------------------------------
# Editable
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 3:

    @overlay.method("Editable")
    def insert_text(self: _Editable, text: str, position: int) -> object:
        # Call the GIR method directly by bypassing the overlay descriptor.
        # GTK3 Editable.insert_text has a different signature (text, n_chars, position).
        insert: Callable[[_Editable, str, int, int], object] = Gtk.Editable.insert_text  # type: ignore[assignment]
        return insert(self, text, -1, position)

    @overlay.method("Editable")
    def get_selection_bounds(self: _Editable) -> tuple[int, int] | tuple[()]:
        get_bounds: Callable[[_Editable], tuple[bool, int, int]] = Gtk.Editable.get_selection_bounds  # type: ignore[assignment]
        ok, start, end = get_bounds(self)
        return () if not ok else (start, end)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 3:

    @overlay.method("Table")
    def attach(
        fn: Callable[
            [object, object, int, int, int, int, object, object, int, int], object
        ],
        self: object,
        child: object,
        left_attach: int,
        right_attach: int,
        top_attach: int,
        bottom_attach: int,
        xoptions: object = None,
        yoptions: object = None,
        xpadding: int = 0,
        ypadding: int = 0,
    ) -> object:
        if xoptions is None:
            xoptions = Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL
        if yoptions is None:
            yoptions = Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL
        return fn(
            self,
            child,
            left_attach,
            right_attach,
            top_attach,
            bottom_attach,
            xoptions,
            yoptions,
            xpadding,
            ypadding,
        )


# ---------------------------------------------------------------------------
# TreeView drag-and-drop
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 3:

    @overlay.method("TreeView")
    def enable_model_drag_source(
        fn: Callable[[object, object, list[object], object], object],
        self: object,
        start_button_mask: object,
        targets: Iterable[object],
        actions: object,
    ) -> object:
        return fn(self, start_button_mask, _construct_target_list(targets), actions)

    @overlay.method("TreeView")
    def enable_model_drag_dest(
        fn: Callable[[object, list[object], object], object],
        self: object,
        targets: Iterable[object],
        actions: object,
    ) -> object:
        return fn(self, _construct_target_list(targets), actions)


# ---------------------------------------------------------------------------
# Stock item constants
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 3:
    overlay.constants(
        {
            "STOCK_ABOUT": "gtk-about",
            "STOCK_ADD": "gtk-add",
            "STOCK_APPLY": "gtk-apply",
            "STOCK_CANCEL": "gtk-cancel",
            "STOCK_CLOSE": "gtk-close",
            "STOCK_DELETE": "gtk-delete",
            "STOCK_HELP": "gtk-help",
            "STOCK_NEW": "gtk-new",
            "STOCK_NO": "gtk-no",
            "STOCK_OK": "gtk-ok",
            "STOCK_OPEN": "gtk-open",
            "STOCK_QUIT": "gtk-quit",
            "STOCK_REFRESH": "gtk-refresh",
            "STOCK_REMOVE": "gtk-remove",
            "STOCK_SAVE": "gtk-save",
            "STOCK_YES": "gtk-yes",
        }
    )
