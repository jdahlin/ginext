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

"""connect_object / connect_object_after behaviour.

These are pygobject-shaped helpers — `connect_object()` swaps the emitting
instance for a supplied object in callback arg 0. They are installed onto the
GObject class only by the pygobject-compat layer (see
gi._gobject_signals / repository._install_gobject_signal_methods), so the tests
live in the compat suite, where the layer is active. Relocated from the core
signal tests when connect_object moved out of native ginext.
"""

from __future__ import annotations

import gc
from typing import Any

import pytest

from gi.repository import Gio


def test_connect_object_replaces_instance_arg() -> None:
    """`connect_object()` substitutes the supplied object for the
    emitting instance in callback arg 0."""
    cancellable = Gio.Cancellable.new()
    target = Gio.Cancellable.new()
    seen = []

    def handler(obj: Any) -> None:
        seen.append(obj)

    cancellable.connect_object("cancelled", handler, target)
    cancellable.cancel()
    assert seen == [target]


def test_connect_object_preserves_signal_args_and_user_data() -> None:
    """For multi-arg signals the emitting instance is replaced, but the
    remaining signal args and trailing user_data are preserved."""
    action = Gio.SimpleAction.new("demo", None)
    target = Gio.Cancellable.new()
    seen = []

    def handler(obj: Any, parameter: Any, suffix: Any) -> None:
        seen.append((obj, parameter, suffix))

    action.connect_object("activate", handler, target, "tail")
    action.activate(None)
    assert seen == [(target, None, "tail")]


def test_connect_object_after_runs_after_default_slot() -> None:
    cancellable = Gio.Cancellable.new()
    target = Gio.Cancellable.new()
    seen = []

    def handler(obj: Any) -> None:
        seen.append(obj)

    cancellable.connect_object_after("cancelled", handler, target)
    cancellable.cancel()
    assert seen == [target]


def test_connect_object_accepts_non_gobject_target() -> None:
    """connect_object forwards any object as the swapped first arg — pygobject
    passes arbitrary Python objects, not just GObjects (test_signal
    TestConnectPyObject*), so a non-GObject target is accepted, not rejected."""
    cancellable = Gio.Cancellable.new()
    seen = []
    cancellable.connect_object("cancelled", lambda obj: seen.append(obj), "swap-data")
    cancellable.cancel()
    assert seen == ["swap-data"]


@pytest.mark.xfail(
    reason="relies on GObject.weak_ref callback (overlay) not yet implemented",
    strict=False,
)
def test_connect_object_auto_disconnects_when_target_dies() -> None:
    """Mirror `g_signal_connect_object()`: the target is not kept alive,
    and once it dies the handler is disconnected from the emitter."""
    cancellable = Gio.Cancellable.new()
    target_finalized = []
    fired = []

    target = Gio.Cancellable.new()
    target.weak_ref(lambda: target_finalized.append(True))

    hid = cancellable.connect_object(
        "cancelled",
        lambda obj: fired.append(obj),
        target,
    )
    assert cancellable.handler_is_connected(hid)

    del target
    gc.collect()

    assert target_finalized == [True]
    assert not cancellable.handler_is_connected(hid)

    cancellable.cancel()
    assert fired == []
