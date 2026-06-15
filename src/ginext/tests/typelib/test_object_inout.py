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

"""OUT GObject argument marshalling.

GIMarshallingTests.Object has four shapes:
* full_out          — OUT, transfer-full      (supported, exercised here)
* none_out          — OUT, transfer-none      (supported, exercised here)
* full_inout        — INOUT, transfer-full    (supported, exercised here)
* none_inout        — INOUT, transfer-none    (supported, exercised here)
"""

from __future__ import annotations

from typing import Any

import pytest

from .support import open_namespace_for_test


@pytest.fixture
def t(call_mode: Any) -> Any:
    return open_namespace_for_test(call_mode, "GIMarshallingTests", "1.0")


def _is_marshall_object(obj: Any, t: Any) -> bool:
    return obj is not None and isinstance(obj, t.Object)


def test_object_full_out_returns_object(t: Any) -> None:
    """OUT-only transfer-full returns a freshly-allocated wrapper."""
    obj = t.Object.full_out()
    assert _is_marshall_object(obj, t)
    assert obj.__grefcount__ == 1


def test_object_none_out_returns_object(t: Any) -> None:
    """OUT-only transfer-none returns a borrowed wrapper around a
    static instance."""
    obj = t.Object.none_out()
    assert _is_marshall_object(obj, t)
    assert obj.__grefcount__ == 2


def test_object_full_inout_returns_replacement(t: Any) -> None:
    original = t.Object(int=42)
    result = t.Object.full_inout(original)
    assert _is_marshall_object(result, t)
    assert result is not original
    assert original.__grefcount__ == 1
    assert result.__grefcount__ == 1


def test_object_none_inout_returns_replacement(t: Any) -> None:
    original = t.Object(int=42)
    result = t.Object.none_inout(original)
    assert _is_marshall_object(result, t)
    assert result is not original
    assert original.__grefcount__ == 1
    assert result.__grefcount__ == 2
