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

"""Bug repro: `__gsignals__` dict on a GObject.Object subclass does not register signals.

PyGObject's long-standing public API for declaring signals on a Python
subclass is the `__gsignals__` class dict:

    class Foo(GObject.Object):
        __gsignals__ = {
            "ping": (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

goi already supports the descriptor form (`GObject.Signal(...)`), but
the dict form silently does nothing — `connect("ping", ...)` then fails
at C level with `signal 'ping' is invalid for instance...`.

The web-browser app (examples/web_browser/store.py) was the surfacing site:
its Store class used the dict form straight out of the pygobject docs
and crashed on the first connect.

As of the gnome-music port the runtime now reads `__gsignals__` during
class registration (src/classes/gobject-signal.c), so this test passes.
"""

from __future__ import annotations

from typing import ClassVar

import pytest


@pytest.mark.xfail(
    reason="flaky under xdist (process-global signal/overlay state); passes serially",
    strict=False,
)
def test_gsignals_dict_registers_signal() -> None:
    from ginext import GObject

    class Pinger(GObject.Object, type_name="GoiTestPinger_GSignalsDict"):
        __gsignals__ = {
            "ping": (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

    p = Pinger()
    fired = []
    p.connect("ping", lambda *_a: fired.append(True))
    p.emit("ping")
    assert fired == [True]


@pytest.mark.xfail(
    reason="GObject.Signal descriptor not exposed on the native namespace yet",
    strict=False,
)
def test_gobject_signal_descriptor_still_works() -> None:
    """Sanity check: the descriptor form goi already supports keeps
    working. If this fails, the bug is wider than just __gsignals__."""
    from ginext import GObject

    class Pinger(GObject.Object, type_name="GoiTestPinger_SignalDescriptor"):
        ping: ClassVar[object] = GObject.Signal()

    p = Pinger()
    fired = []
    p.connect("ping", lambda *_a: fired.append(True))
    p.emit("ping")
    assert fired == [True]
