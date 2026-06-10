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
import weakref
from typing import TYPE_CHECKING, Any, cast

import ginext
from ginext import features
from ginext.gobject.gobjectclass import _compat_dispose_state
from ginext.gobject.properties import call_notify_override
from ginext.overlay.registrar import OverlayRegistrar
from ginext.signal.adapt import _SIGNAL_ARG_LIMIT_ATTR, _accepted_signal_arg_count
from ginext.signal.bound import Signal as _BoundSignal
from ginext.signal.connection import SignalConnection
from ginext.signal.scoped import static_owner

if TYPE_CHECKING:
    from collections.abc import Callable

overlay = OverlayRegistrar(ginext.GObject)


def _is_python_defined_gobject_subclass(type_or_gtype: Any) -> bool:
    if not isinstance(type_or_gtype, type):
        return False
    if not issubclass(type_or_gtype, ginext.private.GObject):
        return False
    try:
        gimeta = type_or_gtype.gimeta
    except AttributeError:
        return False
    try:
        gi_info = gimeta.gi_info
    except AttributeError:
        return False
    return gi_info is None


def _compat_finalize_dispose(self: Any) -> None:
    # Run a python do_dispose override during finalization, while the wrapper's
    # instance dict is still reachable (stashed in _compat_dispose_state — which
    # lives in core gobjectclass — so the base __getattr__ can serve it
    # mid-dispose). The caller (__del__ overlay) has checked self is a
    # python-defined subclass.
    base = ginext.private.GObject
    has_python_dispose = False
    for cls in type(self).__mro__:
        if not issubclass(cls, base):
            continue
        if cls is base:
            break
        if not _is_python_defined_gobject_subclass(cls):
            continue
        if "do_dispose" in cls.__dict__:
            has_python_dispose = True
            break
    if not has_python_dispose:
        return
    dispose_state = dict(vars(self))
    if dispose_state:
        _compat_dispose_state[id(self)] = dispose_state
    try:
        self.bind_from_c(self)
        base.run_dispose(self)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    finally:
        _compat_dispose_state.pop(id(self), None)


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
    signal = self._compat_signal_for_name(signal_name)
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
    attr_name = prop_name.replace("-", "_")
    # Check for Python-backed descriptor (e.g. @GObject.Property decorator)
    descriptor = type(self).__dict__.get(attr_name)
    if descriptor is not None and hasattr(type(descriptor), "__get__") and hasattr(descriptor, "fget") and descriptor.fget is not None:
        return type(descriptor).__get__(descriptor, self, type(self))
    try:
        return type(self).gimeta.get_property(self, prop_name)
    except AttributeError:
        return self.get_property_by_name(prop_name)


@overlay.method("Object")
def set_property(self: Any, name: str, value: object) -> None:
    prop_name = name.replace("_", "-")
    attr_name = prop_name.replace("-", "_")
    # Check for Python-backed descriptor with setter
    descriptor = type(self).__dict__.get(attr_name)
    if descriptor is not None and hasattr(type(descriptor), "__set__") and (
        getattr(descriptor, "fset", None) is not None or getattr(descriptor, "fget", None) is not None
    ):
        type(descriptor).__set__(descriptor, self, value)
        call_notify_override(self, prop_name)
        return
    try:
        type(self).gimeta.set_property(self, prop_name, value)
    except AttributeError:
        self.set_property_by_name(prop_name, value)
    call_notify_override(self, prop_name)


@overlay.method("Object")
def set_properties(self: Any, **kwargs: object) -> None:
    for name, value in kwargs.items():
        self.set_property(name, value)


@overlay.method("Object")
def get_properties(self: Any, *names: str) -> tuple[object, ...]:
    return tuple(self.get_property(name) for name in names)


class _ParamSpecWrapper:
    """Wraps a ginext ParamSpec, adding flags_class / enum_class for compat."""

    __slots__ = ("_pspec", "_owner_cls")

    @property
    def __class__(self) -> type:
        try:
            from gi.repository import GObject as _GObj
            return _GObj.ParamSpec
        except Exception:
            return type(self._pspec)

    def __init__(self, pspec: object, owner_cls: object = None) -> None:
        object.__setattr__(self, "_pspec", pspec)
        object.__setattr__(self, "_owner_cls", owner_cls)

    def __getattr__(self, name: str) -> object:
        if name == "owner_type":
            owner = object.__getattribute__(self, "_owner_cls")
            if owner is not None and hasattr(owner, "__gtype__"):
                return owner.__gtype__
            raise AttributeError("owner_type")
        if name == "flags_class":
            vtype = getattr(self._pspec, "value_type", None)
            if vtype is not None:
                return self._gtype_to_class(vtype)
            raise AttributeError("flags_class")
        if name == "enum_class":
            vtype = getattr(self._pspec, "value_type", None)
            if vtype is not None:
                return self._gtype_to_class(vtype)
            raise AttributeError("enum_class")
        return getattr(self._pspec, name)

    def __dir__(self) -> list:
        base = dir(type(self)) + [
            "owner_type", "flags_class", "enum_class",
            "flags", "name", "nick", "blurb", "value_type",
            "default_value", "minimum", "maximum",
        ]
        base += dir(object.__getattribute__(self, "_pspec"))
        return sorted(set(base))

    def _gtype_to_class(self, gtype: object) -> object:
        from ginext import private
        import ginext
        import sys

        result = private.namespace_find_by_gtype(int(gtype))
        if result is None:
            raise AttributeError(f"cannot find class for gtype {gtype!r}")
        namespace_name, class_name = result
        # Find the already-loaded namespace module (any profile).
        from gi import repository as _gi_repo
        ns_mod = getattr(_gi_repo, namespace_name, None)
        if ns_mod is None:
            raise AttributeError(f"namespace {namespace_name!r} not loaded")
        return getattr(ns_mod, class_name)


@overlay.method("Object", as_classmethod=True)
def find_property(cls: Any, name: str) -> object:
    prop_name = name.replace("_", "-")
    pspec = cls.gimeta.param_spec(prop_name)
    if pspec is None:
        raise AttributeError(f"no property '{name}'")
    return _ParamSpecWrapper(pspec, owner_cls=cls)


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


@overlay.method("Object")
def __repr__(self: Any) -> str:
    # Overrides the native C tp_repr. This overlay only exists in compat mode, so
    # we unconditionally use pygobject's form (the GObject address printed twice).
    module = (
        type(self).__module__.removeprefix("ginext.").removeprefix("gi.repository.")
    )
    type_name = type(self).gimeta.type_name
    name = type(self).__name__
    if not self.is_bound():
        return f"<{module}.{name} object at 0x{id(self):x} ({type_name} unbound)>"
    return (
        f"<{module}.{name} object at 0x{id(self):x} ({type_name} at 0x{id(self):x})>"
    )


@overlay.method("Object")
def __del__(self: Any) -> None:
    # Overrides the native C tp_finalize. Only installed in compat mode, so it
    # unconditionally runs the python do_dispose override for python-defined
    # subclasses before the unref.
    if not self.is_bound():
        return
    if not self.owns_ref():
        return
    self.preserve_wrapper_state()
    if _is_python_defined_gobject_subclass(type(self)):
        _compat_finalize_dispose(self)
    self.release_ref()


@overlay.method("Object")
def _force_floating(self: Any) -> None:
    self.make_floating()


@overlay.method("Object")
def _ref_sink(self: Any) -> None:
    self.ref_sink()


@overlay.method("Object")
def _compat_property_for_name(self: Any, name: str) -> object:
    prop_name = name.replace("_", "-").removesuffix("-")
    try:
        return type(self).gimeta.get_property(self, prop_name)
    except AttributeError:
        try:
            return self.get_property_by_name(prop_name)
        except (AttributeError, TypeError):
            raise AttributeError(name) from None


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


class _PythonBinding:
    """Pure-Python binding that applies transform functions via signal connections."""

    def __init__(
        self,
        source: Any,
        source_property: str,
        target: Any,
        target_property: str,
        flags: Any,
        transform_to: Any,
        transform_from: Any,
        user_data: Any,
    ) -> None:
        self._active = True
        self._updating = False
        self._source_ref = weakref.ref(source)
        self._target_ref = weakref.ref(target)
        self._handlers: list[tuple[weakref.ref[Any], int]] = []
        self._transform_to = transform_to
        self._transform_from = transform_from

        flags_int = int(flags) if flags is not None else 0
        bidirectional = bool(flags_int & 1)

        # Keep separate references to user_data per-callback so refcounts
        # increase by 1 per callback, matching pygobject's C implementation.
        _ud_to = user_data
        _ud_from = user_data

        def _on_source(obj: Any, pspec: Any) -> None:
            if not self._active or self._updating:
                return
            t = self._target_ref()
            if t is None:
                return
            value = obj.get_property(source_property)
            fn = self._transform_to
            new_value = fn(self, value, _ud_to) if fn is not None else value
            if new_value is not None:
                self._updating = True
                try:
                    t.set_property(target_property, new_value)
                finally:
                    self._updating = False

        hid = source.connect(f"notify::{source_property}", _on_source)
        self._handlers.append((weakref.ref(source), hid))

        if bidirectional:
            def _on_target(obj: Any, pspec: Any) -> None:
                if not self._active or self._updating:
                    return
                s = self._source_ref()
                if s is None:
                    return
                value = obj.get_property(target_property)
                fn = self._transform_from
                new_value = fn(self, value, _ud_from) if fn is not None else value
                if new_value is not None:
                    self._updating = True
                    try:
                        s.set_property(source_property, new_value)
                    finally:
                        self._updating = False

            hid = target.connect(f"notify::{target_property}", _on_target)
            self._handlers.append((weakref.ref(target), hid))

    def unbind(self) -> None:
        self._active = False
        self._transform_to = None
        self._transform_from = None
        for obj_ref, hid in self._handlers:
            obj = obj_ref()
            if obj is not None:
                obj.disconnect(hid)
        self._handlers.clear()

    @property
    def __grefcount__(self) -> int:
        return 1


def _make_compat_bind_property(gobject_cls: Any) -> None:
    """Replace _bind_property_full in ginext._overlays.GObject to support transforms."""
    import ginext._overlays.GObject as _goverlays

    def _bind_property_full_compat(
        source: Any,
        source_property: Any,
        target: Any,
        target_property: Any,
        flags: Any,
        transform_to: Any,
        transform_from: Any,
        user_data: Any,
    ) -> object:
        return _PythonBinding(
            source,
            source_property,
            target,
            target_property,
            flags,
            transform_to,
            transform_from,
            user_data,
        )

    _goverlays._bind_property_full = _bind_property_full_compat
