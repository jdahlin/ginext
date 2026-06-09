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

from ginext.gobject.properties import (
    _Property,
    RangeValue,
    call_notify_override,
    coerce_property_default,
    gimeta_type_name,
    own_annotations_dict,
    unset,
)

T = TypeVar("T")

_unset_sentinel = unset


class _CompatProperty(Generic[T]):
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
        if fget is not None and not callable(fget):
            raise TypeError("GObject.Property getter must be callable")
        if setter is not None and not callable(setter):
            raise TypeError("GObject.Property setter must be callable")
        if flags is not None:
            readonly = readonly or not bool(flags & 2)
            construct_only = construct_only or bool(flags & 8)
        if gimeta_type_name(value_type) == "GType" and default is not _unset_sentinel:
            raise TypeError("GType properties do not support defaults")
        if (
            gimeta_type_name(value_type) == "GVariant"
            and default is not _unset_sentinel
            and default is not None
            and gimeta_type_name(type(default)) != "GVariant"
        ):
            raise TypeError("GVariant property default must be GLib.Variant or None")
        self.type: type | None = value_type
        self.nick = nick
        self.blurb = blurb
        self.readonly = readonly
        self.construct_only = construct_only
        self.default = default
        self.maximum = maximum
        self.minimum = minimum
        self.fget = fget
        self.fset = setter
        self._infer_type_from_getter()

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        # Inject the type into __annotations__ so register_gobject_subclass
        # picks it up via its annotation-iteration path.
        if self.type is not None:
            anns = own_annotations_dict(owner)
            if name not in anns:
                owner.__annotations__ = {**anns, name: self.type}
            # Coerce GVariant string defaults (GLib.Variant("i", 42) may return "42")
            coerce_property_default(self.type, self)  # type: ignore[arg-type]

    def _infer_type_from_getter(self) -> None:
        if self.type is not None or self.fget is None:
            return
        return_type = getattr(self.fget, "__annotations__", {}).get("return")
        if isinstance(return_type, type):
            self.type = return_type

    def __call__(self, getter: object) -> "_CompatProperty[T]":
        if not callable(getter):
            raise TypeError("GObject.Property getter must be callable")
        self.fget = getter
        self._infer_type_from_getter()
        return self

    def getter(self, getter: object) -> "_CompatProperty[T]":
        return self(getter)

    def setter(self, setter: object) -> "_CompatProperty[T]":
        if not callable(setter):
            raise TypeError("GObject.Property setter must be callable")
        self.fset = setter
        return self

    def __get__(self, obj: object, objtype: object = None) -> object:
        if obj is None:
            return self
        if self.fget is not None:
            return self.fget(obj)
        return type(obj).gimeta.get_property(obj, self.name)  # type: ignore[attr-defined]

    def __set__(self, obj: object, value: object) -> None:
        if self.fset is not None:
            self.fset(obj, value)
            call_notify_override(obj, self.name.replace("_", "-"))
            return
        if self.fget is not None:
            raise TypeError(f"property {self.name!r} is not writable")
        type(obj).gimeta.set_property(obj, self.name, value)  # type: ignore[attr-defined]
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
    ) -> "_CompatProperty[Any]": ...

    def CompatProperty(
        value_type: type[T] | None = None,
        /,
        **kw: object,
    ) -> Any: ...

else:
    CompatProperty = _CompatProperty


def install_properties(cls: type) -> None:
    properties = {
        name: attr
        for name, attr in cls.__dict__.items()
        if isinstance(attr, (_Property, _CompatProperty))
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
