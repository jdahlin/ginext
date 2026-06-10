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

"""Port of goi/tests/test_invoke_argchecks.py."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

import pytest

from ginext.tests.gi_test_utils import load_test_namespace


INT8_MAX = 0x7F
UINT8_MAX = 0xFF
INT16_MAX = 0x7FFF
UINT16_MAX = 0xFFFF
INT32_MAX = 0x7FFFFFFF
UINT32_MAX = 0xFFFFFFFF
INT64_MAX = 0x7FFFFFFFFFFFFFFF
UINT64_MAX = 0xFFFFFFFFFFFFFFFF
SHORT_MAX = 0x7FFF
USHORT_MAX = 0xFFFF
INT_MAX_C = 0x7FFFFFFF
UINT_MAX_C = 0xFFFFFFFF
# C long/unsigned long are 32-bit on LLP64 (Windows), 64-bit on LP64.
_LLP64 = sys.platform == "win32"
LONG_MAX = INT32_MAX if _LLP64 else INT64_MAX
ULONG_MAX = UINT32_MAX if _LLP64 else UINT64_MAX
SSIZE_MAX = 0x7FFFFFFFFFFFFFFF
SIZE_MAX = 0xFFFFFFFFFFFFFFFF
FLOAT_MAX = (2.0 - 2**-23) * (2**127)
DOUBLE_MAX = sys.float_info.max
TIME_T_SENTINEL = 1234567890
UTF8_SENTINEL = "const \u2665 utf8"

INT_NOT_STR = "'str' object cannot be interpreted as an integer"
UL_NOT_STR = "argument 1 must be int, not str"
FLOAT_NOT_STR = "must be real number, not str"
STR_NOT_INT = "argument 1 must be str, bytes, or bytearray, not int"


@pytest.fixture(scope="module")
def gim() -> Any:
    return load_test_namespace("GIMarshallingTests")


@dataclass(frozen=True)
class Case:
    id: str
    func_name: str
    good: object
    bad: object
    expected: str


WRONG_TYPE = [
    Case("int8", "int8_in_max", INT8_MAX, "xy", INT_NOT_STR),
    Case("uint8", "uint8_in", UINT8_MAX, "xy", INT_NOT_STR),
    Case("int16", "int16_in_max", INT16_MAX, "x", INT_NOT_STR),
    Case("uint16", "uint16_in", UINT16_MAX, "x", INT_NOT_STR),
    Case("int32", "int32_in_max", INT32_MAX, "x", INT_NOT_STR),
    Case("uint32", "uint32_in", UINT32_MAX, "x", INT_NOT_STR),
    Case("int64", "int64_in_max", INT64_MAX, "x", INT_NOT_STR),
    Case("short", "short_in_max", SHORT_MAX, "x", INT_NOT_STR),
    Case("ushort", "ushort_in", USHORT_MAX, "x", INT_NOT_STR),
    Case("int", "int_in_max", INT_MAX_C, "x", INT_NOT_STR),
    Case("uint", "uint_in", UINT_MAX_C, "x", INT_NOT_STR),
    Case("long", "long_in_max", LONG_MAX, "x", INT_NOT_STR),
    Case("ssize", "ssize_in_max", SSIZE_MAX, "x", INT_NOT_STR),
    Case("time_t", "time_t_in", TIME_T_SENTINEL, "x", INT_NOT_STR),
    Case("uint64", "uint64_in", UINT64_MAX, "x", UL_NOT_STR),
    # On LLP64 (Windows) unsigned long is 32-bit and routes through the
    # uint32 marshaller (INT_NOT_STR); on LP64 it is 64-bit (UL_NOT_STR).
    Case(
        "ulong",
        "ulong_in",
        ULONG_MAX,
        "x",
        INT_NOT_STR if _LLP64 else UL_NOT_STR,
    ),
    Case("size", "size_in", SIZE_MAX, "x", UL_NOT_STR),
    Case("float", "float_in", FLOAT_MAX, "x", FLOAT_NOT_STR),
    Case("double", "double_in", DOUBLE_MAX, "x", FLOAT_NOT_STR),
    Case("utf8", "utf8_none_in", UTF8_SENTINEL, 5, STR_NOT_INT),
]


@pytest.fixture(params=WRONG_TYPE, ids=lambda case: case.id)
def case(request: pytest.FixtureRequest) -> Case:
    return request.param  # type: ignore[no-any-return]


def test_accepts_good(gim: Any, case: Case) -> None:
    getattr(gim, case.func_name)(case.good)


@pytest.mark.parametrize(
    ("func_name", "good_int"),
    [("int8_in_max", INT8_MAX), ("uint8_in", UINT8_MAX)],
    ids=["int8", "uint8"],
)
@pytest.mark.parametrize(
    "bad_value",
    ["", "ab", b"", b"ab", [120]],
    ids=["empty-str", "len2-str", "empty-bytes", "len2-bytes", "list"],
)
def test_int8_uint8_reject_non_char(
    gim: Any, func_name: str, good_int: Any, bad_value: Any
) -> None:
    with pytest.raises(TypeError):
        getattr(gim, func_name)(bad_value)


def test_int8_accepts_length1_bytes_and_str(gim: Any) -> None:
    gim.int8_in_max(b"\x7f")
    gim.int8_in_max("\x7f")
    gim.uint8_in(b"\xff")
    gim.uint8_in("\xff")


def test_wrong_type_positional(gim: Any, case: Case) -> None:
    with pytest.raises(TypeError) as exc_info:
        getattr(gim, case.func_name)(case.bad)

    assert str(exc_info.value) == case.expected


F = "int_three_in_three_out"


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        ((), {}, f"{F}() takes exactly 3 arguments (0 given)"),
        ((1,), {}, f"{F}() takes exactly 3 arguments (1 given)"),
        ((1, 2), {}, f"{F}() takes exactly 3 arguments (2 given)"),
        ((1, 2, 3, 4), {}, f"{F}() takes exactly 3 arguments (4 given)"),
        ((), {"c": 4}, f"{F}() takes exactly 3 non-keyword arguments (0 given)"),
        (
            (1, 2, 3, 4),
            {"c": 6},
            f"{F}() takes exactly 3 non-keyword arguments (4 given)",
        ),
        (
            (1, 2, 3),
            {"a": 4, "b": 5},
            f"{F}() got multiple values for keyword argument 'a'",
        ),
        ((), {"d": 4}, f"{F}() got an unexpected keyword argument 'd'"),
        ((), {"e": 2}, f"{F}() got an unexpected keyword argument 'e'"),
    ],
    ids=[
        "too-few-0",
        "too-few-1",
        "too-few-2",
        "too-many-4",
        "mixed-too-few",
        "mixed-too-many",
        "multi-values",
        "unknown-kw-d",
        "unknown-kw-e",
    ],
)
def test_arity_and_kwargs(gim: Any, args: Any, kwargs: Any, expected: str) -> None:
    with pytest.raises(TypeError) as exc_info:
        gim.int_three_in_three_out(*args, **kwargs)

    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    ("args", "kwargs"),
    [
        ((), {"a": 1, "b": 2, "c": 3}),
        ((1,), {"b": 2, "c": 3}),
        ((1, 2), {"c": 3}),
        ((1,), {"c": 3, "b": 2}),
        ((), {"c": 3, "a": 1, "b": 2}),
    ],
    ids=["all-kw", "1-pos-2-kw", "2-pos-1-kw", "out-of-order-kw", "scrambled-kw"],
)
def test_kwargs_dispatch(gim: Any, args: Any, kwargs: Any) -> None:
    assert gim.int_three_in_three_out(*args, **kwargs) == (1, 2, 3)


def test_kwargs_static_constructor(gim: Any) -> None:
    obj1 = gim.Object.new(42)
    obj2 = gim.Object.new(int_=42)

    assert obj1.get_property_by_name("int") == obj2.get_property_by_name("int") == 42


def test_int_args_accept_floats_truncated(gim: Any) -> None:
    assert gim.int_three_in_three_out(1.7, 2.3, 3.0) == (1, 2, 3)


def test_kwargs_unknown_after_valid_positional(gim: Any) -> None:
    with pytest.raises(TypeError) as exc_info:
        gim.int_three_in_three_out(1, 2, 3, nope=4)

    assert "got an unexpected keyword argument 'nope'" in str(exc_info.value)


def test_object_arg_type_error_uses_expected_type_and_instance_repr(gim: Any) -> None:
    from ginext import GObject

    wrong = GObject.Object()

    with pytest.raises(
        TypeError,
        match=(
            r"self: expected GIMarshallingTests\.Object, but got "
            r"<(?:gi\.overrides\.)?GObject\.Object object at 0x"
        ),
    ):
        gim.Object.none_in(wrong)
