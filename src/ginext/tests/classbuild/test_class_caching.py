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

"""Built classes are cached by namespace/version/name and by GType."""

from __future__ import annotations


def test_repeated_access_returns_same_class() -> None:
    from ginext import Gio

    a = Gio.Cancellable
    b = Gio.Cancellable
    assert a is b


def test_class_identity_across_from_imports() -> None:
    from ginext import Gio as gio1
    from ginext import Gio as gio2

    assert gio1.Cancellable is gio2.Cancellable


def test_returned_instance_uses_cached_class() -> None:
    """A method that returns a GObject of a known class wraps it with
    the same class object as direct attribute access yields."""
    from ginext import Gio

    cls = Gio.Cancellable
    obj = Gio.Cancellable()
    assert type(obj) is cls


def test_lookup_by_gtype_returns_cached_class() -> None:
    """Wrapping a returned pointer should use the class cache keyed by
    GType, returning the same class as namespace attribute access."""
    from ginext import Gio

    cls_by_attr = Gio.SimpleAction
    returned = Gio.SimpleAction.new("demo", None)
    assert type(returned) is cls_by_attr
