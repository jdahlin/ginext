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

"""Enum and flags marshalling as plain integers."""

from __future__ import annotations


def test_enum_return_is_plain_int() -> None:
    from ginext import GLib

    value = GLib.unichar_type("A")
    assert isinstance(value, int)


def test_enum_return_can_be_passed_back_as_arg() -> None:
    from ginext import GLib

    script = GLib.unichar_get_script("A")
    iso15924 = GLib.unicode_script_to_iso15924(script)
    assert isinstance(iso15924, int)
    assert iso15924 != 0


def test_flags_arg_accepts_plain_int() -> None:
    from ginext import GLib

    formatted = GLib.format_size_full(1024, 0)
    assert isinstance(formatted, str)
    assert formatted
