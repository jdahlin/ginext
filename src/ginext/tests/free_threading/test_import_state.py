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
import sysconfig

from . import support

pytestmark = support.pytestmark


def test_importing_ginext_does_not_enable_gil() -> None:
    assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
    assert not sys._is_gil_enabled()

    import ginext.private
    from ginext import Gio, GLib, GObject

    assert ginext.private is not None
    assert Gio is not None
    assert GLib is not None
    assert GObject is not None
    assert not sys._is_gil_enabled()
