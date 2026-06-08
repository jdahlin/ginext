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

"""Port of goi/tests/test_managed_dict_store_attr.py."""

from __future__ import annotations

import gc
from typing import Any


def test_property_getter_can_store_attr_on_self(GObject: Any) -> None:
    from ginext import Gio

    class CoreArtistLike(GObject):  # type: ignore[misc]
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._model: Any = None

        @property
        def model(self) -> Any:
            if self._model is None:
                self._model = Gio.ListStore(item_type=Gio.SimpleAction.gimeta.gtype)
            return self._model

    artist = CoreArtistLike()
    model = artist.model

    assert isinstance(model, Gio.ListStore)
    assert artist.model is model


def test_subclass_dict_round_trips_across_wrap_cycle(GObject: Any) -> None:
    from ginext import Gio

    class WithAttrs(GObject):  # type: ignore[misc]
        pass

    store = Gio.ListStore(item_type=WithAttrs.gimeta.gtype)
    obj = WithAttrs()
    obj.label = "alpha"
    obj.tag = 42
    store.append(obj)

    del obj
    gc.collect()

    wrapped = store[0]

    assert wrapped.label == "alpha"
    assert wrapped.tag == 42

    wrapped.label = "beta"
    wrapped.fresh = "ok"

    assert wrapped.label == "beta"
    assert wrapped.fresh == "ok"


def test_storing_then_reading_through_managed_dict(GObject: Any) -> None:
    class Holder(GObject):  # type: ignore[misc]
        pass

    holder = Holder()

    for i in range(50):
        setattr(holder, f"k{i}", i)
    for i in range(50):
        assert getattr(holder, f"k{i}") == i
