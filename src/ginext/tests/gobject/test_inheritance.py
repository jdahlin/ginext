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

from typing import cast

import pytest

from ginext.tests.conftest import _MakeSubclass


def test_two_level_subclass_registers_distinct_gtype(
    GObject: object, Property: object
) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        a: int = Property(default=1)  # type: ignore[operator]

    class B(A):
        b: int = Property(default=2)  # type: ignore[operator]

    assert getattr(A, "gimeta").gtype != getattr(B, "gimeta").gtype
    assert getattr(A, "gimeta").gtype != getattr(GObject, "gimeta").gtype


def test_subclass_pspecs_only_lists_locally_declared(
    GObject: object, Property: object
) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        inherited: int = Property(default=1)  # type: ignore[operator]

    class B(A):
        own: int = Property(default=2)  # type: ignore[operator]

    assert set(getattr(A, "gimeta").pspecs) == {"inherited"}
    assert set(getattr(B, "gimeta").pspecs) == {"own"}


def test_three_level_parent_chain(GObject: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        pass

    class B(A):
        pass

    class C(B):
        pass

    assert getattr(C, "gimeta").parent is B
    assert getattr(B, "gimeta").parent is A
    assert getattr(A, "gimeta").parent is GObject


def test_subclass_prop_ids_restart_from_one(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        a1: int = Property()  # type: ignore[operator]
        a2: int = Property()  # type: ignore[operator]

    class B(A):
        b1: int = Property()  # type: ignore[operator]

    assert getattr(A, "gimeta").prop_ids == {"a1": 1, "a2": 2}
    assert getattr(B, "gimeta").prop_ids == {"b1": 1}


def test_two_subclasses_of_same_parent_dont_collide(
    GObject: object, Property: object
) -> None:
    class Base(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=0)  # type: ignore[operator]

    class Left(Base):
        left_value: int = Property(default=1)  # type: ignore[operator]

    class Right(Base):
        right_value: int = Property(default=2)  # type: ignore[operator]

    assert getattr(Left, "gimeta").gtype != getattr(Right, "gimeta").gtype
    assert getattr(Left, "gimeta").parent is Base
    assert getattr(Right, "gimeta").parent is Base


def test_multiple_inheritance_picks_first_base(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        a: int = Property()  # type: ignore[operator]

    class B(GObject):  # type: ignore[misc,valid-type]
        b: int = Property()  # type: ignore[operator]

    class C(A, B):
        c: int = Property()  # type: ignore[operator]

    assert getattr(C, "gimeta").parent is A
    assert set(getattr(C, "gimeta").pspecs) == {"c"}


def test_read_inherited_property_default(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=42)  # type: ignore[operator]

    class B(A):
        pass

    assert getattr(B(), "x") == 42


def test_write_inherited_property_then_read(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=0)  # type: ignore[operator]

    class B(A):
        pass

    obj = B()
    setattr(obj, "x", 7)
    assert getattr(obj, "x") == 7


def test_own_and_inherited_properties_dont_alias(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=10)  # type: ignore[operator]

    class B(A):
        y: int = Property(default=20)  # type: ignore[operator]

    obj = B()
    assert (getattr(obj, "x"), getattr(obj, "y")) == (10, 20)
    setattr(obj, "x", 1)
    setattr(obj, "y", 2)
    assert (getattr(obj, "x"), getattr(obj, "y")) == (1, 2)


def test_inherited_property_independent_per_instance(
    GObject: object, Property: object
) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=0)  # type: ignore[operator]

    class B(A):
        pass

    first, second = B(), B()
    setattr(first, "x", 100)
    assert getattr(second, "x") == 0


def test_three_level_chain_all_properties_accessible(
    GObject: object, Property: object
) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        a_val: int = Property(default=1)  # type: ignore[operator]

    class B(A):
        b_val: int = Property(default=2)  # type: ignore[operator]

    class C(B):
        c_val: int = Property(default=3)  # type: ignore[operator]

    obj = C()
    assert (getattr(obj, "a_val"), getattr(obj, "b_val"), getattr(obj, "c_val")) == (1, 2, 3)
    setattr(obj, "a_val", 100)
    setattr(obj, "b_val", 200)
    setattr(obj, "c_val", 300)
    assert (getattr(obj, "a_val"), getattr(obj, "b_val"), getattr(obj, "c_val")) == (100, 200, 300)


def test_five_level_chain(make_subclass: _MakeSubclass, Property: object, GObject: object) -> None:
    classes: list[object] = [GObject]
    for index in range(5):
        classes.append(
            make_subclass(
                {f"f{index}": (int, Property(default=index))},  # type: ignore[operator]
                base=cast(type, classes[-1]),
                prefix=f"L{index}",
            )
        )

    obj = cast(type, classes[-1])()
    for index in range(5):
        assert getattr(obj, f"f{index}") == index


def test_inheritance_with_mixed_types(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        name: str = Property(default="alice")  # type: ignore[operator]

    class B(A):
        count: int = Property(default=0)  # type: ignore[operator]

    obj = B()
    assert (getattr(obj, "name"), getattr(obj, "count")) == ("alice", 0)
    setattr(obj, "name", "bob")
    setattr(obj, "count", 42)
    assert (getattr(obj, "name"), getattr(obj, "count")) == ("bob", 42)


def test_inherited_readonly_still_rejects_write(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        ro: int = Property(default=1, readonly=True)  # type: ignore[operator]

    class B(A):
        pass

    obj = B()
    with pytest.raises(AttributeError, match="read-only"):
        setattr(obj, "ro", 5)


def test_inherited_property_type_check_on_set(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=0)  # type: ignore[operator]

    class B(A):
        pass

    obj = B()
    with pytest.raises((TypeError, ValueError, OverflowError)):
        setattr(obj, "x", "not an int")


def test_subclass_redeclares_parent_property_name(GObject: object, Property: object) -> None:
    class A(GObject):  # type: ignore[misc,valid-type]
        x: int = Property(default=1)  # type: ignore[operator]

    class B(A):
        x: int = Property(default=2)  # type: ignore[operator]

    assert getattr(A(), "x") == 1
    assert getattr(B(), "x") == 2
    assert getattr(A, "gimeta").pspecs["x"] != getattr(B, "gimeta").pspecs["x"]


def test_property_from_interface_can_be_overridden(GObject: object, Property: object) -> None:
    from ginext import Gio

    class MyAction(Gio.SimpleAction):
        enabled: bool = Property(default=False)  # type: ignore[operator]

    obj = MyAction(name="example")
    assert getattr(obj, "enabled") is False
    setattr(obj, "enabled", True)
    assert getattr(obj, "enabled") is True
