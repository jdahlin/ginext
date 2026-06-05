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

"""Cell-weakening for bound-method handlers.

When `Signal.connect` resolves an owner that *is* the bound method's
`__self__`, the closure receives a `_WeakBoundCallable` instead of the
raw bound method. The wrapper holds the unbound function strongly and
the host weakly, so the closure doesn't pin its own owner. Every other
shape (lambdas, free functions, partials, bound methods where the
host is unrelated to the owner) is unaffected — the regular arg
adapter runs.

These tests exercise:
- the leak shape that the trick is designed to fix
- the wrapper's call behaviour (alive → invoke, dead → no-op)
- the negative cases (no weakening for lambdas, static_owner, mismatched
  owner)
- introspection: SignalConnection.callback still returns the original
- arg-adapter arity still works through the wrapper
"""

import gc
import itertools
import types
import warnings
import weakref
from typing import Any


import ginext
from ginext.gobject.gobjectclass import GObject
from ginext.signal.scoped import _WeakBoundCallable


_seq = itertools.count()


def _name(prefix: str) -> str:
    return f"GinextWeakBM{prefix}{next(_seq):04d}"


# ── The cycle that weakening breaks ────────────────────────────────────


def test_bound_method_self_pattern_releases_host_on_gc() -> None:
    """obj.signal.connect(obj.method) followed by `del obj; gc.collect()`
    must collect obj. Without weakening, the closure pins obj for the
    lifetime of the signal source."""

    class Holder(GObject, type_name=_name("H")):
        pinged = GObject.Signal()

        def on_ping(self, src: Any) -> None:
            pass

    holder = Holder()
    holder_ref = weakref.ref(holder)
    holder.pinged.connect(holder.on_ping)
    del holder
    gc.collect()
    assert holder_ref() is None


def test_bound_method_on_separate_source_releases_host() -> None:
    """Same pattern but with a separate source: source.sig.connect(
    holder.method) with owner=holder. Now holder is the owner-and-host;
    source is independent."""
    from ginext import Gio

    class Holder(GObject, type_name=_name("H")):
        def on_cancel(self, src: Any) -> None:
            pass

    source = Gio.Cancellable()
    holder = Holder()
    holder_ref = weakref.ref(holder)
    source.cancelled.connect(holder.on_cancel, owner=holder)
    del holder
    gc.collect()
    assert holder_ref() is None
    # source still alive
    assert isinstance(source, Gio.Cancellable)


# ── Wrapper call behaviour ─────────────────────────────────────────────


def test_handler_fires_while_host_is_alive() -> None:
    """The wrapper is a transparent passthrough as long as the host is
    reachable."""
    from ginext import Gio

    class Holder(GObject, type_name=_name("H")):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[str] = []

        def on_cancel(self, src: Any) -> None:
            self.seen.append("fired")

    source = Gio.Cancellable()
    holder = Holder()
    source.cancelled.connect(holder.on_cancel, owner=holder)
    source.cancel()
    assert holder.seen == ["fired"]


def test_handler_noops_after_host_finalization() -> None:
    """Once the host is collected, the source can still emit without
    crashing. The wrapper's weakref returns None and the call is a
    silent no-op."""
    from ginext import Gio

    class Holder(GObject, type_name=_name("H")):
        def on_cancel(self, src: Any) -> None:
            raise AssertionError("should not be called after host death")

    source = Gio.Cancellable()
    holder = Holder()
    source.cancelled.connect(holder.on_cancel, owner=holder)
    del holder
    gc.collect()
    # The owner-weak-notify in the closure record fires on holder's
    # GObject finalization, disconnecting the handler at the GSignal
    # layer. Even if that didn't happen, the wrapper's weakref check
    # would prevent the assertion in on_cancel from firing.
    source.cancel()


# ── Negative cases: when weakening must NOT apply ───────────────────────


def test_lambda_is_not_weakened() -> None:
    """Lambdas don't have __self__ — they're handled by the regular arg
    adapter, not the weak wrapper."""
    from ginext import Gio

    source = Gio.Cancellable()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ginext.UnownedSignalHandlerWarning)
        conn = source.cancelled.connect(lambda s: None)
    # The connection's callback is the lambda itself (introspection),
    # and the inner target stored in the closure is *not* a
    # _WeakBoundCallable.
    assert not isinstance(conn.callback, _WeakBoundCallable)
    conn.disconnect()


def test_static_owner_skips_weakening() -> None:
    """owner=static_owner means "process lifetime, no auto-disconnect."
    Even a bound-method callback must stay strong so the host is held
    until disconnect."""
    from ginext import Gio

    class Holder(GObject, type_name=_name("H")):
        def on_cancel(self, src: Any) -> None:
            pass

    source = Gio.Cancellable()
    holder = Holder()
    holder_ref = weakref.ref(holder)
    conn = source.cancelled.connect(holder.on_cancel, owner=ginext.static_owner)
    del holder
    gc.collect()
    # With static_owner, weakening doesn't apply. The bound method
    # still holds holder strongly via the closure → holder is pinned.
    assert holder_ref() is not None
    conn.disconnect()


def test_explicit_other_owner_skips_weakening() -> None:
    """owner != __self__ means the user explicitly tied the handler's
    lifetime to a different object. The bound method must stay strong
    so the host outlives the owner if the user expects it to."""
    from ginext import Gio

    class Holder(GObject, type_name=_name("H")):
        def on_cancel(self, src: Any) -> None:
            pass

    source = Gio.Cancellable()
    holder = Holder()
    holder_ref = weakref.ref(holder)
    # Explicit owner != bound method's __self__.
    conn = source.cancelled.connect(holder.on_cancel, owner=source)
    del holder
    gc.collect()
    # holder pinned because we did NOT weaken.
    assert holder_ref() is not None
    conn.disconnect()


# ── Introspection ──────────────────────────────────────────────────────


def test_connection_callback_returns_original_bound_method() -> None:
    """SignalConnection.callback should expose the original bound
    method, not the internal wrapper, so users can compare identity
    or read attributes from it."""

    class Holder(GObject, type_name=_name("H")):
        pinged = GObject.Signal()

        def on_ping(self, src: Any) -> None:
            pass

    holder = Holder()
    bm = holder.on_ping
    conn = holder.pinged.connect(bm)
    assert conn.callback is bm  # exact identity preserved
    conn.disconnect()


def test_unit_weak_bound_callable_no_ops_after_host_dies() -> None:
    """Direct unit test of _WeakBoundCallable."""

    class Host:
        def __init__(self) -> None:
            self.seen: list[Any] = []

        def fire(self, *args: Any) -> None:
            self.seen.append(args)

    host = Host()
    host_ref = weakref.ref(host)
    wbc = _WeakBoundCallable(types.MethodType(Host.fire, host), None)
    wbc("a", "b")
    assert host.seen == [("a", "b")]
    del host
    gc.collect()
    assert host_ref() is None
    # Wrapper still callable; just no-ops.
    assert wbc("x", "y") is None


def test_unit_weak_bound_callable_arity_slicing() -> None:
    """When n_args is set, the wrapper slices signal_args to that
    length before invoking the unbound function."""

    class Host:
        def __init__(self) -> None:
            self.received: Any = None

        def one_arg(self, x: Any) -> None:
            self.received = x

    host = Host()
    wbc = _WeakBoundCallable(types.MethodType(Host.one_arg, host), 1)
    wbc("a", "b", "c", "d")
    assert host.received == "a"


def test_unit_weak_bound_callable_zero_arity() -> None:
    """n_args=0 means the wrapper invokes the function with no signal
    args (the host is still passed as `self` via the unbound function
    call)."""

    class Host:
        def __init__(self) -> None:
            self.calls = 0

        def fire(self) -> None:
            self.calls += 1

    host = Host()
    wbc = _WeakBoundCallable(types.MethodType(Host.fire, host), 0)
    wbc("ignored", "args")
    assert host.calls == 1


# ── Arg adapter integration ────────────────────────────────────────────


def test_weakened_bound_method_respects_zero_arg_signature() -> None:
    """`def handler(self): ...` (no signal args) connected to a signal
    that emits a source must still fire correctly — the weak wrapper
    knows the arity and drops the source arg."""

    class Holder(GObject, type_name=_name("H")):
        pinged = GObject.Signal()

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def on_ping(self) -> None:
            self.calls += 1

    holder = Holder()
    holder.pinged.connect(holder.on_ping)
    holder.pinged.emit()
    assert holder.calls == 1


def test_weakened_bound_method_with_var_args() -> None:
    """A bound method with *args declared accepts the full signal arg
    tuple. n_args is None → no slicing."""

    class Holder(GObject, type_name=_name("H")):
        bumped = GObject.Signal(int)

        def __init__(self) -> None:
            super().__init__()
            self.received: Any = None

        def on_bump(self, *args: Any) -> None:
            self.received = args

    holder = Holder()
    holder.bumped.connect(holder.on_bump)
    holder.bumped.emit(42)
    # args = (holder_source, 42)
    assert holder.received is not None
    assert len(holder.received) == 2
    assert holder.received[1] == 42


# ── Scoped callable now holds owner weakly ─────────────────────────────


def test_scoped_callable_holds_owner_weakly() -> None:
    """ScopedCallable now exposes __self__ as a property over a weakref,
    so a scoped wrapper held by a closure no longer pins the owner."""
    from ginext import Gio

    source = Gio.Cancellable()
    source_ref = weakref.ref(source)
    scoped = source.scoped(lambda src: None)
    # The scoped wrapper holds the owner via weakref only.
    assert scoped.__self__ is source
    del source
    gc.collect()
    assert source_ref() is None
    assert scoped.__self__ is None
