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

from __future__ import annotations


def test_new_for_value_accepts_gobject_instance_without_explicit_gvalue() -> None:
    from ginext import Gdk, GObject

    class Item(GObject.Object):
        pass

    provider = Gdk.ContentProvider.new_for_value(
        Item()
    )  # Item is a GObject but stubs expect Value

    assert isinstance(provider, Gdk.ContentProvider)


def test_new_for_value_accepts_strv_without_explicit_gvalue() -> None:
    from ginext import Gdk

    provider = Gdk.ContentProvider.new_for_value(
        ["first", "second"]
    )  # list[str] (strv) is accepted at runtime

    assert isinstance(provider, Gdk.ContentProvider)
