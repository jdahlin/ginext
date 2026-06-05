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

"""Tests for the overlay system.

Covers ``private.invoke`` (both str-ns and Namespace-ns forms),
namespace lifecycle (registrar attached during bootstrap and removed
after), and the shipped overlays (``GLib.idle_add`` body, Gio sequence
protocols, freeze_notify context manager).
"""

from __future__ import annotations

import inspect

import pytest


# ── private.invoke ───────────────────────────────────────────────────────


def test_invoke_with_string_namespace() -> None:
    """private.invoke("GLib", "idle_add", priority, function) dispatches
    straight to the typelib's idle_add, bypassing any overlay."""
    from ginext import GLib, private

    fired: list[object] = []

    def _cb() -> bool:
        fired.append(True)
        return False

    handle = private.invoke("GLib", "idle_add", 200, _cb)
    assert isinstance(handle, int)
    ctx = GLib.MainContext.default()
    for _ in range(5):
        ctx.iteration(False)
        if fired:
            break
    assert len(fired) == 1


def test_invoke_with_namespace_instance() -> None:
    """The same call works passing the Namespace instance for ns."""
    from ginext import GLib, private

    fired: list[object] = []

    def _cb() -> bool:
        fired.append(1)
        return False

    private.invoke(GLib, "idle_add", 200, _cb)
    ctx = GLib.MainContext.default()
    for _ in range(5):
        ctx.iteration(False)
        if fired:
            break
    assert fired == [1]


def test_invoke_rejects_missing_args() -> None:
    from ginext import private

    with pytest.raises(TypeError, match="requires at least"):
        private.invoke("GLib")


def test_invoke_rejects_unknown_function() -> None:
    from ginext import private

    with pytest.raises(AttributeError, match="has no attribute"):
        private.invoke("GLib", "definitely_not_a_function_name")


# ── Registrar lifecycle ─────────────────────────────────────────────────


def test_registrar_removed_after_bootstrap() -> None:
    """<Namespace>.overlay is only present during _overlays/<Ns>.py
    import; it must be gone by the time app code reaches the namespace."""
    from ginext import GLib

    assert not hasattr(GLib, "overlay")


def test_registrar_removed_for_namespaces_with_overlays() -> None:
    """Same for every namespace that ships an overlay module."""
    from ginext import GLib, GObject, Gio

    for ns in (GLib, GObject, Gio):
        assert not hasattr(ns, "overlay"), f"{ns} still exposes .overlay"


# ── GLib.idle_add overlay ───────────────────────────────────────────────


def test_idle_add_signature_is_reshaped() -> None:
    """The overlay's body provides the Pythonic signature, and that's
    what inspect.signature returns."""
    from ginext import GLib

    sig = inspect.signature(GLib.idle_add)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["function", "priority"]
    assert params[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params[1].kind is inspect.Parameter.KEYWORD_ONLY
    assert params[1].default == 200


def test_idle_add_default_priority_fires() -> None:
    from ginext import GLib

    fired: list[str] = []

    def _cb() -> bool:
        fired.append("ok")
        return False

    GLib.idle_add(_cb)
    ctx = GLib.MainContext.default()
    for _ in range(5):
        if not ctx.iteration(False):
            break
    assert fired == ["ok"]


def test_idle_add_with_explicit_priority_fires() -> None:
    from ginext import GLib

    fired: list[str] = []

    def _cb() -> bool:
        fired.append("explicit")
        return False

    GLib.idle_add(_cb, priority=150)
    ctx = GLib.MainContext.default()
    for _ in range(5):
        if not ctx.iteration(False):
            break
    assert fired == ["explicit"]


def test_replace_overlay_hides_injected_fn_argument() -> None:
    from ginext import GLib

    sig = inspect.signature(GLib.markup_escape_text)
    assert list(sig.parameters) == ["text", "length"]
    assert GLib.markup_escape_text("a&b") == "a&amp;b"


# ── Gio.ListStore overlay (sequence protocols + Task.new) ───────────────


def test_list_store_supports_len() -> None:
    from ginext import Gio

    store = Gio.ListStore(item_type=Gio.Cancellable)
    assert len(store) == 0
    store.append(Gio.Cancellable())
    assert len(store) == 1


def test_list_store_supports_getitem() -> None:
    from ginext import Gio

    store = Gio.ListStore(item_type=Gio.Cancellable)
    a = Gio.Cancellable()
    store.append(a)
    assert store[0] is a
    assert store[-1] is a


def test_task_new_is_accessible() -> None:
    """Gio.Task.new (typelib-elided 'new' method) is surfaced by the
    overlay as a static factory."""
    from typing import Any

    from ginext import Gio

    fired: list[tuple[Any, ...]] = []

    def _cb(*a: Any) -> bool:
        fired.append(a)
        return False

    task = Gio.Task.new(None, None, _cb, "sentinel")
    task.return_int(42)
    from ginext import GLib

    ctx = GLib.MainContext.default()
    for _ in range(5):
        if not ctx.iteration(False):
            break
    assert fired and fired[0][-1] == "sentinel"


# ── freeze_notify context manager (lives on the Python GObject root) ────


def test_freeze_notify_works_as_context_manager() -> None:
    """Calling obj.freeze_notify() as a context manager pairs it with
    thaw_notify on exit. Works on any GObject; using Gio.Cancellable
    here to avoid pulling in Property registration."""
    from ginext import Gio

    obj = Gio.Cancellable()
    ctx = obj.freeze_notify()
    # Returns a real context manager
    assert hasattr(ctx, "__enter__")
    assert hasattr(ctx, "__exit__")
    with obj.freeze_notify():
        pass
    # No exception = success
