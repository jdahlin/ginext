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

"""GObject property machinery: the value-backed `Property` descriptor.

`_Property` is the descriptor users declare with `name: int = Property(...)`;
`Property` is its dataclass_transform field-specifier alias (a typing stub under
TYPE_CHECKING, the class itself at runtime). The module-level helpers (annotation
resolution, GVariant default coercion, the `do_notify` override dispatch) are
shared with the GObject base class and with gi-compat's `_propertyhelper`.

This module knows nothing about how a GObject class is *built* — it only
manipulates instances and their `gimeta`, so it stays below `gobjectclass` in
the import graph (gobjectclass imports from here, not the reverse).
"""

from __future__ import annotations

import builtins as _builtins
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Protocol,
    Type,
    TypeAlias,
    TypeVar,
    cast,
    get_args,
    overload,
    runtime_checkable,
)

from .. import features, private
from .gtype import GType
from .resolve import ginext_root, own_gimeta

if TYPE_CHECKING:
    from .gobjectclass import GObject


@runtime_checkable
class _HasDoNotify(Protocol):
    def do_notify(self, *args: object) -> object: ...


ValueType = bool | int | float | str | object
RangeValue: TypeAlias = int | float

unset: Any = object()
T = TypeVar("T", bound=ValueType)


class _PropertyMeta(type):
    def __instancecheck__(cls, instance: object) -> bool:
        try:
            if isinstance(instance, private.DeclaredProperty):
                return True
        except AttributeError:
            pass
        return super().__instancecheck__(instance)


class _Property(Generic[T], metaclass=_PropertyMeta):
    """A value-backed GObject property descriptor.

    The value is stored on the GObject itself, so reads and writes go
    straight through the GObject property machinery — there are no
    Python getter/setter functions. If you want computed access, use a
    plain Python ``@property``; the getter/setter form is a PyGObject
    compatibility feature and lives in ``gi._propertyhelper``.
    """

    name: str
    nick: str | None
    blurb: str | None
    readonly: bool
    construct_only: bool
    maximum: RangeValue | None
    minimum: RangeValue | None
    default: T
    owner: "type[GObject]"

    def __init__(
        self,
        value_type: type | None = None,
        /,
        *,
        nick: str | None = None,
        blurb: str | None = None,
        flags: int | None = None,
        readonly: bool = False,
        construct_only: bool = False,
        maximum: RangeValue | None = None,
        minimum: RangeValue | None = None,
        default: T = unset,
        **kwargs: object,
    ) -> None:
        if not features.is_enabled(features.NEW_PROPERTY_API):
            raise TypeError("GObject.Property is disabled by new_property_api")
        property_type = kwargs.pop("type", None)
        if kwargs:
            raise TypeError(f"unexpected keyword argument {next(iter(kwargs))!r}")
        if property_type is not None and value_type is not None:
            raise TypeError("property type must not be passed twice")
        resolved_type = value_type if value_type is not None else property_type
        if resolved_type is not None and not isinstance(resolved_type, _builtins.type):
            raise TypeError("GObject.Property type must be a type")
        value_type = resolved_type
        if value_type is GType.GTYPE and default is not unset:
            raise TypeError("GType properties do not support defaults")
        if (
            gimeta_type_name(value_type) == "GVariant"
            and default is not unset
            and default is not None
            and not isinstance(default, str)
            and gimeta_type_name(type(default)) != "GVariant"
        ):
            raise TypeError("GVariant properties require a GLib.Variant default")
        if flags is not None:
            readonly = readonly or not bool(flags & 2)
            construct_only = construct_only or bool(flags & 8)
        self.type = value_type
        self.nick = nick
        self.blurb = blurb
        self.readonly = readonly
        self.construct_only = construct_only
        self.default = default
        self.maximum = maximum
        self.minimum = minimum

    def __set_name__(self, owner: "type[GObject]", name: str) -> None:
        self.owner = owner
        self.name = name

    @property
    def pspec(self) -> object:
        owner = self.owner
        name = self.name
        if owner is None or name is None:
            raise AttributeError("property has no installed ParamSpec yet")
        gimeta = own_gimeta(owner)
        if gimeta is None or not hasattr(gimeta, "gtype"):
            raise AttributeError("property has no installed ParamSpec yet")
        pspec = gimeta.param_spec(name.replace("_", "-"))
        if pspec is not None:
            return pspec
        raise AttributeError(f"property {name!r} has no installed ParamSpec")

    def __get__(
        self, obj: "GObject | None", objtype: "Type[GObject] | None" = None
    ) -> T:
        # Class-level access (`Foo.prop`) hits __get__ with obj=None. Return
        # the descriptor so callers can introspect Property metadata; users
        # who want the GParamSpec read it via `Foo.gimeta.pspecs[name]`.
        if obj is None:
            return cast("T", self)
        value = type(obj).gimeta.get_property(obj, self.name)
        if _is_gtype_value_type(self.type):
            return cast("T", int(cast("Any", value)))
        return cast("T", value)

    def __set__(self, obj: "GObject", value: ValueType) -> None:
        if self.readonly:
            raise AttributeError(f"property {self.name!r} is read-only")
        self.owner.gimeta.set_property(obj, self.name, value)
        call_notify_override(obj, self.name.replace("_", "-"))


# TODO: Remove the TYPE_CHECKING overloads below once mypy suppresses [assignment]
# for user-defined @dataclass_transform field specifier classes.
# https://github.com/python/mypy/issues/14868
if TYPE_CHECKING:

    @overload
    def Property(
        value_type: _builtins.type[T] | None = None,
        /,
        *,
        default: T,
        nick: str | None = None,
        blurb: str | None = None,
        flags: int | None = None,
        readonly: bool = False,
        construct_only: bool = False,
        maximum: RangeValue | None = None,
        minimum: RangeValue | None = None,
    ) -> T: ...

    @overload
    def Property(
        value_type: _builtins.type[T] | None = None,
        /,
        *,
        nick: str | None = None,
        blurb: str | None = None,
        flags: int | None = None,
        readonly: bool = False,
        construct_only: bool = False,
        maximum: RangeValue | None = None,
        minimum: RangeValue | None = None,
    ) -> "_Property[Any]": ...

    def Property(
        value_type: _builtins.type[T] | None = None,
        /,
        **kw: object,
    ) -> Any: ...

else:
    Property = _Property


class _PspecProperty:
    """Descriptor synthesized from a GObject pspec.

    Makes an introspected or inherited GObject property reachable as a plain
    attribute (``obj.name``) instead of only via ``get_property`` /
    ``set_property``. Reads and writes route through those methods — which
    normalise the name (``some_int`` -> ``some-int``) and fall back to the C
    accessor — so even a freshly wrapped instance resolves the value. Installed
    lazily on first attribute miss (see ``GObject.__getattr__``), then cached on
    the class like any other descriptor.
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __get__(self, obj: "GObject | None", objtype: object = None) -> object:
        if obj is None:
            return self
        return obj.get_property(self.name)

    def __set__(self, obj: "GObject", value: object) -> None:
        obj.set_property(self.name, value)


def validate_pygobject_property_metadata(cls: type) -> None:
    if "__gproperties__" not in cls.__dict__:
        return
    gproperties = cls.__dict__["__gproperties__"]
    if not isinstance(gproperties, dict):
        raise TypeError("__gproperties__ must be a dict")
    for name in gproperties:
        if not isinstance(name, str):
            raise TypeError("__gproperties__ names must be strings")


def _gimeta_value(value: object) -> object | None:
    return value.gimeta if hasattr(value, "gimeta") else None


def gimeta_type_name(value: object) -> str | None:
    gimeta = _gimeta_value(value)
    if gimeta is None or not hasattr(gimeta, "type_name"):
        return None
    return cast("str", gimeta.type_name)


def _gimeta_gtype(value: object, default: int) -> int:
    gimeta = _gimeta_value(value)
    if gimeta is None or not hasattr(gimeta, "gtype"):
        return default
    return int(cast("Any", gimeta.gtype))


def _is_gtype_value_type(value_type: object) -> bool:
    try:
        return _gimeta_gtype(value_type, 0) == _gimeta_gtype(GType.GTYPE, -1)
    except AttributeError, TypeError:
        return False


def coerce_property_default(value_type: object, prop: "_Property[object]") -> None:
    default = prop.default
    if gimeta_type_name(value_type) == "GVariant" and isinstance(default, str):
        prop.default = ginext_root().GLib.Variant.parse(None, default, None, None)


def property_value_type(value_type: object) -> object:
    args = get_args(value_type)
    if len(args) == 2 and type(None) in args:
        first, second = args
        return second if first is type(None) else first
    return value_type


def resolve_annotations(raw_annotations: dict[str, object]) -> dict[str, object]:
    annotations = dict(raw_annotations)
    unresolved = {
        name: value for name, value in annotations.items() if isinstance(value, str)
    }
    if not unresolved:
        return annotations

    frame = sys._getframe(1)
    while frame is not None and unresolved:
        progressed = False
        for name, value in list(unresolved.items()):
            try:
                resolved = eval(value, frame.f_globals, frame.f_locals)
            except NameError, TypeError, SyntaxError:
                continue
            if isinstance(resolved, str):
                if resolved != value:
                    unresolved[name] = resolved
                    progressed = True
                continue
            annotations[name] = resolved
            del unresolved[name]
            progressed = True
        if progressed:
            continue
        next_frame = frame.f_back
        if next_frame is None:
            break
        frame = next_frame
    return annotations


def call_notify_override(obj: object, prop_name: str) -> None:
    overrides = type(obj).__dict__.get("_pygobject_signal_overrides", set())
    if "notify" not in overrides:
        return
    if not isinstance(obj, _HasDoNotify):
        return
    default_handler = obj.do_notify
    if not callable(default_handler):
        return
    gimeta = own_gimeta(type(obj))
    pspec = {} if gimeta is None else gimeta.pspecs
    target = pspec.get(prop_name)
    if target is None:
        default_handler()
    else:
        default_handler(target)
