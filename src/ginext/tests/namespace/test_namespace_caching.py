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

"""Namespaces are cached: repeated access returns the same object."""

from __future__ import annotations


def test_repeated_attribute_access_returns_same_object() -> None:
    import ginext

    a = ginext.GLib
    b = ginext.GLib
    assert a is b


def test_attribute_and_from_import_return_same_object() -> None:
    import ginext
    from ginext import GLib

    assert ginext.GLib is GLib


def test_namespace_cache_survives_unrelated_access() -> None:
    import ginext

    glib_a = ginext.GLib
    _ = ginext.Gio
    glib_b = ginext.GLib
    assert glib_a is glib_b


def test_member_lookup_caches() -> None:
    """Looking up the same class on a namespace returns the same object."""
    from ginext import Gio

    a = Gio.Cancellable
    b = Gio.Cancellable
    assert a is b


def test_namespace_member_cache_survives_unrelated_lookup() -> None:
    from ginext import Gio

    cls_a = Gio.Cancellable
    _ = getattr(Gio, "File", None)  # may or may not be present
    cls_b = Gio.Cancellable
    assert cls_a is cls_b
