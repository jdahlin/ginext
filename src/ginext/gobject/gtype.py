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

"""The GObject GType hierarchy.

GType is modelled as a metaclass hierarchy: GTypeMeta gives each concrete
GType subclass its int value, name, parent/children/is_a queries, and the
pytype lookup. compat_gtype_from_raw wraps a raw (gtype, name) pair.
"""

from __future__ import annotations

import types
from typing import ClassVar, Type, cast

from .. import abi, features, private
from .resolve import classbuild_module, gobject_repo

_compat_gtype_cache: dict[tuple[int, str], type[GType]] = {}


class GTypeMeta(type):
    gimeta: private.GIMeta
    gtype_name: str
    __prepare__ = type.__prepare__

    def __instancecheck__(cls, instance: object) -> bool:
        if isinstance(instance, type):
            return issubclass(instance, GType)
        return super().__instancecheck__(instance)

    @property
    def name(cls) -> str:
        return cls.gtype_name

    def __setattr__(cls, name: str, value: object) -> None:
        if name == "name":
            raise AttributeError("GType name is read-only")
        super().__setattr__(name, value)

    def __int__(cls) -> int:
        if not hasattr(cls, "gimeta"):
            raise TypeError("base GType has no concrete GType value")
        return int(cls.gimeta.gtype)

    def __index__(cls) -> int:
        return int(cls)

    def __eq__(cls, other: object) -> bool:
        if not hasattr(cls, "gimeta"):
            return super().__eq__(other)
        if isinstance(other, type) and issubclass(other, GType):
            if not hasattr(other, "gimeta"):
                return False
            return int(cls) == int(other)
        if isinstance(other, int):
            return int(cls) == other
        return False

    def __hash__(cls) -> int:
        if not hasattr(cls, "gimeta"):
            return super().__hash__()
        return hash(int(cls))

    def __repr__(cls) -> str:
        if not hasattr(cls, "gimeta"):
            return super().__repr__()
        return f"<GType {cls.gtype_name} ({int(cls)})>"

    @property
    def parent(cls) -> type[GType] | None:
        GObject = gobject_repo()
        p = int(GObject.type_parent(int(cls)))
        if p == 0:
            return None
        return compat_gtype_from_raw(p, GObject.type_name(p))

    @property
    def children(cls) -> list[type[GType]]:
        GObject = gobject_repo()
        return [
            compat_gtype_from_raw(c, GObject.type_name(c))
            for c in GObject.type_children(int(cls))
        ]

    @property
    def depth(cls) -> int:
        return int(gobject_repo().type_depth(int(cls)))

    @property
    def interfaces(cls) -> list[type[GType]]:
        GObject = gobject_repo()
        return [
            compat_gtype_from_raw(i, GObject.type_name(i))
            for i in GObject.type_interfaces(int(cls))
        ]

    @property
    def pytype(cls) -> type | None:
        classbuild = classbuild_module()
        classes: dict[tuple[str, int], type] = classbuild._classes_by_gtype

        if features.is_enabled(features.PYGOBJECT_COMPAT):
            result = classes.get((abi.PYGOBJECT.name, int(cls)))
            if result is not None:
                return result
        gimeta = vars(cls).get("gimeta")
        profile = gimeta.profile if gimeta is not None else abi.NATIVE
        return classes.get((profile.name, int(cls)))

    def has_value_table(cls) -> bool:
        return private.type_has_value_table(int(cls))

    def is_abstract(cls) -> bool:
        GObject = gobject_repo()
        return bool(GObject.type_test_flags(int(cls), GObject.TypeFlags.ABSTRACT))

    def is_classed(cls) -> bool:
        GObject = gobject_repo()
        return bool(
            GObject.type_test_flags(int(cls), GObject.TypeFundamentalFlags.CLASSED)
        )

    def is_deep_derivable(cls) -> bool:
        GObject = gobject_repo()
        return bool(
            GObject.type_test_flags(
                int(cls), GObject.TypeFundamentalFlags.DEEP_DERIVABLE
            )
        )

    def is_derivable(cls) -> bool:
        GObject = gobject_repo()
        return bool(
            GObject.type_test_flags(int(cls), GObject.TypeFundamentalFlags.DERIVABLE)
        )

    def is_value_abstract(cls) -> bool:
        GObject = gobject_repo()
        return bool(GObject.type_test_flags(int(cls), GObject.TypeFlags.VALUE_ABSTRACT))

    def is_value_type(cls) -> bool:
        return bool(gobject_repo().type_check_is_value_type(int(cls)))


class GType(metaclass=GTypeMeta):
    gimeta: ClassVar[private.GIMeta]
    gtype_name: ClassVar[str]

    NONE: ClassVar[type[GType]]
    BOOLEAN: ClassVar[type[GType]]
    CHAR: ClassVar[type[GType]]
    UCHAR: ClassVar[type[GType]]
    INT: ClassVar[type[GType]]
    UINT: ClassVar[type[GType]]
    LONG: ClassVar[type[GType]]
    ULONG: ClassVar[type[GType]]
    INT64: ClassVar[type[GType]]
    UINT64: ClassVar[type[GType]]
    FLOAT: ClassVar[type[GType]]
    DOUBLE: ClassVar[type[GType]]
    STRING: ClassVar[type[GType]]
    GTYPE: ClassVar[type[GType]]
    PARAM: ClassVar[type[GType]]
    OBJECT: ClassVar[type[GType]]
    BOXED: ClassVar[type[GType]]
    POINTER: ClassVar[type[GType]]
    STRV: ClassVar[type[GType]]

    def __int__(self) -> int:
        return int(type(self))


def compat_gtype_from_raw(gtype: int, type_name: str) -> type[GType]:
    key = (int(gtype), type_name)
    cached = _compat_gtype_cache.get(key)
    if cached is not None:
        return cached
    for value in globals().values():
        if (
            isinstance(value, type)
            and issubclass(value, GType)
            and hasattr(value, "gimeta")
            and int(value.gimeta.gtype) == int(gtype)
        ):
            _compat_gtype_cache[key] = value
            return value

    def _is_a(cls: type, other: object) -> bool:
        return bool(gobject_repo().type_is_a(cls, other))

    wrapper = cast(
        "type[GType]",
        type(
            (type_name or f"GType_{gtype}").upper().replace("G", "G_", 1),
            (GType,),
            {
                "__module__": __name__,
                "gimeta": types.SimpleNamespace(
                    gtype=int(gtype),
                    profile=abi.NATIVE,
                ),
                "gtype_name": type_name,
                "is_a": classmethod(_is_a),
            },
        ),
    )
    _compat_gtype_cache[key] = wrapper
    return wrapper


def _gtype_constant(name: str) -> type[GType]:
    cls = type(
        name.upper().replace("G", "G_", 1),
        (GType,),
        {
            "__module__": __name__,
            "gimeta": private.GIMeta.from_type_name(name),
            "gtype_name": name,
        },
    )
    cls = cast("Type[GType]", cls)
    cls.gimeta.profile = abi.NATIVE
    if cls.gimeta.gtype == 0:
        raise RuntimeError(f"unknown GType {name!r}")
    return cls


def _gtype_constant_from_value(name: str, gtype: int) -> type[GType]:
    cls = type(
        name.upper().replace("G", "G_", 1),
        (GType,),
        {
            "__module__": __name__,
            "gimeta": types.SimpleNamespace(
                gtype=gtype,
                profile=abi.NATIVE,
            ),
            "gtype_name": name,
        },
    )
    cls = cast("Type[GType]", cls)
    if cls.gimeta.gtype == 0:
        raise RuntimeError(f"unknown GType {name!r}")
    return cls


GType.NONE = _gtype_constant("void")
GType.BOOLEAN = _gtype_constant("gboolean")
GType.CHAR = _gtype_constant("gchar")
GType.UCHAR = _gtype_constant("guchar")
GType.INT = _gtype_constant("gint")
GType.UINT = _gtype_constant("guint")
GType.LONG = _gtype_constant("glong")
GType.ULONG = _gtype_constant("gulong")
GType.INT64 = _gtype_constant("gint64")
GType.UINT64 = _gtype_constant("guint64")
GType.FLOAT = _gtype_constant("gfloat")
GType.DOUBLE = _gtype_constant("gdouble")
GType.STRING = _gtype_constant("gchararray")
GType.GTYPE = _gtype_constant("GType")
GType.PARAM = _gtype_constant("GParam")
GType.OBJECT = _gtype_constant("GObject")
GType.BOXED = _gtype_constant("GBoxed")
GType.POINTER = _gtype_constant("gpointer")
GType.STRV = _gtype_constant_from_value("GStrv", int(private.gstrv_get_type()))
