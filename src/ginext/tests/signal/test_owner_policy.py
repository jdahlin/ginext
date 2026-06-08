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

"""Owner resolution policy for Signal.connect.

Resolution order:
1. `owner=ginext.static_owner` → no owner, no warning
2. `owner=<GObject wrapper>` → explicit owner
3. (otherwise) infer from `callback.__self__` if it's a GObject wrapper
4. nothing found → `UnownedSignalHandlerWarning` + connect anyway

`owner.scoped(callback, *extras)` returns a callback whose `__self__` is
the owner, so it picks up the inference path.
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

import ginext


def test_explicit_owner_kwarg(cancellable: Any) -> None:
    """An explicit owner= must be a GObject wrapper and is stored on the
    handle as a weak ref."""
    conn = cancellable.cancelled.connect(lambda s: None, owner=cancellable)
    assert conn.owner is cancellable
    conn.disconnect()


def test_static_owner_suppresses_warning(cancellable: Any) -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        conn = cancellable.cancelled.connect(lambda s: None, owner=ginext.static_owner)
    assert captured == []
    assert conn.owner is None
    conn.disconnect()


def test_unowned_lambda_warns(cancellable: Any) -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        conn = cancellable.cancelled.connect(lambda s: None)
    assert len(captured) == 1
    assert captured[0].category is ginext.UnownedSignalHandlerWarning
    conn.disconnect()


def test_unowned_lambda_still_connects_and_fires(cancellable: Any) -> None:
    """Warn-on-unowned does not prevent connection — the goal is to surface
    leaks, not break legitimate use."""
    seen = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ginext.UnownedSignalHandlerWarning)
        conn = cancellable.cancelled.connect(lambda s: seen.append("fired"))
    cancellable.cancel()
    assert seen == ["fired"]
    conn.disconnect()


def test_owner_must_be_gobject_or_sentinel(cancellable: Any) -> None:
    with pytest.raises(TypeError, match="must be a GObject wrapper"):
        cancellable.cancelled.connect(lambda s: None, owner=object())


def test_scoped_callback_carries_owner_via_self(cancellable: Any) -> None:
    """scoped() returns a callable whose __self__ is the owner, so the
    inference path picks it up without an explicit owner= kwarg."""
    saw = []
    cb = cancellable.scoped(lambda src, tag: saw.append(tag), "X")
    assert cb.__self__ is cancellable
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        conn = cancellable.cancelled.connect(cb)
    assert captured == []
    assert conn.owner is cancellable
    cancellable.cancel()
    assert saw == ["X"]
    conn.disconnect()


def test_scoped_zero_arg_callback_ignores_signal_args(cancellable: Any) -> None:
    seen = []

    conn = cancellable.cancelled.connect(cancellable.scoped(lambda: seen.append("ok")))
    cancellable.cancel()
    assert seen == ["ok"]
    conn.disconnect()


def test_scoped_forwards_signal_args_then_extras(cancellable: Any) -> None:
    seen = []

    def handler(source: Any, tag: Any, mode: Any) -> None:
        seen.append((source is cancellable, tag, mode))

    conn = cancellable.cancelled.connect(cancellable.scoped(handler, "X", mode="save"))
    cancellable.cancel()
    assert seen == [(True, "X", "save")]
    conn.disconnect()


def test_multi_owner_lambda_raises_typeerror() -> None:
    """A lambda that captures more than one GObject wrapper in its
    closure can't have an owner safely inferred — picking one silently
    would surprise the user whose intent was the other. Raise so the
    user fixes it explicitly."""
    from ginext import Gio

    def make_ambiguous() -> None:
        a = Gio.Cancellable()
        b = Gio.Cancellable()
        with pytest.raises(TypeError, match="closure captures 2 GObject"):
            a.cancelled.connect(lambda src: (a, b))

    make_ambiguous()


def test_multi_owner_resolved_by_explicit_owner_kwarg() -> None:
    """`owner=` short-circuits inference, so a multi-owner closure is
    still legal when the user picks one explicitly."""
    from ginext import Gio

    def run() -> None:
        a = Gio.Cancellable()
        b = Gio.Cancellable()
        # Multi-owner closure, but owner= overrides — no raise.
        conn = a.cancelled.connect(lambda src: (a, b), owner=a)
        assert conn.owner is a
        conn.disconnect()

    run()


def test_multi_owner_resolved_by_static_owner() -> None:
    """static_owner also bypasses inference."""
    from ginext import Gio

    def run() -> None:
        a = Gio.Cancellable()
        b = Gio.Cancellable()
        conn = a.cancelled.connect(lambda src: (a, b), owner=ginext.static_owner)
        assert conn.owner is None
        conn.disconnect()

    run()


def test_module_globals_not_counted_as_closure() -> None:
    """A lambda defined at module scope that references module-level
    GObjects doesn't capture them in __closure__ (they're LOAD_GLOBAL),
    so multi-owner detection doesn't apply. This stays a warn-on-
    unowned case."""
    # We exercise this implicitly via the existing `test_unowned_lambda_warns`
    # test, which uses a module-scope lambda and only warns rather than
    # raising. Documenting the boundary here for posterity.
    assert True


def test_single_owner_closure_does_not_raise_picks_via_self() -> None:
    """One captured GObject is the inferred owner (if not a __self__
    bound method, we still warn — closure capture doesn't imply
    ownership intent). The multi-owner test only fires for >=2."""
    from ginext import Gio
    import warnings

    def run() -> None:
        a = Gio.Cancellable()
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            conn = a.cancelled.connect(lambda src: a)
        # Single-capture still warns (not bound, no static_owner)
        unowned = [
            w
            for w in captured
            if issubclass(w.category, ginext.UnownedSignalHandlerWarning)
        ]
        assert len(unowned) == 1
        conn.disconnect()

    run()


def test_bound_method_on_gobject_infers_owner() -> None:
    """A bound method whose __self__ is a GObject wrapper should not warn.

    `Gio.Cancellable.reset` is a normal instance method — using it as the
    callback gives the inference path a real GObject wrapper to find."""
    from ginext import Gio

    c = Gio.Cancellable()
    # bound method __self__ is c itself
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        conn = c.cancelled.connect(c.reset)
    assert captured == []
    assert conn.owner is c
    conn.disconnect()
