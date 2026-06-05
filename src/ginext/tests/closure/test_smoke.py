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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Smoke tests for the ported closure layer.

Calls the native GObjectBase.signal_connect entry
point directly against a real GObject signal (Gio.Cancellable::cancelled)
to verify the GClosure subclass, closure record, source weak edge, and
disconnect path all work before the abi2 attribute machinery lands.
"""

from __future__ import annotations

import gc
import sys
import weakref
from typing import Any

import pytest

import ginext


def _handler_disconnect(source: Any, handler_id: int) -> None:
    ginext.GObject.signal_handler_disconnect(source, handler_id)


def _handler_is_connected(source: Any, handler_id: int) -> bool:
    return bool(ginext.GObject.signal_handler_is_connected(source, handler_id))


def _raw_signal_connect(
    source: Any, name: str, callback: object, after: bool = False
) -> int:
    return int(source.signal_connect(name, callback, after, False, None, None, -1))


def test_connect_fires_callback_on_emit(cancellable: Any) -> None:
    seen = []
    handler_id = _raw_signal_connect(
        cancellable, "cancelled", lambda source: seen.append("fired")
    )
    assert handler_id != 0
    assert _handler_is_connected(cancellable, handler_id)

    cancellable.cancel()
    assert seen == ["fired"]


def test_disconnect_prevents_subsequent_fire(cancellable: Any) -> None:
    seen = []
    handler_id = _raw_signal_connect(
        cancellable, "cancelled", lambda source: seen.append(1)
    )
    _handler_disconnect(cancellable, handler_id)
    assert not _handler_is_connected(cancellable, handler_id)

    cancellable.cancel()
    assert seen == []


def test_unknown_signal_raises() -> None:
    from ginext import Gio

    c = Gio.Cancellable()
    with pytest.raises(ValueError, match="no such signal"):
        _raw_signal_connect(c, "no-such-signal", lambda *_: None)


def test_non_callable_raises(cancellable: Any) -> None:
    with pytest.raises(TypeError, match="callable"):
        _raw_signal_connect(cancellable, "cancelled", 42)


def test_closure_does_not_keep_source_alive() -> None:
    """Verifies the closure holds the source weakly. Connecting a handler
    should NOT prevent the GObject wrapper from being finalized when its
    last strong ref is dropped. (Inline construction; using a fixture
    would leave pytest holding a ref.)"""
    from ginext import Gio

    cancellable = Gio.Cancellable()
    _raw_signal_connect(cancellable, "cancelled", lambda source: None)
    ref = weakref.ref(cancellable)
    del cancellable
    gc.collect()
    assert ref() is None


def test_callback_refcount_held_for_duration(cancellable: Any) -> None:
    def handler(source: Any) -> None:
        pass

    base = sys.getrefcount(handler)
    handler_id = _raw_signal_connect(cancellable, "cancelled", handler)
    # GClosure holds one ref + the record holds another via callable.
    assert sys.getrefcount(handler) >= base + 1

    _handler_disconnect(cancellable, handler_id)
    # After disconnect + finalize, the closure's refs are dropped.
    gc.collect()
    assert sys.getrefcount(handler) == base


def test_after_flag_orders_handler_after_default(cancellable: Any) -> None:
    """after=True should connect with G_CONNECT_AFTER so the user handler
    runs after the class default handler. Tested by connecting one handler
    before-default and one after-default and checking they both fire in
    that order."""
    order = []
    before_id = _raw_signal_connect(
        cancellable, "cancelled", lambda source: order.append("before")
    )
    after_id = _raw_signal_connect(
        cancellable, "cancelled", lambda source: order.append("after"), True
    )

    cancellable.cancel()

    _handler_disconnect(cancellable, before_id)
    _handler_disconnect(cancellable, after_id)
    assert order == ["before", "after"]


def test_handle_survives_callback_exception(cancellable: Any) -> None:
    """An exception inside the callback must not leave the closure in a
    broken state — the disconnect path still works."""

    def boom(source: Any) -> None:
        raise RuntimeError("boom")

    handler_id = _raw_signal_connect(cancellable, "cancelled", boom)
    cancellable.cancel()  # exception is printed, not raised through C
    _handler_disconnect(cancellable, handler_id)
    assert not _handler_is_connected(cancellable, handler_id)
