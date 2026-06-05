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

"""Signed and unsigned integer argument/return marshalling."""

from __future__ import annotations

from typing import Any

import pytest


def test_int_arg_and_return() -> None:
    """abs()-style scalar passthrough.

    GLib.random_int_range(low, high) takes two ints and returns an int.
    """
    from ginext import GLib

    v = GLib.random_int_range(0, 10)
    assert isinstance(v, int)
    assert 0 <= v < 10


def test_uint_return() -> None:
    from ginext import GLib

    v = GLib.random_int()
    assert isinstance(v, int)
    assert v >= 0


@pytest.mark.parametrize("low,high", [(0, 1), (-5, 5), (100, 200)])
def test_int_range_respects_bounds(low: Any, high: Any) -> None:
    from ginext import GLib

    for _ in range(20):
        v = GLib.random_int_range(low, high)
        assert low <= v < high


def test_int_arg_overflow_raises() -> None:
    """Passing a Python int that doesn't fit the target C width must
    raise OverflowError, not silently truncate."""
    from ginext import GLib

    with pytest.raises((OverflowError, ValueError)):
        GLib.random_int_range(2**63, 2**63 + 1)


def test_int_arg_type_check() -> None:
    """A non-int (e.g. string) must raise TypeError."""
    from ginext import GLib

    with pytest.raises(TypeError):
        GLib.random_int_range("0", 10)  # type: ignore[arg-type]
