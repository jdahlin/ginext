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

"""UTF-8 string argument/return marshalling."""

from __future__ import annotations

import pytest


def test_string_return() -> None:
    from ginext import GLib

    name = GLib.get_user_name()
    assert isinstance(name, str)
    assert len(name) > 0


def test_string_return_can_be_compared_to_str() -> None:
    from ginext import GLib

    a = GLib.get_user_name()
    b = GLib.get_user_name()
    assert a == b


def test_string_arg_round_trips_through_method() -> None:
    """A string argument passed to a GI function should reach C
    unchanged and any string return should decode back to Python str."""
    from ginext import GLib

    # GLib.uri_escape_string is a good utf8-in / utf8-out testbed.
    if not hasattr(GLib, "uri_escape_string"):
        pytest.skip("GLib.uri_escape_string not present")
    s = GLib.uri_escape_string("hello world", None, False)
    assert s == "hello%20world"


def test_unicode_string_round_trip() -> None:
    from ginext import GLib

    if not hasattr(GLib, "uri_escape_string"):
        pytest.skip("GLib.uri_escape_string not present")
    s = GLib.uri_escape_string("héllo", None, False)
    assert "%" in s  # non-ASCII is percent-encoded


def test_string_arg_rejects_non_string() -> None:
    from ginext import GLib

    if not hasattr(GLib, "uri_escape_string"):
        pytest.skip("GLib.uri_escape_string not present")
    with pytest.raises(TypeError):
        GLib.uri_escape_string(123, None, False)  # type: ignore[arg-type]


def test_null_string_arg_rejected_when_nonnullable() -> None:
    """Nullable args accept None; non-nullable args reject it."""
    from ginext import GLib

    if not hasattr(GLib, "uri_escape_string"):
        pytest.skip("GLib.uri_escape_string not present")
    with pytest.raises((TypeError, ValueError)):
        GLib.uri_escape_string(None, None, False)  # type: ignore[arg-type]
