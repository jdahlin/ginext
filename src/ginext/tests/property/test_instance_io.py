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

import struct
from typing import Any

import pytest

from ..conftest import BUILTIN_VALUE_TYPES


LONG_BITS = struct.calcsize("l") * 8
LONG_MAX = 2 ** (LONG_BITS - 1) - 1
LONG_MIN = -LONG_MAX - 1
ULONG_MAX = 2**LONG_BITS - 1


@pytest.fixture
def GoiBench() -> Any:
    from ginext import private

    try:
        private.require_namespace("GoiBench", "1.0")
    except ImportError:
        pytest.skip("GoiBench typelib not available in this test environment")
    from ginext import GoiBench

    return GoiBench


GTYPE_ROUND_TRIPS = [
    pytest.param("BOOLEAN", False, True, id="gboolean"),
    pytest.param("CHAR", -7, 12, id="gchar"),
    pytest.param("UCHAR", 7, 255, id="guchar"),
    pytest.param("INT", -42, 42, id="gint"),
    pytest.param("UINT", 42, 123, id="guint"),
    pytest.param("LONG", -100_000, 100_000, id="glong"),
    pytest.param("ULONG", 100_000, 200_000, id="gulong"),
    pytest.param("INT64", -(2**40), 2**40, id="gint64"),
    pytest.param("UINT64", 2**40, 2**40 + 1, id="guint64"),
    pytest.param("FLOAT", 1.25, -2.5, id="gfloat"),
    pytest.param("DOUBLE", 1.25, -2.5, id="gdouble"),
    pytest.param("STRING", "default", "updated", id="gchararray"),
]


GTYPE_INTEGER_BOUNDARIES = [
    pytest.param("CHAR", -128, 127, id="gchar"),
    pytest.param("UCHAR", 0, 255, id="guchar"),
    pytest.param("INT", -(2**31), 2**31 - 1, id="gint"),
    pytest.param("UINT", 0, 2**32 - 1, id="guint"),
    pytest.param("LONG", LONG_MIN, LONG_MAX, id="glong"),
    pytest.param("ULONG", 0, ULONG_MAX, id="gulong"),
    pytest.param("INT64", -(2**63), 2**63 - 1, id="gint64"),
    pytest.param("UINT64", 0, 2**64 - 1, id="guint64"),
]


GTYPE_OVERFLOWS = [
    pytest.param("CHAR", 128, id="gchar-high"),
    pytest.param("CHAR", -129, id="gchar-low"),
    pytest.param("UCHAR", 256, id="guchar-high"),
    pytest.param("UCHAR", -1, id="guchar-low"),
    pytest.param("INT", 2**31, id="gint-high"),
    pytest.param("INT", -(2**31) - 1, id="gint-low"),
    pytest.param("UINT", 2**32, id="guint-high"),
    pytest.param("UINT", -1, id="guint-low"),
    pytest.param("LONG", 2 ** (LONG_BITS - 1), id="glong-high"),
    pytest.param("ULONG", -1, id="gulong-low"),
    pytest.param("INT64", 2**63, id="gint64-high"),
    pytest.param("UINT64", -1, id="guint64-low"),
]


GTYPE_WRONG_TYPE_WRITES = [
    pytest.param("CHAR", "x", id="gchar"),
    pytest.param("UCHAR", "x", id="guchar"),
    pytest.param("INT", "x", id="gint"),
    pytest.param("UINT", "x", id="guint"),
    pytest.param("LONG", None, id="glong"),
    pytest.param("ULONG", object(), id="gulong"),
    pytest.param("INT64", "x", id="gint64"),
    pytest.param("UINT64", "x", id="guint64"),
    pytest.param("FLOAT", "x", id="gfloat"),
    pytest.param("DOUBLE", None, id="gdouble"),
]


@pytest.mark.parametrize("case", BUILTIN_VALUE_TYPES)
def test_instance_read_without_default_returns_type_zero(
    make_property_class: Any, case: Any
) -> None:
    cls = make_property_class(case.annotation)
    actual = cls().x
    if case.zero is None:
        assert actual is None
    elif isinstance(case.zero, bool):
        assert actual is case.zero
    else:
        assert actual == case.zero


def test_instance_read_returns_declared_default(make_property_class: Any) -> None:
    cls = make_property_class(str, name="title", default="hello")
    assert cls().title == "hello"


@pytest.mark.parametrize(
    "annotation, value",
    [
        pytest.param(bool, True, id="bool-true"),
        pytest.param(bool, False, id="bool-false"),
        pytest.param(int, 42, id="int-positive"),
        pytest.param(int, -42, id="int-negative"),
        pytest.param(int, 0, id="int-zero"),
        pytest.param(float, 3.14, id="float"),
        pytest.param(float, -0.0, id="float-neg-zero"),
        pytest.param(str, "hello", id="str-ascii"),
        pytest.param(str, "", id="str-empty"),
        pytest.param(str, "中文", id="str-utf8"),
    ],
)
def test_write_then_read_round_trip(
    make_property_class: Any, annotation: Any, value: Any
) -> None:
    cls = make_property_class(annotation)
    obj = cls()
    obj.x = value
    assert obj.x == value


def test_c_g_object_get_loop_reads_declared_python_property(
    GoiBench: Any, make_property_class: Any
) -> None:
    cls = make_property_class(int, default=7)
    obj = cls()

    assert GoiBench.g_object_get_int_loop(obj, "x", 5) == 35

    obj.x = 11
    assert GoiBench.g_object_get_int_loop(obj, "x", 5) == 55


def test_c_g_object_get_loop_reads_inherited_python_property(
    GoiBench: Any, make_property_class: Any, make_subclass: Any
) -> None:
    base = make_property_class(int, name="value", default=3, prefix="BaseProp")
    child = make_subclass(base=base, prefix="ChildProp")
    obj = child()

    assert GoiBench.g_object_get_int_loop(obj, "value", 4) == 12

    obj.value = 9
    assert GoiBench.g_object_get_int_loop(obj, "value", 4) == 36


@pytest.mark.parametrize("constant, default, value", GTYPE_ROUND_TRIPS)
def test_gtype_constant_write_then_read_round_trip(
    GType: Any, make_property_class: Any, constant: Any, default: Any, value: Any
) -> None:
    cls = make_property_class(getattr(GType, constant), default=default)
    obj = cls()
    assert obj.x == default

    obj.x = value
    assert obj.x == value


@pytest.mark.parametrize("constant, lower, upper", GTYPE_INTEGER_BOUNDARIES)
def test_integer_gtype_write_boundaries(
    GType: Any, make_property_class: Any, constant: Any, lower: Any, upper: Any
) -> None:
    cls = make_property_class(getattr(GType, constant))
    obj = cls()

    obj.x = lower
    assert obj.x == lower

    obj.x = upper
    assert obj.x == upper


def test_string_property_accepts_none_and_bytes(make_property_class: Any) -> None:
    cls = make_property_class(str, default="hello")
    obj = cls()

    obj.x = None
    assert obj.x is None

    obj.x = b"from bytes"
    assert obj.x == "from bytes"


@pytest.mark.parametrize("constant, value", GTYPE_OVERFLOWS)
def test_numeric_gtype_write_out_of_range_raises(
    GType: Any, make_property_class: Any, constant: Any, value: Any
) -> None:
    cls = make_property_class(getattr(GType, constant))
    obj = cls()

    with pytest.raises(OverflowError):
        obj.x = value


@pytest.mark.parametrize("constant, value", GTYPE_WRONG_TYPE_WRITES)
def test_numeric_gtype_wrong_type_write_raises_and_keeps_previous_value(
    GType: Any,
    make_property_class: Any,
    constant: Any,
    value: Any,
) -> None:
    cls = make_property_class(getattr(GType, constant), default=1)
    obj = cls()

    with pytest.raises(TypeError):
        obj.x = value

    assert obj.x == 1


def test_float_gtype_write_wrong_type_raises(
    GType: Any, make_property_class: Any
) -> None:
    cls = make_property_class(GType.FLOAT)
    obj = cls()

    with pytest.raises(TypeError):
        obj.x = object()


def test_gtype_value_reads_as_integer(GType: Any, make_property_class: Any) -> None:
    cls = make_property_class(GType.GTYPE, default=GType.INT.gimeta.gtype)

    assert isinstance(cls().x, int)


def test_gtype_value_write_round_trips(GType: Any, make_property_class: Any) -> None:
    cls = make_property_class(GType.GTYPE)
    obj = cls()

    obj.x = GType.INT.gimeta.gtype
    assert obj.x == GType.INT.gimeta.gtype


def test_string_value_with_embedded_nul_is_truncated(make_property_class: Any) -> None:
    cls = make_property_class(str)
    obj = cls()
    obj.x = "x\x00y"
    assert obj.x == "x"


def test_two_instances_have_independent_storage(make_property_class: Any) -> None:
    cls = make_property_class(int, default=0)
    a, b = cls(), cls()
    a.x = 1
    b.x = 2
    assert a.x == 1
    assert b.x == 2


def test_multiple_properties_dont_alias(make_subclass: Any, Property: Any) -> None:
    cls = make_subclass(
        {
            "a": (int, Property(default=0)),
            "b": (int, Property(default=0)),
            "c": (int, Property(default=0)),
        },
        prefix="Slots",
    )
    obj = cls()
    obj.a, obj.b, obj.c = 1, 2, 3
    assert (obj.a, obj.b, obj.c) == (1, 2, 3)


def test_writing_wrong_type_int_to_str_raises(make_property_class: Any) -> None:
    cls = make_property_class(str, name="title")
    obj = cls()
    with pytest.raises((TypeError, ValueError)):
        obj.title = 12345


def test_writing_to_readonly_raises(make_property_class: Any) -> None:
    cls = make_property_class(int, name="ro", default=42, readonly=True)
    obj = cls()
    with pytest.raises(Exception):
        obj.ro = 99
    assert obj.ro == 42


def test_construct_only_assignment_after_init_raises(make_property_class: Any) -> None:
    cls = make_property_class(int, name="co", default=1, construct_only=True)
    obj = cls()
    with pytest.raises(Exception):
        obj.co = 2


def test_class_attribute_access_returns_descriptor_or_pspec(
    make_property_class: Any,
) -> None:
    cls = make_property_class(int, default=0)
    assert not isinstance(cls.x, int)


def test_hasattr_on_class_and_instance_sees_property(make_property_class: Any) -> None:
    cls = make_property_class(int, default=0)
    assert hasattr(cls, "x")
    assert hasattr(cls(), "x")


def test_property_value_is_not_stored_in_instance_dict(
    make_property_class: Any,
) -> None:
    cls = make_property_class(int, default=0)
    obj = cls()
    obj.x = 7

    assert obj.x == 7
    assert "x" not in obj.__dict__
