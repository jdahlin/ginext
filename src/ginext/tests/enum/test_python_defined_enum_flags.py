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

"""Backlog port of goi/tests/test_enum.py.

goi covered Python-defined GEnum/GFlags subclasses. ginext currently
builds introspected enum and flags classes, but does not expose
PyGObject-compatible ``GObject.GEnum`` / ``GObject.GFlags`` base classes
for user-defined enum registration.
"""

from __future__ import annotations

import itertools
from typing import Any, cast

import pytest

pytestmark = pytest.mark.xfail(
    reason="Python-defined GObject.GEnum/GObject.GFlags registration pending",
    run=False,
    strict=False,
)

_type_seq = itertools.count()


def _type_name(prefix: str) -> str:
    return f"{prefix}{next(_type_seq)}"


def test_enum_gtype() -> None:
    from ginext import GObject

    class MyEnum(GObject.GEnum):
        ONE = 1
        TWO = 2
        THREE = 3

    assert MyEnum.__gtype__ != GObject.GEnum.__gtype__
    assert MyEnum.__gtype__.parent == GObject.GEnum.__gtype__
    assert MyEnum.__gtype__.pytype is MyEnum


def test_enum_values() -> None:
    from ginext import GObject

    class MyEnum(GObject.GEnum):
        ONE = 1
        FORTY_TWO = 42

    assert isinstance(MyEnum.ONE, MyEnum)
    assert cast("Any", MyEnum.ONE).value_name == "ONE"
    assert cast("Any", MyEnum.ONE).value_nick == "one"
    assert cast("Any", MyEnum.FORTY_TWO).value_name == "FORTY_TWO"
    assert cast("Any", MyEnum.FORTY_TWO).value_nick == "forty-two"


def test_enum_custom_type_name() -> None:
    from ginext import GObject

    type_name = _type_name("GinextEnum")

    class MyEnum(GObject.GEnum):
        __gtype_name__ = type_name
        ONE = 1

    assert MyEnum.__gtype__.name == type_name


def test_flags_gtype() -> None:
    from ginext import GObject

    class MyFlags(GObject.GFlags):
        ONE = 1
        TWO = 2
        FOUR = 4

    assert MyFlags.__gtype__ != GObject.GFlags.__gtype__
    assert MyFlags.__gtype__.parent == GObject.GFlags.__gtype__
    assert MyFlags.__gtype__.pytype is MyFlags


def test_flags_values() -> None:
    from ginext import GObject

    class MyFlags(GObject.GFlags):
        ONE = 1
        THIRTY_TWO = 32

    assert isinstance(MyFlags.ONE, MyFlags)
    assert cast("Any", MyFlags.ONE).value_names == ["ONE"]
    assert cast("Any", MyFlags.ONE).value_nicks == ["one"]
    assert cast("Any", MyFlags.ONE | MyFlags.THIRTY_TWO).value_names == [
        "ONE",
        "THIRTY_TWO",
    ]


def test_flags_custom_type_name() -> None:
    from ginext import GObject

    type_name = _type_name("GinextFlags")

    class MyFlags(GObject.GFlags):
        __gtype_name__ = type_name
        ONE = 1

    assert MyFlags.__gtype__.name == type_name
