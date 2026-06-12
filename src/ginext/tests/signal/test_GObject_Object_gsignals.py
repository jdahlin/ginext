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

"""__gsignals__ dict and GObject.Signal descriptor registration tests.

PyGObject's long-standing public API for declaring signals on a Python
subclass is the `__gsignals__` class dict:

    class Foo(GObject.Object):
        __gsignals__ = {
            "ping": (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

ginext also supports the descriptor form (`GObject.Signal(...)`), and
that form is the native ginext way to declare signals.

The dict form is only processed when PYGOBJECT_COMPAT is enabled.
"""

from __future__ import annotations

from typing import ClassVar

import pytest


def test_gsignals_dict_ignored_in_native_mode() -> None:
    from ginext import GObject

    # __gsignals__ is a compat-only feature; native ginext ignores it silently
    class Pinger(GObject.Object, type_name="GoiTestPinger_GSignalsDict"):
        __gsignals__ = {
            "ping": (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

    assert "ping" not in Pinger.gimeta.signal_infos


def test_gobject_signal_descriptor_still_works() -> None:
    """GObject.Signal() descriptor form registers the signal and is accessible."""
    from ginext import GObject

    class Pinger(GObject.Object, type_name="GoiTestPinger_SignalDescriptor"):
        ping: ClassVar[object] = GObject.Signal()

    p = Pinger()
    fired = []
    conn = p.ping.connect(lambda *_a: fired.append(True), owner=p)
    p.ping.emit()
    conn.disconnect()
    assert fired == [True]
