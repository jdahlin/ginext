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
from ginext.gobject.gobjectclass import _compat_dispose_state, _obj_signal_for_name
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
    if not isinstance(signal_name, str):
        raise TypeError(f"signal name must be a str, not {type(signal_name).__name__}")
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
    # Only delegate to _CompatProperty getters (not generic Python property objects)
    # so that get_property() always reads GObject native storage for plain properties.
    descriptor = type(self).__dict__.get(attr_name)
    if descriptor is not None and hasattr(descriptor, "fget") and descriptor.fget is not None:
        from gi._propertyhelper import _CompatProperty
        if isinstance(descriptor, _CompatProperty):
            return descriptor.fget(self)
    try:
        return type(self).gimeta.get_property(self, prop_name)
    except AttributeError:
        return self.get_property_by_name(prop_name)


def _coerce_char_value(value: Any, pspec_info: "dict | None") -> Any:
    """Coerce and validate a value for a gchar/guchar property pspec.

    Returns the coerced value, or raises OverflowError/TypeError on bad input.
    """
    if pspec_info is None:
        return value
    minimum = pspec_info.get("minimum")
    maximum = pspec_info.get("maximum")
    if minimum is None and maximum is None:
        return value

    # bytes → int
    if isinstance(value, (bytes, bytearray)):
        if len(value) != 1:
            raise TypeError(
                f"cannot marshal bytes of length {len(value)!r} as gchar"
            )
        b = value[0]
        # For signed char: bytes values ≥128 are interpreted as negative
        value = b if (minimum is None or minimum >= 0) else (b if b < 128 else b - 256)
        return value

    # str → int (single ASCII char only: 0x00..0x7F)
    if isinstance(value, str):
        if len(value) != 1:
            raise TypeError(
                f"cannot marshal {value!r} as gchar: expected a single character"
            )
        c = ord(value[0])
        if c > 127:
            raise TypeError(
                f"cannot marshal {value!r} as gchar: character out of ASCII range"
            )
        return c

    # Numeric range check → OverflowError
    if isinstance(value, int) and not isinstance(value, bool):
        if minimum is not None and value < minimum:
            raise OverflowError(
                f"value {value!r} is out of bounds [{minimum}, {maximum}]"
            )
        if maximum is not None and value > maximum:
            raise OverflowError(
                f"value {value!r} is out of bounds [{minimum}, {maximum}]"
            )
    return value


def _get_pspec_numeric_info(cls: Any, prop_name: str) -> "dict | None":
    """Return numeric pspec info (min/max/default) for a C property, or None."""
    try:
        from ginext import private
        pspec = cls.gimeta.param_spec(prop_name)
        if pspec is None:
            return None
        return private.param_spec_numeric_info(pspec)
    except Exception:
        pass
    return None


def _get_pspec(cls: Any, prop_name: str) -> Any | None:
    try:
        return cls.gimeta.param_spec(prop_name)
    except Exception:
        return None


@overlay.method("Object")
def set_property(self: Any, name: str, value: object) -> None:
    prop_name = name.replace("_", "-")
    attr_name = prop_name.replace("-", "_")
    descriptor_obj = type(self).__dict__.get(attr_name)
    # Check for Python-backed descriptor with setter
    if descriptor_obj is not None and hasattr(type(descriptor_obj), "__set__") and (
        getattr(descriptor_obj, "fset", None) is not None or getattr(descriptor_obj, "fget", None) is not None
    ):
        type(descriptor_obj).__set__(descriptor_obj, self, value)
        call_notify_override(self, prop_name)
        return
    # For C properties, validate/coerce numeric values (char overflow, bytes/str coercion)
    if getattr(descriptor_obj, "type", None) is str and not isinstance(value, str):
        value = str(value)
    if not hasattr(descriptor_obj, "gimeta"):
        pspec = _get_pspec(type(self), prop_name)
        if getattr(getattr(pspec, "value_type", None), "name", None) == "gchararray" and not isinstance(value, str):
            value = str(value)
        pspec_info = _get_pspec_numeric_info(type(self), prop_name)
        if pspec_info is not None and prop_name != "unichar":
            value = _coerce_char_value(value, pspec_info)
    try:
        type(self).gimeta.set_property(self, prop_name, value)
    except AttributeError as exc:
        msg = str(exc)
        if "construct-only" in msg or "construct_only" in msg:
            raise TypeError(msg) from None
        try:
            self.set_property_by_name(prop_name, value)
        except ValueError as inner:
            raise TypeError(str(inner)) from None
    except UnicodeEncodeError as exc:
        raise TypeError(str(exc)) from None
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

    def _get_numeric_info(self) -> "dict | None":
        try:
            from ginext import private
            pspec = object.__getattribute__(self, "_pspec")
            return private.param_spec_numeric_info(pspec)
        except Exception:
            pass
        return None

    def __getattr__(self, name: str) -> object:
        if name == "owner_type":
            owner = object.__getattribute__(self, "_owner_cls")
            if owner is not None and hasattr(owner, "__gtype__"):
                return owner.__gtype__
            raise AttributeError("owner_type")
        if name in ("minimum", "maximum", "default_value"):
            info = self._get_numeric_info()
            if info is not None and name in info:
                return info[name]
            raise AttributeError(name)
        if name == "flags":
            try:
                from ginext import private
                ptr = self._get_pspec_pointer()
                if ptr:
                    ps_info = private.param_spec_info(ptr)
                    raw_flags = ps_info.get("flags", 0)
                    try:
                        from gi.repository import GObject as _GO
                        return _GO.ParamFlags(raw_flags)
                    except Exception:
                        return raw_flags
            except Exception:
                pass
            raise AttributeError("flags")
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
        result = _namespace_find_by_gtype(int(gtype))
        if result is None:
            raise AttributeError(f"cannot find class for gtype {gtype!r}")
        namespace_name, class_name = result
        # Find the already-loaded namespace module (any profile).
        from gi import repository as _gi_repo
        ns_mod = getattr(_gi_repo, namespace_name, None)
        if ns_mod is None:
            raise AttributeError(f"namespace {namespace_name!r} not loaded")
        return getattr(ns_mod, class_name)


def _namespace_find_by_gtype(gtype: int) -> tuple[str, str] | None:
    from gi import repository as _gi_repo

    for namespace_name, ns_mod in vars(_gi_repo).items():
        version = getattr(ns_mod, "_version", None)
        if version is None:
            continue
        try:
            names = ginext.private.namespace_dir(namespace_name, version)
        except (AttributeError, TypeError, ValueError):
            continue
        for name in names:
            try:
                _kind, info = ginext.private.namespace_find(namespace_name, version, name)
            except (AttributeError, TypeError, ValueError):
                continue
            if int(getattr(info, "gtype", 0)) == gtype:
                return namespace_name, name
    return None


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
    # Try hyphenated form (pygobject uses "my-signal" while ginext stores "my_signal")
    hyphen_name = name.replace("_", "-")
    underscore_name = hyphen_name.replace("-", "_")
    try:
        return cast("_BoundSignal", _obj_signal_for_name(self, hyphen_name))
    except AttributeError:
        pass
    # signal_for_name searches only registered signals on the concrete GType.
    # For signals defined on GInterfaces implemented by a Python subclass (e.g. a
    # Python class that implements Gtk.TreeModel), the signal isn't found via
    # signal_for_name. Search:
    # 1. _compat_signal_descriptors: saved SignalDescriptors before compat overrides
    # 2. The MRO class dicts for a SignalDescriptor
    try:
        import ginext.signal.descriptor as _sig_desc
        import ginext.signal.bound as _sig_bound

        cls = type(self)

        # Check the saved signal descriptors map first (populated by compat overrides
        # that replaced signal attributes with plain functions)
        for base in cls.__mro__:
            saved = base.__dict__.get("_compat_signal_descriptors")
            if saved and underscore_name in saved:
                sd = saved[underscore_name]
                bound = sd.__get__(self, cls)
                if isinstance(bound, _sig_bound.Signal):
                    return cast("_BoundSignal", bound)
                break

        from gi._signalhelper import compat_signal_descriptors_for_gimeta

        for base in cls.__mro__:
            gimeta = getattr(base, "gimeta", None)
            if gimeta is None:
                continue
            sd = compat_signal_descriptors_for_gimeta(gimeta).get(underscore_name)
            if sd is None:
                continue
            bound = sd.__get__(self, cls)
            if isinstance(bound, _sig_bound.Signal):
                return cast("_BoundSignal", bound)

        # Fall back to searching the MRO class dicts for still-intact SignalDescriptors
        # or PyGObject-compat Signal (str subclass with get_signal_args).
        # Use duck-typing rather than isinstance(val, gi._signalhelper.Signal) so
        # that test fixtures which pop gi._signalhelper from sys.modules don't
        # break class-identity checks on pre-existing Signal instances.

        for base in cls.__mro__:
            val = base.__dict__.get(underscore_name)
            if val is None:
                continue
            if isinstance(val, _sig_desc.SignalDescriptor):
                bound = val.__get__(self, cls)
                if isinstance(bound, _sig_bound.Signal):
                    return cast("_BoundSignal", bound)
            elif isinstance(val, _sig_bound.Signal):
                return cast("_BoundSignal", val)
            elif (
                isinstance(val, str)
                and type(val) is not str
                and hasattr(val, "arg_types")
                and hasattr(val, "get_signal_args")
            ):
                # PyGObject Signal (str subclass descriptor). A ginext
                # _CompatSignalDescriptor was registered in the compat signal
                # descriptor bucket during class building (from __gsignals__);
                # check there first.
                # If missing (Signal defined directly as class attr, not via
                # __gsignals__), register it now as a _CompatSignalDescriptor.
                # Use duck-typing instead of isinstance(val, Signal) so that
                # module reloads (e.g. test fixtures that pop gi._signalhelper
                # from sys.modules) don't break class identity checks on
                # existing Signal instances.
                from gi._signalhelper import (
                    _CompatSignalDescriptor,
                    _compat_signal_type,
                    register_compat_signal_descriptor,
                )

                gimeta = getattr(base, "gimeta", None)
                if gimeta is None:
                    continue
                signal_descriptors = compat_signal_descriptors_for_gimeta(gimeta)
                sd = signal_descriptors.get(underscore_name)
                if sd is None:
                    # Not yet registered — create and register lazily.
                    if not str(val):
                        val = val.copy(underscore_name)
                        setattr(base, underscore_name, val)
                    signal_name = underscore_name.replace("_", "-")
                    resolved_args = tuple(
                        cast("type", _compat_signal_type(t)) for t in val.arg_types
                    )
                    resolved_ret = cast(
                        "type | None", _compat_signal_type(val.return_type)
                    )
                    sd = _CompatSignalDescriptor(
                        *resolved_args,
                        name=signal_name,
                        return_type=resolved_ret,
                        flags=int(cast("Any", val.flags)),
                        accumulator=val.accumulator,
                        accu_data=val.accu_data,
                    )
                    sd.__set_name__(base, underscore_name)
                    sd._register(gimeta)
                    register_compat_signal_descriptor(gimeta, underscore_name, sd)
                bound = sd.__get__(self, cls)
                if isinstance(bound, _sig_bound.Signal):
                    return cast("_BoundSignal", bound)
    except Exception:
        pass
    raise AttributeError(underscore_name) from None


@overlay.property("Object")
def __grefcount__(self: Any) -> int:
    try:
        return int(self.ref_count())
    except ValueError as exc:
        raise TypeError(str(exc)) from None


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
    is_bound = getattr(self, "is_bound", None)
    if not callable(is_bound) or not is_bound():
        return
    owns_ref = getattr(self, "owns_ref", None)
    if not callable(owns_ref) or not owns_ref():
        return
    preserve_wrapper_state = getattr(self, "preserve_wrapper_state", None)
    if callable(preserve_wrapper_state):
        preserve_wrapper_state()
    is_python_defined_gobject_subclass = globals().get(
        "_is_python_defined_gobject_subclass"
    )
    compat_finalize_dispose = globals().get("_compat_finalize_dispose")
    if callable(is_python_defined_gobject_subclass) and is_python_defined_gobject_subclass(
        type(self)
    ):
        if callable(compat_finalize_dispose):
            compat_finalize_dispose(self)
    release_ref = getattr(self, "release_ref", None)
    if callable(release_ref):
        release_ref()


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
