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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Gtk.ListBox.bind_model: factory's `(item, user_data)` arity + return.

Two PyGObject-shaped contracts the gnome-music PlaylistsWidget shape
relies on:

1) Factory signature is `(item, user_data)`, even when the caller
   passes `user_data=None` (explicit None must reach the callback —
   only a *truly omitted* user_data slot stays hidden, matching the
   AsyncReadyCallback case pinned in test_Gio_Async).

2) The widget the factory returns is `transfer="full"` from GTK's
   POV. The closure-return marshaller has to take an extra ref on
   the underlying GObject so the wrapper's GC doesn't free the
   widget between the callback returning and `gtk_list_box_insert`
   actually using it. Without the bump, GTK logs
   `g_object_is_floating: G_IS_OBJECT(object) failed` and crashes on
   the unref that follows.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def namespaces() -> tuple[Any, Any, Any]:
    from ginext import GObject, Gio, Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    return GObject, Gio, Gtk


def test_bind_model_factory_receives_none_user_data(
    namespaces: tuple[Any, Any, Any],
) -> None:
    """Caller passes `user_data=None` → factory still gets the 2-arg
    `(item, user_data)` form with None in slot 2."""
    GObject, Gio, Gtk = namespaces

    class Item(GObject.Object, type_name="BindModelArityItem"):  # type: ignore[misc,name-defined,call-arg]
        val = GObject.Property(int)

    seen: list[Any] = []

    def factory(item: Any, user_data: Any) -> Any:
        seen.append((item.get_property("val"), user_data))
        row = Gtk.ListBoxRow()
        row.add(Gtk.Label.new(str(item.get_property("val"))))
        return row

    listbox = Gtk.ListBox()
    store = Gio.ListStore.new(item_type=Item.gimeta.gtype)
    listbox.bind_model(store, factory, None, None)

    for v in (1, 2, 3):
        item = Item()
        item.set_property("val", v)
        store.append(item)

    assert [s[0] for s in seen] == [1, 2, 3]
    # user_data slot surfaced as None for every call.
    assert all(s[1] is None for s in seen)


def test_bind_model_pygobject_arity(namespaces: tuple[Any, Any, Any]) -> None:
    """PyGObject shape: user_data_free_func is auto-managed and may be
    omitted. Both forms must work — the 2-arg form (no user_data, no
    destroy) and the 3-arg form (user_data supplied, destroy omitted,
    which is the gnome-music PlaylistsWidget shape:
    `self._sidebar.bind_model(self._model, self._add_playlist_to_sidebar)`
    and `self._songs_list.bind_model(playlist.get_property("model"),
    self._create_song_widget, playlist)`).
    """
    GObject, Gio, Gtk = namespaces

    class Item(GObject.Object, type_name="BindModelArityShapeItem"):  # type: ignore[misc,name-defined,call-arg]
        val = GObject.Property(int)

    # 2-arg form — factory takes just (item).
    lb1 = Gtk.ListBox()
    m1 = Gio.ListStore.new(item_type=Item.gimeta.gtype)
    seen1: list[Any] = []

    def f1(item: Any) -> Any:
        seen1.append(item.get_property("val"))
        return Gtk.ListBoxRow()

    lb1.bind_model(m1, f1)
    item1 = Item()
    item1.set_property("val", 7)
    m1.append(item1)
    assert seen1 == [7]

    # 3-arg form — factory takes (item, user_data); destroy omitted.
    lb2 = Gtk.ListBox()
    m2 = Gio.ListStore.new(item_type=Item.gimeta.gtype)
    seen2: list[Any] = []

    def f2(item: Any, user_data: Any) -> Any:
        seen2.append((item.get_property("val"), user_data))
        return Gtk.ListBoxRow()

    lb2.bind_model(m2, f2, "tag")
    item2 = Item()
    item2.set_property("val", 9)
    m2.append(item2)
    assert seen2 == [(9, "tag")]


def test_bind_model_factory_return_survives_python_gc(
    namespaces: tuple[Any, Any, Any],
) -> None:
    """Factory returns a widget by value; goi must bump the ref so
    GTK's `g_object_unref(widget)` after `gtk_list_box_insert` doesn't
    operate on freed memory. Without the bump the items-changed
    propagation logs `g_object_is_floating: G_IS_OBJECT(object)
    failed` repeatedly."""
    GObject, Gio, Gtk = namespaces

    class Item(GObject.Object, type_name="BindModelRefItem"):  # type: ignore[misc,name-defined,call-arg]
        val = GObject.Property(int)

    def factory(item: Any, _user_data: Any) -> Any:
        row = Gtk.ListBoxRow()
        row.add(Gtk.Label.new(str(item.get_property("val"))))
        return row  # local — would be GC'd immediately on the way out

    listbox = Gtk.ListBox()
    store = Gio.ListStore.new(item_type=Item.gimeta.gtype)
    listbox.bind_model(store, factory, None, None)

    # Enough items to exercise the items-changed → bound_model_changed
    # → g_object_is_floating chain repeatedly.
    for v in range(8):
        item = Item()
        item.set_property("val", v)
        store.append(item)

    # If the ref bump is missing, GTK's own logging would already have
    # emitted a critical and we can't reliably catch that from inside
    # the same process. The success signal is: append() returned
    # cleanly and the model has the expected count.
    assert store.get_n_items() == 8


pytestmark = pytest.mark.xdist_group("gtk3")
