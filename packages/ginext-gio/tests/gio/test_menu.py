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


def test_menu_and_menu_item_are_constructible() -> None:
    from ginext import Gio

    assert isinstance(Gio.Menu(), Gio.Menu)
    assert isinstance(Gio.MenuItem(), Gio.MenuItem)


def test_menu_item_set_attribute_list_form() -> None:
    """Copied from PyGObject's Gio.MenuItem coverage for future compat work."""
    from ginext import GLib, Gio

    menu = Gio.Menu()
    item = Gio.MenuItem()
    item.set_attribute([("label", "s", "Test"), ("action", "s", "app.test")])
    menu.append_item(item)

    value = menu.get_item_attribute_value(0, "label", GLib.VariantType.new("s"))
    assert value is not None
    assert value.unpack() == "Test"
    value = menu.get_item_attribute_value(0, "action", GLib.VariantType.new("s"))
    assert value is not None
    assert value.unpack() == "app.test"


def test_menu_append_exposes_label_and_action_attributes() -> None:
    from ginext import Gio

    menu = Gio.Menu()
    menu.append("Open", "app.open")

    assert menu.get_n_items() == 1
    label_val = menu.get_item_attribute_value(0, "label", None)
    assert label_val is not None
    assert label_val.unpack() == "Open"
    action_val = menu.get_item_attribute_value(0, "action", None)
    assert action_val is not None
    assert action_val.unpack() == "app.open"


def test_menu_append_submenu_exposes_linked_menu_model() -> None:
    from ginext import Gio

    menu = Gio.Menu()
    submenu = Gio.Menu()
    submenu.append("Child", "app.child")

    menu.append_submenu("More", submenu)

    linked = menu.get_item_link(0, "submenu")

    assert linked is not None
    assert isinstance(linked, Gio.MenuModel)
    assert linked.get_n_items() == 1
    child_val = linked.get_item_attribute_value(0, "label", None)
    assert child_val is not None
    assert child_val.unpack() == "Child"


def test_menu_item_set_attribute_with_no_value_clears_attribute() -> None:
    from ginext import Gio

    menu = Gio.Menu()
    item = Gio.MenuItem()
    item.set_attribute("label", "s", "Test")
    item.set_attribute("label")
    menu.append_item(item)

    assert menu.get_item_attribute_value(0, "label", None) is None
