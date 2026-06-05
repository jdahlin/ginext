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

from ..conftest import NUMERIC_BOUNDS_TYPES, read_numeric_pspec


def assert_numeric(actual: Any, expected: Any) -> None:
    if isinstance(expected, float):
        assert actual == pytest.approx(expected)
    else:
        assert actual == expected


@pytest.mark.parametrize("case", NUMERIC_BOUNDS_TYPES)
def test_numeric_pspec_bounds_match_property_bounds(
    GType: Any, make_property_class: Any, pspec_default: Any, case: Any
) -> None:
    cls = make_property_class(
        getattr(GType, case.constant),
        default=case.default,
        minimum=case.minimum,
        maximum=case.maximum,
    )

    pspec = read_numeric_pspec(cls.gimeta.pspecs["x"])
    assert_numeric(pspec.minimum, case.minimum)
    assert_numeric(pspec.maximum, case.maximum)
    assert_numeric(pspec.default_value, case.default)
    assert_numeric(pspec_default(cls.gimeta.pspecs["x"]), case.default)


@pytest.mark.parametrize("case", NUMERIC_BOUNDS_TYPES)
def test_numeric_default_outside_explicit_bounds_raises(
    GType: Any, GObject: Any, Property: Any, case: Any
) -> None:
    annotation = getattr(GType, case.constant)
    with pytest.raises((OverflowError, ValueError)):

        class Foo(GObject):  # type: ignore[misc]
            x: annotation = Property(  # type: ignore[valid-type]
                default=case.maximum + 1,
                minimum=case.minimum,
                maximum=case.maximum,
            )


@pytest.mark.parametrize("case", NUMERIC_BOUNDS_TYPES)
def test_numeric_minimum_greater_than_maximum_raises(
    GType: Any, GObject: Any, Property: Any, case: Any
) -> None:
    annotation = getattr(GType, case.constant)
    with pytest.raises(ValueError):

        class Foo(GObject):  # type: ignore[misc]
            x: annotation = Property(  # type: ignore[valid-type]
                default=case.default,
                minimum=case.maximum,
                maximum=case.minimum,
            )
