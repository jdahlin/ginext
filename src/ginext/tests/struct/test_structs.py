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

from __future__ import annotations

import math

import pytest

from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def gm() -> Namespace:
    return load_test_namespace("GIMarshallingTests")


@pytest.fixture(scope="module")
def regress() -> Namespace:
    return load_test_namespace("Regress")


@pytest.fixture(scope="module")
def glib() -> Namespace:
    return load_test_namespace("GLib", "2.0")


def test_simple_struct_default_constructor_and_fields(gm: Namespace) -> None:
    struct = gm.SimpleStruct()

    assert isinstance(struct, gm.SimpleStruct)
    assert struct.long_ == 0
    assert struct.int8 == 0

    struct.long_ = 6
    struct.int8 = 7

    assert struct.long_ == 6
    assert struct.int8 == 7


def test_simple_struct_instance_method(gm: Namespace) -> None:
    struct = gm.SimpleStruct()
    struct.long_ = 6
    struct.int8 = 7

    assert struct.method() is None


def test_simple_struct_unbound_method_type_check(gm: Namespace) -> None:
    struct = gm.NestedStruct()

    with pytest.raises(TypeError):
        gm.SimpleStruct.inv(struct)
    with pytest.raises(TypeError):
        gm.SimpleStruct.inv(None)


def test_simple_struct_return_function(gm: Namespace) -> None:
    struct = gm.simple_struct_returnv()

    assert isinstance(struct, gm.SimpleStruct)
    assert struct.long_ == 6
    assert struct.int8 == 7


def test_nested_struct_field_returns_wrapper(gm: Namespace) -> None:
    struct = gm.NestedStruct()

    assert isinstance(struct.simple_struct, gm.SimpleStruct)
    struct.simple_struct.long_ = 42
    assert struct.simple_struct.long_ == 42


def test_not_simple_struct_null_pointer_field(gm: Namespace) -> None:
    struct = gm.NotSimpleStruct()

    assert struct.pointer is None


def test_test_struct_a_fields_and_clone(regress: Namespace) -> None:
    struct = regress.TestStructA()
    struct.some_int = 10
    struct.some_int8 = 21
    struct.some_double = 3.14
    struct.some_enum = regress.TestEnum.VALUE3

    clone = struct.clone()

    assert clone is not struct
    assert clone.some_int == 10
    assert clone.some_int8 == 21
    assert clone.some_double == pytest.approx(3.14)
    assert clone.some_enum == regress.TestEnum.VALUE3


def test_test_struct_a_double_field_accepts_nan(regress: Namespace) -> None:
    struct = regress.TestStructA()

    struct.some_double = float("nan")

    assert math.isnan(struct.some_double)


def test_test_struct_b_nested_clone(regress: Namespace) -> None:
    struct = regress.TestStructB()
    struct.some_int8 = 8
    struct.nested_a.some_int = 20
    struct.nested_a.some_int8 = 12
    struct.nested_a.some_double = 333.3333
    struct.nested_a.some_enum = regress.TestEnum.VALUE2

    clone = struct.clone()

    assert clone is not struct
    assert clone.some_int8 == 8
    assert clone.nested_a.some_int == 20
    assert clone.nested_a.some_int8 == 12
    assert clone.nested_a.some_double == pytest.approx(333.3333)
    assert clone.nested_a.some_enum == regress.TestEnum.VALUE2


def test_test_struct_a_parse_type_function(regress: Namespace) -> None:
    struct = regress.TestStructA.parse("ignored")

    assert isinstance(struct, regress.TestStructA)
    assert struct.some_int == 23


def test_fixed_array_field(regress: Namespace) -> None:
    struct = regress.TestStructFixedArray()
    struct.just_int = 5
    struct.array = list(range(10))

    assert struct.just_int == 5
    assert struct.array == list(range(10))


def test_glib_list_gpointer_field_accepts_int_and_none(glib: Namespace) -> None:
    record = glib.List()

    record.data = 123
    assert record.data == 123

    record.data = None
    assert record.data == 0


def test_gtype_record_field_accepts_class_and_rejects_raw_int(regress: Namespace) -> None:
    record = regress.TestStructE()

    record.some_type = regress.TestObj
    assert record.some_type == regress.TestObj.gimeta.gtype

    with pytest.raises(TypeError, match="GType"):
        record.some_type = 42
    with pytest.raises(TypeError, match="GType"):
        record.some_type = int


# --- __match_args__ (positional structural matching) -----------------------


def test_struct_match_args_is_scalar_fields_in_order(regress: Namespace) -> None:
    """A record's __match_args__ lists its readable primitive-scalar fields in
    declaration order, so it can be matched positionally like a namedtuple.
    The non-scalar `some_enum` field is intentionally excluded."""
    assert regress.TestSimpleBoxedA.__match_args__ == (
        "some_int",
        "some_int8",
        "some_double",
    )


def test_struct_positional_pattern_match(regress: Namespace) -> None:
    boxed = regress.TestSimpleBoxedA()
    boxed.some_int = 7
    boxed.some_double = 2.5

    match boxed:
        case regress.TestSimpleBoxedA(some_int, _int8, some_double):
            assert some_int == 7
            assert some_double == pytest.approx(2.5)
        case _:  # pragma: no cover - guards against a matching regression
            raise AssertionError("TestSimpleBoxedA did not match positionally")


def test_struct_keyword_pattern_match(regress: Namespace) -> None:
    boxed = regress.TestSimpleBoxedA()
    boxed.some_int = 11

    match boxed:
        case regress.TestSimpleBoxedA(some_int=value):
            assert value == 11
        case _:  # pragma: no cover
            raise AssertionError("TestSimpleBoxedA did not match by keyword")
