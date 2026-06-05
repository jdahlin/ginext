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

"""Floating-point argument/return marshalling."""

from __future__ import annotations

import pytest


def test_double_return() -> None:
    from ginext import GLib

    v = GLib.random_double()
    assert isinstance(v, float)
    assert 0.0 <= v < 1.0


def test_double_range_return() -> None:
    from ginext import GLib

    v = GLib.random_double_range(1.5, 2.5)
    assert 1.5 <= v < 2.5
    assert isinstance(v, float)


def test_float_arg_accepts_int_promotion() -> None:
    from ginext import GLib

    v = GLib.random_double_range(0, 10)
    assert 0.0 <= v < 10.0


def test_float_arg_rejects_string() -> None:
    from ginext import GLib

    with pytest.raises(TypeError):
        GLib.random_double_range("0.0", 1.0)  # type: ignore[arg-type]
