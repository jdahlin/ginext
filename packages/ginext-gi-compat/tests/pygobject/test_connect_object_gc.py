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

"""Backlog port of goi/tests/test_GObject_connect_object_gc.py."""

from __future__ import annotations

import gc


def test_connect_object_wrapper_survives_gc_cycle() -> None:
    from ginext import Gio

    seen = []

    def on_add(store: object, *args: object) -> None:
        seen.append((store, args))

    store = Gio.ListStore(item_type=Gio.FileInfo)
    store.connect_object("items-changed", on_add, store)

    holder = Gio.FileInfo()
    holder.set_attribute_object("store", store)

    del store
    gc.collect()

    recovered = holder.get_attribute_object("store")
    assert recovered is not None

    recovered.append(Gio.FileInfo())

    assert len(seen) == 1
    assert seen[0][0] is recovered
    assert seen[0][1] == (0, 0, 1)
