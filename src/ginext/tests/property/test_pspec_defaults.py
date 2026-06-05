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

import math
import struct
from typing import Any

import pytest

from ..conftest import BUILTIN_VALUE_TYPES, GINT64_MAX, GINT64_MIN


def assert_default(actual: Any, expected: Any) -> None:
    if expected is None:
        assert actual is None
    elif isinstance(expected, bool):
        assert actual is expected
    else:
        assert actual == expected


@pytest.mark.parametrize("case", BUILTIN_VALUE_TYPES)
def test_no_default_uses_type_zero(
    make_property_class: Any, pspec_default: Any, case: Any
) -> None:
    cls = make_property_class(case.annotation)
    assert_default(pspec_default(cls.gimeta.pspecs["x"]), case.zero)


@pytest.mark.parametrize(
    "annotation, default",
    [
        pytest.param(bool, True, id="bool-true"),
        pytest.param(bool, False, id="bool-false"),
        pytest.param(int, 0, id="int-zero"),
        pytest.param(int, 1, id="int-one"),
        pytest.param(int, -1, id="int-neg-one"),
        pytest.param(int, 42, id="int-positive"),
        pytest.param(int, -(2**30), id="int-large-negative"),
        pytest.param(int, 2**30 - 1, id="int-large-positive"),
        pytest.param(int, -(2**40), id="int-very-large-negative"),
        pytest.param(int, 2**40, id="int-very-large-positive"),
        pytest.param(float, 0.0, id="float-zero"),
        pytest.param(float, 1.5, id="float-positive"),
        pytest.param(float, -3.14, id="float-negative"),
        pytest.param(float, 1e10, id="float-large"),
        pytest.param(float, -1e-10, id="float-small-negative"),
        pytest.param(str, "", id="str-empty"),
        pytest.param(str, "hello", id="str-ascii"),
        pytest.param(str, "中文", id="str-utf8"),
        pytest.param(str, "with\nnewline", id="str-newline"),
    ],
)
def test_explicit_default_round_trips(
    make_property_class: Any, pspec_default: Any, annotation: Any, default: Any
) -> None:
    cls = make_property_class(annotation, default=default)
    assert_default(pspec_default(cls.gimeta.pspecs["x"]), default)


def test_none_default_is_treated_as_unset(
    GObject: Any, Property: Any, pspec_default: Any
) -> None:
    class Foo(GObject):  # type: ignore[misc]
        a: int = Property(default=None)
        b: float = Property(default=None)
        c: str = Property(default=None)

    assert pspec_default(Foo.gimeta.pspecs["a"]) == 0
    assert pspec_default(Foo.gimeta.pspecs["b"]) == 0.0
    assert pspec_default(Foo.gimeta.pspecs["c"]) is None


@pytest.mark.parametrize(
    "default",
    [
        pytest.param(0, id="zero"),
        pytest.param(1, id="one"),
        pytest.param(-1, id="neg-one"),
        pytest.param(2**30, id="large-pos"),
        pytest.param(-(2**30), id="large-neg"),
        pytest.param(GINT64_MAX, id="gint64-max"),
        pytest.param(GINT64_MIN, id="gint64-min"),
    ],
)
def test_int_default_boundaries(
    make_property_class: Any, pspec_default: Any, default: Any
) -> None:
    cls = make_property_class(int, default=default)
    assert pspec_default(cls.gimeta.pspecs["x"]) == default


@pytest.mark.parametrize(
    "default",
    [
        pytest.param(2**63, id="just-over-gint64-max"),
        pytest.param(-(2**63) - 1, id="just-under-gint64-min"),
        pytest.param(2**63, id="needs-uint64"),
        pytest.param(2**100, id="bignum"),
    ],
)
def test_int_default_out_of_gint64_range_raises(
    GObject: Any, Property: Any, default: Any
) -> None:
    with pytest.raises((OverflowError, ValueError)):

        class Foo(GObject):  # type: ignore[misc]
            x: int = Property(default=default)


def test_int_default_from_bool_is_coerced(
    make_property_class: Any, pspec_default: Any
) -> None:
    cls = make_property_class(int, default=True)
    assert pspec_default(cls.gimeta.pspecs["x"]) == 1


@pytest.mark.parametrize(
    "default",
    [
        pytest.param(0.0, id="zero"),
        pytest.param(-0.0, id="neg-zero"),
        pytest.param(1.0, id="one"),
        pytest.param(-1.0, id="neg-one"),
        pytest.param(0.1 + 0.2, id="non-exact-binary"),
        pytest.param(1e-300, id="tiny-denormal"),
        pytest.param(1e300, id="huge"),
        pytest.param(-1e300, id="huge-neg"),
        pytest.param(math.pi, id="pi"),
    ],
)
def test_float_default_boundaries(
    make_property_class: Any, pspec_default: Any, default: Any
) -> None:
    cls = make_property_class(float, default=default)
    actual = pspec_default(cls.gimeta.pspecs["x"])
    assert struct.pack("d", actual) == struct.pack("d", default)


def test_float_default_neg_zero_distinguishable_from_zero(
    make_property_class: Any, pspec_default: Any
) -> None:
    cls = make_property_class(float, default=-0.0)
    actual = pspec_default(cls.gimeta.pspecs["x"])
    assert math.copysign(1.0, actual) == -1.0


@pytest.mark.parametrize(
    "default",
    [
        pytest.param(float("inf"), id="inf"),
        pytest.param(float("-inf"), id="neg-inf"),
        pytest.param(float("nan"), id="nan"),
    ],
)
def test_float_default_infinities_and_nan_are_rejected(
    GObject: Any, Property: Any, default: Any
) -> None:
    with pytest.raises((ValueError, TypeError)):

        class Foo(GObject):  # type: ignore[misc]
            x: float = Property(default=default)


def test_float_default_from_int_is_coerced(
    make_property_class: Any, pspec_default: Any
) -> None:
    cls = make_property_class(float, default=5)
    assert pspec_default(cls.gimeta.pspecs["x"]) == 5.0


@pytest.mark.parametrize(
    "default, expected",
    [
        pytest.param(True, True, id="true"),
        pytest.param(False, False, id="false"),
        pytest.param(1, True, id="truthy-int"),
        pytest.param(0, False, id="zero-int"),
        pytest.param("x", True, id="truthy-str"),
        pytest.param("", False, id="empty-str-falsy"),
        pytest.param([1], True, id="truthy-list"),
    ],
)
def test_bool_default_coerces_via_truthiness(
    make_property_class: Any, pspec_default: Any, default: Any, expected: Any
) -> None:
    cls = make_property_class(bool, default=default)
    assert pspec_default(cls.gimeta.pspecs["x"]) is expected


def test_string_default_for_int_field_raises(GObject: Any, Property: Any) -> None:
    with pytest.raises(TypeError):

        class Foo(GObject):  # type: ignore[misc]
            x: int = Property(default="not-a-number")


def test_list_default_for_str_field_raises(GObject: Any, Property: Any) -> None:
    with pytest.raises(TypeError):

        class Foo(GObject):  # type: ignore[misc]
            x: str = Property(default=[1, 2, 3])


def test_no_default_distinguishes_from_empty_default(
    GObject: Any, Property: Any, pspec_default: Any
) -> None:
    class Both(GObject):  # type: ignore[misc]
        unset: str = Property()
        empty: str = Property(default="")

    assert pspec_default(Both.gimeta.pspecs["unset"]) is None
    assert pspec_default(Both.gimeta.pspecs["empty"]) == ""


@pytest.mark.parametrize(
    "default",
    [
        pytest.param("a", id="ascii-single"),
        pytest.param("ASCII string", id="ascii-multi"),
        pytest.param("ñ", id="latin1"),
        pytest.param("中", id="cjk-single"),
        pytest.param("中文测试", id="cjk-multi"),
        pytest.param("🦀", id="single-emoji"),
        pytest.param("🦀🐍🏗️🎯", id="multi-emoji"),
        pytest.param("a̐éö̲", id="combining-marks"),
        pytest.param("​", id="zero-width-space"),
        pytest.param("hello\x00world", id="embedded-null"),
        pytest.param("trailing\n", id="trailing-newline"),
        pytest.param("\t\r\n\v\f", id="whitespace-mix"),
        pytest.param("x" * 100_000, id="100kb"),
    ],
)
def test_string_default_utf8_round_trip(
    make_property_class: Any, pspec_default: Any, default: Any
) -> None:
    cls = make_property_class(str, default=default)
    actual = pspec_default(cls.gimeta.pspecs["x"])
    assert actual == default.split("\x00", 1)[0]


def test_string_default_invalid_utf16_surrogate(GObject: Any, Property: Any) -> None:
    with pytest.raises((UnicodeEncodeError, ValueError)):

        class Foo(GObject):  # type: ignore[misc]
            x: str = Property(default="\ud800")
