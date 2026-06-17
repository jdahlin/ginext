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

"""Arg adapter: callbacks accept any positional prefix of the signal args.

Cancellable::cancelled emits one runtime arg (the source). Test that
each of these handler shapes works without raising:

- `lambda: ...`        → 0 args (drop source)
- `lambda src: ...`    → 1 arg (full)
- `def f(*a): ...`     → varargs (passthrough)
- callable object with `__call__(self)` → 0 args
- functools.partial that adds extras
- `inspect.signature`-uninspectable callable (builtin) → passthrough
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import pytest

import ginext
from ginext.signal.adapt import _make_arg_adapter

if TYPE_CHECKING:
    import ginext.Gio as Gio


def _connect(cancellable: Gio.Cancellable, cb: object) -> Gio.SignalConnection:
    """Connect a handler with static_owner to skip the warning."""
    return cancellable.cancelled.connect(cb, owner=ginext.static_owner)


def test_zero_arg_lambda(cancellable: Gio.Cancellable) -> None:
    fires = []
    conn = _connect(cancellable, lambda: fires.append("called"))
    cancellable.cancel()
    assert fires == ["called"]
    conn.disconnect()


def test_one_arg_lambda_receives_source(cancellable: Gio.Cancellable) -> None:
    seen = []
    conn = _connect(cancellable, lambda src: seen.append(src))
    cancellable.cancel()
    assert seen == [cancellable]
    conn.disconnect()


def test_varargs_passthrough_gets_all_args(cancellable: Gio.Cancellable) -> None:
    seen = []

    def handler(*args: object) -> None:
        seen.append(args)

    conn = _connect(cancellable, handler)
    cancellable.cancel()
    # one signal arg = the source
    assert seen == [(cancellable,)]
    conn.disconnect()


def test_callable_object_zero_arg(cancellable: Gio.Cancellable) -> None:
    class Handler:
        def __init__(self) -> None:
            self.count = 0

        def __call__(self) -> None:
            self.count += 1

    h = Handler()
    conn = _connect(cancellable, h)
    cancellable.cancel()
    assert h.count == 1
    conn.disconnect()


def test_callable_object_one_arg(cancellable: Gio.Cancellable) -> None:
    class Handler:
        def __init__(self) -> None:
            self.received: object = None

        def __call__(self, src: object) -> None:
            self.received = src

    h = Handler()
    conn = _connect(cancellable, h)
    cancellable.cancel()
    assert h.received is cancellable
    conn.disconnect()


def test_partial_drops_extra_signal_args(cancellable: Gio.Cancellable) -> None:
    """A functools.partial binds extras at the END; signal args go to the
    callable first. So `partial(f, "tag")` means `f(signal_args..., "tag")`.
    The adapter must respect partial's residual arity."""
    seen = []

    def handler(src: object, tag: object) -> None:
        seen.append((src is cancellable, tag))

    bound = functools.partial(handler, tag="tagged")
    conn = _connect(cancellable, bound)
    cancellable.cancel()
    assert seen == [(True, "tagged")]
    conn.disconnect()


def test_uninspectable_callable_passthrough(cancellable: Gio.Cancellable) -> None:
    """list.append is a built-in method without inspect.signature support.
    The adapter should return it unchanged and let it run on the full
    signal-arg tuple."""
    target: list[object] = []
    conn = _connect(cancellable, target.append)
    cancellable.cancel()
    # target.append got called with the source as its only arg
    assert len(target) == 1
    assert target[0] is cancellable
    conn.disconnect()


def test_signal_connection_callback_is_original(cancellable: Gio.Cancellable) -> None:
    """`conn.callback` returns the user's original callable, not the
    adapter wrapper."""

    def cb() -> None:
        return None

    conn = _connect(cancellable, cb)
    assert conn.callback is cb
    conn.disconnect()


def test_old_connect_user_data_uses_original_callback_arity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "old_signal_api")
    ginext.features.reset_for_test()
    from ginext import Gio

    action = Gio.SimpleAction(name="arity-test")
    seen = []
    # old_signal_api returns SignalConnection; stub types connect() -> int
    conn: Gio.SignalConnection = action.connect(
        "notify::enabled", lambda tag: seen.append(tag), "tag"
    )
    action.set_enabled(False)
    conn.disconnect()
    ginext.features.reset_for_test()

    assert seen == ["tag"]


# --- direct adapter unit tests ---


def test_adapter_zero_arg() -> None:
    fired = []

    def target() -> None:
        fired.append("ok")

    adapter = _make_arg_adapter(target)
    adapter("arg1", "arg2")
    assert fired == ["ok"]


def test_adapter_n_arg() -> None:
    seen = []

    def target(a: object, b: object) -> None:
        seen.append((a, b))

    adapter = _make_arg_adapter(target)
    adapter("x", "y", "extra", "ignored")
    assert seen == [("x", "y")]


def test_adapter_varargs_returns_target_unchanged() -> None:
    def target(*args: object) -> object:
        return args

    adapter = _make_arg_adapter(target)
    assert adapter is target


def test_adapter_uninspectable_callable_passes_through() -> None:
    """A callable whose __signature__ raises should be returned as-is.

    We synthesize one — most CPython builtins do expose a signature in
    3.11+, so we can't pick a real "uninspectable" example reliably."""

    class Opaque:
        def __call__(self, *args: object) -> object:
            return ("called", args)

        @property
        def __signature__(self) -> None:
            raise ValueError("uninspectable")

    target = Opaque()
    adapter = _make_arg_adapter(target)
    assert adapter is target
    assert target("a", "b") == ("called", ("a", "b"))


def test_adapter_does_not_synthesize_missing_required_args() -> None:
    def target(a: object, b: object) -> object:
        return (a, b)

    adapter = _make_arg_adapter(target)
    with pytest.raises(TypeError, match="required positional argument"):
        adapter("only-one")


def test_adapter_uses_defaults_when_signal_has_too_few_args() -> None:
    seen = []

    def target(a: object, b: object = "default") -> None:
        seen.append((a, b))

    adapter = _make_arg_adapter(target)
    adapter("x")
    assert seen == [("x", "default")]


def test_adapter_default_args_count_as_positional() -> None:
    """A param with a default still counts as positional-or-keyword and
    is included in the prefix."""
    seen = []

    def target(a: object, b: object = 2) -> None:
        seen.append((a, b))

    adapter = _make_arg_adapter(target)
    adapter("x", "y", "extra")
    assert seen == [("x", "y")]
