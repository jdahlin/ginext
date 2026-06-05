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

"""Port of goi/tests/test_subclass_with_gobject_class_attr.py."""

from __future__ import annotations

from typing import Any

import pytest


def test_subclass_with_gobject_class_attr_doesnt_abort(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:
    from ginext import Gio

    seed_action = Gio.SimpleAction(name="seed")
    TextureCacheLike = type(GObject)(
        unique_type_name("TextureCacheLike"),
        (GObject,),
        {
            "__annotations__": {"label": str},
            "label": Property(default=""),
            "_seed": seed_action,
        },
    )

    obj = TextureCacheLike()

    assert obj.label == ""
    assert TextureCacheLike._seed is seed_action


def test_class_attr_gobject_attribute_lookup_still_misses_cleanly() -> None:
    from ginext import Gio

    action: Any = Gio.SimpleAction(name="a")

    with pytest.raises(AttributeError):
        _ = action.this_attribute_does_not_exist_anywhere


def test_repeated_class_attr_probe_is_stable(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:
    from ginext import Gio

    seed = Gio.SimpleAction(name="seed")
    for _ in range(5):
        ns = {
            "__annotations__": {"title": str},
            "title": Property(default=""),
            "_seed": seed,
        }
        cls = type(GObject)(unique_type_name("RepeatedProbe"), (GObject,), ns)
        inst = cls()

        assert inst.title == ""
