# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

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

class _GTypeCarrier:
    def __init__(self, gtype: object) -> None:
        self.__gtype__ = gtype


def test_new_with_properties_accepts_gobject_class() -> None:
    from ginext import Gio, GObject

    obj = GObject.new_with_properties(Gio.Cancellable, {})
    assert isinstance(obj, Gio.Cancellable)


def test_new_with_properties_accepts_gtype_object() -> None:
    from ginext import Gio, GObject

    obj = GObject.new_with_properties(Gio.Cancellable.gimeta.gtype, {})
    assert isinstance(obj, Gio.Cancellable)


def test_new_with_properties_accepts_object_with_gtype() -> None:
    from ginext import Gio, GObject

    obj = GObject.new_with_properties(_GTypeCarrier(Gio.Cancellable.gimeta.gtype), {})
    assert isinstance(obj, Gio.Cancellable)


def test_new_with_properties_accepts_gobject_instance_as_type() -> None:
    from ginext import Gio, GObject

    obj = GObject.new_with_properties(Gio.Cancellable(), {})
    assert isinstance(obj, Gio.Cancellable)


def test_interface_list_properties_accepts_gtype_object() -> None:
    from ginext import Gio, GObject

    props = GObject.interface_list_properties(Gio.Action.gimeta.gtype)
    assert any(p.name == "enabled" for p in props)


def test_interface_list_properties_accepts_object_with_gtype() -> None:
    from ginext import Gio, GObject

    props = GObject.interface_list_properties(_GTypeCarrier(Gio.Action.gimeta.gtype))
    assert any(p.name == "name" for p in props)


def test_invoke_gtype_argument_accepts_object_with_gtype() -> None:
    from ginext import Gio

    store = Gio.ListStore(item_type=_GTypeCarrier(Gio.FileInfo.gimeta.gtype))
    assert isinstance(store, Gio.ListStore)


def test_invoke_gtype_argument_accepts_gobject_instance_as_type() -> None:
    from ginext import Gio

    store = Gio.ListStore(item_type=Gio.FileInfo())
    assert isinstance(store, Gio.ListStore)
