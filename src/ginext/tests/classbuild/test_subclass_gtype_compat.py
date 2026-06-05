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

"""Port of goi/tests/test_subclass_gtype.py."""

from __future__ import annotations

from typing import Any


def test_subclass_without_gtype_name_gets_fresh_gtype(GObject: Any) -> None:
    class Plain(GObject):  # type: ignore[misc]
        pass

    assert Plain.gimeta.gtype != GObject.gimeta.gtype
    assert Plain.gimeta.parent is GObject


def test_subclass_with_gtype_name_gets_fresh_gtype(
    GObject: Any, unique_type_name: Any
) -> None:
    name = unique_type_name("GinextSubFresh")

    class Fresh(GObject, type_name=name):  # type: ignore[misc, call-arg]
        pass

    assert Fresh.gimeta.type_name == name
    assert Fresh.gimeta.gtype != GObject.gimeta.gtype
    assert Fresh.gimeta.parent is GObject


def test_subclass_instantiation_uses_fresh_gtype(
    GObject: Any, unique_type_name: Any
) -> None:
    name = unique_type_name("GinextSubInst")

    class Fresh(GObject, type_name=name):  # type: ignore[misc, call-arg]
        pass

    inst = Fresh()

    assert isinstance(inst, Fresh)
    assert isinstance(inst, GObject)
    assert Fresh.gimeta.type_name == name


def test_two_subclasses_get_distinct_gtypes(
    GObject: Any, unique_type_name: Any
) -> None:
    name_a = unique_type_name("GinextSubA")
    name_b = unique_type_name("GinextSubB")

    class A(GObject, type_name=name_a):  # type: ignore[misc, call-arg]
        pass

    class B(GObject, type_name=name_b):  # type: ignore[misc, call-arg]
        pass

    assert A.gimeta.gtype != B.gimeta.gtype
    assert A.gimeta.parent is B.gimeta.parent


def test_child_without_explicit_type_name_gets_own_gtype(
    GObject: Any, unique_type_name: Any
) -> None:
    name = unique_type_name("GinextSubBase")

    class Base(GObject, type_name=name):  # type: ignore[misc, call-arg]
        pass

    class Child(Base):
        pass

    assert Child.gimeta.gtype != Base.gimeta.gtype
    assert Child.gimeta.parent is Base
