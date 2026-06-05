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

"""`once=True` auto-disconnect semantics.

The closure marshal disconnects the handler before invoking the Python
callback when `once=True`. This guarantees a re-entrant emit inside the
callback does not see the same handler again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ginext import Gio


def test_once_fires_and_self_disconnects(cancellable: Gio.Cancellable) -> None:
    fires = []
    conn = cancellable.cancelled.connect(
        lambda src: fires.append(1), owner=cancellable, once=True
    )
    assert conn.once is True
    original_id = conn.handler_id
    assert original_id != 0
    cancellable.cancel()
    assert fires == [1]
    # `is_connected` queries the live GSignal state; after the marshal's
    # self-disconnect it must be False even though the handle's cached
    # handler_id is preserved as a historical identifier.
    assert not conn.is_connected


def test_once_records_flag_on_handle(cancellable: Gio.Cancellable) -> None:
    conn = cancellable.cancelled.connect(lambda src: None, owner=cancellable, once=True)
    assert conn.once is True
    conn.disconnect()


def test_once_with_after_flag_composes(cancellable: Gio.Cancellable) -> None:
    """Both flags should compose orthogonally — the handler runs after the
    default handler and self-disconnects in one emit."""
    fires = []
    conn = cancellable.cancelled.connect(
        lambda src: fires.append("after"),
        owner=cancellable,
        after=True,
        once=True,
    )
    cancellable.cancel()
    assert fires == ["after"]
    assert not conn.is_connected


def test_once_disconnect_before_callback_runs(cancellable: Gio.Cancellable) -> None:
    """If the once-handler emits the same signal recursively, the second
    emission must not see this handler. Cancellable.cancelled is a one-shot
    signal so we can't truly re-emit it; instead, observe is_connected
    *from inside* the handler — it should already be disconnected."""
    states = []

    def handler(src: Gio.Cancellable) -> None:
        # Drain the connection's state at call time. After the marshal's
        # disconnect-before-call, the handler_id has been cleared.
        states.append(conn.is_connected)

    conn = cancellable.cancelled.connect(handler, owner=cancellable, once=True)
    cancellable.cancel()
    assert states == [False]
