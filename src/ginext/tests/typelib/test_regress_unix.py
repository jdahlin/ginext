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

from .support import open_namespace_for_test


@pytest.fixture
def t(call_mode: Any) -> Any:
    # RegressUnix exercises POSIX-only types (dev_t/gid_t/pid_t/socklen_t/uid_t)
    # and its typelib is not built on non-Unix platforms (e.g. Windows).
    try:
        return open_namespace_for_test(call_mode, "RegressUnix", "1.0")
    except ImportError:
        pytest.skip("RegressUnix typelib not available on this platform")


def test_devt(t: Any) -> None:
    assert t.test_devt(1234) == 1234


def test_gidt(t: Any) -> None:
    assert t.test_gidt(1234) == 1234


def test_pidt(t: Any) -> None:
    assert t.test_pidt(1234) == 1234


def test_socklent(t: Any) -> None:
    assert t.test_socklent(1234) == 1234


def test_uidt(t: Any) -> None:
    assert t.test_uidt(1234) == 1234
