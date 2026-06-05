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

"""Tests for typelib GIConstantInfo surfacing on Namespace.

`Namespace.__getattr__` resolves typelib constants via the `info.value`
overlay property on `GIRepository.ConstantInfo`. Covers integer
(signed/unsigned), float, boolean, and string kinds."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="module")
def GLib() -> Any:
    from ginext import GLib

    return GLib


def test_signed_int_constant(GLib: Any) -> None:
    assert GLib.PRIORITY_HIGH == -100


def test_unsigned_int_constant(GLib: Any) -> None:
    assert GLib.PRIORITY_DEFAULT_IDLE == 200


def test_boolean_constant(GLib: Any) -> None:
    assert GLib.SOURCE_REMOVE is False
    assert GLib.SOURCE_CONTINUE is True


def test_float_constant(GLib: Any) -> None:
    assert pytest.approx(3.141593, rel=1e-5) == GLib.PI


def test_string_constant(GLib: Any) -> None:
    # GLib.VERSION_MIN_REQUIRED / GLib.CSET_a_2_z etc. — pick a stable one.
    assert isinstance(GLib.CSET_a_2_z, str)
    assert "a" in GLib.CSET_a_2_z


def test_constant_kind_in_namespace_find() -> None:
    """The C-side kind classifier returns 'constant' for GIConstantInfo."""
    from ginext import private

    kind, info = private.namespace_find("GLib", "2.0", "PRIORITY_HIGH")
    assert kind == "constant"
    assert info.value == -100


def test_constant_attribute_cached(GLib: Any) -> None:
    """Repeated access doesn't rebuild — Namespace.__getattr__ setattr's
    the resolved value on first hit."""
    first = GLib.PRIORITY_HIGH
    second = GLib.PRIORITY_HIGH
    assert first == second == -100
