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

from __future__ import annotations

from typing import Any

import pytest


def _require_list_store() -> Any:
    from ginext import Gio

    if not hasattr(Gio, "ListStore"):
        pytest.skip("Gio.ListStore not present")
    return Gio


def test_item_type_constructor_kwarg_accepts_class() -> None:
    Gio = _require_list_store()

    store = Gio.ListStore(item_type=Gio.FileInfo)
    assert isinstance(store, Gio.ListStore)


def test_item_type_constructor_kwarg_accepts_raw_gtype() -> None:
    Gio = _require_list_store()

    store = Gio.ListStore(item_type=Gio.FileInfo.gimeta.gtype)
    assert isinstance(store, Gio.ListStore)


def test_item_type_constructor_arg_rejects_non_type_value() -> None:
    Gio = _require_list_store()

    with pytest.raises(TypeError):
        Gio.ListStore(item_type="not a type")


def test_append_accepts_matching_gobject() -> None:
    Gio = _require_list_store()

    store = Gio.ListStore(item_type=Gio.Cancellable)
    item = Gio.Cancellable()
    store.append(item)


def test_append_rejects_wrong_type() -> None:
    Gio = _require_list_store()

    store = Gio.ListStore(item_type=Gio.Cancellable)
    with pytest.raises(TypeError):
        store.append("not a gobject")


@pytest.fixture
def list_store_item(GObject: Any, unique_type_name: Any) -> Any:
    return type(GObject)(unique_type_name("PygListItem"), (GObject,), {})


@pytest.fixture
def list_store(list_store_item: Any) -> Any:
    Gio = _require_list_store()

    return Gio.ListStore(item_type=list_store_item)


def test_list_model_len(list_store: Any, list_store_item: Any) -> None:
    assert len(list_store) == 0
    assert not list_store

    for index in range(1, 10):
        list_store.append(list_store_item())
        assert len(list_store) == index

    assert list_store
    list_store.remove_all()
    assert not list_store
    assert len(list_store) == 0


def test_list_model_get_item_simple(list_store: Any, list_store_item: Any) -> None:
    with pytest.raises(IndexError):
        list_store[0]

    first_item = list_store_item()
    list_store.append(first_item)
    assert list_store[0] is first_item
    assert list_store[-1] is first_item


def test_list_model_get_item_slice(list_store: Any, list_store_item: Any) -> None:
    source = [list_store_item() for _ in range(30)]
    for item in source:
        list_store.append(item)

    assert list_store[1:10] == source[1:10]
    assert list_store[::-1] == source[::-1]
    assert list_store[:] == source[:]


def test_list_model_contains(list_store: Any, list_store_item: Any) -> None:
    item = list_store_item()
    list_store.append(item)

    assert item in list_store
    assert list_store_item() not in list_store
    with pytest.raises(TypeError):
        object() in list_store


def test_list_store_delitem_simple(list_store: Any, list_store_item: Any) -> None:
    item = list_store_item()
    list_store.append(item)

    del list_store[0]

    assert not list_store


def test_list_store_setitem_simple(list_store: Any, list_store_item: Any) -> None:
    first = list_store_item()
    replacement = list_store_item()
    list_store.append(first)

    list_store[0] = replacement

    assert list_store[:] == [replacement]


def test_list_model_iter(list_store: Any, list_store_item: Any) -> None:
    assert list(iter(list_store)) == []

    items = [list_store_item() for _ in range(5)]
    for item in items:
        list_store.append(item)

    # iteration yields the items in order, and is repeatable
    assert list(list_store) == items
    assert [item for item in list_store] == items  # noqa: C416
    assert list(list_store) == items
    # iter() returns a fresh iterator each time
    assert next(iter(list_store)) is items[0]


def test_list_model_getitem_out_of_range(list_store: Any, list_store_item: Any) -> None:
    list_store.append(list_store_item())

    with pytest.raises(IndexError):
        list_store[1]
    with pytest.raises(IndexError):
        list_store[-2]


def test_list_model_getitem_rejects_bad_key_type(list_store: Any) -> None:
    with pytest.raises(TypeError):
        list_store["nope"]


def test_list_store_delitem_slice(list_store: Any, list_store_item: Any) -> None:
    items = [list_store_item() for _ in range(5)]
    for item in items:
        list_store.append(item)

    del list_store[1:3]

    assert list_store[:] == [items[0], items[3], items[4]]


def test_list_store_delitem_rejects_bad_key_type(list_store: Any) -> None:
    with pytest.raises(TypeError):
        del list_store["nope"]


def test_list_store_setitem_negative_index(
    list_store: Any, list_store_item: Any
) -> None:
    list_store.append(list_store_item())
    replacement = list_store_item()

    list_store[-1] = replacement

    assert list_store[:] == [replacement]


def test_list_store_setitem_slice(
    list_store: Any, list_store_item: Any
) -> None:
    a = list_store_item()
    b = list_store_item()
    list_store.append(a)
    replacement = list_store_item()
    list_store[0:1] = [replacement]
    assert list_store[:] == [replacement]
    list_store[:] = [a, b]
    assert list_store[:] == [a, b]


def test_list_store_setitem_rejects_bad_key_type(
    list_store: Any, list_store_item: Any
) -> None:
    list_store.append(list_store_item())
    with pytest.raises(TypeError):
        list_store["nope"] = list_store_item()
