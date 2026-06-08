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

"""pygobject-shaped signal-connection methods installed onto GObject.

These are the connection helpers whose *shape* is pygobject's, not part of
ginext's native signal API: ``connect_object``/``connect_object_after`` (swap
the emitter for a supplied object), ``connect_data`` (GConnectFlags), and the
``*_by_func`` lookups that match handlers by their Python callable. They are
installed onto the core ``GObject`` class by `repository._install_gobject_compat`
when the pygobject-compat layer is active, so native (non-compat) ginext does
not carry them.

They build on the connection bookkeeping that stays in core
(``_compat_signal_for_name``, ``_compat_remember_connection``,
``_compat_connections``, ``_compat_forget_connection``): `connect`/`disconnect`
maintain that ledger, and the ``*_by_func`` helpers query it.
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any, Callable

import ginext
from ginext.signal.adapt import _SIGNAL_ARG_LIMIT_ATTR, _accepted_signal_arg_count
from ginext.signal.scoped import static_owner

if TYPE_CHECKING:
    from ginext.signal.connection import SignalConnection


def _same_callback(left: object, right: object) -> bool:
    if left is right:
        return True
    left_self = left.__self__ if isinstance(left, types.MethodType) else None
    right_self = right.__self__ if isinstance(right, types.MethodType) else None
    left_func = left.__func__ if isinstance(left, types.MethodType) else None
    right_func = right.__func__ if isinstance(right, types.MethodType) else None
    return left_self is right_self and left_func is not None and left_func is right_func


def connect_data(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    *user_data: object,
    connect_flags: object = 0,
) -> "SignalConnection":
    GObjectRepo = ginext.GObject
    flags = GObjectRepo.ConnectFlags(connect_flags)
    after = bool(flags & GObjectRepo.ConnectFlags.AFTER)
    swapped = bool(flags & GObjectRepo.ConnectFlags.SWAPPED)
    if swapped and len(user_data) != 1:
        raise ValueError("SWAPPED connect_data requires exactly one user data")

    if swapped:
        data = user_data[0]
        retained_args = _accepted_signal_arg_count(callback, 2)
        signal_arg_limit = None if retained_args is None else 1 + retained_args

        def adapter(*args: object) -> object:
            source, *signal_args = args
            return callback(data, *signal_args, source)

    else:
        signal_arg_limit = _accepted_signal_arg_count(callback, len(user_data))

        def adapter(*args: object) -> object:
            return callback(*args, *user_data)

    _adapter: Any = adapter
    _adapter.__pygi_user_callable__ = callback
    setattr(adapter, _SIGNAL_ARG_LIMIT_ATTR, signal_arg_limit)
    signal = self._compat_signal_for_name(signal_name)
    connection = signal.connect(
        adapter, after=after, owner=static_owner, _weak_callback_record=True
    )
    self._compat_remember_connection(connection)
    return connection


def connect_object(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    obj: object,
    *user_data: object,
    after: bool = False,
) -> "SignalConnection":
    # NOTE: connect_object accepts any object as the swap target, not just
    # GObjects — pygobject's connect_object passes arbitrary Python objects
    # as the swapped first arg (see test_signal TestConnectPyObject*). When
    # the target is a GObject its lifetime is tied to the handler; otherwise
    # it is simply forwarded.
    retained_args = _accepted_signal_arg_count(callback, 1 + len(user_data))
    signal_arg_limit = None if retained_args is None else 1 + retained_args

    def adapter(_source: object, *signal_args: object) -> object:
        return callback(obj, *signal_args, *user_data)

    _adapter2: Any = adapter
    _adapter2.__pygi_user_callable__ = callback
    setattr(adapter, _SIGNAL_ARG_LIMIT_ATTR, signal_arg_limit)
    signal = self._compat_signal_for_name(signal_name)
    owner = (
        obj
        if isinstance(obj, ginext.private.GObject) and obj.is_bound()
        else static_owner
    )
    connection = signal.connect(
        adapter, after=after, owner=owner, _weak_callback_record=True
    )
    self._compat_remember_connection(connection)
    return connection


def connect_object_after(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    obj: object,
    *user_data: object,
) -> "SignalConnection":
    return self.connect_object(signal_name, callback, obj, *user_data, after=True)


def disconnect_by_func(self: Any, callback: Callable[..., Any]) -> None:
    for connection in list(self._compat_connections()):
        if _same_callback(connection.callback, callback):
            connection.disconnect()
            self._compat_forget_connection(connection)


def handler_block_by_func(self: Any, callback: Callable[..., Any]) -> int:
    count = 0
    GObjectRepo = ginext.GObject
    for connection in self._compat_connections():
        if _same_callback(connection.callback, callback) and connection.is_connected:
            GObjectRepo.signal_handler_block(self, connection.handler_id)
            count += 1
    return count


def handler_unblock_by_func(self: Any, callback: Callable[..., Any]) -> int:
    count = 0
    GObjectRepo = ginext.GObject
    for connection in self._compat_connections():
        if _same_callback(connection.callback, callback) and connection.is_connected:
            GObjectRepo.signal_handler_unblock(self, connection.handler_id)
            count += 1
    return count
