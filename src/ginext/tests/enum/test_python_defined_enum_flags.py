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

"""Backlog port of goi/tests/test_enum.py.

goi covered Python-defined GEnum/GFlags subclasses. ginext currently
builds introspected enum and flags classes, but does not expose
PyGObject-compatible ``GObject.GEnum`` / ``GObject.GFlags`` base classes
for user-defined enum registration.
"""

from __future__ import annotations

import itertools
from typing import ClassVar, Protocol, cast

import pytest

from ginext import private

_type_seq = itertools.count()


def _type_name(prefix: str) -> str:
    return f"{prefix}{next(_type_seq)}"


class _HasGIMeta(Protocol):
    gimeta: ClassVar[private.GIMeta]


def _gimeta(cls: type[object]) -> private.GIMeta:
    return cast(type[_HasGIMeta], cls).gimeta


def test_enum_gtype() -> None:
    from ginext import GObject

    class MyEnum(GObject.GEnum):
        ONE = 1
        TWO = 2
        THREE = 3

    assert "__gtype__" not in vars(MyEnum)
    gimeta = _gimeta(MyEnum)
    assert gimeta.gtype > 255
    assert gimeta.type_name == "MyEnum"
    assert gimeta is _gimeta(MyEnum)


def test_enum_values() -> None:
    from ginext import GObject

    class MyEnum(GObject.GEnum):
        ONE = 1
        FORTY_TWO = 42

    assert isinstance(MyEnum.ONE, MyEnum)
    assert int(MyEnum.ONE) == 1
    assert int(MyEnum.FORTY_TWO) == 42


def test_enum_custom_type_name() -> None:
    from ginext import GObject

    type_name = _type_name("GinextEnum")

    class MyEnum(GObject.GEnum):
        __gtype_name__ = type_name
        ONE = 1

    assert "__gtype__" not in vars(MyEnum)
    assert _gimeta(MyEnum).type_name == type_name


def test_flags_gtype() -> None:
    from ginext import GObject

    class MyFlags(GObject.GFlags):
        ONE = 1
        TWO = 2
        FOUR = 4

    assert "__gtype__" not in vars(MyFlags)
    gimeta = _gimeta(MyFlags)
    assert gimeta.gtype > 255
    assert gimeta.type_name == "MyFlags"
    assert gimeta is _gimeta(MyFlags)


def test_flags_values() -> None:
    from ginext import GObject

    class MyFlags(GObject.GFlags):
        ONE = 1
        THIRTY_TWO = 32

    assert isinstance(MyFlags.ONE, MyFlags)
    assert int(MyFlags.ONE) == 1
    assert MyFlags.ONE | MyFlags.THIRTY_TWO == MyFlags(33)


def test_flags_custom_type_name() -> None:
    from ginext import GObject

    type_name = _type_name("GinextFlags")

    class MyFlags(GObject.GFlags):
        __gtype_name__ = type_name
        ONE = 1

    assert "__gtype__" not in vars(MyFlags)
    assert _gimeta(MyFlags).type_name == type_name


def test_imported_enums_do_not_expose_compat_attrs_in_core() -> None:
    import ginext

    t = ginext._load_namespace("GIMarshallingTests", "1.0")
    if hasattr(t.GEnum, "__gtype__"):
        pytest.skip("pygobject compat enum attrs already installed in this process")
    for cls, member, names in (
        (
            t.GEnum,
            t.GEnum.VALUE3,
            ("__gtype__", "__info__", "__enum_values__", "value_name", "value_nick"),
        ),
        (
            t.Flags,
            t.Flags.VALUE3,
            (
                "__gtype__",
                "__info__",
                "__flags_values__",
                "value_names",
                "value_nicks",
                "first_value_name",
                "first_value_nick",
            ),
        ),
    ):
        assert "gimeta" not in vars(cls)
        for name in names:
            assert not hasattr(cls, name), name
            assert not hasattr(member, name), name
        assert cls.gimeta is cls.gimeta
