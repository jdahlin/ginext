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


def test_imports_scalar_namespace_function() -> None:
    from ginext import GLib

    assert isinstance(GLib.get_user_name(), str)


def test_constructs_concrete_gobject_and_invokes_method() -> None:
    from ginext import Gio

    cancellable = Gio.Cancellable()

    cancellable.cancel()
    assert cancellable.is_cancelled() is True


def test_gobject_return_uses_cached_class() -> None:
    from ginext import Gio

    cancellable = Gio.Cancellable()
    ref = cancellable.ref()

    assert type(ref) is Gio.Cancellable
    assert ref.is_cancelled() is False


def test_suffixed_import() -> None:
    from ginext import GLib2

    assert GLib2.__name__ == "GLib"
    assert GLib2.__version__ == (2, 0)
    assert isinstance(GLib2.get_user_name(), str)
