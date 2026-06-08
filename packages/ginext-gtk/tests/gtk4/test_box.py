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

"""Gtk.Box construct property behavior."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.parametrize("orientation", [0, "horizontal"])
def test_enum_typed_construct_property_is_accepted(
    orientation: object, require_gtk4_display: Any
) -> None:
    pytest.importorskip("ginext")
    Gtk = require_gtk4_display

    if not hasattr(Gtk, "Box"):
        pytest.skip("Gtk.Box not present")

    box = Gtk.Box(orientation=orientation)

    assert box.get_property("orientation") == Gtk.Orientation.HORIZONTAL


def test_box_append_real_widget_child(require_gtk4_display: Any) -> None:
    Gtk = require_gtk4_display

    box = Gtk.Box()
    child = Gtk.Label(label="row")
    box.append(child)

    assert box.get_first_child() is child


def test_box_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    box = Gtk.Box()
    first = Gtk.Label(label="first")
    second = Gtk.Label(label="second")

    box.append(first)
    box.append(second)

    assert len(box) == 2
    assert list(box) == [first, second]
