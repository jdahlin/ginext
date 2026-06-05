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

"""Nullable arguments accept None and pass NULL to the C call."""

from __future__ import annotations

import pytest


def test_nullable_string_arg_accepts_none() -> None:
    from ginext import GLib

    if not hasattr(GLib, "uri_escape_string"):
        pytest.skip("GLib.uri_escape_string not present")
    # `reserved_chars_allowed` (2nd arg) is nullable.
    s = GLib.uri_escape_string("abc def", None, False)
    assert s == "abc%20def"


def test_non_nullable_string_arg_rejects_none() -> None:
    from ginext import GLib

    if not hasattr(GLib, "uri_escape_string"):
        pytest.skip("GLib.uri_escape_string not present")
    with pytest.raises((TypeError, ValueError)):
        GLib.uri_escape_string(None, None, False)  # type: ignore[arg-type]
