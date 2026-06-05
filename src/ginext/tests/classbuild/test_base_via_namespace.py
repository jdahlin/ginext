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

"""Base classes are reached through GObject namespace, not via top-level
ginext classes.

The documented spelling is:
    class MyObject(GObject.Object):
        ...
"""

from __future__ import annotations


def test_gobject_object_is_accessible_via_namespace() -> None:
    from ginext import GObject

    assert isinstance(GObject.Object, type)


def test_can_subclass_gobject_object_directly() -> None:
    from ginext import GObject

    class MyObj(GObject.Object):
        pass

    obj = MyObj()
    assert isinstance(obj, GObject.Object)
    assert isinstance(obj, MyObj)


def test_no_top_level_gobjectbase_attribute() -> None:
    import ginext

    assert not hasattr(ginext, "GObjectBase")


def test_subclass_registers_with_gtype() -> None:
    from ginext import GObject

    class Trackable(GObject.Object):
        pass

    # Newly registered class must have a non-zero GType.
    gtype = Trackable.gimeta.gtype
    assert gtype is not None
    assert int(gtype) != 0


def test_subclasses_share_wrapper_identity_machinery() -> None:
    """Imported GObject classes and Python-defined subclasses should
    share the same wrapper identity machinery (qdata)."""
    from ginext import Gio

    class MyCancellable(Gio.Cancellable):
        pass

    obj = MyCancellable()
    # GObject.Object.ref() returns the same native pointer through invoke,
    # so qdata should preserve the exact Python wrapper.
    wrapped_again = obj.ref()
    assert wrapped_again is obj
