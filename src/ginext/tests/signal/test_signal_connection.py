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

"""SignalConnection handle: attributes, disconnect, blocked() context."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ginext

if TYPE_CHECKING:
    from ginext import Gio


def test_handle_carries_metadata(cancellable: Gio.Cancellable) -> None:
    def cb(s: Gio.Cancellable) -> None:
        return None

    conn = cancellable.cancelled.connect(cb, owner=cancellable, after=True)
    assert isinstance(conn, ginext.SignalConnection)
    assert conn.handler_id != 0
    assert conn.source is cancellable
    assert conn.callback is cb
    assert conn.after is True
    assert conn.once is False
    assert conn.is_connected
    conn.disconnect()


def test_disconnect_is_idempotent(cancellable: Gio.Cancellable) -> None:
    conn = cancellable.cancelled.connect(lambda s: None, owner=cancellable)
    conn.disconnect()
    conn.disconnect()  # second call must not raise
    assert conn.handler_id == 0


def test_disconnect_via_signal_object_also_works(cancellable: Gio.Cancellable) -> None:
    """signal.disconnect(handle) and handle.disconnect() are equivalent."""
    conn = cancellable.cancelled.connect(lambda s: None, owner=cancellable)
    cancellable.cancelled.disconnect(conn)
    assert not conn.is_connected


def test_blocked_context_suppresses_handler(cancellable: Gio.Cancellable) -> None:
    fires = []
    conn = cancellable.cancelled.connect(lambda s: fires.append(1), owner=cancellable)
    with conn.blocked():
        cancellable.cancel()
    assert fires == []
    conn.disconnect()


def test_blocked_only_blocks_target_handler(cancellable: Gio.Cancellable) -> None:
    fires_a = []
    fires_b = []
    conn_a = cancellable.cancelled.connect(
        lambda s: fires_a.append(1), owner=cancellable
    )
    conn_b = cancellable.cancelled.connect(
        lambda s: fires_b.append(1), owner=cancellable
    )
    with conn_a.blocked():
        cancellable.cancel()
    assert fires_a == []
    assert fires_b == [1]
    conn_a.disconnect()
    conn_b.disconnect()


def test_blocked_unblocks_on_exception(cancellable: Gio.Cancellable) -> None:
    """The block/unblock pair must balance even if the body raises."""
    fires = []
    conn = cancellable.cancelled.connect(lambda s: fires.append(1), owner=cancellable)
    try:
        with conn.blocked():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    # After the block exits, the handler should fire normally.
    cancellable.cancel()
    assert fires == [1]
    conn.disconnect()


def test_repr_shows_state(cancellable: Gio.Cancellable) -> None:
    conn = cancellable.cancelled.connect(lambda s: None, owner=cancellable)
    assert "connected" in repr(conn)
    conn.disconnect()
    assert "disconnected" in repr(conn)
