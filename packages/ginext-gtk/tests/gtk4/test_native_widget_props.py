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

"""Subclassing a native widget and adding properties.

A Python subclass of a native Gtk widget can declare its own ``Property()``
fields and still reach every inherited (introspected) widget property as a plain
attribute — declared and inherited properties read/write the same way.
"""

from __future__ import annotations

from typing import Any


def test_subclass_native_widget_mixes_declared_and_inherited() -> None:
    from ginext import GObject, Gtk

    class LabelledBox(Gtk.Box):
        caption: str = GObject.Property(default="untitled")

    box = LabelledBox(orientation="vertical", spacing=6)

    # Declared field on the subclass.
    assert box.caption == "untitled"
    box.caption = "Sidebar"
    assert box.caption == "Sidebar"

    # Inherited introspected widget properties, as plain attributes.
    assert box.orientation == Gtk.Orientation.VERTICAL
    assert box.spacing == 6
    box.spacing = 12
    assert box.spacing == 12

    # The synthesized fields advertise themselves in __annotations__.
    annotations = type(box).__annotations__
    assert "caption" in annotations
    assert "spacing" in annotations


def test_inherited_widget_property_reads_on_plain_instance() -> None:
    from ginext import Gtk

    box: Any = Gtk.Box(orientation="horizontal", spacing=3)
    assert box.orientation == Gtk.Orientation.HORIZONTAL
    assert box.spacing == 3
