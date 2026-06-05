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

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="module")
def GLib() -> Any:
    from ginext import GLib

    return GLib


@pytest.mark.parametrize(
    "constructor",
    [
        pytest.param("new", id="new"),
        pytest.param("new_take", id="new-take"),
    ],
)
def test_gbytes_create(GLib: Any, constructor: str) -> None:
    data = b"\x00\x01\xff"

    value = getattr(GLib.Bytes, constructor)(data)

    assert value.get_size() == 3
    assert value.get_data() == data


def test_gbytes_compare(GLib: Any) -> None:
    a1 = GLib.Bytes.new(b"\x00\x01\xff")
    a2 = GLib.Bytes.new(b"\x00\x01\xff")
    b = GLib.Bytes.new(b"\x00\x01\xfe")

    assert a1.equal(a2) is True
    assert a2.equal(a1) is True
    assert a1.equal(b) is False
    assert b.equal(a2) is False
    assert a1.compare(a2) == 0
    assert a1.compare(b) > 0
    assert b.compare(a1) < 0


@pytest.mark.parametrize(
    ("constructor", "args", "expected"),
    [
        pytest.param("new", (), b"", id="new"),
        pytest.param("new_take", (b"\x00\x01\xff",), b"\x00\x01\xff", id="new-take"),
    ],
)
def test_byte_array_constructors(
    GLib: Any, constructor: str, args: tuple[bytes, ...], expected: bytes
) -> None:
    assert getattr(GLib.ByteArray, constructor)(*args) == expected
