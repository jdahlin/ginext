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

import pytest


from typing import Any


@pytest.mark.parametrize(
    ("format_string", "value", "getter", "expected"),
    [
        pytest.param("b", True, "get_boolean", True, id="boolean"),
        pytest.param("i", 42, "get_int32", 42, id="int32"),
        pytest.param("s", "hello", "get_string", "hello", id="string"),
    ],
)
def test_simple_variant_constructor(
    format_string: str, value: Any, getter: str, expected: Any
) -> None:
    from ginext import GLib

    variant = GLib.Variant(format_string, value)

    assert isinstance(variant, GLib.Variant)
    assert variant.get_type_string() == format_string
    assert getattr(variant, getter)() == expected


def test_new_tuple_accepts_varargs() -> None:
    from ginext import GLib

    variant = GLib.Variant.new_tuple(
        GLib.Variant("i", -1),
        GLib.Variant("s", "hello"),
    )

    assert variant.unpack() == (-1, "hello")


def test_variant_unpack() -> None:
    from ginext import GLib

    variant = GLib.Variant("((si)(ub))", (("hello", -1), (42, True)))

    assert variant.unpack() == (("hello", -1), (42, True))
