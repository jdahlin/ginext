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


def test_return_value_round_trips_glib_bytes_without_explicit_gvalue() -> None:
    from ginext import Gio, GLib

    task = Gio.Task.new(None, None, None)
    payload = GLib.Bytes.new(b"abc")

    task.return_value(payload)
    ok, result = task.propagate_value()

    assert ok is True
    assert isinstance(result, GLib.Bytes)
    assert result.equal(payload) is True


def test_return_value_round_trips_gobject_instance_without_explicit_gvalue() -> None:
    from ginext import Gio, GObject

    class Item(GObject.Object):
        pass

    task = Gio.Task.new(None, None, None)
    payload = Item()

    task.return_value(payload)
    ok, result = task.propagate_value()

    assert ok is True
    assert result is payload
