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

import sys
import warnings
import weakref as _weakref
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast

from .. import features
from ..gobject import gobjectclass as _gobject_root
from .. import private
from ..gobject.gtype import GTypeMeta
from ..gobject.properties import call_notify_override
from ..signal.adapt import _SIGNAL_ARG_LIMIT_ATTR, _accepted_signal_arg_count
from ..signal.bound import Signal as _BoundSignal
from ..signal.connection import SignalConnection
from ..signal.scoped import static_owner
from ginext import GLib, GObject

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..overlay import OverlayRegistrar
    from ..signal.bound import _PropertyDetail


overlay: OverlayRegistrar = GObject.overlay
overlay.hide_attribute("Value")


@overlay.replace
def type_from_name(fn: Any, name: str) -> int:
    """Return the GType id (int) for a type name, or 0 if not found."""
    return int(fn(name))


@overlay.replace
def type_fundamental(fn: Any, type_id: int) -> int:
    """Return the fundamental GType id (int) of a type."""
    return int(fn(type_id))


@overlay.replace
def type_children(fn: Any, type_id: int) -> list[int]:
    """Return the list of child GType ids for a type."""
    return list(fn(type_id))


@overlay.replace
def type_interfaces(fn: Any, type_id: int) -> list[int]:
    """Return the list of interface GType ids a type implements."""
    return list(fn(type_id))


overlay.deprecated(
    "markup_escape_text", GLib.markup_escape_text, "GLib.markup_escape_text"
)
overlay.deprecated("PRIORITY_DEFAULT", GLib.PRIORITY_DEFAULT, "GLib.PRIORITY_DEFAULT")
overlay.deprecated(
    "PRIORITY_DEFAULT_IDLE", GLib.PRIORITY_DEFAULT_IDLE, "GLib.PRIORITY_DEFAULT_IDLE"
)
overlay.deprecated("PRIORITY_HIGH", GLib.PRIORITY_HIGH, "GLib.PRIORITY_HIGH")
overlay.deprecated(
    "PRIORITY_HIGH_IDLE", GLib.PRIORITY_HIGH_IDLE, "GLib.PRIORITY_HIGH_IDLE"
)
overlay.deprecated("PRIORITY_LOW", GLib.PRIORITY_LOW, "GLib.PRIORITY_LOW")
overlay.deprecated("GError", GLib.GError, "GLib.GError")
overlay.deprecated(
    "PARAM_CONSTRUCT", GObject.ParamFlags.CONSTRUCT, "GObject.ParamFlags.CONSTRUCT"
)
overlay.deprecated(
    "SIGNAL_ACTION", GObject.SignalFlags.ACTION, "GObject.SignalFlags.ACTION"
)
overlay.deprecated("property", _gobject_root.Property, "GObject.Property")
overlay.deprecated("IO_STATUS_ERROR", GLib.IOStatus.ERROR, "GLib.IOStatus.ERROR")
overlay.deprecated("MainLoop", GLib.MainLoop, "GLib.MainLoop")
overlay.deprecated("MainContext", GLib.MainContext, "GLib.MainContext")
overlay.deprecated(
    "main_context_default", GLib.main_context_default, "GLib.main_context_default"
)
overlay.deprecated("G_MAXINT8", 2**7 - 1, "GLib.MAXINT8")
overlay.deprecated("G_MININT8", -(2**7), "GLib.MININT8")
overlay.deprecated("G_MAXUINT8", 2**8 - 1, "GLib.MAXUINT8")
overlay.deprecated("G_MAXINT16", 2**15 - 1, "GLib.MAXINT16")
overlay.deprecated("G_MININT16", -(2**15), "GLib.MININT16")
overlay.deprecated("G_MAXUINT16", 2**16 - 1, "GLib.MAXUINT16")
overlay.deprecated("G_MAXINT32", 2**31 - 1, "GLib.MAXINT32")
overlay.deprecated("G_MININT32", -(2**31), "GLib.MININT32")
overlay.deprecated("G_MAXUINT32", 2**32 - 1, "GLib.MAXUINT32")
overlay.deprecated("G_MAXINT64", 2**63 - 1, "GLib.MAXINT64")
overlay.deprecated("G_MININT64", -(2**63), "GLib.MININT64")
overlay.deprecated("G_MAXUINT64", GLib.MAXUINT64, "GLib.MAXUINT64")
overlay.constant("Property", _gobject_root.Property)


class _FreezeNotifyContext:
    __slots__ = ("_obj",)

    def __init__(self, obj: object) -> None:
        self._obj = obj

    def __enter__(self) -> _FreezeNotifyContext:
        return self

    def __exit__(
        self, exc_type: object, exc_value: object, tb: object
    ) -> Literal[False]:
        self._obj.thaw_notify()  # type: ignore[attr-defined]
        return False


class _NotifySignalSelector:
    __slots__ = ("_source",)

    def __init__(self, source: _gobject_root.GObject) -> None:
        self._source = source

    def __call__(self, detail: str | "_PropertyDetail") -> _BoundSignal:
        signal = _notify_bound_signal(self._source)
        return signal.detail_signal(detail)


class _NotifyCompatProxy:
    __slots__ = ("_source",)

    def __init__(self, source: _gobject_root.GObject) -> None:
        self._source = source

    def __call__(self, detail: str | "_PropertyDetail") -> object:
        from .. import private

        return private.invoke("GObject", "Object.notify", self._source, str(detail))

    def __getattr__(self, name: str) -> object:
        return getattr(_notify_bound_signal(self._source), name)

    def __repr__(self) -> str:
        return repr(_notify_bound_signal(self._source))


def _notify_bound_signal(source: _gobject_root.GObject) -> _BoundSignal:
    try:
        return source.signal_for_name("notify")
    except AttributeError:
        info = GObject.Object.gimeta.signal_infos["notify"]
        method = GObject.Object.gimeta.signal_method_backings.get("notify")
        return _BoundSignal(source, "notify", cast("Any", info), method)


@overlay.method("Object")
def freeze_notify(fn: Any, self: Any) -> _FreezeNotifyContext:
    fn(self)
    return _FreezeNotifyContext(self)


@overlay.property("Object")
def notify(self: _gobject_root.GObject) -> _NotifySignalSelector | _NotifyCompatProxy:
    if not features.is_enabled(features.NEW_SIGNAL_API):
        raise AttributeError("notify")
    if features.is_enabled(features.PYGOBJECT_COMPAT):
        return _NotifyCompatProxy(self)
    return _NotifySignalSelector(self)


class _HandlerBlockContext:
    __slots__ = ("_obj", "_handler_id")

    def __init__(self, obj: _gobject_root.GObject, handler_id: int) -> None:
        self._obj = obj
        self._handler_id = handler_id

    def __enter__(self) -> _HandlerBlockContext:
        GObject.signal_handler_block(self._obj, self._handler_id)
        return self

    def __exit__(
        self, exc_type: object, exc_value: object, tb: object
    ) -> Literal[False]:
        GObject.signal_handler_unblock(self._obj, self._handler_id)
        return False


def _normalize_handler_id(handler: object) -> int:
    if isinstance(handler, int):
        return handler
    raw = getattr(handler, "handler_id", None)
    if isinstance(raw, int):
        return raw
    raise TypeError(
        f"expected handler_id or SignalConnection, got {type(handler).__name__}"
    )


@overlay.method("Object")
def handler_block(
    self: _gobject_root.GObject, handler_id: int | SignalConnection
) -> _HandlerBlockContext:
    return _HandlerBlockContext(self, _normalize_handler_id(handler_id))


@overlay.method("Object")
def handler_unblock(
    self: _gobject_root.GObject, handler_id: int | SignalConnection
) -> None:
    GObject.signal_handler_unblock(self, _normalize_handler_id(handler_id))


@overlay.method("Object")
def get_data(self: Any, key: object = None) -> None:
    raise RuntimeError(
        "Data access methods are unsupported. Use Python attributes instead."
    )


@overlay.method("Object")
def force_floating(self: Any) -> None:
    raise RuntimeError("This method is currently unsupported.")


@overlay.method("Object")
def bind_property(
    fn: Any,
    self: Any,
    source_property: object,
    target: object,
    target_property: object,
    flags: object = None,
    transform_to: object = None,
    transform_from: object = None,
    user_data: object = None,
) -> object:
    if flags is None:
        flags = GObject.BindingFlags.DEFAULT
    if transform_to is None and transform_from is None:
        return fn(
            self,
            source_property,
            target,
            target_property,
            flags,
        )
    return _bind_property_full(
        self,
        source_property,
        target,
        target_property,
        flags,
        transform_to,
        transform_from,
        user_data,
    )


def _bind_property_full(
    source: object,
    source_property: object,
    target: object,
    target_property: object,
    flags: object,
    transform_to: object,
    transform_from: object,
    user_data: object,
) -> NoReturn:
    raise NotImplementedError(
        "bind_property with transform functions is not yet implemented"
    )


@overlay.method("Binding")
def __call__(self: Any) -> Any:
    from gi import _gi as _gi_m

    warnings.warn(
        "Binding.__call__ is deprecated and shouldn't be used anymore. "
        "It will be removed in a future version.",
        _gi_m.Warning,
        stacklevel=2,
    )
    return self


@overlay.method("Object")
def weak_ref(self: Any, callback: object = None, *args: object) -> object:
    if callback is None:
        return _weakref.ref(self)
    raise NotImplementedError("weak_ref with a callback is not yet implemented")


# User-defined GObject subclasses inherit from gobject.GObject (Python
# root), not the typelib's GObject.Object — install the same methods
# on the root so they're visible there too.
_root = _gobject_root.GObject
if (
    "freeze_notify" in _root.__dict__
    and "freeze_notify" not in GObject.Object.gimeta.typelib_methods
):
    GObject.Object.gimeta.typelib_methods["freeze_notify"] = _root.__dict__[
        "freeze_notify"
    ]


def _root_freeze_notify(self: _gobject_root.GObject) -> _FreezeNotifyContext:
    GObject.Object.gimeta.typelib_methods["freeze_notify"](self)
    return _FreezeNotifyContext(self)


def _root_notify(
    self: _gobject_root.GObject,
) -> _NotifySignalSelector | _NotifyCompatProxy:
    if not features.is_enabled(features.NEW_SIGNAL_API):
        raise AttributeError("notify")
    if features.is_enabled(features.PYGOBJECT_COMPAT):
        return _NotifyCompatProxy(self)
    return _NotifySignalSelector(self)


def _root_bind_property(
    self: Any,
    source_property: object,
    target: object,
    target_property: object,
    flags: object = None,
    transform_to: object = None,
    transform_from: object = None,
    user_data: object = None,
) -> object:
    if flags is None:
        flags = GObject.BindingFlags.DEFAULT
    if transform_to is None and transform_from is None:
        bind_property = GObject.Object.gimeta.typelib_methods["bind_property"]
        return bind_property(
            self,
            source_property,
            target,
            target_property,
            flags,
        )
    return _bind_property_full(
        self,
        source_property,
        target,
        target_property,
        flags,
        transform_to,
        transform_from,
        user_data,
    )


_root.freeze_notify = _root_freeze_notify  # type: ignore[method-assign, assignment]
_root.notify = property(_root_notify)  # type: ignore[attr-defined]
_root.handler_block = handler_block  # type: ignore[attr-defined]
_root.handler_unblock = handler_unblock  # type: ignore[attr-defined]
_root.bind_property = _root_bind_property  # type: ignore[attr-defined]
_root.weak_ref = weak_ref  # type: ignore[attr-defined]
_root.get_data = get_data  # type: ignore[attr-defined]
_root.force_floating = force_floating  # type: ignore[attr-defined]


# GObject.list_properties(type_or_instance) — pygobject compat function.
# Accepts: Python class with gimeta, string type name, __gtype__ object, or instance.
# Returns a list of ParamSpec-like objects with .name and .value_type attributes.
# Caches results by GType so repeated calls return the same list (enabling == comparisons).

_G_TYPE_INTERFACE = 8
_G_TYPE_OBJECT = 80

_list_props_cache: dict[int, list[Any]] = {}


class _ParamSpec:
    __slots__ = ("name", "value_type")

    def __init__(self, name: str, value_type: int) -> None:
        self.name = name
        self.value_type = value_type

    def __repr__(self) -> str:
        return f"<GParam name={self.name!r}>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _ParamSpec):
            return self.name == other.name and self.value_type == other.value_type
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.name, self.value_type))


@overlay.add("Object.new_with_properties")  # type: ignore[arg-type, untyped-decorator]
def new_with_properties(
    fn: Any, type_or_gtype: object, properties: dict[str, Any]
) -> Any:
    return fn(type_or_gtype, properties)


@overlay.add("interface_list_properties")  # type: ignore[arg-type, untyped-decorator]
def interface_list_properties(fn: Any, type_or_gtype: object) -> list[Any]:
    return fn(type_or_gtype)  # type: ignore[no-any-return]


def _interface_list_properties(gtype: int) -> list[_ParamSpec]:
    result: list[_ParamSpec] = []
    raw: list[tuple[str, int]] = interface_list_properties(gtype)  # type: ignore[arg-type]
    for name, value_type in raw:
        result.append(_ParamSpec(name, value_type))
    return result


def _resolve_to_gtype(arg: object) -> int:
    """Return the GType for arg, or -1 on failure (TypeError should be raised by caller)."""
    # Handle instances: delegate to their class
    if not isinstance(arg, type) and not isinstance(arg, str):
        # Check for __gtype__ (compat GTypeMeta)
        gtype_attr = getattr(type(arg), "__gtype__", None)
        if gtype_attr is not None and type(arg) is not type:
            return _resolve_to_gtype(type(arg))
        # Check for GObject instance via gimeta on the class
        cls = type(arg)
        gimeta = getattr(cls, "gimeta", None)
        if gimeta is not None and hasattr(gimeta, "gtype"):
            return int(gimeta.gtype)
        # Try __gtype__ on instance (e.g. GTypeMeta is itself a type but subclasses type)
        gtype = getattr(arg, "__gtype__", None)
        if gtype is not None:
            try:
                return int(gtype)
            except TypeError, ValueError:
                pass
        return -1

    if isinstance(arg, str):
        result = int(GObject.type_from_name(arg))
        return result if result else -1

    # arg is a type/class
    # First check for GTypeMeta (the gtype object itself is a class)
    if isinstance(arg, GTypeMeta):
        try:
            return int(arg)
        except TypeError, ValueError:
            pass
        return -1

    # Regular class with gimeta
    gimeta = None
    for base in arg.__mro__:
        g = base.__dict__.get("gimeta")
        if g is not None:
            gimeta = g
            break
    if gimeta is not None and hasattr(gimeta, "gtype"):
        gt = int(gimeta.gtype)
        return gt if gt else -1
    return -1


@overlay.add
def list_properties(type_or_instance: object) -> list[Any]:
    gtype = _resolve_to_gtype(type_or_instance)
    if gtype <= 0:
        raise TypeError(
            f"argument must be a GObject type, string type name, or GObject instance, "
            f"not {type(type_or_instance).__name__!r}"
        )

    cached = _list_props_cache.get(gtype)
    if cached is not None:
        return cached

    fundamental = int(GObject.type_fundamental(gtype))
    if fundamental == _G_TYPE_INTERFACE:
        result = _interface_list_properties(gtype)
    elif fundamental == _G_TYPE_OBJECT:
        # Resolve to the Python class to call the class struct list_properties on it
        try:
            data = private.GIMeta.info_by_gtype(gtype).object_info()
        except (AttributeError, RuntimeError) as exc:
            raise TypeError(f"could not find GObject class for gtype {gtype}") from exc
        ns = sys.modules["ginext"]._load_namespace(data["namespace"], data["version"])
        cls = getattr(ns, data["name"])
        result = list(cls.list_properties())
    else:
        raise TypeError(
            f"argument must be a GObject type or interface, "
            f"not {type(type_or_instance).__name__!r}"
        )

    _list_props_cache[gtype] = result
    return result


# pygobject-compat signal/property API. These live in the overlay layer rather
# than the GObject.Object base; the base keeps only signal_for_name and the
# pspec machinery they build on.
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
    return cast("SignalConnection", self.connect(signal_name, callback, *user_data, **kwargs))


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
