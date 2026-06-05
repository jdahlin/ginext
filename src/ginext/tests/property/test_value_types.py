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

import pytest

from ..conftest import PSPEC_GTYPE_CONSTANTS
from ..gi_test_utils import load_test_namespace
from ..conftest import BUILTIN_VALUE_TYPES


@pytest.mark.parametrize("case", BUILTIN_VALUE_TYPES)
def test_annotation_drives_pspec_value_type(
    make_property_class: Any, pspec_info: Any, case: Any
) -> None:
    cls = make_property_class(case.annotation, name="field")
    info = pspec_info(cls.gimeta.pspecs["field"])
    assert info.value_type_name == case.gtype_name


@pytest.mark.parametrize("case", BUILTIN_VALUE_TYPES)
def test_pspec_name_matches_attribute_name(
    make_property_class: Any, pspec_info: Any, case: Any
) -> None:
    cls = make_property_class(case.annotation, name="snake_case_name")
    assert "snake_case_name" in cls.gimeta.pspecs
    info = pspec_info(cls.gimeta.pspecs["snake_case_name"])
    assert info.name == "snake-case-name"


def test_bytes_maps_to_string(make_property_class: Any, pspec_info: Any) -> None:
    cls = make_property_class(bytes, name="blob")
    info = pspec_info(cls.gimeta.pspecs["blob"])
    assert info.value_type_name == "gchararray"


@pytest.mark.parametrize("constant, gtype_name", PSPEC_GTYPE_CONSTANTS)
def test_gtype_constant_annotation_drives_pspec_value_type(
    GType: Any,
    make_property_class: Any,
    pspec_info: Any,
    constant: Any,
    gtype_name: Any,
) -> None:
    cls = make_property_class(getattr(GType, constant), name="field")
    info = pspec_info(cls.gimeta.pspecs["field"])
    assert info.value_type_name == gtype_name


def test_unsupported_annotation_raises(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:
    name = unique_type_name("BadAnnotation")
    with pytest.raises(TypeError, match="unsupported property type"):

        class Foo(GObject, type_name=name):  # type: ignore[misc, call-arg]
            field: dict[str, Any] = Property()


def test_unsupported_python_type_raises_typeerror(GObject: Any, Property: Any) -> None:
    with pytest.raises(TypeError, match="unsupported property type for field"):

        class Foo(GObject):  # type: ignore[misc]
            field: list[Any] = Property()


def test_unsupported_annotation_after_valid_property_raises(
    GObject: Any, Property: Any
) -> None:
    with pytest.raises(TypeError, match="unsupported property type for bad"):

        class Foo(GObject):  # type: ignore[misc]
            good: int = Property()
            bad: list[Any] = Property()


def test_annotation_with_non_integer_gtype_is_unsupported(
    GObject: Any, Property: Any
) -> None:
    class BadMeta:
        gtype = object()

    class BadType:
        gimeta = BadMeta()

    with pytest.raises(TypeError, match="unsupported property type for field"):

        class Foo(GObject):  # type: ignore[misc]
            field: BadType = Property()


def test_enum_annotation_is_unsupported(GObject: Any, Property: Any) -> None:
    import enum

    class Color(enum.Enum):
        RED = 1

    with pytest.raises(TypeError, match="unsupported property type"):

        class Foo(GObject):  # type: ignore[misc]
            color: Color = Property(default=Color.RED)


def test_flags_annotation_registers_pspec(
    make_property_class: Any, pspec_info: Any
) -> None:
    tests = load_test_namespace("GIMarshallingTests")
    cls = make_property_class(tests.Flags, name="mask", default=tests.Flags.VALUE2)

    info = pspec_info(cls.gimeta.pspecs["mask"])

    assert info.value_type == tests.Flags.gimeta.gtype
    obj = cls()
    assert obj.mask == int(tests.Flags.VALUE2)
    obj.mask = tests.Flags.VALUE1 | tests.Flags.VALUE3
    assert obj.mask == int(tests.Flags.VALUE1 | tests.Flags.VALUE3)


def test_variant_annotation_registers_pspec(
    make_property_class: Any, pspec_info: Any
) -> None:
    from ginext import GLib

    cls = make_property_class(GLib.Variant, name="payload", default="42")

    info = pspec_info(cls.gimeta.pspecs["payload"])

    assert info.value_type_name == "GVariant"
    obj = cls()
    assert obj.payload.unpack() == 42
    obj.payload = None
    assert obj.payload is None
