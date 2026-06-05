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

from typing import Any


def test_subclass_registers_a_gtype(GObject: Any, unique_type_name: Any) -> None:
    name = unique_type_name("PropEmpty")

    class Empty(GObject, type_name=name):  # type: ignore[misc, call-arg]
        pass

    assert Empty.gimeta.type_name == name
    assert Empty.gimeta.gtype != 0
    assert Empty.gimeta.pspecs == {}
    assert Empty.gimeta.prop_ids == {}
    assert Empty.gimeta.gi_info is None


def test_each_property_field_produces_a_pspec(
    make_subclass: Any, Property: Any
) -> None:
    cls = make_subclass(
        {
            "title": (str, Property(default="")),
            "count": (int, Property(default=0)),
            "ratio": (float, Property(default=0.0)),
            "on": (bool, Property(default=False)),
        },
        prefix="Fields",
    )
    assert set(cls.gimeta.pspecs) == {"title", "count", "ratio", "on"}


def test_prop_ids_are_dense_and_one_based(make_subclass: Any, Property: Any) -> None:
    cls = make_subclass(
        {
            "a": (int, Property(default=0)),
            "b": (int, Property(default=0)),
            "c": (int, Property(default=0)),
        },
        prefix="Props",
    )
    assert cls.gimeta.prop_ids == {"a": 1, "b": 2, "c": 3}


def test_class_without_property_descriptor_is_not_a_pspec(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject):  # type: ignore[misc]
        title: str = Property(default="")
        plain: int = 7

    assert "title" in Foo.gimeta.pspecs
    assert "plain" not in Foo.gimeta.pspecs


def test_explicit_type_name_overrides_module_qualified_default(GObject: Any) -> None:
    class Foo(GObject, type_name="MyExplicitName"):  # type: ignore[misc, call-arg]
        pass

    assert Foo.gimeta.type_name == "MyExplicitName"


def test_default_type_name_includes_module_and_class(
    GObject: Any, unique_type_name: Any
) -> None:
    cls_name = unique_type_name("Auto")
    cls = type(GObject)(cls_name, (GObject,), {"__annotations__": {}})

    assert cls_name in cls.gimeta.type_name
    assert "+" in cls.gimeta.type_name


def test_subclass_parent_is_gobject(GObject: Any) -> None:
    class Foo(GObject):  # type: ignore[misc]
        pass

    assert Foo.gimeta.parent is GObject


def test_duplicate_gtype_name_auto_disambiguates(GObject: Any) -> None:
    class First(GObject, type_name="GinextDupCheck"):  # type: ignore[misc, call-arg]
        pass

    class Second(GObject, type_name="GinextDupCheck"):  # type: ignore[misc, call-arg]
        pass

    assert First.gimeta.type_name == "GinextDupCheck"
    assert Second.gimeta.type_name == "GinextDupCheck_2"
    assert First.gimeta.gtype != Second.gimeta.gtype
