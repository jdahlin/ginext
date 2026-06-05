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

"""Abstract GObject types must be rejected at construction time."""

from __future__ import annotations

import pytest


def test_constructing_abstract_class_raises() -> None:
    from ginext import GObject

    candidates = []
    if hasattr(GObject, "InitiallyUnowned"):
        candidates.append(GObject.InitiallyUnowned)

    if not candidates:
        pytest.skip("no abstract class available to probe")

    saw_abstract = False
    for cls in candidates:
        if not getattr(cls, "__gtype_is_abstract__", False):
            continue
        saw_abstract = True
        with pytest.raises(TypeError) as excinfo:
            cls()
        msg = str(excinfo.value).lower()
        assert "abstract" in msg

    if not saw_abstract:
        pytest.skip("no abstract class available to probe")
