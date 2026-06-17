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

"""Signal.emit path.

Tests the zero-arg fast path (Cancellable::cancelled) and the arg-
validation surface of the args path. Round-trip emit-with-args
coverage lands in tests/signal/test_python_defined_signals.py once
Python-defined signals exist.
"""

import pytest


def test_zero_arg_emit_fires_handlers() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    fires = []
    conn = c.cancelled.connect(lambda src: fires.append(1), owner=c)
    c.cancelled.emit()
    assert fires == [1]
    conn.disconnect()


def test_emit_with_args_rejects_wrong_arity() -> None:
    """Cancellable::cancelled has no args. Passing args must raise a
    helpful TypeError naming the expected count."""
    from ginext import Gio

    c = Gio.Cancellable()
    with pytest.raises(TypeError, match="expects 0 argument"):
        c.cancelled.emit("unexpected")  # type: ignore[call-arg]


def test_emit_with_args_for_zero_arg_signal_still_works_with_no_args() -> None:
    """The zero-arg path is preserved exactly; only adding args triggers
    the args codepath."""
    from ginext import Gio

    c = Gio.Cancellable()
    fires = []
    conn = c.cancelled.connect(lambda src: fires.append("z"), owner=c)
    c.cancelled.emit()
    c.cancelled.emit()
    assert fires == ["z", "z"]
    conn.disconnect()
