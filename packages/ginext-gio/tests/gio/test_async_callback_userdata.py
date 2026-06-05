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

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest


@pytest.fixture(scope="module", autouse=True)
def _setup() -> None:
    import ginext

    ginext.private.require_namespace("GLib", "2.0")
    ginext.private.require_namespace("Gio", "2.0")


@pytest.fixture
def GLib() -> Any:
    from ginext import GLib

    return GLib


@pytest.fixture
def Gio() -> Any:
    from ginext import Gio

    return Gio


def _iterate_until(GLib: Any, predicate: Callable[[], bool], limit: int = 30) -> None:
    ctx = GLib.MainContext.default()
    for _ in range(limit):
        if predicate():
            return
        ctx.iteration(False)


def test_task_callback_omitted_user_data_is_hidden_from_variadic_callback(
    GLib: Any, Gio: Any
) -> None:
    received: list[Any] = []

    def callback(*args: Any) -> None:
        received.append(args)

    task = Gio.Task.new(None, None, callback)
    task.return_int(42)
    _iterate_until(GLib, lambda: bool(received))

    assert [len(args) for args in received] == [2]


def test_task_callback_explicit_none_user_data_is_delivered(
    GLib: Any, Gio: Any
) -> None:
    received: list[Any] = []

    def callback(_source: Any, _result: Any, user_data: Any) -> None:
        received.append(user_data)

    task = Gio.Task.new(None, None, callback, None)
    task.return_int(42)
    _iterate_until(GLib, lambda: bool(received))

    assert received == [None]


def test_task_callback_explicit_object_user_data_is_delivered(
    GLib: Any, Gio: Any
) -> None:
    sentinel = object()
    received: list[Any] = []

    def callback(_source: Any, _result: Any, user_data: Any) -> None:
        received.append(user_data)

    task = Gio.Task.new(None, None, callback, sentinel)
    task.return_int(42)
    _iterate_until(GLib, lambda: bool(received))

    assert received == [sentinel]
