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

"""Module-like behavior on the namespace object.

The plan: the namespace should be module-like enough for normal Python
behavior (dir(), repr, __name__, __version__).
"""

from __future__ import annotations


def test_has_name_attribute() -> None:
    from ginext import GLib

    assert GLib.__name__ == "GLib"


def test_has_version_attribute() -> None:
    from ginext import GLib

    assert isinstance(GLib.__version__, tuple)
    assert all(isinstance(c, int) for c in GLib.__version__)
    assert GLib.__version__[0] >= 2


def test_dir_lists_known_members() -> None:
    from ginext import Gio

    listed = dir(Gio)
    assert "Cancellable" in listed


def test_dir_lists_known_functions() -> None:
    from ginext import GLib

    listed = dir(GLib)
    assert "get_user_name" in listed


def test_repr_includes_namespace_and_version() -> None:
    from ginext import GLib

    r = repr(GLib)
    assert "GLib" in r
    assert "2.0" in r


def test_namespace_supports_getattr_with_default() -> None:
    from ginext import Gio

    sentinel = object()
    assert getattr(Gio, "NoSuchAttr_XYZ", sentinel) is sentinel
