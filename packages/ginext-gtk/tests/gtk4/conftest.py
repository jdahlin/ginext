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

import sys
from typing import Any

import pytest


@pytest.fixture
def require_gtk4_display(request: pytest.FixtureRequest) -> Any:
    # A real display is needed for widget instantiation. On Unix that means a
    # Wayland/X compositor (the `wayland` fixture spins up weston); on Windows
    # the win32 GDK backend always provides one, so the Wayland fixture is not
    # relevant there.
    if sys.platform != "win32":
        request.getfixturevalue("wayland")

    from ginext import Gdk, Gtk

    if Gtk.get_major_version() != 4:
        pytest.skip("requires Gtk-4.0")
    ok = Gtk.init_check()
    if isinstance(ok, tuple):
        ok = ok[0]
    if not ok:
        pytest.skip("GTK widget instantiation requires a real display")
    if Gdk.Display.get_default() is None:
        pytest.skip("GTK widget instantiation requires a real display")

    return Gtk
