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


def test_get_objects_returns_object_list_without_display() -> None:
    from ginext import GObject, Gtk

    builder = Gtk.Builder.new_from_string(
        """
        <interface>
          <object class="GtkAdjustment" id="adjustment">
            <property name="upper">10</property>
          </object>
        </interface>
        """,
        -1,
    )

    objects = builder.get_objects()

    assert len(objects) == 1
    assert isinstance(objects[0], Gtk.Adjustment)
    assert isinstance(objects[0], GObject.Object)


def test_builder_collection_dunders_without_display() -> None:
    from ginext import Gtk

    builder = Gtk.Builder.new_from_string(
        """
        <interface>
          <object class="GtkAdjustment" id="adjustment-a">
            <property name="upper">10</property>
          </object>
          <object class="GtkAdjustment" id="adjustment-b">
            <property name="upper">20</property>
          </object>
        </interface>
        """,
        -1,
    )

    objects = builder.get_objects()

    assert len(builder) == 2
    assert list(builder) == objects
    assert objects[0] in builder
    assert object() not in builder
