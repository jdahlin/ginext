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

"""Error shape for unknown members on a namespace."""

from __future__ import annotations

import pytest


def test_unknown_member_raises_attribute_error() -> None:
    from ginext import Gio

    with pytest.raises(AttributeError):
        Gio.ThisDoesNotExistXYZ


def test_unknown_member_error_names_namespace_and_attr() -> None:
    from ginext import Gio

    with pytest.raises(AttributeError) as excinfo:
        Gio.ThisDoesNotExistXYZ
    msg = str(excinfo.value)
    assert "Gio" in msg
    assert "ThisDoesNotExistXYZ" in msg


def test_getattr_with_default_returns_default_for_missing_member() -> None:
    from ginext import Gio

    sentinel = object()
    assert getattr(Gio, "Nope", sentinel) is sentinel


def test_unknown_member_does_not_pollute_dir() -> None:
    from ginext import Gio

    before = set(dir(Gio))
    with pytest.raises(AttributeError):
        Gio.ThisDoesNotExistXYZ
    after = set(dir(Gio))
    assert before == after
