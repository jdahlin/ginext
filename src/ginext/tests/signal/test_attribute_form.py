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

"""End-to-end ABI2 signal attribute path.

`obj.cancelled.connect(cb)` should produce a real GSignal connection via
the lazy Signal lookup hooked into GObject wrapper.__getattr__. The
`Gio.SimpleAction.activate` covers the awkward case where a class signal
has the same Python name as a method inherited from an interface.
"""

from __future__ import annotations

from typing import Any

import pytest

from ginext.signal.bound import Signal


def test_attribute_access_returns_signal(cancellable: Any) -> None:
    assert isinstance(cancellable.cancelled, Signal)


def test_repr_marks_pure_signal_without_callable_suffix(cancellable: Any) -> None:
    sig = cancellable.cancelled
    assert repr(sig) == "<Signal Cancellable.cancelled>"


def test_connect_emit_disconnect_roundtrip(cancellable: Any) -> None:
    seen = []
    h = cancellable.cancelled.connect(
        lambda source: seen.append(source), owner=cancellable
    )
    cancellable.cancel()
    assert seen == [cancellable]
    h.disconnect()


def test_handler_receives_same_wrapper_instance(cancellable: Any) -> None:
    """The closure marshal routes G_TYPE_OBJECT values through the wrapper
    factory, which returns the same Python wrapper that was already attached
    to the GObject — same identity, not a fresh wrapping."""
    received = []
    h = cancellable.cancelled.connect(
        lambda src: received.append(src), owner=cancellable
    )
    cancellable.cancel()
    assert received[0] is cancellable
    h.disconnect()


def test_calling_pure_signal_raises_type_error(cancellable: Any) -> None:
    with pytest.raises(TypeError, match="is a signal, not a method"):
        cancellable.cancelled()


def test_unknown_attribute_raises_attribute_error(cancellable: Any) -> None:
    with pytest.raises(AttributeError):
        cancellable.this_attribute_does_not_exist


def test_signal_lookup_table_is_class_attribute() -> None:
    from ginext import Gio

    assert "cancelled" in Gio.Cancellable.gimeta.signal_infos
    # No method named "cancelled" exists, so no backing.
    assert "cancelled" not in Gio.Cancellable.gimeta.signal_method_backings


def test_signal_lookup_table_excludes_methods() -> None:
    """The 'cancel' method is unrelated to the 'cancelled' signal — they're
    distinct attributes. Make sure ClassBuilder didn't accidentally cross-wire."""
    from ginext import Gio

    assert "cancel" not in Gio.Cancellable.gimeta.signal_infos
    assert "cancel" in Gio.Cancellable.gimeta.method_infos
    assert callable(Gio.Cancellable.cancel)


def test_method_signal_collision_on_inherited_interface_method() -> None:
    from ginext import Gio

    action = Gio.SimpleAction.new("demo", None)
    seen = []
    # action.activate is a _SignalMethod at runtime (signal/method collision);
    # the stub types it as the GIR method, not the signal descriptor.
    activate: Any = action.activate
    activate.connect(lambda _action, parameter: seen.append(parameter), owner=action)

    assert isinstance(action.activate, Signal)
    assert callable(action.activate)

    action.activate(None)

    assert seen == [None]


def test_each_access_returns_fresh_signal_object(cancellable: Any) -> None:
    """Signals bind a source so they're per-access objects; identity should
    not be preserved across accesses (but equivalence of behaviour is)."""
    assert cancellable.cancelled is not cancellable.cancelled


def test_after_flag_via_attribute_path(cancellable: Any) -> None:
    order = []
    before = cancellable.cancelled.connect(
        lambda s: order.append("before"), owner=cancellable
    )
    after = cancellable.cancelled.connect(
        lambda s: order.append("after"), owner=cancellable, after=True
    )
    cancellable.cancel()
    before.disconnect()
    after.disconnect()
    assert order == ["before", "after"]


def test_emit_with_args_on_zero_arg_signal_raises(cancellable: Any) -> None:
    """Cancellable::cancelled takes no args. Emitting with extras must
    raise so the user sees the mismatch rather than silently dropping
    or corrupting handler args."""
    sig = cancellable.cancelled
    sig.emit()  # no-arg emit is fine
    with pytest.raises(TypeError, match="expects 0 argument"):
        sig.emit("extra")
