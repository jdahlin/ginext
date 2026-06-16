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

"""Parent chain: Python classes built from GI info reflect the GObject
inheritance hierarchy.

In-scope: GObject -> concrete subclass. Interfaces are out of scope
for the first pass.
"""

from __future__ import annotations


def test_cancellable_inherits_from_gobject_object() -> None:
    from ginext import Gio, GObject

    assert issubclass(Gio.Cancellable, GObject.Object)


def test_mro_terminates_at_object() -> None:
    from ginext import Gio

    mro = Gio.Cancellable.__mro__
    assert mro[-1] is object


def test_mro_contains_gobject_object() -> None:
    from ginext import Gio, GObject

    assert GObject.Object in Gio.Cancellable.__mro__


def test_parent_class_is_a_namespace_member() -> None:
    """Parent classes resolve through their owning namespace, not via a
    private base class on ginext."""
    from ginext import GObject, Gio

    # The immediate Python parent of Cancellable is GObject.Object
    # (since Cancellable has no intermediate concrete parent).
    bases = [b for b in Gio.Cancellable.__bases__ if isinstance(b, type)]
    assert GObject.Object in bases


def test_parent_methods_are_callable_on_child_instance() -> None:
    from ginext import Gio

    cancellable = Gio.Cancellable()
    assert cancellable.is_floating() is False
    cancellable.freeze_notify()
    cancellable.thaw_notify()


def test_subclassing_imported_class_in_python() -> None:
    """Pure-Python subclasses of imported classes should be supported."""
    from ginext import Gio

    class MyCancellable(Gio.Cancellable):
        pass

    obj = MyCancellable()
    assert isinstance(obj, MyCancellable)
    assert isinstance(obj, Gio.Cancellable)


def test_subclassing_imported_class_with_python_mixin_first() -> None:
    from ginext import Gio

    class Mixin:
        pass

    class MyCancellable(Mixin, Gio.Cancellable):
        pass

    obj = MyCancellable()
    assert isinstance(obj, MyCancellable)
    assert isinstance(obj, Gio.Cancellable)
    assert Mixin in MyCancellable.__mro__
    assert Gio.Cancellable in MyCancellable.__mro__


def test_implemented_interfaces_are_in_mro() -> None:
    from ginext import Gio

    assert Gio.ActionMap in Gio.SimpleActionGroup.__mro__
    assert Gio.ActionGroup in Gio.SimpleActionGroup.__mro__


def test_interface_methods_are_callable_on_implementing_class() -> None:
    from ginext import Gio

    group = Gio.SimpleActionGroup()
    action = Gio.SimpleAction.new("close", None)
    group.add_action(action)

    assert group.lookup_action("close") is action
