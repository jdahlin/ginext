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

from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

import struct

from ginext.gobject.properties import (
    PropertyBase,
    RangeValue,
    call_notify_override,
    coerce_property_default,
    gimeta_type_name,
    own_annotations_dict,
    unset,
)


def _gtype_inherent_bounds(type_obj: object) -> tuple[int | float, int | float] | None:
    """Return (min, max) inherent bounds for a numeric GType, or None."""

    def _max(c: str) -> int:
        return 2 ** ((8 * struct.calcsize(c)) - 1) - 1

    def _umax(c: str) -> int:
        return 2 ** (8 * struct.calcsize(c)) - 1

    _BOUNDS: dict[str, tuple[int | float, int | float]] = {
        "gchar": (-128, 127),
        "guchar": (0, 255),
        "gint": (-_max("i") - 1, _max("i")),
        "guint": (0, _umax("I")),
        "glong": (-_max("l") - 1, _max("l")),
        "gulong": (0, _umax("L")),
        "gint64": (-_max("q") - 1, _max("q")),
        "guint64": (0, _umax("Q")),
        "gfloat": (-3.4028234663852886e38, 3.4028234663852886e38),
        "gdouble": (-1.7976931348623157e308, 1.7976931348623157e308),
    }
    name = gimeta_type_name(type_obj)
    if name is None:
        return None
    return _BOUNDS.get(name)


T = TypeVar("T")

_unset_sentinel = unset


class CompatProperty(Generic[T]):
    """Standalone compat property descriptor — no Property inheritance.

    Provides PyGObject-compatible getter/setter decorator support on top of
    raw GObject property access (gimeta.get_property / gimeta.set_property).
    Registration is driven by duck-typing: C code reads ``default``, ``nick``,
    ``blurb``, ``minimum``, ``maximum``, ``readonly``, ``construct_only``
    directly from the descriptor object.
    """

    name: str
    default: object
    nick: str | None
    blurb: str | None
    readonly: bool
    construct_only: bool
    maximum: RangeValue | None
    minimum: RangeValue | None
    fget: Callable[..., object] | None
    fset: Callable[..., object] | None

    def __init__(
        self,
        getter: object = None,
        /,
        *,
        setter: object = None,
        nick: str | None = None,
        blurb: str | None = None,
        flags: int | None = None,
        readonly: bool = False,
        construct_only: bool = False,
        maximum: RangeValue | None = None,
        minimum: RangeValue | None = None,
        default: object = _unset_sentinel,
        **kwargs: object,
    ) -> None:
        fget = kwargs.pop("getter", None)
        value_type = kwargs.pop("type", None)
        if kwargs:
            raise TypeError(f"unexpected keyword argument {next(iter(kwargs))!r}")
        if fget is not None and getter is not None:
            raise TypeError("getter must not be passed twice")
        if fget is None:
            fget = getter
        # PyGObject lets you pass the value type positionally (e.g. Property(int))
        if fget is not None and isinstance(fget, type) and value_type is None:
            value_type = fget
            fget = None
        if value_type is not None and not isinstance(value_type, type):
            raise TypeError("GObject.Property type must be a type")
        if nick is not None and not isinstance(nick, str):
            raise TypeError("GObject.Property nick must be a string")
        if blurb is not None and not isinstance(blurb, str):
            raise TypeError("GObject.Property blurb must be a string")
        if fget is not None and not callable(fget):
            raise TypeError("GObject.Property getter must be callable")
        if setter is not None and not callable(setter):
            raise TypeError("GObject.Property setter must be callable")
        if flags is not None:
            readonly = readonly or not bool(flags & 2)
            construct_only = construct_only or bool(flags & 8)
        # Validate enum/flags default values
        if value_type is not None:
            from enum import Flag, Enum

            if isinstance(value_type, type) and issubclass(value_type, (Flag, Enum)):
                if default is _unset_sentinel and fget is None:
                    raise TypeError(
                        f"GObject.Property of enum/flags type {value_type.__name__!r}"
                        f" requires an explicit default value"
                    )
                if default is not _unset_sentinel and not isinstance(
                    default, value_type
                ):
                    raise TypeError(
                        f"enum/flags default must be an instance of {value_type.__name__!r},"
                        f" not {type(default).__name__!r}"
                    )
        _UNSUPPORTED_TYPES = (complex,)
        if value_type in _UNSUPPORTED_TYPES:
            raise TypeError(f"GObject.Property type {value_type!r} is not supported")
        if gimeta_type_name(value_type) == "GType" and default is not _unset_sentinel:
            raise TypeError("GType properties do not support defaults")
        if (
            value_type is bool
            and default is _unset_sentinel
            and fget is None
            and setter is None
            and not kwargs.get("getter")
        ):
            raise TypeError(
                "GObject.Property of type bool requires an explicit default value"
            )
        if (
            value_type is bool
            and default is not _unset_sentinel
            and not isinstance(default, (bool, int))
        ):
            raise TypeError(
                f"GObject.Property bool default must be bool or int, got {type(default).__name__!r}"
            )
        if (
            value_type is object
            and default is not _unset_sentinel
            and default is not None
        ):
            raise TypeError(
                "GObject.Property type=object does not support non-None defaults"
            )
        if (
            gimeta_type_name(value_type) == "GVariant"
            and default is not _unset_sentinel
            and default is not None
            and gimeta_type_name(type(default)) != "GVariant"
        ):
            raise TypeError("GVariant property default must be GLib.Variant or None")
        _vtype_name = gimeta_type_name(value_type) or getattr(
            value_type, "gtype_name", None
        )
        if (
            _vtype_name == "GStrv"
            and default is not _unset_sentinel
            and default is not None
        ):
            if isinstance(default, str) or not hasattr(default, "__iter__"):
                raise TypeError(
                    f"GStrv property default must be a list of strings or None,"
                    f" not {type(default).__name__!r}"
                )
            for i, item in enumerate(default):
                if not isinstance(item, str):
                    raise TypeError(
                        f"GStrv property default item {i} must be a str,"
                        f" not {type(item).__name__!r}"
                    )
        self.type: type | None = value_type
        self.nick = nick
        self.blurb = blurb
        self.readonly = readonly
        self.construct_only = construct_only
        # Apply pygobject-compatible defaults for common types when not set explicitly
        if default is _unset_sentinel and value_type is str and fget is None:
            default = ""
        self.default = default
        self.maximum = maximum
        self.minimum = minimum
        if value_type is not None and (minimum is not None or maximum is not None):
            bounds = _gtype_inherent_bounds(value_type)
            if bounds is not None:
                inherent_min, inherent_max = bounds
                if minimum is not None and minimum < inherent_min:
                    raise TypeError(
                        f"Minimum value {minimum!r} is below the inherent minimum"
                        f" {inherent_min!r} of the type"
                    )
                if maximum is not None and maximum > inherent_max:
                    raise TypeError(
                        f"Maximum value {maximum!r} exceeds the inherent maximum"
                        f" {inherent_max!r} of the type"
                    )
        self.fget = fget
        self.fset = setter
        self._infer_type_from_getter()

    @property
    def __doc__(self) -> str | None:  # type: ignore[override]
        if self.blurb is not None:
            return self.blurb
        if self.fget is not None:
            return getattr(self.fget, "__doc__", None)
        return None

    def _type_from_python(self, python_type: type) -> object:
        """Map a Python type to its corresponding GObject GType."""
        from gi.repository import GObject as _GObj

        # Check for GTypeMeta (GType constants like TYPE_INT, TYPE_NONE) first
        try:
            from ginext.gobject.gtype import GTypeMeta

            if isinstance(python_type, GTypeMeta):
                return python_type
        except ImportError:
            pass
        _PY_TO_GTYPE = {
            int: _GObj.TYPE_INT,
            bool: _GObj.TYPE_BOOLEAN,
            float: _GObj.TYPE_DOUBLE,
            str: _GObj.TYPE_STRING,
            object: _GObj.TYPE_PYOBJECT,
        }
        if python_type in _PY_TO_GTYPE:
            return _PY_TO_GTYPE[python_type]
        # Special-case the compat GObject base classes that lack __gtype__
        try:
            import ginext.private as _gp

            if python_type is _gp.GBoxed:
                return _GObj.TYPE_BOXED
        except ImportError, AttributeError:
            pass
        # If it's a GObject class with __gtype__, return that
        if hasattr(python_type, "__gtype__"):
            return python_type.__gtype__
        # If it's already a GType (has is_a method), return it
        if hasattr(python_type, "is_a"):
            return python_type
        raise TypeError(f"Cannot convert {python_type!r} to GType")

    def __repr__(self) -> str:
        _PY_TO_GTYPE = {
            int: "gint",
            str: "gchararray",
            float: "gdouble",
            bool: "gboolean",
            object: "gpointer",
            bytes: "gchararray",
        }
        if self.type is not None:
            type_name = (
                _PY_TO_GTYPE.get(self.type)
                or gimeta_type_name(self.type)
                or repr(self.type)
            )
        else:
            type_name = "unknown"
        name = getattr(self, "name", None)
        if name is None:
            return f"<GObject Property (uninitialized) ({type_name})>"
        return f"<GObject Property {name!r} ({type_name})>"

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        # install_properties is not auto-called for GObject subclasses (install_metaclass is a stub),
        # so raise the conflict error here instead — but only for GObject subclasses.
        if any(hasattr(b, "__gtype__") for b in owner.__mro__) and (
            "do_get_property" in owner.__dict__ or "do_set_property" in owner.__dict__
        ):
            raise TypeError("GObject.Property conflicts with property vfuncs")
        # Inject the type into __annotations__ so register_gobject_subclass
        # picks it up via its annotation-iteration path.
        if self.type is not None:
            anns = own_annotations_dict(owner)
            if name not in anns:
                owner.__annotations__ = {**anns, name: self.type}
            # Coerce GVariant string defaults (GLib.Variant("i", 42) may return "42")
            coerce_property_default(self.type, self)  # type: ignore[arg-type]

    def _infer_type_from_getter(self) -> None:
        if self.fget is None:
            return
        if self.type is None:
            return_type = getattr(self.fget, "__annotations__", {}).get("return")
            if isinstance(return_type, type):
                self.type = return_type
        if self.blurb is None:
            doc = getattr(self.fget, "__doc__", None)
            if doc:
                self.blurb = doc

    def __call__(self, getter: object) -> CompatProperty[T]:
        if not callable(getter):
            raise TypeError("GObject.Property getter must be callable")
        self.fget = getter
        self._infer_type_from_getter()
        return self

    def getter(self, getter: object) -> CompatProperty[T]:
        return self(getter)

    def setter(self, setter: object) -> CompatProperty[T]:
        if not callable(setter):
            raise TypeError("GObject.Property setter must be callable")
        self.fset = setter
        return self

    def __get__(self, obj: object, objtype: object = None) -> object:
        if obj is None:
            return self
        if self.fget is not None:
            return self.fget(obj)
        if self.fset is not None:
            raise TypeError(f"property {self.name!r} is not readable")
        return type(obj).gimeta.get_property(obj, self.name)  # type: ignore[attr-defined]

    def __set__(self, obj: object, value: object) -> None:
        if self.fset is not None:
            self.fset(obj, value)
            call_notify_override(obj, self.name.replace("_", "-"))
            return
        if self.fget is not None:
            raise TypeError(f"property {self.name!r} is not writable")
        # Coerce non-string values to str for string properties (pygobject compat)
        if self.type is str and not isinstance(value, str):
            value = str(value)
        # Silently ignore out-of-range values (GObject behaviour)
        if self.minimum is not None and value < self.minimum:  # type: ignore[operator]
            return
        if self.maximum is not None and value > self.maximum:  # type: ignore[operator]
            return
        try:
            type(obj).gimeta.set_property(obj, self.name, value)  # type: ignore[attr-defined]
        except (AttributeError, ValueError) as exc:
            raise TypeError(str(exc)) from None
        call_notify_override(obj, self.name.replace("_", "-"))


# TODO: Remove the TYPE_CHECKING overloads below once mypy suppresses [assignment]
# for user-defined @dataclass_transform field specifier classes.
# https://github.com/python/mypy/issues/14868
if TYPE_CHECKING:

    @overload
    def CompatProperty(
        value_type: type[T] | None = None,
        /,
        *,
        type: Any = None,
        default: T,
        nick: str | None = None,
        blurb: str | None = None,
        flags: int | None = None,
        readonly: bool = False,
        construct_only: bool = False,
        maximum: RangeValue | None = None,
        minimum: RangeValue | None = None,
        getter: Any = None,
        setter: Any = None,
    ) -> T: ...

    @overload
    def CompatProperty(
        value_type: type[T] | None = None,
        /,
        *,
        type: Any = None,
        nick: str | None = None,
        blurb: str | None = None,
        flags: int | None = None,
        readonly: bool = False,
        construct_only: bool = False,
        maximum: RangeValue | None = None,
        minimum: RangeValue | None = None,
        getter: Any = None,
        setter: Any = None,
    ) -> CompatProperty[Any]: ...

    def CompatProperty(
        value_type: type[T] | None = None,
        /,
        **kw: object,
    ) -> Any: ...

else:
    CompatProperty = CompatProperty


def install_properties(cls: type) -> None:
    properties = {
        name: attr
        for name, attr in cls.__dict__.items()
        if isinstance(attr, (PropertyBase, CompatProperty))
    }
    if not properties:
        return
    if "do_get_property" in cls.__dict__ or "do_set_property" in cls.__dict__:
        raise TypeError("GObject.Property conflicts with property vfuncs")

    gproperties = dict(cls.__dict__.get("__gproperties__", {}))
    for name, prop in properties.items():
        if name in gproperties:
            raise ValueError(f"Property {name!r} is already defined")
        gproperties[name] = prop

    _cls: Any = cls

    def do_get_property(self: object, pspec: object) -> object:
        name = str(getattr(pspec, "name", pspec)).replace("-", "_")
        return getattr(self, name)

    def do_set_property(self: object, pspec: object, value: object) -> None:
        name = str(getattr(pspec, "name", pspec)).replace("-", "_")
        setattr(self, name, value)

    _cls.__gproperties__ = gproperties
    _cls.do_get_property = do_get_property
    _cls.do_set_property = do_set_property
