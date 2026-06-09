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

# mypy: disable-error-code="explicit-any"

"""pygobject-compat ``connect``/``emit``/``get_property``/``set_property`` & co.

These are pygobject-shaped methods, not part of ginext's native API (native uses
the attribute signal API and attribute property access). They are registered as
a *second* overlay source for ``GObject.Object`` (alongside the native
``ginext._overlays.GObject``) via an ``OverlayRegistrar``. Importing this module
registers them; ``repository._install_gobject_signal_methods`` then applies the
``("GObject", "Object")`` overlays — at compat-load time, after the class is
already built — with ``install_class_overlay``.
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any, cast

import ginext
from ginext import features
from ginext.gobject.properties import call_notify_override
from ginext.overlay.registrar import OverlayRegistrar
from ginext.signal.adapt import _SIGNAL_ARG_LIMIT_ATTR, _accepted_signal_arg_count
from ginext.signal.bound import Signal as _BoundSignal
from ginext.signal.connection import SignalConnection
from ginext.signal.scoped import static_owner

if TYPE_CHECKING:
    from collections.abc import Callable

overlay = OverlayRegistrar(ginext.GObject)


@overlay.method("Object")
def connect(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    *user_data: object,
    **kwargs: object,
) -> SignalConnection:
    if not features.is_enabled(features.OLD_SIGNAL_API):
        raise TypeError("GObject.connect() is disabled by old_signal_api")
    if user_data:
        original_callback = callback
        signal_arg_limit = _accepted_signal_arg_count(original_callback, len(user_data))

        def callback(*signal_args: object) -> object:
            return original_callback(*signal_args, *user_data)

        setattr(callback, _SIGNAL_ARG_LIMIT_ATTR, signal_arg_limit)
        kwargs.setdefault("owner", static_owner)
    signal = self.signal_for_name(signal_name)
    kwargs.setdefault("_weak_callback_record", True)
    connection = signal.connect(callback, **cast("Any", kwargs))
    self._compat_remember_connection(connection)
    return cast("SignalConnection", connection)


@overlay.method("Object")
def connect_after(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    *user_data: object,
    **kwargs: object,
) -> SignalConnection:
    kwargs["after"] = True
    return cast(
        "SignalConnection",
        self.connect(signal_name, callback, *user_data, **kwargs),
    )


@overlay.method("Object")
def emit(self: Any, signal_name: str, *args: object) -> object:
    if not features.is_enabled(features.OLD_SIGNAL_API):
        raise TypeError("GObject.emit() is disabled by old_signal_api")
    signal = self._compat_signal_for_name(signal_name)
    return signal.emit(*args)


@overlay.method("Object")
def get_property(self: Any, name: str) -> object:
    prop_name = name.replace("_", "-")
    try:
        return type(self).gimeta.get_property(self, prop_name)
    except AttributeError:
        return self.get_property_by_name(prop_name)


@overlay.method("Object")
def set_property(self: Any, name: str, value: object) -> None:
    prop_name = name.replace("_", "-")
    try:
        type(self).gimeta.set_property(self, prop_name, value)
    except AttributeError:
        self.set_property_by_name(prop_name, value)
    call_notify_override(self, prop_name)


@overlay.method("Object")
def disconnect(self: Any, connection: SignalConnection | int) -> None:
    if isinstance(connection, SignalConnection):
        connection.disconnect()
        self._compat_forget_connection(connection)
        return
    if not features.is_enabled(features.OLD_SIGNAL_API):
        raise TypeError("GObject.disconnect(handler_id) is disabled by old_signal_api")
    self.disconnect_handler_id(int(connection))
    self._compat_forget_handler_id(int(connection))


@overlay.method("Object")
def handler_is_connected(self: Any, handler_id: object) -> bool:
    raw = (
        handler_id.handler_id
        if isinstance(handler_id, SignalConnection)
        else handler_id
    )
    return bool(self.handler_id_is_connected(int(cast("Any", raw))))


@overlay.method("Object")
def _compat_connections(self: Any) -> list[SignalConnection]:
    connections = vars(self).get("_compat_signal_connections")
    if connections is None:
        connections = []
        self._compat_signal_connections = connections
    return cast("list[SignalConnection]", connections)


@overlay.method("Object")
def _compat_remember_connection(self: Any, connection: SignalConnection) -> None:
    self._compat_connections().append(connection)


@overlay.method("Object")
def _compat_forget_connection(self: Any, connection: SignalConnection) -> None:
    connections = self._compat_connections()
    if connection in connections:
        connections.remove(connection)


@overlay.method("Object")
def _compat_forget_handler_id(self: Any, handler_id: int) -> None:
    connections = self._compat_connections()
    connections[:] = [c for c in connections if c.handler_id != handler_id]


@overlay.method("Object")
def _compat_signal_for_name(self: Any, name: str) -> _BoundSignal:
    try:
        return cast("_BoundSignal", self.signal_for_name(name))
    except AttributeError:
        return _BoundSignal(self, name.replace("_", "-"), None, None)


@overlay.property("Object")
def __grefcount__(self: Any) -> int:
    return int(self.ref_count())


def _same_callback(left: object, right: object) -> bool:
    if left is right:
        return True
    left_self = left.__self__ if isinstance(left, types.MethodType) else None
    right_self = right.__self__ if isinstance(right, types.MethodType) else None
    left_func = left.__func__ if isinstance(left, types.MethodType) else None
    right_func = right.__func__ if isinstance(right, types.MethodType) else None
    return left_self is right_self and left_func is not None and left_func is right_func


@overlay.method("Object")
def connect_data(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    *user_data: object,
    connect_flags: object = 0,
) -> SignalConnection:
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
    return cast("SignalConnection", connection)


@overlay.method("Object")
def connect_object(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    obj: object,
    *user_data: object,
    after: bool = False,
) -> SignalConnection:
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
    return cast("SignalConnection", connection)


@overlay.method("Object")
def connect_object_after(
    self: Any,
    signal_name: str,
    callback: Callable[..., Any],
    obj: object,
    *user_data: object,
) -> SignalConnection:
    return cast(
        "SignalConnection",
        self.connect_object(signal_name, callback, obj, *user_data, after=True),
    )


@overlay.method("Object")
def disconnect_by_func(self: Any, callback: Callable[..., Any]) -> None:
    for connection in list(self._compat_connections()):
        if _same_callback(connection.callback, callback):
            connection.disconnect()
            self._compat_forget_connection(connection)


@overlay.method("Object")
def handler_block_by_func(self: Any, callback: Callable[..., Any]) -> int:
    count = 0
    GObjectRepo = ginext.GObject
    for connection in self._compat_connections():
        if _same_callback(connection.callback, callback) and connection.is_connected:
            GObjectRepo.signal_handler_block(self, connection.handler_id)
            count += 1
    return count


@overlay.method("Object")
def handler_unblock_by_func(self: Any, callback: Callable[..., Any]) -> int:
    count = 0
    GObjectRepo = ginext.GObject
    for connection in self._compat_connections():
        if _same_callback(connection.callback, callback) and connection.is_connected:
            GObjectRepo.signal_handler_unblock(self, connection.handler_id)
            count += 1
    return count
