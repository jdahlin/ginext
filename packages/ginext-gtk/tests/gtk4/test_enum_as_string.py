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

"""Enum-valued construction kwargs accept the enum nick as a string.

Relocated from the core enum tests: the string-to-enum coercion is core, but
this case is expressed through Gtk.Box's `orientation`, so it lives in the Gtk
suite.
"""

from __future__ import annotations


def test_enum_as_string() -> None:
    from ginext import Gtk

    box = Gtk.Box(orientation="vertical")
    assert box.get_property("orientation") == Gtk.Orientation.VERTICAL
