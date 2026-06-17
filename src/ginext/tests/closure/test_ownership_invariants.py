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

"""Owner-aware closure invariants — ginext-native versions of the goi
ownership-contract and leak-regression tests.

This file covers the native-feasible invariants using ginext's actual
surface. Test names mirror the originating goi tests / named GNOME issue
numbers where relevant.
"""

import gc
import itertools
import weakref
from typing import Any, cast


from ginext.gobject.gobjectclass import GObject


_seq = itertools.count()


def _name(prefix: str) -> str:
    return f"GinextOwn{prefix}{next(_seq):04d}"


def _iterate_until(predicate: Any, GLib: Any, max_iter: int = 64) -> None:
    ctx = GLib.MainContext.default()
    for _ in range(max_iter):
        if predicate():
            return
        if not ctx.iteration(False):
            break


# ── owner-death auto-disconnect ─────────────────────────────────────────


def test_owner_death_disconnects_source_handler() -> None:
    """When the owner GObject is finalized, the closure record's weak
    notify fires and disconnects the handler from the source — so the
    signal can keep firing after but the orphaned handler never runs."""
    from ginext import Gio

    def run() -> list[int]:
        source = Gio.Cancellable()
        owner = Gio.Cancellable()  # using Cancellable as a generic GObject
        fires: list[int] = []
        source.cancelled.connect(lambda s: fires.append(1), owner=owner)
        # Drop the owner; its weakref-finalize unrefs the GObject; the
        # closure record's owner-weak-notify disconnects the handler.
        del owner
        gc.collect()
        source.cancel()
        return fires

    assert run() == []


# ── handle doesn't keep source alive ───────────────────────────────────


def test_closure_handle_does_not_keep_signal_source_alive() -> None:
    """Holding the SignalConnection handle alone must not pin the source
    GObject. The handle has only a weak ref to the source."""
    from ginext import Gio

    source = Gio.Cancellable()
    source_ref = weakref.ref(source)
    conn = source.cancelled.connect(lambda s: None, owner=source)
    # Drop the source. The handle still exists (`conn`) but doesn't keep
    # the source alive.
    del source
    gc.collect()
    assert source_ref() is None
    # The handle reports disconnected after source death.
    assert conn.source is None
    assert not conn.is_connected


# ── issue_219: bound-method owner is not retained by the closure ────────


def test_issue_219_closure_handle_does_not_retain_bound_method_owner() -> None:
    """`obj.signal.connect(obj.method)` — the most common handler shape
    in Gtk apps — must not pin `obj`. Without weakening, the GClosure
    holds the bound method which strongly references its __self__, so
    `obj` survives until the source is finalized. With weakening,
    Signal.connect substitutes a WeakBoundCallable that holds the
    function side strongly and __self__ weakly, so `obj` can be
    collected as soon as user code drops its references."""

    class Holder(GObject, type_name=_name("Holder")):
        pinged = GObject.Signal()

        def on_ping(self, src: Any) -> None:
            pass

    holder = Holder()
    holder_ref = weakref.ref(holder)
    holder.pinged.connect(holder.on_ping)
    del holder
    gc.collect()
    assert holder_ref() is None


def test_scoped_with_other_object_method_does_not_retain_other_object() -> None:
    """`source.scoped(holder.on_fire)` — owner is source, but the inner
    bound method references holder. With the current ScopedCallable,
    holder is pinned by the strong `_callback` ref until the source
    dies. Goi rewrites the inner callback's closure cells to release
    such non-owner hosts; ginext doesn't yet."""
    from ginext import Gio

    class Holder:
        def __init__(self) -> None:
            self.fired = False

        def on_fire(self, src: Any) -> None:
            self.fired = True

    source = Gio.Cancellable()
    holder = Holder()
    holder_ref = weakref.ref(holder)
    source.cancelled.connect(source.scoped(holder.on_fire))
    del holder
    gc.collect()
    assert holder_ref() is None


# ── issue_42: source can outlive the logical owner ──────────────────────


def test_issue_42_helper_signal_source_can_outlive_visible_owner() -> None:
    """A common pattern: a helper object connects to a signal on a
    long-lived source. When the helper dies (owner), the source stays
    alive but the helper's handler is gone."""
    from ginext import Gio

    source = Gio.Cancellable()
    fires_before: list[int] = []
    fires_after: list[int] = []

    def helper_scope() -> None:
        helper = Gio.Cancellable()
        source.cancelled.connect(lambda s: fires_before.append(1), owner=helper)
        # helper falls out of scope at function return; its weakref-
        # finalize fires and the handler should auto-disconnect.

    helper_scope()
    gc.collect()

    # Attach a fresh handler after the helper is gone — proves the
    # source still works.
    other_conn = source.cancelled.connect(lambda s: fires_after.append(1), owner=source)
    source.cancel()
    assert fires_before == []  # owner died, handler gone
    assert fires_after == [1]  # source still emits
    other_conn.disconnect()


# ── issue_36_557: repeated owner-death doesn't accumulate live closures ──


def test_issues_36_557_repeated_owner_death_does_not_accumulate() -> None:
    """Connecting many handlers whose owners then die should not leave
    any of them connected to the source. Each owner-death must
    individually trigger a disconnect."""
    from ginext import Gio

    source = Gio.Cancellable()
    fires: list[str] = []

    def make_and_drop_owner() -> None:
        owner = Gio.Cancellable()
        source.cancelled.connect(lambda s: fires.append("leaked"), owner=owner)
        # owner goes out of scope at function exit

    for _ in range(20):
        make_and_drop_owner()
    gc.collect()

    source.cancel()
    assert fires == []


# ── issue_735: owner == self lambda releases source via owner death ─────


def test_issue_735_owner_self_lambda_releases_source_while_handle_survives() -> None:
    """When the owner is the source itself (`obj.sig.connect(cb, owner=obj)`),
    dropping the wrapper unrefs the GObject. The handle can outlive the
    source as a stale weak reference; introspection works without crashing."""
    from ginext import Gio

    obj = Gio.Cancellable()
    obj_ref = weakref.ref(obj)
    conn = obj.cancelled.connect(lambda s: None, owner=obj)
    del obj
    gc.collect()
    assert obj_ref() is None
    # Handle survives, reports None source + not connected.
    assert conn.source is None
    assert not conn.is_connected
    # disconnect after source death is a clean no-op.
    conn.disconnect()


# ── reentrant disconnect during emit is idempotent ──────────────────────


def test_reentrant_handler_remove_during_invocation_is_idempotent() -> None:
    """A handler that disconnects itself during emit must not crash or
    cause a double-disconnect on subsequent disconnect() calls."""
    from ginext import Gio

    source = Gio.Cancellable()
    fires: list[int] = []
    conn = None

    def handler(src: Any) -> None:
        fires.append(1)
        assert conn is not None
        conn.disconnect()
        conn.disconnect()  # second time is no-op
        conn.disconnect()  # third time too

    conn = source.cancelled.connect(handler, owner=source)
    source.cancel()
    assert fires == [1]
    assert not conn.is_connected


# ── python-defined signal: owner-death still disconnects ────────────────


def test_owner_death_disconnects_python_defined_signal_handler() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    src = Source()
    fires: list[int] = []

    def make_and_drop_owner() -> None:
        from ginext import Gio

        owner = Gio.Cancellable()
        src.pinged.connect(lambda s: fires.append(1), owner=owner)

    make_and_drop_owner()
    gc.collect()
    src.pinged.emit()
    assert fires == []


# ── ports from goi/tests/closure/test_closure_ownership_contracts.py ───
#
# Below: the remaining native-feasible tests from goi's contracts file,
# translated to the ginext API surface. Tests that exercised goi's
# debug-inventory, scope=async/notified callback args, GBinding, Gtk
# templates, or GListModel factories are intentionally not ported —
# those rely on features ginext doesn't ship.


def test_scope_and_destroy_releases_async_user_data_after_completion() -> None:
    """goi: closure-ownership-contracts.test_scope_and_destroy_releases_async_user_data_after_completion

    After the async callback fires, both the callback and its user_data state
    should be released by the closure machinery.
    """
    from ginext import Gio, GLib

    class State:
        pass

    state = State()
    state_ref = weakref.ref(state)
    seen: list[bool] = []

    def callback(_source: Any, _result: Any, user_data: Any) -> None:
        seen.append(user_data is state_ref())

    callback_ref = weakref.ref(callback)
    task = Gio.Task.new(None, None, callback, state)
    del callback
    del state

    task.return_int(42)
    _iterate_until(lambda: bool(seen), GLib)
    del task
    gc.collect()
    gc.collect()

    assert seen == [True]
    assert state_ref() is None
    assert callback_ref() is None


def test_scope_and_destroy_distinguishes_multiple_async_callbacks_sharing_state() -> (
    None
):
    """goi: closure-ownership-contracts.test_scope_and_destroy_distinguishes_multiple_async_callbacks_sharing_state"""
    from ginext import Gio, GLib

    class State:
        pass

    state = State()
    state_ref = weakref.ref(state)
    seen: list[bool] = []

    def callback(_source: Any, _result: Any, user_data: Any) -> None:
        seen.append(user_data is state_ref())

    task1 = Gio.Task.new(None, None, callback, state)
    task2 = Gio.Task.new(None, None, callback, state)
    del state
    del callback

    task1.return_int(1)
    _iterate_until(lambda: len(seen) >= 1, GLib)
    assert state_ref() is not None

    task2.return_int(2)
    _iterate_until(lambda: len(seen) >= 2, GLib)
    del task1
    del task2
    gc.collect()
    gc.collect()

    assert seen == [True, True]
    assert state_ref() is None


def test_owner_with_separate_source_can_outlive_owner_in_handler_emit() -> None:
    """`source.signal.connect(cb, owner=other)` — the goi
    `connect_object` shape, adapted. The handler must auto-disconnect
    when `other` is finalized, and emit on `source` afterwards must
    not fire it."""
    from ginext import Gio

    source = Gio.Cancellable()
    fires: list[str] = []

    def run() -> None:
        owner = Gio.Cancellable()
        source.cancelled.connect(lambda s: fires.append("leaked"), owner=owner)
        # owner goes out of scope here; weak-notify on its GObject
        # fires and the closure record disconnects the handler.

    run()
    gc.collect()
    source.cancel()
    assert fires == []


def test_owner_death_releases_callback_object() -> None:
    """A callable-object handler must be releasable when its owner dies.
    The closure record holds the callback strongly, but the record
    itself is freed via the GClosure's finalize when the GSignal
    connection ends (owner death triggers a disconnect)."""
    from ginext import Gio

    class HeavyCallback:
        def __init__(self) -> None:
            self.fired = False

        def __call__(self, src: Any) -> None:
            self.fired = True

    source = Gio.Cancellable()
    callback = HeavyCallback()
    callback_ref = weakref.ref(callback)

    def run(callback: HeavyCallback) -> None:
        owner = Gio.Cancellable()
        # static_owner would pin the callback forever; using a fresh
        # owner that dies at function-exit triggers cleanup.
        source.cancelled.connect(callback, owner=owner)

    run(callback)
    # Drop the user-side ref to the callback; only the closure holds it now.
    del callback
    gc.collect()
    assert callback_ref() is None


def test_scoped_lambda_direct_owner_cell_does_not_keep_owner_alive() -> None:
    """A scoped lambda whose closure captures the owner should not
    keep the owner alive. ScopedCallable's __self__ is weak, but the
    inner lambda still references owner via a closure cell that
    pygir has not rewritten to a weak reference."""

    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    class Owner(GObject, type_name=_name("Own")):
        def __init__(self) -> None:
            super().__init__()
            self.events: list[str] = []

    def build_and_drop() -> tuple[Any, Any]:
        source = Source()
        owner = Owner()
        owner_ref = weakref.ref(owner)
        source.pinged.connect(owner.scoped(lambda src: owner.events.append("called")))
        return source, owner_ref

    source, owner_ref = build_and_drop()
    gc.collect()
    assert owner_ref() is None  # currently fails: owner pinned by lambda cell
    source.pinged.emit()  # would no-op via the weak __self__ anyway


def test_scoped_lambda_indirect_owner_capture_is_not_weakened() -> None:
    """When the inner lambda captures the owner *indirectly* (through
    another object's attribute, not as a direct closure cell), no
    weakening is possible — and the contract is that indirect refs
    DO keep the owner alive until the handler is explicitly removed."""

    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    class Owner(GObject, type_name=_name("Own")):
        def __init__(self) -> None:
            super().__init__()
            self.events: list[str] = []

    source = Source()
    owner = Owner()
    owner_ref = weakref.ref(owner)
    state: dict[str, Owner | None] = {"owner": owner}  # indirect reference

    conn = source.pinged.connect(
        owner.scoped(lambda src: cast("Any", state["owner"]).events.append("called"))
    )
    del owner
    gc.collect()

    # owner stays alive because `state["owner"]` keeps a strong ref.
    assert owner_ref() is not None

    # Once we explicitly disconnect and drop the indirect ref, the
    # owner is collectable.
    conn.disconnect()
    state["owner"] = None
    gc.collect()
    assert owner_ref() is None


def test_handler_connected_state_reflects_live_signal_connection() -> None:
    """`SignalConnection.is_connected` mirrors the GSignal layer state.
    After owner death, the closure record's owner-weak-notify
    disconnects at the C layer and is_connected reports False."""

    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    src = Source()
    conn_holder: dict[str, Any] = {}

    def hook_up() -> None:
        from ginext import Gio

        owner = Gio.Cancellable()
        conn_holder["conn"] = src.pinged.connect(lambda s: None, owner=owner)
        assert conn_holder["conn"].is_connected

    hook_up()
    gc.collect()
    assert not conn_holder["conn"].is_connected
    src.pinged.emit()  # safe; handler gone
