# Copyright 2026 Johan Dahlin
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

from __future__ import annotations

import enum
import math
import struct
import sys
import warnings
from typing import Any, Callable, Iterable, cast

import ginext
from gi import PyGIDeprecationWarning
from gi._propertyhelper import CompatProperty as Property
from ginext.gobject.gobjectclass import GObject as _GObject
from ginext.gobject.gobjectclass import GInterface as _GInterface
from ginext.gobject.gtype import GType
from ginext.gobject.gtype import compat_gtype_from_raw
from ginext.gobject.resolve import own_gimeta
from ginext.enum import (
    GIEnum,
    GIFlags,
    register_enum_base_hook as _register_enum_base_hook,
)
from ginext.namespace import Namespace
from ginext.signal.connection import SignalConnection
from ginext.signal.descriptor import SignalDescriptor


__path__: list[str] = []

_GFLOAT_MAX = 3.4028234663852886e38
_GULONG_MAX = (1 << (struct.calcsize("L") * 8)) - 1
_MISSING = object()
_GOBJECT_VALUE_CLASS_KEY = "_gi_repository_gobject_value_class"


class GEnum(GIEnum):
    @property
    def value_name(self) -> str:
        return getattr(type(self), "_value_names", {}).get(int(self), self.name)

    @property
    def value_nick(self) -> str:
        return getattr(type(self), "_value_nicks", {}).get(
            int(self), self.name.lower().replace("_", "-")
        )


class GFlags(GIFlags):
    @property
    def value_names(self) -> list[str]:
        names: dict[int, str] = getattr(type(self), "_value_names", {})
        return [
            names.get(int(member), member.name or "")
            for member in type(self)
            if member in self
        ]

    @property
    def value_nicks(self) -> list[str]:
        nicks: dict[int, str] = getattr(type(self), "_value_nicks", {})
        return [
            nicks.get(int(member), (member.name or "").lower().replace("_", "-"))
            for member in type(self)
            if member in self
        ]

    @property
    def first_value_name(self) -> str:
        names = self.value_names
        return names[0] if names else "0"

    @property
    def first_value_nick(self) -> str:
        nicks = self.value_nicks
        return nicks[0] if nicks else "0"


def _gi_enum_base_hook(base: type) -> type:
    return GFlags if issubclass(base, enum.IntFlag) else GEnum


_register_enum_base_hook(_gi_enum_base_hook)


def _clear_value_cache(obj: object, name: str) -> None:
    if hasattr(obj, name):
        delattr(obj, name)


def _coerce_char_value(value: object, *, unsigned: bool) -> object:
    if isinstance(value, bytes):
        if len(value) != 1:
            kind = "uchar" if unsigned else "char"
            raise TypeError(f"{kind} GValue expects a single byte")
        value = value[0]
    elif isinstance(value, str):
        if len(value) != 1:
            kind = "uchar" if unsigned else "char"
            raise TypeError(f"{kind} GValue expects a single character")
        value = ord(value)
    if isinstance(value, int):
        if unsigned:
            if value < 0 or value > 255:
                raise OverflowError("value out of range for guchar")
        elif value < -128 or value > 127:
            raise OverflowError("value out of range for gchar")
    return value


def _check_gfloat_range(value: object) -> None:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric) and abs(numeric) > _GFLOAT_MAX:
            raise OverflowError("value out of range for gfloat")


def _value_gtype_info(namespace: Namespace, g_type: object) -> tuple[Any, str | None]:
    if g_type is None:
        return 0, None
    if g_type is bool:
        return GType.BOOLEAN, None
    if g_type is int:
        return GType.INT, None
    if g_type is float:
        return GType.DOUBLE, None
    if g_type is str:
        return GType.STRING, None
    if g_type is object:
        return GType.POINTER, None

    gimeta = getattr(g_type, "gimeta", None)
    if isinstance(g_type, type):
        type_name = getattr(g_type, "gtype_name", None) or getattr(
            gimeta, "type_name", None
        )
        if g_type is getattr(ginext.GLib, "Error", None):
            return int(ginext.private.gerror_get_type()), "GError"
        return getattr(g_type, "__gtype__", g_type), type_name
    if gimeta is not None and hasattr(gimeta, "gtype"):
        return gimeta.gtype, getattr(gimeta, "type_name", None)
    return g_type, getattr(g_type, "gtype_name", None)


def _native_gobject_value_base() -> type[Any]:
    kind, info = ginext.private.namespace_find(
        "GObject", ginext.GObject._version, "Value"
    )
    assert kind == "record"
    return ginext.GObject._record_builder.build_record(info)


def _make_gobject_value_class(namespace: Namespace) -> type:
    cached = getattr(ginext, _GOBJECT_VALUE_CLASS_KEY, None)
    if cached is not None:
        return cached
    base: type[Any] = _native_gobject_value_base()

    class Value(base):
        __module__ = namespace.__name__

        def __new__(cls, g_type: object = None, value: object = None):
            obj = super().__new__(cls)
            if g_type is not None:
                coerced_gtype, type_name = _value_gtype_info(namespace, g_type)
                ginext.private.gvalue_init_value(obj, coerced_gtype)
                if type_name is not None:
                    obj._value_type_name = type_name
            if value is not None:
                obj.set_value(value)
            return obj

        def init(self, g_type: object) -> None:
            coerced_gtype, type_name = _value_gtype_info(namespace, g_type)
            ginext.private.gvalue_init_value(self, coerced_gtype)
            if type_name is not None:
                self._value_type_name = type_name

        @property
        def g_type(self):
            raw = int(ginext.private.gvalue_get_gtype(self))
            type_name = getattr(self, "_value_type_name", None)
            if raw == 0:
                return namespace.TYPE_INVALID
            return compat_gtype_from_raw(raw, type_name or namespace.type_name(raw))

        def __repr__(self) -> str:
            g_type = self.g_type
            if g_type == namespace.TYPE_INVALID:
                type_name = "invalid"
            else:
                type_name = getattr(g_type, "gtype_name", str(g_type))
            return f"<Value ({type_name}) {self.get_value()!r}>"

        def unset(self) -> None:
            _clear_value_cache(self, "_cached_variant")
            _clear_value_cache(self, "_pyobject_value")
            ginext.private.gvalue_unset_value(self)

        def reset(self) -> None:
            _clear_value_cache(self, "_cached_variant")
            _clear_value_cache(self, "_pyobject_value")
            ginext.private.gvalue_reset_value(self)

        def get_value(self) -> object:
            g_type = self.g_type
            raw = int(g_type)
            type_name = getattr(self, "_value_type_name", None)
            if raw == 0:
                return None
            if type_name == "PyObject":
                cached = getattr(self, "_pyobject_value", _MISSING)
                if cached is not _MISSING:
                    return cached
                return None
            if type_name == "GValueArray":
                return ginext.private.gvalue_get_value(self)
            if raw == int(namespace.TYPE_POINTER):
                value = ginext.private.gvalue_get_value(self)
                return 0 if value is None else value
            if raw == int(namespace.TYPE_VARIANT.gimeta.gtype):
                cached = getattr(self, "_cached_variant", None)
                if cached is not None:
                    return cached
            if raw == int(namespace.TYPE_GTYPE):
                value = self.get_gtype()
                raw_value = int(getattr(getattr(value, "gimeta", None), "gtype", value))
                if raw_value == 0:
                    return namespace.TYPE_INVALID
                return compat_gtype_from_raw(raw_value, namespace.type_name(raw_value))
            return ginext.private.gvalue_get_value(self)

        def set_value(self, value: object) -> None:
            g_type = self.g_type
            raw = int(g_type)
            type_name = getattr(self, "_value_type_name", None)
            if raw == 0:
                raise TypeError("GObject.Value needs to be initialized first")
            if type_name == "PyObject":
                self._pyobject_value = value
                return None
            if (
                type_name == "GValueArray"
                and value is not None
                and not isinstance(value, namespace.ValueArray)
            ):
                array = namespace.ValueArray.new(0)
                for item in cast("Iterable[object]", value):
                    if isinstance(item, base):
                        array.append(item)
                    else:
                        array.append(type(self)(type(item), item))
                value = array
            if raw == int(namespace.TYPE_CHAR):
                value = _coerce_char_value(value, unsigned=False)
            if raw == int(namespace.TYPE_UCHAR):
                value = _coerce_char_value(value, unsigned=True)
            if (
                raw == int(namespace.TYPE_ULONG)
                and isinstance(value, int)
                and (value < 0 or value > _GULONG_MAX)
            ):
                raise OverflowError("value out of range for gulong")
            if raw == int(namespace.TYPE_FLOAT):
                _check_gfloat_range(value)
            if raw == int(namespace.TYPE_VARIANT.gimeta.gtype):
                self._cached_variant = value
            return ginext.private.gvalue_set_value(self, value)

        def set_string(self, value: object) -> object:
            if isinstance(value, bytes):
                raise TypeError("string GValue expects str or None")
            self.set_value(value)
            return None

        def set_float(self, value: object) -> object:
            _check_gfloat_range(value)
            self.set_value(value)
            return None

        def get_boxed(self) -> object:
            g_type = self.g_type
            if not getattr(g_type, "is_a", lambda other: False)(namespace.TYPE_BOXED):
                warnings.warn(
                    "Calling get_boxed() on a non-boxed GValue is deprecated",
                    PyGIDeprecationWarning,
                    stacklevel=2,
                )
                return self.get_value()
            return self._typelib_get_boxed()

        def set_boxed(self, value: object) -> object:
            g_type = self.g_type
            if not getattr(g_type, "is_a", lambda other: False)(namespace.TYPE_BOXED):
                warnings.warn(
                    "Calling set_boxed() on a non-boxed GValue is deprecated",
                    PyGIDeprecationWarning,
                    stacklevel=2,
                )
                self.set_value(value)
                return None
            return self._typelib_set_boxed(value)

    Value.__name__ = "Value"
    Value.__qualname__ = "Value"
    setattr(ginext, _GOBJECT_VALUE_CLASS_KEY, Value)
    return Value


def _install_gobject_compat(namespace: Namespace) -> object:
    from ._signalhelper import Signal, SignalOverride

    GEnum.__gtype__ = _gtype_for_name("GEnum")
    GFlags.__gtype__ = _gtype_for_name("GFlags")
    namespace.GObject = _GObject
    namespace.GInterface = _GInterface
    namespace.GEnum = GEnum
    namespace.GFlags = GFlags
    namespace.GBoxed = ginext.private.GBoxed
    namespace.GPointer = ginext.private.GBoxed
    namespace.Property = Property
    namespace.Signal = Signal
    namespace.SignalOverride = SignalOverride
    namespace.GType = GType
    namespace.Type = GType
    namespace.new = _gobject_new
    _gobject_cls: Any = namespace.GObject
    _gobject_cls.newv = classmethod(_gobject_newv)
    _install_gobject_signal_methods(_gobject_cls)
    _install_gobject_props(_gobject_cls)
    namespace.type_from_name = _gobject_type_from_name
    namespace.Value = _make_gobject_value_class(namespace)
    namespace.TYPE_INVALID = compat_gtype_from_raw(0, "invalid")
    namespace.TYPE_NONE = GType.NONE
    namespace.TYPE_BOOLEAN = GType.BOOLEAN
    namespace.TYPE_CHAR = GType.CHAR
    namespace.TYPE_UCHAR = GType.UCHAR
    namespace.TYPE_INT = GType.INT
    namespace.TYPE_UINT = GType.UINT
    namespace.TYPE_LONG = GType.LONG
    namespace.TYPE_ULONG = GType.ULONG
    namespace.TYPE_INT64 = GType.INT64
    namespace.TYPE_UINT64 = GType.UINT64
    namespace.TYPE_FLOAT = GType.FLOAT
    namespace.TYPE_DOUBLE = GType.DOUBLE
    namespace.TYPE_STRING = GType.STRING
    namespace.TYPE_GTYPE = GType.GTYPE
    namespace.TYPE_PARAM = GType.PARAM
    namespace.TYPE_VALUE = compat_gtype_from_raw(
        int(ginext.private.gvalue_get_type()), "GValue"
    )
    namespace.TYPE_OBJECT = GType.OBJECT
    namespace.TYPE_INTERFACE = object
    namespace.TYPE_BOXED = GType.BOXED
    namespace.TYPE_ENUM = namespace.GEnum.__gtype__
    namespace.TYPE_FLAGS = namespace.GFlags.__gtype__
    namespace.TYPE_POINTER = GType.POINTER
    namespace.TYPE_UNICHAR = namespace.TYPE_UINT
    namespace.TYPE_STRV = GType.STRV
    namespace.TYPE_GSTRING = str
    if _PYOBJECT_GTYPE:
        namespace.TYPE_PYOBJECT = compat_gtype_from_raw(_PYOBJECT_GTYPE, "PyObject")
    else:
        namespace.TYPE_PYOBJECT = compat_gtype_from_raw(
            int(namespace.TYPE_POINTER.gimeta.gtype), "PyObject"
        )
    namespace.TYPE_VARIANT = getattr(ginext.GLib, "Variant", object)
    _value_cls: Any = namespace.Value
    _value_cls.__gtype__ = namespace.TYPE_VALUE
    namespace.Float = lambda value=0.0: namespace.Value(GType.FLOAT, value)
    namespace.type_is_a = _gobject_type_is_a
    namespace.type_parent = _gobject_type_parent
    namespace.signal_list_names = _signal_list_names
    namespace.signal_new = _signal_new
    namespace.signal_list_ids = _signal_list_ids
    namespace.signal_lookup = _signal_lookup
    namespace.signal_name = _signal_name
    namespace.signal_query = _signal_query
    namespace.signal_parse_name = _signal_parse_name
    namespace.signal_has_handler_pending = _signal_has_handler_pending
    namespace.signal_handler_find = _signal_handler_find
    namespace.add_emission_hook = _add_emission_hook
    namespace.remove_emission_hook = _remove_emission_hook
    namespace.signal_connect_closure = _signal_connect_closure
    namespace.signal_handlers_block_matched = _signal_handlers_block_matched
    namespace.signal_handlers_unblock_matched = _signal_handlers_unblock_matched
    namespace.signal_handlers_disconnect_matched = _signal_handlers_disconnect_matched
    return namespace


def _install_gobject_signal_methods(gobject_cls: Any) -> None:
    """Install the pygobject-shaped GObject methods onto the GObject class.

    These live in the compat package, not core ginext: native ginext offers the
    attribute-based signal API and attribute property access. connect/emit/
    disconnect/get_property/set_property, the connect_object/connect_data/by-func
    variants and the _compat_* bookkeeping are all pygobject's shape, registered
    (on import of _gobject_compat_methods) as a second overlay source for
    GObject.Object. GObject.Object is already built here, so apply the freshly
    registered ("GObject", "Object") overlays explicitly.
    """
    from ginext.overlay.install import install_class_overlay

    from . import _gobject_compat_methods  # noqa: F401  (registers overlays)

    install_class_overlay(gobject_cls, "GObject", "Object")


def _install_gobject_props(gobject_cls: Any) -> None:
    """Install the pygobject `obj.props` property bag onto the GObject class."""
    from ._gobject_props import install_props

    install_props(gobject_cls)


def _gtype_for_name(name: str) -> type:
    return type(
        name,
        (GType,),
        {
            "__module__": __name__,
            "gimeta": ginext.private.GIMeta.from_type_name(name),
            "gtype_name": name,
        },
    )


def _gobject_new(gtype_or_cls: object, **properties: object) -> object:
    if isinstance(gtype_or_cls, type):
        return gtype_or_cls(**properties)
    raise TypeError("GObject.new requires a GObject class")


def _gobject_newv(cls: type, *args: object) -> object:
    cls_name = cls.__name__
    if not isinstance(cls_name, str):
        raise TypeError("attribute is not a string")
    if not isinstance(cls, type) or not issubclass(cls, _GObject):
        raise TypeError(f"{cls_name} is not a GObject class")
    return cls()


def _register_pyobject_gtype() -> int:
    """Register a named pointer GType 'PyObject' and return its GType value."""
    return int(ginext.private.pointer_type_register_static("PyObject"))


_PYOBJECT_GTYPE: int = _register_pyobject_gtype()


def _resolve_gtype_for_compat(arg: object) -> int:
    """Return int GType for arg, or -1 for invalid Python class.
    Raises TypeError for plain Python int (not a GType subclass)."""
    if isinstance(arg, GType):
        return int(arg)
    if isinstance(arg, int):
        raise TypeError("type must be a GType or GObject class, not plain int")
    if isinstance(arg, type):
        for base in arg.__mro__:
            g = own_gimeta(base)
            if g is not None and hasattr(g, "gtype"):
                gtype = int(g.gtype)
                return gtype if gtype else -1
        gtype_attr = getattr(arg, "__gtype__", None)
        if gtype_attr is not None:
            try:
                return int(gtype_attr)
            except TypeError, ValueError:
                pass
        return -1
    cls = type(arg)
    for base in cls.__mro__:
        g = own_gimeta(base)
        if g is not None and hasattr(g, "gtype"):
            gtype = int(g.gtype)
            return gtype if gtype else -1
    return -1


def _gobject_type_from_name(name: str) -> object:
    if name == "GError":
        return compat_gtype_from_raw(int(ginext.private.gerror_get_type()), "GError")
    result = ginext.GObject.type_from_name(name)
    raw = int(result) if result is not None else 0
    if raw == 0:
        raise RuntimeError(f"invalid type name: {name!r}")
    return compat_gtype_from_raw(raw, name)


def _gobject_type_is_a(instance_type: object, iface_type: object) -> bool:
    inst_gtype = _resolve_gtype_for_compat(instance_type)
    if inst_gtype <= 0:
        raise TypeError(
            f"argument 1 must be a GObject type, not {type(instance_type).__name__!r}"
        )
    try:
        iface_gtype = _resolve_gtype_for_compat(iface_type)
    except TypeError:
        raise
    if iface_gtype <= 0:
        return False
    return bool(ginext.private.invoke("GObject", "type_is_a", inst_gtype, iface_gtype))


def _gobject_type_parent(type_or_gtype: object) -> object:
    gtype = _resolve_gtype_for_compat(type_or_gtype)
    if gtype <= 0:
        raise TypeError(
            f"argument must be a GObject type, not {type(type_or_gtype).__name__!r}"
        )
    result = ginext.private.invoke("GObject", "type_parent", gtype)
    raw = int(result) if result is not None else 0
    if raw == 0:
        raise RuntimeError(f"{type_or_gtype!r} does not have a parent type")
    type_name = ginext.GObject.type_name(raw)
    return compat_gtype_from_raw(raw, type_name)


def _gobject_float(value: object = 0.0) -> object:
    return ginext.GObject.Value(GType.FLOAT, value)


def _install_glib_compat(namespace: Namespace) -> object:
    namespace.MININT8 = -(2**7)
    namespace.MAXINT8 = 2**7 - 1
    namespace.MAXUINT8 = 2**8 - 1
    namespace.MININT16 = -(2**15)
    namespace.MAXINT16 = 2**15 - 1
    namespace.MAXUINT16 = 2**16 - 1
    namespace.MINSHORT = -(2**15)
    namespace.MAXSHORT = 2**15 - 1
    namespace.MAXUSHORT = 2**16 - 1
    namespace.MININT = -(2**31)
    namespace.MAXINT = 2**31 - 1
    namespace.MAXUINT = 2**32 - 1
    namespace.MININT32 = -(2**31)
    namespace.MAXINT32 = 2**31 - 1
    namespace.MAXUINT32 = 2**32 - 1
    namespace.MININT64 = -(2**63)
    namespace.MAXINT64 = 2**63 - 1
    namespace.MAXUINT64 = 2**64 - 1
    # C long/unsigned long are pointer-width on LP64 but only 32-bit on LLP64
    # (Windows). Reuse the fixed-width limits per platform.
    if sys.platform == "win32":
        namespace.MINLONG = namespace.MININT32
        namespace.MAXLONG = namespace.MAXINT32
        namespace.MAXULONG = namespace.MAXUINT32
    else:
        namespace.MINLONG = namespace.MININT64
        namespace.MAXLONG = namespace.MAXINT64
        namespace.MAXULONG = namespace.MAXUINT64
    namespace.MINSSIZE = -(2**63)
    namespace.MAXSSIZE = 2**63 - 1
    namespace.MAXSIZE = 2**64 - 1
    namespace.MINFLOAT = -3.4028234663852886e38
    namespace.MAXFLOAT = 3.4028234663852886e38
    namespace.MINDOUBLE = -1.7976931348623157e308
    namespace.MAXDOUBLE = 1.7976931348623157e308
    namespace.GError = namespace.Error
    if not getattr(namespace.idle_add, "_pygobject_compat_args", False):
        raw_idle_add = namespace.idle_add

        def idle_add(
            function: Callable[..., Any],
            *args: object,
            priority: int = namespace.PRIORITY_DEFAULT_IDLE,
        ):
            if args:

                def callback() -> object:
                    return function(*args)
            else:
                callback = function
            return raw_idle_add(callback, priority=priority)

        idle_add.__dict__["_pygobject_compat_args"] = True
        namespace.idle_add = idle_add
    if not getattr(namespace.timeout_add, "_pygobject_compat_args", False):
        raw_timeout_add = namespace.timeout_add

        def timeout_add(
            interval: int,
            function: Callable[..., Any],
            *args: object,
            priority: int = namespace.PRIORITY_DEFAULT,
        ):
            if args:

                def callback() -> object:
                    return function(*args)
            else:
                callback = function
            return raw_timeout_add(interval, callback, priority=priority)

        timeout_add.__dict__["_pygobject_compat_args"] = True
        namespace.timeout_add = timeout_add
    if not getattr(namespace.timeout_add_seconds, "_pygobject_compat_args", False):
        raw_timeout_add_seconds = namespace.timeout_add_seconds

        def timeout_add_seconds(
            interval: int,
            function: Callable[..., Any],
            *args: object,
            priority: int = namespace.PRIORITY_DEFAULT,
        ):
            if args:

                def callback() -> object:
                    return function(*args)
            else:
                callback = function
            return raw_timeout_add_seconds(interval, callback, priority=priority)

        timeout_add_seconds.__dict__["_pygobject_compat_args"] = True
        namespace.timeout_add_seconds = timeout_add_seconds
    if not getattr(namespace.filename_from_utf8, "_pygobject_compat_shape", False):
        raw_filename_from_utf8 = namespace.filename_from_utf8

        def filename_from_utf8(utf8string: object, length: int = -1):
            result = raw_filename_from_utf8(utf8string, length)
            if isinstance(result, tuple):
                return result[0]
            return result

        filename_from_utf8.__dict__["_pygobject_compat_shape"] = True
        namespace.filename_from_utf8 = filename_from_utf8
    _install_glib_mainloop_compat(namespace)
    _install_glib_variant_compat(namespace)
    return namespace


def _install_gio_compat(namespace: Namespace) -> object:
    try:
        list_store = namespace.ListStore
    except AttributeError:
        return namespace
    if not hasattr(list_store, "__class_getitem__"):
        list_store.__class_getitem__ = classmethod(lambda cls, _item: cls)
    return namespace


def _install_glib_variant_compat(namespace: Namespace) -> None:
    variant = namespace.Variant
    if getattr(variant, "_pygobject_compat_constructor", False):
        return

    constructors = {
        "b": variant.new_boolean,
        "y": variant.new_byte,
        "n": variant.new_int16,
        "q": variant.new_uint16,
        "i": variant.new_int32,
        "u": variant.new_uint32,
        "x": variant.new_int64,
        "t": variant.new_uint64,
        "h": variant.new_handle,
        "d": variant.new_double,
        "s": variant.new_string,
        "o": variant.new_object_path,
        "g": variant.new_signature,
        "v": variant.new_variant,
    }

    def __new__(cls: type, format_string: str, value: object) -> object:
        try:
            constructor = constructors[format_string]
        except KeyError as exc:
            raise TypeError(
                f"GLib.Variant format {format_string!r} is not supported"
            ) from exc
        return constructor(value)

    def __init__(self: object, format_string: str, value: object) -> None:
        pass

    variant.__new__ = staticmethod(__new__)
    variant.__init__ = __init__
    variant._pygobject_compat_constructor = True


def _install_gtk_compat(namespace: Namespace) -> object:
    from . import PyGIDeprecationWarning
    from . import _gtktemplate
    from ginext import record
    from ginext.overlay.callbacks import bind_callback_types
    from ginext.overlay import callback_types

    namespace.PyGTKDeprecationWarning = PyGIDeprecationWarning
    # Record deprecated-construction warnings for Gtk structs use this category
    # rather than the bare DeprecationWarning; register it with core's record
    # module so core needn't hardcode the "Gtk" namespace.
    record.register_deprecation_warning("Gtk", PyGIDeprecationWarning)
    _gtktemplate.install(namespace)
    try:
        sorter_cls = namespace.CustomSorter
    except AttributeError:
        sorter_cls = None
    compat_sorter = False
    if sorter_cls is not None:
        try:
            compat_sorter = sorter_cls._pygobject_compat_sorter
        except AttributeError:
            pass
    if sorter_cls is not None and not compat_sorter:
        raw_new = sorter_cls.new
        raw_set_sort_func = sorter_cls.set_sort_func

        @callback_types("sort_func", "GObject.Object", "GObject.Object")
        def new(
            cls: type,
            sort_func: Callable[..., Any] | None = None,
            user_data: object = None,
            user_destroy: object = None,
        ) -> object:
            return raw_new(
                bind_callback_types(new, "sort_func", sort_func),
                user_data,
                user_destroy,
            )

        @callback_types("sort_func", "GObject.Object", "GObject.Object")
        def set_sort_func(
            self: object,
            sort_func: Callable[..., Any] | None = None,
            user_data: object = None,
            user_destroy: object = None,
        ) -> object:
            return raw_set_sort_func(
                self,
                bind_callback_types(set_sort_func, "sort_func", sort_func),
                user_data,
                user_destroy,
            )

        sorter_cls.new = classmethod(new)
        sorter_cls.set_sort_func = set_sort_func
        sorter_cls._pygobject_compat_sorter = True
    if not getattr(_GObject, "_pygobject_template_init_hook", False):
        raw_init = _GObject.__init__

        def __init__(self, **kwargs):
            raw_init(self, **kwargs)
            hook = type(self).__dict__.get("__dontuse_ginstance_init__")
            if hook is not None:
                try:
                    hook(self)
                except (AttributeError, RuntimeError, TypeError) as exc:
                    sys.excepthook(type(exc), exc, exc.__traceback__)
                else:
                    if ginext.features.is_enabled(ginext.features.NEW_SIGNAL_API):
                        from ginext.signal.adapt import _split_constructor_kwargs

                        properties, _handlers = _split_constructor_kwargs(dict(kwargs))
                    else:
                        properties = dict(kwargs)
                    for name, value in properties.items():
                        setattr(self.props, name, value)

        _gobject: Any = _GObject
        _gobject.__init__ = __init__
        _gobject._pygobject_template_init_hook = True

    import os as _os

    env_gate = _os.environ.get("GINEXT_GTK_AUTO_INIT", "1")
    if env_gate.lower() not in {"0", "false", "no"}:
        try:
            ok = (
                namespace.init_check([])
                if namespace.__version__[0] == 3
                else namespace.init_check()
            )
            if isinstance(ok, tuple):
                ok = ok[0]
        except AttributeError, RuntimeError, TypeError:
            ok = False
        namespace._ginext_display_available = bool(ok)
    return namespace


def _install_glib_mainloop_compat(namespace: Namespace) -> None:
    main_loop = namespace.MainLoop
    if getattr(main_loop, "_pygobject_compat_constructor", False):
        return
    raw_new = main_loop.new

    def __new__(cls: type, context: object = None, is_running: bool = False) -> object:
        return raw_new(context, is_running)

    def __init__(
        self: object, context: object = None, is_running: bool = False
    ) -> None:
        pass

    main_loop.__new__ = staticmethod(__new__)
    main_loop.__init__ = __init__
    main_loop._pygobject_compat_constructor = True


def _signal_descriptors(gtype_or_cls: object) -> dict[str, SignalDescriptor]:
    if not isinstance(gtype_or_cls, type) or not issubclass(gtype_or_cls, _GObject):
        raise TypeError("type must be instantiable or an interface")
    result = {}
    for name, info in getattr(
        getattr(gtype_or_cls, "gimeta", None), "signal_infos", {}
    ).items():
        if isinstance(info, SignalDescriptor):
            result[name] = info
    return result


def _all_signal_descriptors() -> list[tuple[type, str, SignalDescriptor]]:
    pending = list(_GObject.__subclasses__())
    seen = set()
    result: list[tuple[type, str, SignalDescriptor]] = []
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        pending.extend(cls.__subclasses__())
        for name, descriptor in _signal_descriptors(cls).items():
            result.append((cls, name, descriptor))
    return result


def _signal_list_names(gtype_or_cls: object) -> tuple[str, ...]:
    return tuple(
        descriptor._gobject_name or name.replace("_", "-")
        for name, descriptor in _signal_descriptors(gtype_or_cls).items()
    )


def _signal_list_ids(gtype_or_cls: object) -> tuple[int, ...]:
    return tuple(
        descriptor._signal_id
        for descriptor in _signal_descriptors(gtype_or_cls).values()
        if descriptor._signal_id
    )


def _signal_lookup(name: str, gtype_or_cls: object) -> int:
    if isinstance(gtype_or_cls, _GObject) and not isinstance(gtype_or_cls, type):
        gtype_or_cls = type(gtype_or_cls)
    normalized = name.replace("-", "_")
    for attr_name, descriptor in _signal_descriptors(gtype_or_cls).items():
        if attr_name == normalized or descriptor._gobject_name == name.replace(
            "_", "-"
        ):
            return descriptor._signal_id
    # Fall back to native typelib lookup for C-defined signals.
    gtype = getattr(getattr(gtype_or_cls, "gimeta", None), "gtype", None) or int(
        getattr(gtype_or_cls, "__gtype__", 0)
    )
    if gtype:
        result = ginext.private.invoke(
            "GObject", "signal_parse_name", name, gtype, False
        )
        if result[0]:
            return result[1]
    return 0


def _signal_name(signal_id: int) -> str | None:
    if signal_id == 0:
        return None
    for _cls, name, descriptor in _all_signal_descriptors():
        if descriptor._signal_id == signal_id:
            return descriptor._gobject_name or name.replace("_", "-")
    return None


def _signal_query(
    signal: str | int, gtype_or_cls: object | None = None
) -> tuple | None:
    if isinstance(signal, str):
        if gtype_or_cls is None:
            raise TypeError("signal_query(name, type) requires a type")
        signal_id = _signal_lookup(signal, gtype_or_cls)
        if signal_id == 0:
            return None
    else:
        signal_id = signal
        if signal_id == 0:
            return None

    for cls, name, descriptor in _all_signal_descriptors():
        if descriptor._signal_id != signal_id:
            continue
        signal_name = descriptor._gobject_name or name.replace("_", "-")
        flags = getattr(
            descriptor, "_compat_flags", ginext.GObject.SignalFlags.RUN_LAST
        )
        return_type = getattr(descriptor, "_compat_return_type", None)
        arg_types = getattr(descriptor, "_compat_arg_types", descriptor._arg_types)
        return (
            signal_id,
            signal_name,
            getattr(cls, "__gtype__", cls),
            flags,
            GType.NONE if return_type is None else return_type,
            tuple(arg_types),
        )
    # Fall back to native typelib SignalQuery for C-defined signals.
    native = ginext.private.invoke("GObject", "signal_query", signal_id)
    if native is not None and native.signal_id != 0:
        return native
    return None


def _signal_parse_name(
    detailed_signal: str, obj_or_cls: object, force_detail_quark: bool = False
) -> tuple[int, object]:
    cls = type(obj_or_cls) if isinstance(obj_or_cls, _GObject) else obj_or_cls
    detail: object
    if "::" in detailed_signal:
        name, detail = detailed_signal.split("::", 1)
    else:
        name = detailed_signal
        detail = 0
    signal_id = _signal_lookup(name, cls)
    if signal_id == 0:
        raise ValueError(f"unknown signal name: {detailed_signal}")
    return signal_id, detail


def _connection_signal_id(connection: "SignalConnection", cls: type) -> int:
    name = connection.signal_name.split("::", 1)[0]
    return _signal_lookup(name, cls)


def _gtype_for_signal_target(obj_or_cls: object) -> int:
    cls = type(obj_or_cls) if isinstance(obj_or_cls, _GObject) else obj_or_cls
    gimeta = getattr(cls, "gimeta", None)
    if gimeta is None or not isinstance(gimeta.gtype, int):
        raise TypeError("type must be a GObject instance or subclass")
    return gimeta.gtype


def _gimeta_for_signal_target(obj_or_cls: object) -> object:
    cls = type(obj_or_cls) if isinstance(obj_or_cls, _GObject) else obj_or_cls
    gimeta = getattr(cls, "gimeta", None)
    if gimeta is not None:
        return gimeta
    return ginext.private.GIMeta.info_by_gtype(_gtype_for_signal_target(obj_or_cls))


def _add_emission_hook(
    obj_or_cls: object, detailed_signal: str, callback: object
) -> int:
    gimeta = _gimeta_for_signal_target(obj_or_cls)
    return gimeta.add_emission_hook(detailed_signal, callback)


def _remove_emission_hook(
    obj_or_cls: object, detailed_signal: str, hook_id: int
) -> None:
    gimeta = _gimeta_for_signal_target(obj_or_cls)
    gimeta.remove_emission_hook(detailed_signal, hook_id)


def _matches_signal(
    connection: SignalConnection, obj: _GObject, signal_id: int
) -> bool:
    return _connection_signal_id(connection, type(obj)) == signal_id


def _signal_has_handler_pending(
    obj: _GObject, signal_id: int, detail: object = 0, may_be_blocked: bool = False
) -> bool:
    for connection in obj._compat_connections():
        if connection.is_connected and _matches_signal(connection, obj, signal_id):
            return True
    return False


def _signal_handler_find(
    obj: _GObject,
    mask: int,
    *,
    signal_id: int = 0,
    detail: object = 0,
    closure: object = None,
    func: object = 0,
    data: object = 0,
) -> int:
    for connection in obj._compat_connections():
        if not connection.is_connected:
            continue
        if signal_id and not _matches_signal(connection, obj, signal_id):
            continue
        return connection.handler_id
    return 0


def _signal_connect_closure(
    obj: _GObject,
    detailed_signal: str,
    closure: Callable[..., Any],
    after: bool = False,
) -> int:
    connection = obj.connect(detailed_signal, closure, after=after)
    return connection.handler_id


def _matching_connections(
    obj: _GObject, mask: int = 0, signal_id: int = 0, closure: object = None
) -> list[SignalConnection]:
    if int(mask) & 4 and closure not in (None, 0):
        return []
    return [
        connection
        for connection in obj._compat_connections()
        if connection.is_connected
        and (not signal_id or _matches_signal(connection, obj, signal_id))
    ]


def _signal_handlers_block_matched(
    obj: _GObject,
    mask: int,
    *,
    signal_id: int = 0,
    detail: object = 0,
    closure: object = None,
    func: object = 0,
    data: object = 0,
) -> int:
    import ginext as _ginext

    connections = _matching_connections(obj, mask, signal_id, closure)
    for connection in connections:
        _ginext.GObject.signal_handler_block(obj, connection.handler_id)
    return len(connections)


def _signal_handlers_unblock_matched(
    obj: _GObject,
    mask: int,
    *,
    signal_id: int = 0,
    detail: object = 0,
    closure: object = None,
    func: object = 0,
    data: object = 0,
) -> int:
    import ginext as _ginext

    connections = _matching_connections(obj, mask, signal_id, closure)
    for connection in connections:
        _ginext.GObject.signal_handler_unblock(obj, connection.handler_id)
    return len(connections)


def _signal_handlers_disconnect_matched(
    obj: _GObject,
    mask: int,
    *,
    signal_id: int = 0,
    detail: object = 0,
    closure: object = None,
    func: object = 0,
    data: object = 0,
) -> int:
    connections = _matching_connections(obj, mask, signal_id, closure)
    for connection in connections:
        connection.disconnect()
        obj._compat_forget_connection(connection)
    return len(connections)


def _signal_new(
    name: str,
    type_: object,
    flags: object,
    return_type: object,
    param_types: tuple[object, ...],
) -> int:
    if type_ is None:
        raise TypeError("type must not be None")
    raise NotImplementedError("GObject.signal_new compatibility is incomplete")


def __getattr__(name: str) -> Any:
    resolved = ginext.defaults.resolve_namespace_name(name)
    if resolved is None:
        raise AttributeError(name)
    namespace = ginext._load_namespace(*resolved, profile=ginext.abi.PYGOBJECT)
    namespace._module_owner = sys.modules[__name__]
    # PyGObject compat alias — PyGObject's Namespace exposes ``_namespace``
    # as the introspection namespace name.
    namespace._namespace = namespace.__name__
    globals()[name] = namespace
    sys.modules[f"{__name__}.{name}"] = cast("Any", namespace)
    if name == "GObject":
        _install_gobject_compat(namespace)
    elif name == "GLib":
        _install_glib_compat(namespace)
    elif name == "Gio":
        _install_gio_compat(namespace)
    elif name == "Gtk":
        _install_gtk_compat(namespace)
    return namespace


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(ginext.defaults.available_names()))
