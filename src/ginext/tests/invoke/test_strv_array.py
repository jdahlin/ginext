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

"""Zero-terminated string array returns."""

from __future__ import annotations


def test_strv_return_is_list_of_strings() -> None:
    from ginext import GLib

    values = GLib.get_language_names()
    assert isinstance(values, list)
    assert values
    assert all(isinstance(value, str) for value in values)


def test_strv_return_can_be_called_twice() -> None:
    from ginext import GLib

    first = GLib.get_language_names()
    second = GLib.get_language_names()
    assert first == second
