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

import enum
import math
import pathlib
import sys
from ginext.namespace import Namespace

import pytest

from .support import open_namespace_for_test

# C `long`/`unsigned long` are pointer-width on LP64 (Linux/macOS, 64-bit) but
# only 32-bit on LLP64 (Windows). The GIMarshallingTests long_* helpers assert
# against G_MAXLONG/G_MINLONG, which therefore differ per platform — pick the
# expected extremes per platform so the marshalling is still exercised
# everywhere rather than skipped.
_LLP64 = sys.platform == "win32"
_LONG_MAX = (2**31 - 1) if _LLP64 else (2**63 - 1)
_LONG_MIN = (-(2**31)) if _LLP64 else (-(2**63))
_ULONG_MAX = (2**32 - 1) if _LLP64 else (2**64 - 1)


@pytest.fixture
def t(call_mode: str) -> Namespace:
    return open_namespace_for_test(call_mode, "GIMarshallingTests", "1.0")


def test_boolean_return_true(t: Namespace) -> None:
    assert t.boolean_return_true() is True


def test_boolean_return_false(t: Namespace) -> None:
    assert t.boolean_return_false() is False


def test_int32_return_max(t: Namespace) -> None:
    assert t.int32_return_max() == 2_147_483_647


def test_int32_return_min(t: Namespace) -> None:
    assert t.int32_return_min() == -2_147_483_648


def test_uint32_return(t: Namespace) -> None:
    assert t.uint32_return() == 4_294_967_295


def test_int64_return_max(t: Namespace) -> None:
    assert t.int64_return_max() == 9_223_372_036_854_775_807


def test_int64_return_min(t: Namespace) -> None:
    assert t.int64_return_min() == -9_223_372_036_854_775_808


def test_int8_return_max(t: Namespace) -> None:
    assert t.int8_return_max() == 127


def test_int8_return_min(t: Namespace) -> None:
    assert t.int8_return_min() == -128


def test_uint8_return(t: Namespace) -> None:
    assert t.uint8_return() == 255


def test_int16_return_max(t: Namespace) -> None:
    assert t.int16_return_max() == 32_767


def test_int16_return_min(t: Namespace) -> None:
    assert t.int16_return_min() == -32_768


def test_uint16_return(t: Namespace) -> None:
    assert t.uint16_return() == 65_535


def test_array_bool_in(t: Namespace) -> None:
    assert t.array_bool_in([True, False, True, True]) is None


def test_array_bool_out(t: Namespace) -> None:
    t.array_bool_out()


def test_array_enum_in(t: Namespace) -> None:
    assert t.array_enum_in([t.Enum.VALUE1, t.Enum.VALUE2, t.Enum.VALUE3]) is None


def test_array_fixed_caller_allocated_out(t: Namespace) -> None:
    t.array_fixed_caller_allocated_out()


def test_array_fixed_caller_allocated_struct_out(t: Namespace) -> None:
    t.array_fixed_caller_allocated_struct_out()


def test_array_fixed_inout(t: Namespace) -> None:
    assert t.array_fixed_inout([-1, 0, 1, 2]) == [2, 1, 0, -1]


def test_array_fixed_int_in(t: Namespace) -> None:
    assert t.array_fixed_int_in([-1, 0, 1, 2]) is None


def test_array_fixed_int_return(t: Namespace) -> None:
    assert list(t.array_fixed_int_return()) == [-1, 0, 1, 2]


def test_array_fixed_out(t: Namespace) -> None:
    t.array_fixed_out()


def test_array_fixed_out_struct(t: Namespace) -> None:
    t.array_fixed_out_struct()


def test_array_fixed_out_struct_uninitialized(t: Namespace) -> None:
    t.array_fixed_out_struct_uninitialized()


def test_array_fixed_out_unaligned(t: Namespace) -> None:
    t.array_fixed_out_unaligned()


def test_array_fixed_out_uninitialized(t: Namespace) -> None:
    t.array_fixed_out_uninitialized()


def test_array_fixed_return_unaligned(t: Namespace) -> None:
    t.array_fixed_return_unaligned()


def test_array_fixed_short_in(t: Namespace) -> None:
    assert t.array_fixed_short_in([-1, 0, 1, 2]) is None


def test_array_fixed_short_return(t: Namespace) -> None:
    assert list(t.array_fixed_short_return()) == [-1, 0, 1, 2]


def test_array_flags_in(t: Namespace) -> None:
    assert t.array_flags_in([t.Flags.VALUE1, t.Flags.VALUE2, t.Flags.VALUE3]) is None


def test_array_gvariant_container_in(t: Namespace) -> None:
    variants = ["27", "'Hello'"]
    result = t.array_gvariant_container_in(variants)
    assert result is not None


def test_array_gvariant_full_in(t: Namespace) -> None:
    variants = ["27", "'Hello'"]
    result = t.array_gvariant_full_in(variants)
    assert result is not None


def test_array_gvariant_none_in(t: Namespace) -> None:
    variants = ["27", "'Hello'"]
    result = t.array_gvariant_none_in(variants)
    assert result is not None


def test_array_in(t: Namespace) -> None:
    assert t.array_in([-1, 0, 1, 2]) is None


def test_array_in_guint64_len(t: Namespace) -> None:
    assert t.array_in_guint64_len([-1, 0, 1, 2]) is None


def test_array_in_guint8_len(t: Namespace) -> None:
    assert t.array_in_guint8_len([-1, 0, 1, 2]) is None


def test_array_in_len_before(t: Namespace) -> None:
    assert t.array_in_len_before([-1, 0, 1, 2]) is None


def test_array_in_len_zero_terminated(t: Namespace) -> None:
    assert t.array_in_len_zero_terminated([-1, 0, 1, 2]) is None


def test_array_in_nonzero_nonlen(t: Namespace) -> None:
    assert t.array_in_nonzero_nonlen(1, b"abcd") is None


def test_array_in_utf8_two_in(t: Namespace) -> None:
    assert t.array_in_utf8_two_in([-1, 0, 1, 2], "1", "2") is None


def test_array_in_utf8_two_in_out_of_order(t: Namespace) -> None:
    assert t.array_in_utf8_two_in_out_of_order("1", [-1, 0, 1, 2], "2") is None


def test_array_inout(t: Namespace) -> None:
    assert t.array_inout([-1, 0, 1, 2]) == [-2, -1, 0, 1, 2]


def test_array_inout_etc(t: Namespace) -> None:
    assert t.array_inout_etc(42, [-1, 0, 1, 2], 24) == ([42, -1, 0, 1, 24], 66)


def test_array_int64_in(t: Namespace) -> None:
    assert t.array_int64_in([-1, 0, 1, 2]) is None


def test_array_out(t: Namespace) -> None:
    t.array_out()


def test_array_out_etc(t: Namespace) -> None:
    assert t.array_out_etc(42, 24) == ([42, 0, 1, 24], 66)


def test_array_out_unaligned(t: Namespace) -> None:
    t.array_out_unaligned()


def test_array_out_uninitialized(t: Namespace) -> None:
    t.array_out_uninitialized()


def test_array_return(t: Namespace) -> None:
    assert list(t.array_return()) == [-1, 0, 1, 2]


def test_array_return_etc(t: Namespace) -> None:
    assert t.array_return_etc(42, 24) == ([42, 0, 1, 24], 66)


def test_array_return_unaligned(t: Namespace) -> None:
    t.array_return_unaligned()


def test_array_simple_struct_in(t: Namespace) -> None:
    s1 = t.SimpleStruct()
    s1.long_ = 1
    s2 = t.SimpleStruct()
    s2.long_ = 2
    s3 = t.SimpleStruct()
    s3.long_ = 3
    assert t.array_simple_struct_in([s1, s2, s3]) is None


def test_array_string_in(t: Namespace) -> None:
    assert t.array_string_in(["foo", "bar"]) is None


def _make_boxed_structs(t: Namespace) -> list[object]:
    s1 = t.BoxedStruct()
    s1.long_ = 1
    s2 = t.BoxedStruct()
    s2.long_ = 2
    s3 = t.BoxedStruct()
    s3.long_ = 3
    return [s1, s2, s3]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello", "hello"),
        ("", ""),
        ("café — ☕", "café — ☕"),
        (None, None),
    ],
    ids=["plain", "empty", "non-ascii", "none"],
)
def test_boxed_struct_utf8_field_round_trip(
    t: Namespace, value: str | None, expected: str | None
) -> None:
    """Writable `string_` field on BoxedStruct is GIR-typed as utf8
    (gchar*). ginext's primitive marshalling owns the slot: g_free's
    the old value, g_strdup's the new (or NULL for Python None).
    Pin showtime's `new_window.long_name = "new-window"` shape."""
    s = t.BoxedStruct()
    assert s.string_ is None
    s.string_ = value
    assert s.string_ == expected


def test_boxed_struct_utf8_field_overwrite(t: Namespace) -> None:
    """Consecutive writes must not leak the previous g_strdup; the
    accessor frees before strdup'ing. Functionally just observable as
    "no crash, last write wins"."""
    s = t.BoxedStruct()
    for v in ("one", "two", "three", "four"):
        s.string_ = v
    assert s.string_ == "four"


def test_boxed_struct_utf8_field_rejects_non_str(t: Namespace) -> None:
    s = t.BoxedStruct()
    with pytest.raises(TypeError, match="expected str"):
        s.string_ = 42


def test_array_struct_full_in(t: Namespace) -> None:
    assert t.array_struct_full_in(_make_boxed_structs(t)) is None


def test_array_struct_in(t: Namespace) -> None:
    assert t.array_struct_in(_make_boxed_structs(t)) is None


def test_array_struct_take_in(t: Namespace) -> None:
    assert t.array_struct_take_in(_make_boxed_structs(t)) is None


def test_array_struct_take_in_keeps_wrappers_alive(t: Namespace) -> None:
    structs = _make_boxed_structs(t)
    assert t.array_struct_take_in(structs) is None
    assert [getattr(s, "long_") for s in structs] == [1, 2, 3]


def test_array_struct_value_in(t: Namespace) -> None:
    assert t.array_struct_value_in(_make_boxed_structs(t)) is None


def test_array_uint64_in(t: Namespace) -> None:
    # The C function uses g_assert_cmpint which compares as signed,
    # so -1 is expected even though the parameter type is guint64.
    assert t.array_uint64_in([2**64 - 1, 0, 1, 2]) is None


def test_array_uint8_in(t: Namespace) -> None:
    assert t.array_uint8_in([97, 98, 99, 100]) is None


def test_array_uint8_in_bytes(t: Namespace) -> None:
    assert t.array_uint8_in(b"abcd") is None


def test_array_uint8_in_bytearray(t: Namespace) -> None:
    assert t.array_uint8_in(bytearray(b"abcd")) is None


def test_array_uint8_in_memoryview(t: Namespace) -> None:
    # buffer-protocol object: exercises the bulk-memcpy fast path in
    # marshal/c-array.c (pygi_py_to_c_array_invoke), not the element loop.
    assert t.array_uint8_in(memoryview(b"abcd")) is None


def test_array_uint8_in_array_array(t: Namespace) -> None:
    import array

    assert t.array_uint8_in(array.array("B", [97, 98, 99, 100])) is None


def test_array_uint8_in_numpy(t: Namespace) -> None:
    np = pytest.importorskip("numpy")

    assert t.array_uint8_in(np.frombuffer(b"abcd", dtype=np.uint8)) is None


def test_array_fixed_int_in_array_array(t: Namespace) -> None:
    # Wider POD element (gint32): the fast path only fires when the buffer's
    # itemsize matches elem_size, so a typed "i" array must memcpy correctly.
    import array

    assert t.array_fixed_int_in(array.array("i", [-1, 0, 1, 2])) is None


def test_array_unichar_in(t: Namespace) -> None:
    assert t.array_unichar_in(list("const ♥ utf8")) is None


def test_array_unichar_out(t: Namespace) -> None:
    t.array_unichar_out()


def test_array_zero_terminated_in(t: Namespace) -> None:
    assert t.array_zero_terminated_in(["0", "1", "2"]) is None


def test_array_zero_terminated_inout(t: Namespace) -> None:
    assert t.array_zero_terminated_inout(["0", "1", "2"]) == ["-1", "0", "1", "2"]


def test_array_zero_terminated_out(t: Namespace) -> None:
    t.array_zero_terminated_out()


def test_array_zero_terminated_out_unaligned(t: Namespace) -> None:
    t.array_zero_terminated_out_unaligned()


def test_array_zero_terminated_out_uninitialized(t: Namespace) -> None:
    t.array_zero_terminated_out_uninitialized()


def test_array_zero_terminated_return(t: Namespace) -> None:
    assert list(t.array_zero_terminated_return()) == ["0", "1", "2"]


def test_array_zero_terminated_return_null(t: Namespace) -> None:
    assert t.array_zero_terminated_return_null() == []


def test_array_zero_terminated_return_sequential_struct(t: Namespace) -> None:
    t.array_zero_terminated_return_sequential_struct()


def test_array_zero_terminated_return_struct(t: Namespace) -> None:
    t.array_zero_terminated_return_struct()


def test_array_zero_terminated_return_unaligned(t: Namespace) -> None:
    t.array_zero_terminated_return_unaligned()


def test_array_zero_terminated_return_unichar(t: Namespace) -> None:
    assert list(t.array_zero_terminated_return_unichar()) == list("const ♥ utf8")


def test_boolean_in_false(t: Namespace) -> None:
    t.boolean_in_false(False)


def test_boolean_in_true(t: Namespace) -> None:
    t.boolean_in_true(True)


def test_boolean_inout_false_true(t: Namespace) -> None:
    assert t.boolean_inout_false_true(False) is True


def test_boolean_inout_true_false(t: Namespace) -> None:
    assert t.boolean_inout_true_false(True) is False


def test_boolean_out_false(t: Namespace) -> None:
    assert t.boolean_out_false() is False


def test_boolean_out_true(t: Namespace) -> None:
    assert t.boolean_out_true() is True


def test_boolean_out_uninitialized(t: Namespace) -> None:
    assert t.boolean_out_uninitialized()[0] is False


def test_boxed_struct_inout(t: Namespace) -> None:
    s = t.BoxedStruct()
    s.long_ = 42
    result = t.boxed_struct_inout(s)
    assert result.long_ == 0


def test_boxed_struct_out(t: Namespace) -> None:
    t.boxed_struct_out()


def test_boxed_struct_out_uninitialized(t: Namespace) -> None:
    t.boxed_struct_out_uninitialized()


def test_boxed_struct_returnv(t: Namespace) -> None:
    s = t.boxed_struct_returnv()
    assert s.long_ == 42
    assert s.string_ == "hello"
    assert s.g_strv == ["0", "1", "2"]


def test_bytearray_full_inout(t: Namespace) -> None:
    assert t.bytearray_full_inout(b"\x00\x31\xff\x33") == b"hel\x00\xff"


def test_bytearray_full_out(t: Namespace) -> None:
    t.bytearray_full_out()


def test_bytearray_full_return(t: Namespace) -> None:
    assert t.bytearray_full_return() == b"\x00\x31\xff\x33"


def test_bytearray_none_in(t: Namespace) -> None:
    assert t.bytearray_none_in(b"\x00\x31\xff\x33") is None


def test_callback_multiple_out_parameters(t: Namespace) -> None:
    res = t.callback_multiple_out_parameters(lambda: (5.5, 42.0))
    assert abs(res[0] - 5.5) < 1e-6
    assert abs(res[1] - 42.0) < 1e-6


def test_callback_one_out_parameter(t: Namespace) -> None:
    assert abs(t.callback_one_out_parameter(lambda: 5.5) - 5.5) < 1e-6


@pytest.mark.skip(reason="mutates static GIMarshallingTests callback box state")
def test_callback_owned_boxed(t: Namespace) -> None:
    t.callback_owned_boxed(lambda box, data: None, None)


def test_signal_callback_marshals_boxed_struct_args(t: Namespace) -> None:
    obj = t.SignalsObject()
    seen = {}

    def on_boxed(_obj: object, boxed: object) -> None:
        seen["type"] = type(boxed).__name__ if boxed is not None else None
        seen["long_"] = getattr(boxed, "long_", None)
        seen["string_"] = getattr(boxed, "string_", None)
        seen["g_strv"] = getattr(boxed, "g_strv", None)

    obj.some_boxed_struct.connect(on_boxed)
    obj.emit_boxed_struct()

    assert seen == {
        "type": "BoxedStruct",
        "long_": 99,
        "string_": "a string",
        "g_strv": ["foo", "bar", "baz"],
    }


def test_callback_return_value_and_multiple_out_parameters(t: Namespace) -> None:
    assert t.callback_return_value_and_multiple_out_parameters(
        lambda: (5, 42, -1000)
    ) == (5, 42, -1000)


def test_callback_return_value_and_one_out_parameter(t: Namespace) -> None:
    assert t.callback_return_value_and_one_out_parameter(lambda: (5, 42)) == (5, 42)


def test_callback_return_value_only(t: Namespace) -> None:
    assert t.callback_return_value_only(lambda: 42) == 42


def test_callback_user_data_after_callback(t: Namespace) -> None:
    t.callback_user_data_after_callback(1, 2, lambda a, b, ud: a + b, None)


def test_callback_user_data_before_callback(t: Namespace) -> None:
    t.callback_user_data_before_callback(1, 2, None, lambda *args: None)


def test_cleanup_unaligned_buffer(t: Namespace) -> None:
    t.cleanup_unaligned_buffer()


def test_dev_t_in(t: Namespace) -> None:
    t.dev_t_in(1234567890)


def test_dev_t_inout(t: Namespace) -> None:
    assert t.dev_t_inout(1234567890) == 0


def test_dev_t_out(t: Namespace) -> None:
    t.dev_t_out()


def test_dev_t_out_uninitialized(t: Namespace) -> None:
    t.dev_t_out_uninitialized()


def test_dev_t_return(t: Namespace) -> None:
    t.dev_t_return()


def test_double_in(t: Namespace) -> None:
    t.double_in(1.7976931348623157e308)


def test_double_inout(t: Namespace) -> None:
    assert t.double_inout(1.7976931348623157e308) == 2.2250738585072014e-308


def test_double_noncanonical_nan_out(t: Namespace) -> None:
    assert math.isnan(t.double_noncanonical_nan_out())


def test_double_out(t: Namespace) -> None:
    assert t.double_out() == 1.7976931348623157e308


def test_double_out_uninitialized(t: Namespace) -> None:
    assert t.double_out_uninitialized()[0] is False


def test_double_return(t: Namespace) -> None:
    assert t.double_return() == 1.7976931348623157e308


def test_enum_array_return_type(t: Namespace) -> None:
    assert t.enum_array_return_type() == [
        t.ExtraEnum.VALUE1,
        t.ExtraEnum.VALUE2,
        t.ExtraEnum.VALUE3,
    ]


def test_enum_in(t: Namespace) -> None:
    assert t.enum_in(t.Enum.VALUE3) is None


def test_enum_inout(t: Namespace) -> None:
    assert t.enum_inout(t.Enum.VALUE3) == t.Enum.VALUE1


def test_enum_out(t: Namespace) -> None:
    assert t.enum_out() == t.Enum.VALUE3


def test_enum_out_uninitialized(t: Namespace) -> None:
    assert t.enum_out_uninitialized()[0] is False


def test_enum_returnv(t: Namespace) -> None:
    assert t.enum_returnv() == t.Enum.VALUE3


def test_extra_flags_large_in(t: Namespace) -> None:
    assert t.extra_flags_large_in(t.ExtraFlags.VALUE2) is None


def test_enum_python_type(t: Namespace) -> None:
    assert issubclass(t.GEnum, enum.IntEnum)
    assert t.GEnum.__module__ == "GIMarshallingTests"
    assert t.GEnum.__qualname__ == "GEnum"
    assert t.GEnum.value3 is t.GEnum.VALUE3


def test_flags_python_type(t: Namespace) -> None:
    assert issubclass(t.Flags, enum.IntFlag)
    assert t.Flags.__module__ == "GIMarshallingTests"
    assert t.Flags.__qualname__ == "Flags"
    assert t.Flags.value3 is t.Flags.VALUE3


def test_extra_utf8_full_out_invalid(t: Namespace) -> None:
    t.extra_utf8_full_out_invalid()


def test_extra_utf8_full_return_invalid(t: Namespace) -> None:
    t.extra_utf8_full_return_invalid()


def test_filename_copy(t: Namespace) -> None:
    assert t.filename_copy("/foo/bar") == "/foo/bar"


def test_filename_exists(t: Namespace, tmp_path: pathlib.Path) -> None:
    existing = tmp_path / "present"
    existing.write_text("x")
    assert t.filename_exists(str(existing)) is True
    assert t.filename_exists(str(tmp_path / "absent")) is False


def test_filename_list_return(t: Namespace) -> None:
    assert t.filename_list_return() == []


def test_filename_to_glib_repr(t: Namespace) -> None:
    assert t.filename_to_glib_repr("/foo/bar") == b"/foo/bar"


_GSTRV_INPUT = [["0", "1", "2"], ["3", "4", "5"], ["6", "7", "8"]]
_GSTRV_OUTPUT = [
    ["-1", "0", "1", "2"],
    ["-1", "3", "4", "5"],
    ["-1", "6", "7", "8"],
]
_GSTRV_OUTPUT4 = _GSTRV_OUTPUT + [["-1", "9", "10", "11"]]


def test_fixed_array_of_gstrv_transfer_container_in(t: Namespace) -> None:
    assert t.fixed_array_of_gstrv_transfer_container_in(_GSTRV_INPUT) is None


def test_fixed_array_of_gstrv_transfer_container_inout(t: Namespace) -> None:
    assert (
        t.fixed_array_of_gstrv_transfer_container_inout(_GSTRV_INPUT) == _GSTRV_OUTPUT
    )


def test_fixed_array_of_gstrv_transfer_container_out(t: Namespace) -> None:
    t.fixed_array_of_gstrv_transfer_container_out()


def test_fixed_array_of_gstrv_transfer_container_return(t: Namespace) -> None:
    t.fixed_array_of_gstrv_transfer_container_return()


def test_fixed_array_of_gstrv_transfer_full_in(t: Namespace) -> None:
    assert t.fixed_array_of_gstrv_transfer_full_in(_GSTRV_INPUT) is None


def test_fixed_array_of_gstrv_transfer_full_inout(t: Namespace) -> None:
    assert t.fixed_array_of_gstrv_transfer_full_inout(_GSTRV_INPUT) == _GSTRV_OUTPUT


def test_fixed_array_of_gstrv_transfer_full_out(t: Namespace) -> None:
    t.fixed_array_of_gstrv_transfer_full_out()


def test_fixed_array_of_gstrv_transfer_full_return(t: Namespace) -> None:
    t.fixed_array_of_gstrv_transfer_full_return()


def test_fixed_array_of_gstrv_transfer_none_in(t: Namespace) -> None:
    assert t.fixed_array_of_gstrv_transfer_none_in(_GSTRV_INPUT) is None


def test_fixed_array_of_gstrv_transfer_none_inout(t: Namespace) -> None:
    assert t.fixed_array_of_gstrv_transfer_none_inout(_GSTRV_INPUT) == _GSTRV_OUTPUT


def test_fixed_array_of_gstrv_transfer_none_out(t: Namespace) -> None:
    t.fixed_array_of_gstrv_transfer_none_out()


def test_fixed_array_of_gstrv_transfer_none_return(t: Namespace) -> None:
    t.fixed_array_of_gstrv_transfer_none_return()


_UTF8_IN = ["\U0001f170", "β", "c", "d"]
_UTF8_OUT = ["a", "b", "¢", "\U0001f520"]


def test_fixed_array_utf8_container_in(t: Namespace) -> None:
    assert t.fixed_array_utf8_container_in(_UTF8_IN) is None


def test_fixed_array_utf8_container_inout(t: Namespace) -> None:
    assert t.fixed_array_utf8_container_inout(_UTF8_IN) == _UTF8_OUT


def test_fixed_array_utf8_container_out(t: Namespace) -> None:
    t.fixed_array_utf8_container_out()


def test_fixed_array_utf8_container_return(t: Namespace) -> None:
    t.fixed_array_utf8_container_return()


def test_fixed_array_utf8_full_in(t: Namespace) -> None:
    assert t.fixed_array_utf8_full_in(_UTF8_IN) is None


def test_fixed_array_utf8_full_inout(t: Namespace) -> None:
    assert t.fixed_array_utf8_full_inout(_UTF8_IN) == _UTF8_OUT


def test_fixed_array_utf8_full_out(t: Namespace) -> None:
    t.fixed_array_utf8_full_out()


def test_fixed_array_utf8_full_return(t: Namespace) -> None:
    t.fixed_array_utf8_full_return()


def test_fixed_array_utf8_none_in(t: Namespace) -> None:
    assert t.fixed_array_utf8_none_in(_UTF8_IN) is None


def test_fixed_array_utf8_none_inout(t: Namespace) -> None:
    assert t.fixed_array_utf8_none_inout(_UTF8_IN) == _UTF8_OUT


def test_fixed_array_utf8_none_out(t: Namespace) -> None:
    t.fixed_array_utf8_none_out()


def test_fixed_array_utf8_none_return(t: Namespace) -> None:
    t.fixed_array_utf8_none_return()


def test_flags_in(t: Namespace) -> None:
    assert t.flags_in(t.Flags.VALUE2) is None


def test_flags_in_zero(t: Namespace) -> None:
    assert t.flags_in_zero(0) is None


def test_flags_inout(t: Namespace) -> None:
    assert t.flags_inout(t.Flags.VALUE2) == t.Flags.VALUE1


def test_flags_out(t: Namespace) -> None:
    assert t.flags_out() == t.Flags.VALUE2


def test_flags_out_uninitialized(t: Namespace) -> None:
    assert t.flags_out_uninitialized()[0] is False


def test_flags_returnv(t: Namespace) -> None:
    assert t.flags_returnv() == t.Flags.VALUE2


def test_float_in(t: Namespace) -> None:
    t.float_in(3.4028234663852886e38)


def test_float_inout(t: Namespace) -> None:
    assert t.float_inout(3.4028234663852886e38) == 1.1754943508222875e-38


def test_float_noncanonical_nan_out(t: Namespace) -> None:
    assert math.isnan(t.float_noncanonical_nan_out())


def test_float_out(t: Namespace) -> None:
    assert t.float_out() == 3.4028234663852886e38


def test_float_out_uninitialized(t: Namespace) -> None:
    assert t.float_out_uninitialized()[0] is False


def test_float_return(t: Namespace) -> None:
    assert t.float_return() == 3.4028234663852886e38


def test_garray_bool_none_in(t: Namespace) -> None:
    assert t.garray_bool_none_in([True, False, True, True]) is None


def test_garray_boxed_struct_full_return(t: Namespace) -> None:
    t.garray_boxed_struct_full_return()


def test_garray_enum_none_return(t: Namespace) -> None:
    assert t.garray_enum_none_return() == [
        t.GEnum.VALUE1,
        t.GEnum.VALUE2,
        t.GEnum.VALUE3,
    ]


def test_garray_int_none_in(t: Namespace) -> None:
    assert t.garray_int_none_in([-1, 0, 1, 2]) is None


def test_garray_int_none_return(t: Namespace) -> None:
    assert t.garray_int_none_return() == [-1, 0, 1, 2]


def test_garray_uint64_none_in(t: Namespace) -> None:
    assert t.garray_uint64_none_in([0, 2**64 - 1]) is None


def test_garray_uint64_none_return(t: Namespace) -> None:
    assert t.garray_uint64_none_return() == [0, 2**64 - 1]


def test_garray_unichar_none_in(t: Namespace) -> None:
    assert t.garray_unichar_none_in(list("const ♥ utf8")) is None


def test_garray_utf8_container_in(t: Namespace) -> None:
    assert t.garray_utf8_container_in(["0", "1", "2"]) is None


def test_garray_utf8_container_inout(t: Namespace) -> None:
    assert t.garray_utf8_container_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_garray_utf8_container_out(t: Namespace) -> None:
    t.garray_utf8_container_out()


def test_garray_utf8_container_out_uninitialized(t: Namespace) -> None:
    t.garray_utf8_container_out_uninitialized()


def test_garray_utf8_container_return(t: Namespace) -> None:
    assert t.garray_utf8_container_return() == ["0", "1", "2"]


def test_garray_utf8_full_in(t: Namespace) -> None:
    assert t.garray_utf8_full_in(["0", "1", "2"]) is None


def test_garray_utf8_full_inout(t: Namespace) -> None:
    assert t.garray_utf8_full_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_garray_utf8_full_out(t: Namespace) -> None:
    t.garray_utf8_full_out()


def test_garray_utf8_full_out_caller_allocated(t: Namespace) -> None:
    t.garray_utf8_full_out_caller_allocated()


def test_garray_utf8_full_out_uninitialized(t: Namespace) -> None:
    t.garray_utf8_full_out_uninitialized()


def test_garray_utf8_full_return(t: Namespace) -> None:
    assert t.garray_utf8_full_return() == ["0", "1", "2"]


def test_garray_utf8_none_in(t: Namespace) -> None:
    assert t.garray_utf8_none_in(["0", "1", "2"]) is None


def test_garray_utf8_none_inout(t: Namespace) -> None:
    assert t.garray_utf8_none_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_garray_utf8_none_out(t: Namespace) -> None:
    t.garray_utf8_none_out()


def test_garray_utf8_none_out_uninitialized(t: Namespace) -> None:
    t.garray_utf8_none_out_uninitialized()


def test_garray_utf8_none_return(t: Namespace) -> None:
    assert t.garray_utf8_none_return() == ["0", "1", "2"]


def test_gbytes_full_return(t: Namespace) -> None:
    # PyGObject parity: returns a GLib.Bytes boxed wrapper, not raw
    # bytes. Callers explicitly extract via .get_data() (this matches
    # pygobject/tests/test_gi.py's test_gbytes).
    result = t.gbytes_full_return()
    assert result.get_data() == b"\x00\x31\xff\x33"


def test_gbytes_none_in(t: Namespace) -> None:
    assert t.gbytes_none_in(b"\x00\x31\xff\x33") is None


def test_gclosure_in(t: Namespace) -> None:
    assert t.gclosure_in(lambda: 42) is None


def test_gclosure_return(t: Namespace) -> None:
    closure = t.gclosure_return()
    assert closure is not None


def test_genum_in(t: Namespace) -> None:
    assert t.genum_in(t.GEnum.VALUE3) is None


def test_genum_inout(t: Namespace) -> None:
    assert t.genum_inout(t.GEnum.VALUE3) == t.GEnum.VALUE1


def test_genum_out(t: Namespace) -> None:
    assert t.genum_out() == t.GEnum.VALUE3


def test_genum_out_uninitialized(t: Namespace) -> None:
    assert t.genum_out_uninitialized()[0] is False


def test_genum_returnv(t: Namespace) -> None:
    assert t.genum_returnv() == t.GEnum.VALUE3


def test_gerror(t: Namespace) -> None:
    with pytest.raises(RuntimeError, match="gi-marshalling-tests-gerror-message"):
        t.gerror()


def test_gerror_array_in(t: Namespace) -> None:
    with pytest.raises(RuntimeError, match="gi-marshalling-tests-gerror-message"):
        t.gerror_array_in([1, 2, 3])


def test_gerror_out(t: Namespace) -> None:
    t.gerror_out()


def test_gerror_out_transfer_none(t: Namespace) -> None:
    t.gerror_out_transfer_none()


def test_gerror_out_transfer_none_uninitialized(t: Namespace) -> None:
    t.gerror_out_transfer_none_uninitialized()


def test_gerror_out_uninitialized(t: Namespace) -> None:
    t.gerror_out_uninitialized()


def test_gerror_return(t: Namespace) -> None:
    t.gerror_return()


def test_ghashtable_double_in(t: Namespace) -> None:
    assert t.ghashtable_double_in({"-1": -0.1, "0": 0.0, "1": 0.1, "2": 0.2}) is None


def test_ghashtable_enum_none_in(t: Namespace) -> None:
    assert (
        t.ghashtable_enum_none_in(
            {
                1: t.ExtraEnum.VALUE1,
                2: t.ExtraEnum.VALUE2,
                3: t.ExtraEnum.VALUE3,
            }
        )
        is None
    )


def test_ghashtable_enum_none_return(t: Namespace) -> None:
    assert t.ghashtable_enum_none_return() == {
        1: t.ExtraEnum.VALUE1,
        2: t.ExtraEnum.VALUE2,
        3: t.ExtraEnum.VALUE3,
    }


def test_ghashtable_float_in(t: Namespace) -> None:
    assert t.ghashtable_float_in({"-1": -0.1, "0": 0.0, "1": 0.1, "2": 0.2}) is None


def test_ghashtable_int64_in(t: Namespace) -> None:
    assert t.ghashtable_int64_in({"-1": -1, "0": 0, "1": 1, "2": 2**32}) is None


def test_ghashtable_int_none_in(t: Namespace) -> None:
    assert t.ghashtable_int_none_in({-1: 1, 0: 0, 1: -1, 2: -2}) is None


def test_ghashtable_int_none_return(t: Namespace) -> None:
    assert t.ghashtable_int_none_return() == {-1: 1, 0: 0, 1: -1, 2: -2}


def test_ghashtable_uint64_in(t: Namespace) -> None:
    assert t.ghashtable_uint64_in({"-1": 2**32, "0": 0, "1": 1, "2": 2}) is None


def test_ghashtable_utf8_container_in(t: Namespace) -> None:
    assert (
        t.ghashtable_utf8_container_in({"-1": "1", "0": "0", "1": "-1", "2": "-2"})
        is None
    )


def test_ghashtable_utf8_container_inout(t: Namespace) -> None:
    assert t.ghashtable_utf8_container_inout(
        {"-1": "1", "0": "0", "1": "-1", "2": "-2"}
    ) == {"-1": "1", "0": "0", "1": "1"}


def test_ghashtable_utf8_container_out(t: Namespace) -> None:
    t.ghashtable_utf8_container_out()


def test_ghashtable_utf8_container_out_uninitialized(t: Namespace) -> None:
    t.ghashtable_utf8_container_out_uninitialized()


def test_ghashtable_utf8_container_return(t: Namespace) -> None:
    assert t.ghashtable_utf8_container_return() == {
        "-1": "1",
        "0": "0",
        "1": "-1",
        "2": "-2",
    }


def test_ghashtable_utf8_full_in(t: Namespace) -> None:
    assert (
        t.ghashtable_utf8_full_in({"-1": "1", "0": "0", "1": "-1", "2": "-2"}) is None
    )


def test_ghashtable_utf8_full_inout(t: Namespace) -> None:
    assert t.ghashtable_utf8_full_inout(
        {"-1": "1", "0": "0", "1": "-1", "2": "-2"}
    ) == {"-1": "1", "0": "0", "1": "1"}


def test_ghashtable_utf8_full_out(t: Namespace) -> None:
    t.ghashtable_utf8_full_out()


def test_ghashtable_utf8_full_out_uninitialized(t: Namespace) -> None:
    t.ghashtable_utf8_full_out_uninitialized()


def test_ghashtable_utf8_full_return(t: Namespace) -> None:
    assert t.ghashtable_utf8_full_return() == {
        "-1": "1",
        "0": "0",
        "1": "-1",
        "2": "-2",
    }


def test_ghashtable_utf8_none_in(t: Namespace) -> None:
    assert (
        t.ghashtable_utf8_none_in({"-1": "1", "0": "0", "1": "-1", "2": "-2"}) is None
    )


def test_ghashtable_utf8_none_inout(t: Namespace) -> None:
    assert t.ghashtable_utf8_none_inout(
        {"-1": "1", "0": "0", "1": "-1", "2": "-2"}
    ) == {"-1": "1", "0": "0", "1": "1"}


def test_ghashtable_utf8_none_out(t: Namespace) -> None:
    t.ghashtable_utf8_none_out()


def test_ghashtable_utf8_none_out_uninitialized(t: Namespace) -> None:
    t.ghashtable_utf8_none_out_uninitialized()


def test_ghashtable_utf8_none_return(t: Namespace) -> None:
    assert t.ghashtable_utf8_none_return() == {
        "-1": "1",
        "0": "0",
        "1": "-1",
        "2": "-2",
    }


def test_gid_t_in(t: Namespace) -> None:
    t.gid_t_in(65534)


def test_gid_t_inout(t: Namespace) -> None:
    assert t.gid_t_inout(65534) == 0


def test_gid_t_out(t: Namespace) -> None:
    t.gid_t_out()


def test_gid_t_out_uninitialized(t: Namespace) -> None:
    t.gid_t_out_uninitialized()


def test_gid_t_return(t: Namespace) -> None:
    t.gid_t_return()


def test_glist_int_none_in(t: Namespace) -> None:
    assert t.glist_int_none_in([-1, 0, 1, 2]) is None


def test_glist_int_none_return(t: Namespace) -> None:
    assert t.glist_int_none_return() == [-1, 0, 1, 2]


def test_glist_uint32_none_in(t: Namespace) -> None:
    assert t.glist_uint32_none_in([0, 2**32 - 1]) is None


def test_glist_uint32_none_return(t: Namespace) -> None:
    assert t.glist_uint32_none_return() == [0, 2**32 - 1]


def test_glist_utf8_container_in(t: Namespace) -> None:
    assert t.glist_utf8_container_in(["0", "1", "2"]) is None


def test_glist_utf8_container_inout(t: Namespace) -> None:
    assert t.glist_utf8_container_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_glist_utf8_container_out(t: Namespace) -> None:
    t.glist_utf8_container_out()


def test_glist_utf8_container_out_uninitialized(t: Namespace) -> None:
    t.glist_utf8_container_out_uninitialized()


def test_glist_utf8_container_return(t: Namespace) -> None:
    assert t.glist_utf8_container_return() == ["0", "1", "2"]


def test_glist_utf8_full_in(t: Namespace) -> None:
    assert t.glist_utf8_full_in(["0", "1", "2"]) is None


def test_glist_utf8_full_inout(t: Namespace) -> None:
    assert t.glist_utf8_full_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_glist_utf8_full_out(t: Namespace) -> None:
    t.glist_utf8_full_out()


def test_glist_utf8_full_out_uninitialized(t: Namespace) -> None:
    t.glist_utf8_full_out_uninitialized()


def test_glist_utf8_full_return(t: Namespace) -> None:
    assert t.glist_utf8_full_return() == ["0", "1", "2"]


def test_glist_utf8_none_in(t: Namespace) -> None:
    assert t.glist_utf8_none_in(["0", "1", "2"]) is None


def test_glist_utf8_none_inout(t: Namespace) -> None:
    assert t.glist_utf8_none_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_glist_utf8_none_out(t: Namespace) -> None:
    t.glist_utf8_none_out()


def test_glist_utf8_none_out_uninitialized(t: Namespace) -> None:
    t.glist_utf8_none_out_uninitialized()


def test_glist_utf8_none_return(t: Namespace) -> None:
    assert t.glist_utf8_none_return() == ["0", "1", "2"]


def test_gptrarray_boxed_struct_full_return(t: Namespace) -> None:
    t.gptrarray_boxed_struct_full_return()


def test_gptrarray_utf8_container_in(t: Namespace) -> None:
    assert t.gptrarray_utf8_container_in(["0", "1", "2"]) is None


def test_gptrarray_utf8_container_inout(t: Namespace) -> None:
    assert t.gptrarray_utf8_container_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_gptrarray_utf8_container_out(t: Namespace) -> None:
    t.gptrarray_utf8_container_out()


def test_gptrarray_utf8_container_out_uninitialized(t: Namespace) -> None:
    t.gptrarray_utf8_container_out_uninitialized()


def test_gptrarray_utf8_container_return(t: Namespace) -> None:
    assert t.gptrarray_utf8_container_return() == ["0", "1", "2"]


def test_gptrarray_utf8_full_in(t: Namespace) -> None:
    assert t.gptrarray_utf8_full_in(["0", "1", "2"]) is None


def test_gptrarray_utf8_full_inout(t: Namespace) -> None:
    assert t.gptrarray_utf8_full_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_gptrarray_utf8_full_out(t: Namespace) -> None:
    t.gptrarray_utf8_full_out()


def test_gptrarray_utf8_full_out_uninitialized(t: Namespace) -> None:
    t.gptrarray_utf8_full_out_uninitialized()


def test_gptrarray_utf8_full_return(t: Namespace) -> None:
    assert t.gptrarray_utf8_full_return() == ["0", "1", "2"]


def test_gptrarray_utf8_none_in(t: Namespace) -> None:
    assert t.gptrarray_utf8_none_in(["0", "1", "2"]) is None


def test_gptrarray_utf8_none_inout(t: Namespace) -> None:
    assert t.gptrarray_utf8_none_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_gptrarray_utf8_none_out(t: Namespace) -> None:
    t.gptrarray_utf8_none_out()


def test_gptrarray_utf8_none_out_uninitialized(t: Namespace) -> None:
    t.gptrarray_utf8_none_out_uninitialized()


def test_gptrarray_utf8_none_return(t: Namespace) -> None:
    assert t.gptrarray_utf8_none_return() == ["0", "1", "2"]


def test_gslist_int_none_in(t: Namespace) -> None:
    assert t.gslist_int_none_in([-1, 0, 1, 2]) is None


def test_gslist_int_none_return(t: Namespace) -> None:
    assert t.gslist_int_none_return() == [-1, 0, 1, 2]


def test_gslist_utf8_container_in(t: Namespace) -> None:
    assert t.gslist_utf8_container_in(["0", "1", "2"]) is None


def test_gslist_utf8_container_inout(t: Namespace) -> None:
    assert t.gslist_utf8_container_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_gslist_utf8_container_out(t: Namespace) -> None:
    t.gslist_utf8_container_out()


def test_gslist_utf8_container_out_uninitialized(t: Namespace) -> None:
    t.gslist_utf8_container_out_uninitialized()


def test_gslist_utf8_container_return(t: Namespace) -> None:
    assert t.gslist_utf8_container_return() == ["0", "1", "2"]


def test_gslist_utf8_full_in(t: Namespace) -> None:
    assert t.gslist_utf8_full_in(["0", "1", "2"]) is None


def test_gslist_utf8_full_inout(t: Namespace) -> None:
    assert t.gslist_utf8_full_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_gslist_utf8_full_out(t: Namespace) -> None:
    t.gslist_utf8_full_out()


def test_gslist_utf8_full_out_uninitialized(t: Namespace) -> None:
    t.gslist_utf8_full_out_uninitialized()


def test_gslist_utf8_full_return(t: Namespace) -> None:
    assert t.gslist_utf8_full_return() == ["0", "1", "2"]


def test_gslist_utf8_none_in(t: Namespace) -> None:
    assert t.gslist_utf8_none_in(["0", "1", "2"]) is None


def test_gslist_utf8_none_inout(t: Namespace) -> None:
    assert t.gslist_utf8_none_inout(["0", "1", "2"]) == ["-2", "-1", "0", "1"]


def test_gslist_utf8_none_out(t: Namespace) -> None:
    t.gslist_utf8_none_out()


def test_gslist_utf8_none_out_uninitialized(t: Namespace) -> None:
    t.gslist_utf8_none_out_uninitialized()


def test_gslist_utf8_none_return(t: Namespace) -> None:
    assert t.gslist_utf8_none_return() == ["0", "1", "2"]


def test_gstrv_in(t: Namespace) -> None:
    assert t.gstrv_in(["0", "1", "2"]) is None


def test_gstrv_inout(t: Namespace) -> None:
    assert t.gstrv_inout(["0", "1", "2"]) == ["-1", "0", "1", "2"]


def test_gstrv_out(t: Namespace) -> None:
    t.gstrv_out()


def test_gstrv_out_uninitialized(t: Namespace) -> None:
    t.gstrv_out_uninitialized()


def test_gstrv_return(t: Namespace) -> None:
    assert t.gstrv_return() == ["0", "1", "2"]


def test_gtype_in(t: Namespace) -> None:
    assert t.gtype_in(4) is None


def test_gtype_inout(t: Namespace) -> None:
    G_TYPE_NONE = 4
    G_TYPE_INT = 24
    assert t.gtype_inout(G_TYPE_NONE) == G_TYPE_INT


def test_gtype_out(t: Namespace) -> None:
    t.gtype_out()


def test_gtype_out_uninitialized(t: Namespace) -> None:
    t.gtype_out_uninitialized()


def test_gtype_return(t: Namespace) -> None:
    assert t.gtype_return() == 4


def test_gtype_string_in(t: Namespace) -> None:
    assert t.gtype_string_in(64) is None


def test_gtype_string_out(t: Namespace) -> None:
    t.gtype_string_out()


def test_gtype_string_return(t: Namespace) -> None:
    assert t.gtype_string_return() == 64


def test_gvalue_copy(t: Namespace) -> None:
    result = t.gvalue_copy(42)
    assert result == 42


def test_gvalue_flat_array(t: Namespace) -> None:
    assert t.gvalue_flat_array([42, "42", True]) is None


def test_gvalue_float(t: Namespace) -> None:
    assert t.gvalue_float(3.14, 3.14) is None


def test_gvalue_in(t: Namespace) -> None:
    assert t.gvalue_in(42) is None


def test_gvalue_in_enum(t: Namespace) -> None:
    assert t.gvalue_in_enum(t.GEnum.VALUE3) is None


def test_gvalue_in_flags(t: Namespace) -> None:
    assert t.gvalue_in_flags(t.Flags.VALUE3) is None


def test_gvalue_in_with_modification(t: Namespace) -> None:
    t.gvalue_in_with_modification(42)


def test_gvalue_in_with_type(t: Namespace) -> None:
    assert t.gvalue_in_with_type("foo", 64) is None


def test_gvalue_inout(t: Namespace) -> None:
    result = t.gvalue_inout(42)
    assert result == "42"
    assert isinstance(result, str)


def test_gvalue_int64_in(t: Namespace) -> None:
    assert t.gvalue_int64_in(9_223_372_036_854_775_807) is None


def test_gvalue_int64_out(t: Namespace) -> None:
    result = t.gvalue_int64_out()
    assert result == 9_223_372_036_854_775_807
    assert isinstance(result, int)


def test_gvalue_noncanonical_nan_double(t: Namespace) -> None:
    t.gvalue_noncanonical_nan_double()


def test_gvalue_noncanonical_nan_float(t: Namespace) -> None:
    t.gvalue_noncanonical_nan_float()


def test_gvalue_out(t: Namespace) -> None:
    result = t.gvalue_out()
    assert result == 42
    assert isinstance(result, int)


def test_gvalue_out_caller_allocates(t: Namespace) -> None:
    result = t.gvalue_out_caller_allocates()
    assert result == 42
    assert isinstance(result, int)


def test_gvalue_out_uninitialized(t: Namespace) -> None:
    assert t.gvalue_out_uninitialized() == (False, None)


def test_gvalue_return(t: Namespace) -> None:
    assert t.gvalue_return() == 42


def test_gvalue_round_trip(t: Namespace) -> None:
    assert t.gvalue_round_trip(42) == 42


def test_init_function(t: Namespace) -> None:
    # The C function pops the last argument from argv; we get back
    # (True, ["foo"]) — pygobject's `(bool_ret, *outs)` shape.
    ok, argv = t.init_function(["foo", "bar"])
    assert ok is True
    assert argv == ["foo"]


def test_int16_in_max(t: Namespace) -> None:
    t.int16_in_max(32_767)


def test_int16_in_min(t: Namespace) -> None:
    t.int16_in_min(-32_768)


def test_int16_inout_max_min(t: Namespace) -> None:
    assert t.int16_inout_max_min(32_767) == -32_768


def test_int16_inout_min_max(t: Namespace) -> None:
    assert t.int16_inout_min_max(-32_768) == 32_767


def test_int16_out_max(t: Namespace) -> None:
    assert t.int16_out_max() == 32_767


def test_int16_out_min(t: Namespace) -> None:
    assert t.int16_out_min() == -32_768


def test_int16_out_uninitialized(t: Namespace) -> None:
    assert t.int16_out_uninitialized()[0] is False


def test_int32_in_max(t: Namespace) -> None:
    t.int32_in_max(2_147_483_647)


def test_int32_in_min(t: Namespace) -> None:
    t.int32_in_min(-2_147_483_648)


def test_int32_inout_max_min(t: Namespace) -> None:
    assert t.int32_inout_max_min(2_147_483_647) == -2_147_483_648


def test_int32_inout_min_max(t: Namespace) -> None:
    assert t.int32_inout_min_max(-2_147_483_648) == 2_147_483_647


def test_int32_out_max(t: Namespace) -> None:
    assert t.int32_out_max() == 2_147_483_647


def test_int32_out_min(t: Namespace) -> None:
    assert t.int32_out_min() == -2_147_483_648


def test_int32_out_uninitialized(t: Namespace) -> None:
    assert t.int32_out_uninitialized()[0] is False


def test_int64_in_max(t: Namespace) -> None:
    t.int64_in_max(9_223_372_036_854_775_807)


def test_int64_in_min(t: Namespace) -> None:
    t.int64_in_min(-9_223_372_036_854_775_808)


def test_int64_inout_max_min(t: Namespace) -> None:
    assert (
        t.int64_inout_max_min(9_223_372_036_854_775_807) == -9_223_372_036_854_775_808
    )


def test_int64_inout_min_max(t: Namespace) -> None:
    assert (
        t.int64_inout_min_max(-9_223_372_036_854_775_808) == 9_223_372_036_854_775_807
    )


def test_int64_out_max(t: Namespace) -> None:
    assert t.int64_out_max() == 9_223_372_036_854_775_807


def test_int64_out_min(t: Namespace) -> None:
    assert t.int64_out_min() == -9_223_372_036_854_775_808


def test_int64_out_uninitialized(t: Namespace) -> None:
    assert t.int64_out_uninitialized()[0] is False


def test_int8_in_max(t: Namespace) -> None:
    t.int8_in_max(127)


def test_int8_in_min(t: Namespace) -> None:
    t.int8_in_min(-128)


def test_int8_inout_max_min(t: Namespace) -> None:
    assert t.int8_inout_max_min(127) == -128


def test_int8_inout_min_max(t: Namespace) -> None:
    assert t.int8_inout_min_max(-128) == 127


def test_int8_out_max(t: Namespace) -> None:
    assert t.int8_out_max() == 127


def test_int8_out_min(t: Namespace) -> None:
    assert t.int8_out_min() == -128


def test_int8_out_uninitialized(t: Namespace) -> None:
    assert t.int8_out_uninitialized()[0] is False


def test_int_in_max(t: Namespace) -> None:
    t.int_in_max(2_147_483_647)


def test_int_in_min(t: Namespace) -> None:
    t.int_in_min(-2_147_483_648)


def test_int_in_type_error(t: Namespace) -> None:
    with pytest.raises(
        TypeError, match=r"'str' object cannot be interpreted as an integer"
    ):
        t.int_in_max("not an int")


def test_int_inout_max_min(t: Namespace) -> None:
    assert t.int_inout_max_min(2_147_483_647) == -2_147_483_648


def test_int_inout_min_max(t: Namespace) -> None:
    assert t.int_inout_min_max(-2_147_483_648) == 2_147_483_647


def test_int_one_in_utf8_two_in_one_allows_none(t: Namespace) -> None:
    t.int_one_in_utf8_two_in_one_allows_none(1, "2", "3")
    t.int_one_in_utf8_two_in_one_allows_none(1, None, "3")


def test_int_out_max(t: Namespace) -> None:
    assert t.int_out_max() == 2_147_483_647


def test_int_out_min(t: Namespace) -> None:
    assert t.int_out_min() == -2_147_483_648


def test_int_out_out(t: Namespace) -> None:
    assert t.int_out_out() == (6, 7)


def test_int_out_uninitialized(t: Namespace) -> None:
    assert t.int_out_uninitialized()[0] is False


def test_int_return_max(t: Namespace) -> None:
    assert t.int_return_max() == 2_147_483_647


def test_int_return_min(t: Namespace) -> None:
    assert t.int_return_min() == -2_147_483_648


def test_int_return_out(t: Namespace) -> None:
    assert t.int_return_out() == (6, 7)


def test_int_three_in_three_out(t: Namespace) -> None:
    assert t.int_three_in_three_out(1, 2, 3) == (1, 2, 3)


def test_int_two_in_utf8_two_in_with_allow_none(t: Namespace) -> None:
    t.int_two_in_utf8_two_in_with_allow_none(1, 2, "3", "4")
    t.int_two_in_utf8_two_in_with_allow_none(1, 2, None, None)


def test_length_array_of_gstrv_transfer_container_in(t: Namespace) -> None:
    assert t.length_array_of_gstrv_transfer_container_in(_GSTRV_INPUT) is None


def test_length_array_of_gstrv_transfer_container_inout(t: Namespace) -> None:
    assert (
        t.length_array_of_gstrv_transfer_container_inout(_GSTRV_INPUT) == _GSTRV_OUTPUT4
    )


def test_length_array_of_gstrv_transfer_container_out(t: Namespace) -> None:
    t.length_array_of_gstrv_transfer_container_out()


def test_length_array_of_gstrv_transfer_container_return(t: Namespace) -> None:
    t.length_array_of_gstrv_transfer_container_return()


def test_length_array_of_gstrv_transfer_full_in(t: Namespace) -> None:
    assert t.length_array_of_gstrv_transfer_full_in(_GSTRV_INPUT) is None


def test_length_array_of_gstrv_transfer_full_inout(t: Namespace) -> None:
    assert t.length_array_of_gstrv_transfer_full_inout(_GSTRV_INPUT) == _GSTRV_OUTPUT4


def test_length_array_of_gstrv_transfer_full_out(t: Namespace) -> None:
    t.length_array_of_gstrv_transfer_full_out()


def test_length_array_of_gstrv_transfer_full_return(t: Namespace) -> None:
    t.length_array_of_gstrv_transfer_full_return()


def test_length_array_of_gstrv_transfer_none_in(t: Namespace) -> None:
    assert t.length_array_of_gstrv_transfer_none_in(_GSTRV_INPUT) is None


def test_length_array_of_gstrv_transfer_none_inout(t: Namespace) -> None:
    assert t.length_array_of_gstrv_transfer_none_inout(_GSTRV_INPUT) == _GSTRV_OUTPUT4


def test_length_array_of_gstrv_transfer_none_out(t: Namespace) -> None:
    t.length_array_of_gstrv_transfer_none_out()


def test_length_array_of_gstrv_transfer_none_return(t: Namespace) -> None:
    t.length_array_of_gstrv_transfer_none_return()


def test_length_array_utf8_container_in(t: Namespace) -> None:
    assert t.length_array_utf8_container_in(_UTF8_IN) is None


def test_length_array_utf8_container_inout(t: Namespace) -> None:
    assert t.length_array_utf8_container_inout(_UTF8_IN) == _UTF8_OUT


def test_length_array_utf8_container_out(t: Namespace) -> None:
    t.length_array_utf8_container_out()


def test_length_array_utf8_container_return(t: Namespace) -> None:
    t.length_array_utf8_container_return()


def test_length_array_utf8_full_in(t: Namespace) -> None:
    assert t.length_array_utf8_full_in(_UTF8_IN) is None


def test_length_array_utf8_full_inout(t: Namespace) -> None:
    assert t.length_array_utf8_full_inout(_UTF8_IN) == _UTF8_OUT


def test_length_array_utf8_full_out(t: Namespace) -> None:
    t.length_array_utf8_full_out()


def test_length_array_utf8_full_return(t: Namespace) -> None:
    t.length_array_utf8_full_return()


def test_length_array_utf8_none_in(t: Namespace) -> None:
    assert t.length_array_utf8_none_in(_UTF8_IN) is None


def test_length_array_utf8_none_inout(t: Namespace) -> None:
    assert t.length_array_utf8_none_inout(_UTF8_IN) == _UTF8_OUT


def test_length_array_utf8_none_out(t: Namespace) -> None:
    t.length_array_utf8_none_out()


def test_length_array_utf8_none_return(t: Namespace) -> None:
    t.length_array_utf8_none_return()


def test_length_array_utf8_optional_inout(t: Namespace) -> None:
    assert t.length_array_utf8_optional_inout(_UTF8_IN) == _UTF8_OUT


def test_long_in_max(t: Namespace) -> None:
    t.long_in_max(_LONG_MAX)


def test_long_in_min(t: Namespace) -> None:
    t.long_in_min(_LONG_MIN)


def test_long_inout_max_min(t: Namespace) -> None:
    assert t.long_inout_max_min(_LONG_MAX) == _LONG_MIN


def test_long_inout_min_max(t: Namespace) -> None:
    assert t.long_inout_min_max(_LONG_MIN) == _LONG_MAX


def test_long_out_max(t: Namespace) -> None:
    assert t.long_out_max() == _LONG_MAX


def test_long_out_min(t: Namespace) -> None:
    assert t.long_out_min() == _LONG_MIN


def test_long_out_uninitialized(t: Namespace) -> None:
    assert t.long_out_uninitialized()[0] is False


def test_long_return_max(t: Namespace) -> None:
    assert t.long_return_max() == _LONG_MAX


def test_long_return_min(t: Namespace) -> None:
    assert t.long_return_min() == _LONG_MIN


def test_multi_array_key_value_in(t: Namespace) -> None:
    assert t.multi_array_key_value_in(["one", "two", "three"], [1, 2, 3]) is None


def test_no_type_flags_in(t: Namespace) -> None:
    assert t.no_type_flags_in(t.NoTypeFlags.VALUE2) is None


def test_no_type_flags_in_zero(t: Namespace) -> None:
    assert t.no_type_flags_in_zero(0) is None


def test_no_type_flags_inout(t: Namespace) -> None:
    assert t.no_type_flags_inout(t.NoTypeFlags.VALUE2) == t.NoTypeFlags.VALUE1


def test_no_type_flags_out(t: Namespace) -> None:
    assert t.no_type_flags_out() == t.NoTypeFlags.VALUE2


def test_no_type_flags_out_uninitialized(t: Namespace) -> None:
    assert t.no_type_flags_out_uninitialized()[0] is False


def test_no_type_flags_returnv(t: Namespace) -> None:
    assert t.no_type_flags_returnv() == t.NoTypeFlags.VALUE2


def test_nullable_gerror(t: Namespace) -> None:
    t.nullable_gerror()


def test_off_t_in(t: Namespace) -> None:
    t.off_t_in(1234567890)


def test_off_t_inout(t: Namespace) -> None:
    assert t.off_t_inout(1234567890) == 0


def test_off_t_out(t: Namespace) -> None:
    t.off_t_out()


def test_off_t_out_uninitialized(t: Namespace) -> None:
    t.off_t_out_uninitialized()


def test_off_t_return(t: Namespace) -> None:
    t.off_t_return()


def test_overrides_struct_returnv(t: Namespace) -> None:
    s = t.overrides_struct_returnv()
    assert s is not None


def test_param_spec_in_bool(t: Namespace) -> None:
    import ginext

    gobj = ginext._load_namespace("GObject", "2.0")
    ps = gobj.param_spec_boolean("mybool", "test-bool", "boolblurb", True, 1)
    assert t.param_spec_in_bool(ps) is None


def test_param_spec_out(t: Namespace) -> None:
    t.param_spec_out()


def test_param_spec_out_uninitialized(t: Namespace) -> None:
    t.param_spec_out_uninitialized()


def test_param_spec_return(t: Namespace) -> None:
    assert t.param_spec_return() is not None


def test_pid_t_in(t: Namespace) -> None:
    t.pid_t_in(12345)


def test_pid_t_inout(t: Namespace) -> None:
    assert t.pid_t_inout(12345) == 0


def test_pid_t_out(t: Namespace) -> None:
    t.pid_t_out()


def test_pid_t_out_uninitialized(t: Namespace) -> None:
    t.pid_t_out_uninitialized()


def test_pid_t_return(t: Namespace) -> None:
    t.pid_t_return()


def test_pointer_array_struct_with_uint8_array(t: Namespace) -> None:
    t.pointer_array_struct_with_uint8_array()


def test_pointer_in_return(t: Namespace) -> None:
    assert t.pointer_in_return(None) is None


def test_pointer_struct_returnv(t: Namespace) -> None:
    s = t.pointer_struct_returnv()
    assert s.long_ == 42


def test_return_gvalue_flat_array(t: Namespace) -> None:
    assert t.return_gvalue_flat_array() == [42, "42", True]


def test_return_gvalue_zero_terminated_array(t: Namespace) -> None:
    assert t.return_gvalue_zero_terminated_array() == [42, "42", True]


def test_short_in_max(t: Namespace) -> None:
    t.short_in_max(32_767)


def test_short_in_min(t: Namespace) -> None:
    t.short_in_min(-32_768)


def test_short_inout_max_min(t: Namespace) -> None:
    assert t.short_inout_max_min(32_767) == -32_768


def test_short_inout_min_max(t: Namespace) -> None:
    assert t.short_inout_min_max(-32_768) == 32_767


def test_short_out_max(t: Namespace) -> None:
    assert t.short_out_max() == 32_767


def test_short_out_min(t: Namespace) -> None:
    assert t.short_out_min() == -32_768


def test_short_out_uninitialized(t: Namespace) -> None:
    assert t.short_out_uninitialized()[0] is False


def test_short_return_max(t: Namespace) -> None:
    assert t.short_return_max() == 32_767


def test_short_return_min(t: Namespace) -> None:
    assert t.short_return_min() == -32_768


def test_simple_struct_returnv(t: Namespace) -> None:
    s = t.simple_struct_returnv()
    assert s.long_ == 6
    assert s.int8 == 7


def test_size_in(t: Namespace) -> None:
    t.size_in(18_446_744_073_709_551_615)


def test_size_inout(t: Namespace) -> None:
    assert t.size_inout(18_446_744_073_709_551_615) == 0


def test_size_out(t: Namespace) -> None:
    assert t.size_out() == 18_446_744_073_709_551_615


def test_size_out_uninitialized(t: Namespace) -> None:
    assert t.size_out_uninitialized()[0] is False


def test_size_return(t: Namespace) -> None:
    assert t.size_return() == 18_446_744_073_709_551_615


def test_socklen_t_in(t: Namespace) -> None:
    t.socklen_t_in(123)


def test_socklen_t_inout(t: Namespace) -> None:
    assert t.socklen_t_inout(123) == 0


def test_socklen_t_out(t: Namespace) -> None:
    t.socklen_t_out()


def test_socklen_t_out_uninitialized(t: Namespace) -> None:
    t.socklen_t_out_uninitialized()


def test_socklen_t_return(t: Namespace) -> None:
    t.socklen_t_return()


def test_ssize_in_max(t: Namespace) -> None:
    t.ssize_in_max(9_223_372_036_854_775_807)


def test_ssize_in_min(t: Namespace) -> None:
    t.ssize_in_min(-9_223_372_036_854_775_808)


def test_ssize_inout_max_min(t: Namespace) -> None:
    assert (
        t.ssize_inout_max_min(9_223_372_036_854_775_807) == -9_223_372_036_854_775_808
    )


def test_ssize_inout_min_max(t: Namespace) -> None:
    assert (
        t.ssize_inout_min_max(-9_223_372_036_854_775_808) == 9_223_372_036_854_775_807
    )


def test_ssize_out_max(t: Namespace) -> None:
    assert t.ssize_out_max() == 9_223_372_036_854_775_807


def test_ssize_out_min(t: Namespace) -> None:
    assert t.ssize_out_min() == -9_223_372_036_854_775_808


def test_ssize_out_uninitialized(t: Namespace) -> None:
    assert t.ssize_out_uninitialized()[0] is False


def test_ssize_return_max(t: Namespace) -> None:
    assert t.ssize_return_max() == 9_223_372_036_854_775_807


def test_ssize_return_min(t: Namespace) -> None:
    assert t.ssize_return_min() == -9_223_372_036_854_775_808


def test_test_interface_test_int8_in(t: Namespace) -> None:
    impl = t.InterfaceImpl()
    assert t.test_interface_test_int8_in(impl, 42) is None


def test_time_t_in(t: Namespace) -> None:
    t.time_t_in(1234567890)


def test_time_t_inout(t: Namespace) -> None:
    assert t.time_t_inout(1234567890) == 0


def test_time_t_out(t: Namespace) -> None:
    t.time_t_out()


def test_time_t_out_uninitialized(t: Namespace) -> None:
    t.time_t_out_uninitialized()


def test_time_t_return(t: Namespace) -> None:
    t.time_t_return()


def test_uid_t_in(t: Namespace) -> None:
    t.uid_t_in(65534)


def test_uid_t_inout(t: Namespace) -> None:
    assert t.uid_t_inout(65534) == 0


def test_uid_t_out(t: Namespace) -> None:
    t.uid_t_out()


def test_uid_t_out_uninitialized(t: Namespace) -> None:
    t.uid_t_out_uninitialized()


def test_uid_t_return(t: Namespace) -> None:
    t.uid_t_return()


def test_uint16_in(t: Namespace) -> None:
    t.uint16_in(65_535)


def test_uint16_inout(t: Namespace) -> None:
    assert t.uint16_inout(65_535) == 0


def test_uint16_out(t: Namespace) -> None:
    assert t.uint16_out() == 65_535


def test_uint16_out_uninitialized(t: Namespace) -> None:
    assert t.uint16_out_uninitialized()[0] is False


def test_uint32_in(t: Namespace) -> None:
    t.uint32_in(4_294_967_295)


def test_uint32_inout(t: Namespace) -> None:
    assert t.uint32_inout(4_294_967_295) == 0


def test_uint32_out(t: Namespace) -> None:
    assert t.uint32_out() == 4_294_967_295


def test_uint32_out_uninitialized(t: Namespace) -> None:
    assert t.uint32_out_uninitialized()[0] is False


def test_uint64_in(t: Namespace) -> None:
    t.uint64_in(18_446_744_073_709_551_615)


def test_uint64_inout(t: Namespace) -> None:
    assert t.uint64_inout(18_446_744_073_709_551_615) == 0


def test_uint64_out(t: Namespace) -> None:
    assert t.uint64_out() == 18_446_744_073_709_551_615


def test_uint64_out_uninitialized(t: Namespace) -> None:
    assert t.uint64_out_uninitialized()[0] is False


def test_uint64_return(t: Namespace) -> None:
    assert t.uint64_return() == 18_446_744_073_709_551_615


def test_uint8_in(t: Namespace) -> None:
    t.uint8_in(255)


def test_uint8_inout(t: Namespace) -> None:
    assert t.uint8_inout(255) == 0


def test_uint8_out(t: Namespace) -> None:
    assert t.uint8_out() == 255


def test_uint8_out_uninitialized(t: Namespace) -> None:
    assert t.uint8_out_uninitialized()[0] is False


def test_uint_in(t: Namespace) -> None:
    t.uint_in(4_294_967_295)


def test_uint_inout(t: Namespace) -> None:
    assert t.uint_inout(4_294_967_295) == 0


def test_uint_out(t: Namespace) -> None:
    assert t.uint_out() == 4_294_967_295


def test_uint_out_uninitialized(t: Namespace) -> None:
    assert t.uint_out_uninitialized()[0] is False


def test_uint_return(t: Namespace) -> None:
    assert t.uint_return() == 4_294_967_295


def test_ulong_in(t: Namespace) -> None:
    t.ulong_in(_ULONG_MAX)


def test_ulong_inout(t: Namespace) -> None:
    assert t.ulong_inout(_ULONG_MAX) == 0


def test_ulong_out(t: Namespace) -> None:
    assert t.ulong_out() == _ULONG_MAX


def test_ulong_out_uninitialized(t: Namespace) -> None:
    assert t.ulong_out_uninitialized()[0] is False


def test_ulong_return(t: Namespace) -> None:
    assert t.ulong_return() == _ULONG_MAX


def test_union_returnv(t: Namespace) -> None:
    u = t.union_returnv()
    assert u.long_ == 42


def test_ushort_in(t: Namespace) -> None:
    t.ushort_in(65_535)


def test_ushort_inout(t: Namespace) -> None:
    assert t.ushort_inout(65_535) == 0


def test_ushort_out(t: Namespace) -> None:
    assert t.ushort_out() == 65_535


def test_ushort_out_uninitialized(t: Namespace) -> None:
    assert t.ushort_out_uninitialized()[0] is False


def test_ushort_return(t: Namespace) -> None:
    assert t.ushort_return() == 65_535


def test_utf8_as_uint8array_in(t: Namespace) -> None:
    t.utf8_as_uint8array_in(b"const \xe2\x99\xa5 utf8")


def test_utf8_dangling_out(t: Namespace) -> None:
    t.utf8_dangling_out()


def test_utf8_full_in(t: Namespace) -> None:
    t.utf8_full_in("const ♥ utf8")


def test_utf8_full_inout(t: Namespace) -> None:
    assert t.utf8_full_inout("const ♥ utf8") == ""


def test_utf8_full_out(t: Namespace) -> None:
    assert t.utf8_full_out() == "const ♥ utf8"


def test_utf8_full_return(t: Namespace) -> None:
    assert t.utf8_full_return() == "const ♥ utf8"


def test_utf8_none_in(t: Namespace) -> None:
    t.utf8_none_in("const ♥ utf8")


def test_utf8_none_inout(t: Namespace) -> None:
    assert t.utf8_none_inout("const ♥ utf8") == ""


def test_utf8_none_out(t: Namespace) -> None:
    assert t.utf8_none_out() == "const ♥ utf8"


def test_utf8_none_out_uninitialized(t: Namespace) -> None:
    assert t.utf8_none_out_uninitialized()[0] is False


def test_utf8_none_return(t: Namespace) -> None:
    assert t.utf8_none_return() == "const ♥ utf8"


def test_zero_terminated_array_of_gstrv_transfer_container_in(t: Namespace) -> None:
    assert t.zero_terminated_array_of_gstrv_transfer_container_in(_GSTRV_INPUT) is None


def test_zero_terminated_array_of_gstrv_transfer_container_inout(t: Namespace) -> None:
    assert (
        t.zero_terminated_array_of_gstrv_transfer_container_inout(_GSTRV_INPUT)
        == _GSTRV_OUTPUT4
    )


def test_zero_terminated_array_of_gstrv_transfer_container_out(t: Namespace) -> None:
    t.zero_terminated_array_of_gstrv_transfer_container_out()


def test_zero_terminated_array_of_gstrv_transfer_container_return(t: Namespace) -> None:
    t.zero_terminated_array_of_gstrv_transfer_container_return()


def test_zero_terminated_array_of_gstrv_transfer_full_in(t: Namespace) -> None:
    assert t.zero_terminated_array_of_gstrv_transfer_full_in(_GSTRV_INPUT) is None


def test_zero_terminated_array_of_gstrv_transfer_full_inout(t: Namespace) -> None:
    assert (
        t.zero_terminated_array_of_gstrv_transfer_full_inout(_GSTRV_INPUT)
        == _GSTRV_OUTPUT4
    )


def test_zero_terminated_array_of_gstrv_transfer_full_out(t: Namespace) -> None:
    t.zero_terminated_array_of_gstrv_transfer_full_out()


def test_zero_terminated_array_of_gstrv_transfer_full_return(t: Namespace) -> None:
    t.zero_terminated_array_of_gstrv_transfer_full_return()


def test_zero_terminated_array_of_gstrv_transfer_none_in(t: Namespace) -> None:
    assert t.zero_terminated_array_of_gstrv_transfer_none_in(_GSTRV_INPUT) is None


def test_zero_terminated_array_of_gstrv_transfer_none_inout(t: Namespace) -> None:
    assert (
        t.zero_terminated_array_of_gstrv_transfer_none_inout(_GSTRV_INPUT)
        == _GSTRV_OUTPUT4
    )


def test_zero_terminated_array_of_gstrv_transfer_none_out(t: Namespace) -> None:
    t.zero_terminated_array_of_gstrv_transfer_none_out()


def test_zero_terminated_array_of_gstrv_transfer_none_return(t: Namespace) -> None:
    t.zero_terminated_array_of_gstrv_transfer_none_return()


def test_zero_terminated_array_utf8_container_in(t: Namespace) -> None:
    assert t.zero_terminated_array_utf8_container_in(_UTF8_IN, None) is None


def test_zero_terminated_array_utf8_container_inout(t: Namespace) -> None:
    assert t.zero_terminated_array_utf8_container_inout(_UTF8_IN) == _UTF8_OUT


def test_zero_terminated_array_utf8_container_out(t: Namespace) -> None:
    t.zero_terminated_array_utf8_container_out()


def test_zero_terminated_array_utf8_container_return(t: Namespace) -> None:
    t.zero_terminated_array_utf8_container_return()


def test_zero_terminated_array_utf8_full_in(t: Namespace) -> None:
    assert t.zero_terminated_array_utf8_full_in(_UTF8_IN, None) is None


def test_zero_terminated_array_utf8_full_inout(t: Namespace) -> None:
    assert t.zero_terminated_array_utf8_full_inout(_UTF8_IN) == _UTF8_OUT


def test_zero_terminated_array_utf8_full_out(t: Namespace) -> None:
    t.zero_terminated_array_utf8_full_out()


def test_zero_terminated_array_utf8_full_return(t: Namespace) -> None:
    t.zero_terminated_array_utf8_full_return()


def test_zero_terminated_array_utf8_none_in(t: Namespace) -> None:
    # The C function takes an extra nullable string arg too.
    assert t.zero_terminated_array_utf8_none_in(_UTF8_IN, None) is None


def test_zero_terminated_array_utf8_none_inout(t: Namespace) -> None:
    assert t.zero_terminated_array_utf8_none_inout(_UTF8_IN) == _UTF8_OUT


def test_zero_terminated_array_utf8_none_out(t: Namespace) -> None:
    t.zero_terminated_array_utf8_none_out()


def test_zero_terminated_array_utf8_none_return(t: Namespace) -> None:
    t.zero_terminated_array_utf8_none_return()
