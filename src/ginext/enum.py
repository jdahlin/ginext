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

import enum
import weakref
from typing import TYPE_CHECKING, Any, TypeVar, cast

from ginext import private


if TYPE_CHECKING:
    from collections.abc import Callable
    from ginext.GIRepository import EnumInfo, FlagsInfo
    from .abi import ABIProfile, NamespaceContext


_ENUM_PICKLE_REGISTRY: dict[int, Any] = {}
_enum_classes_by_key: dict[tuple[str, str, str, str], type[Any]] = {}
_enum_gimeta_specs: weakref.WeakKeyDictionary[
    type[Any],
    tuple[int, str, object, object, dict[int, str], dict[int, str], dict[int, Any]],
] = weakref.WeakKeyDictionary()
_EnumT = TypeVar("_EnumT")


def _enum_gimeta(cls: type[Any], name: str) -> object:
    if name != "gimeta":
        raise AttributeError(name)
    spec = _enum_gimeta_specs.get(cls)
    if spec is None:
        raise AttributeError(name)
    gtype, type_name, profile, gi_info, value_names, value_nicks, values = spec
    if gi_info is None:
        gimeta = private.GIMeta.from_gtype(gtype, type_name)
    else:
        gimeta = private.GIMeta.from_type_name(type_name, gi_info)
    if profile is not None:
        gimeta.profile = cast("ABIProfile", profile)
    gimeta.extensions["enum"] = {
        "value_names": value_names,
        "value_nicks": value_nicks,
        "values": values,
    }
    type.__setattr__(cls, "gimeta", gimeta)
    return gimeta


def _register_genum(type_name: str, members: dict[str, int]) -> int:
    return private.register_static(_GEnumMeta._G_TYPE_ENUM, type_name, members)


def _register_gflags(type_name: str, members: dict[str, int]) -> int:
    return private.register_static(_GFlagsMeta._G_TYPE_FLAGS, type_name, members)


class _GEnumMeta(enum.EnumType):
    # G_TYPE_ENUM = 48 (fundamental type index 12 << 2)
    _G_TYPE_ENUM: int = 48

    def __getattr__(cls, name: str) -> object:
        try:
            return _enum_gimeta(cls, name)
        except AttributeError:
            return cast("Any", super()).__getattr__(name)

    def __new__(
        mcs: type[_GEnumMeta],
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> _GEnumMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)  # type: ignore[arg-type]
        if not any(getattr(b, "__genum_base__", False) for b in bases):
            return cls
        type_name = namespace.get("__gtype_name__") or name
        raw_members: dict[str, Any] = dict(cls.__members__)
        members: dict[str, int] = {k: int(v) for k, v in raw_members.items()}
        gtype_int = _register_genum(type_name, members)
        _enum_gimeta_specs[cls] = (
            gtype_int,
            type_name,
            None,
            None,
            {},
            {},
            {},
        )
        from . import abi, classbuild
        classbuild._classes_by_gtype[(abi.NATIVE.name, gtype_int)] = cls
        return cls


class _GFlagsMeta(enum.EnumType):
    _G_TYPE_FLAGS: int = 52

    def __getattr__(cls, name: str) -> object:
        try:
            return _enum_gimeta(cls, name)
        except AttributeError:
            return cast("Any", super()).__getattr__(name)

    def __new__(
        mcs: type[_GFlagsMeta],
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> _GFlagsMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)  # type: ignore[arg-type]
        if not any(getattr(b, "__gflags_base__", False) for b in bases):
            return cls
        type_name = namespace.get("__gtype_name__") or name
        raw_members_f: dict[str, Any] = dict(cls.__members__)
        members: dict[str, int] = {k: int(v) for k, v in raw_members_f.items()}
        gtype_int = _register_gflags(type_name, members)
        value_names = {int(v): k for k, v in raw_members_f.items()}
        value_nicks = {
            int(v): k.lower().replace("_", "-") for k, v in raw_members_f.items()
        }
        _enum_gimeta_specs[cls] = (
            gtype_int,
            type_name,
            None,
            None,
            value_names,
            value_nicks,
            dict(_enum_primary_members(cls)),
        )
        from . import abi, classbuild
        classbuild._classes_by_gtype[(abi.NATIVE.name, gtype_int)] = cls
        return cls


class GEnum(int, enum.ReprEnum, metaclass=_GEnumMeta):
    """Base class for Python-defined GObject enum types.

    Subclass this and define integer members; the metaclass registers the
    type with the GObject type system via g_enum_register_static.
    """

    __genum_base__ = True


class GFlags(enum.IntFlag, metaclass=_GFlagsMeta):
    """Base class for Python-defined GObject flags types.

    Subclass this and define integer members; the metaclass registers the
    type with the GObject type system via g_flags_register_static.
    """

    __gflags_base__ = True


def _enum_reconstruct(class_id: int, value: int) -> enum.IntEnum:
    return cast("enum.IntEnum", _ENUM_PICKLE_REGISTRY[class_id](value))


class _GIEnumMeta(enum.EnumType):
    def __getattr__(cls, name: str) -> object:
        try:
            return _enum_gimeta(cls, name)
        except AttributeError:
            return cast("Any", super()).__getattr__(name)


class GIEnum(enum.IntEnum, metaclass=_GIEnumMeta):
    def __reduce_ex__(self, protocol: object) -> tuple[object, tuple[int, int]]:
        return _enum_reconstruct, (id(type(self)), int(self))

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _ENUM_PICKLE_REGISTRY[id(cls)] = cls


class GIFlags(enum.IntFlag, metaclass=_GIEnumMeta):
    def __reduce_ex__(self, protocol: object) -> tuple[object, tuple[int, int]]:
        return _enum_reconstruct, (id(type(self)), int(self))

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _ENUM_PICKLE_REGISTRY[id(cls)] = cls


class EnumBuilder:
    def __init__(self, context: NamespaceContext):
        # The live namespace is recovered on demand (callable-alias closures)
        # via the context; the builder never holds it.
        self._context = context

    def build_enum(self, name: str, info: EnumInfo) -> type[GIEnum]:
        cls = self._build_common(name, info, GIEnum)
        return cls

    def build_flags(self, name: str, info: FlagsInfo) -> type[GIFlags]:
        cls = self._build_common(name, info, GIFlags)
        return cls

    def _build_common(
        self,
        name: str,
        info: EnumInfo | FlagsInfo,
        base: type[_EnumT],
    ) -> type[_EnumT]:
        context = self._context
        key = (context.profile.name, context.name, context.version, name)
        cached = _enum_classes_by_key.get(key)
        if cached is not None:
            return cast("type[_EnumT]", cached)

        members: dict[str, int] = {}
        raw_members = info.members
        for raw_name, value in raw_members:
            upper_name = raw_name.upper()
            members.setdefault(upper_name, value)
            if raw_name != upper_name and raw_name not in {"", "mro"}:
                members.setdefault(raw_name, value)

        gtype = info.gtype
        enum_base: type = base
        module_name = context.module_name()

        cls: type[Any] = cast("Any", enum_base)(
            name, members, module=module_name, qualname=name
        )
        assert isinstance(cls, type)
        values = dict(_enum_primary_members(cls))
        value_names = {
            value: _enum_c_value_name(context.name, name, raw_name)
            for raw_name, value in raw_members
        }
        value_nicks = {
            value: raw_name.replace("_", "-") for raw_name, value in raw_members
        }
        if gtype > 255:
            _enum_gimeta_specs[cls] = (
                gtype,
                info.get_type_name(),
                context.profile,
                info,
                value_names,
                value_nicks,
                values,
            )
        _install_enum_callable_aliases(self._context, cls, name)
        _enum_classes_by_key[key] = cls
        # The functional IntEnum/IntFlag API constructs the class dynamically
        # (cls is built above via the untyped functional form), so narrow the
        # built class back to the requested base here.
        return cast("type[_EnumT]", cls)


def _enum_primary_members(cls: type[Any]) -> dict[int, Any]:
    result: dict[int, Any] = {}
    for member in cls:
        result.setdefault(int(member), member)
    return result


def _enum_c_value_name(namespace: str, enum_name: str, member_name: str) -> str:
    words = _camel_words(namespace)
    words.extend(_camel_words(enum_name))
    return f"{'_'.join(words).upper()}_{member_name.upper()}"


def _install_enum_callable_aliases(
    context: NamespaceContext, cls: type, name: str
) -> None:
    prefix = _snake_name(name)
    aliases = {
        "in_": f"{prefix}_in",
        "in_zero": f"{prefix}_in_zero",
        "out": f"{prefix}_out",
        "inout": f"{prefix}_inout",
        "returnv": f"{prefix}_returnv",
    }
    for attr_name, function_name in aliases.items():
        if attr_name in (cls.__members__ if hasattr(cls, "__members__") else {}):
            continue
        setattr(
            cls, attr_name, staticmethod(_enum_callable_alias(context, function_name))
        )


def _enum_callable_alias(
    context: NamespaceContext, function_name: str
) -> Callable[..., object]:
    def alias(*args: object, **kwargs: object) -> object:
        return getattr(context.load_namespace(), function_name)(*args, **kwargs)

    alias.__name__ = function_name.rsplit("_", 1)[-1]
    return alias


def _snake_name(name: str) -> str:
    return "_".join(_camel_words(name)).lower()


def _camel_words(name: str) -> list[str]:
    if name.startswith("GI") and len(name) > 2 and name[2].isupper():
        return ["GI", *_camel_words(name[2:])]
    words = []
    start = 0
    for index, char in enumerate(name[1:], start=1):
        if char.isupper() and name[index - 1].islower():
            words.append(name[start:index])
            start = index
    words.append(name[start:])
    return words


def reset_for_test() -> None:
    _enum_classes_by_key.clear()
    _ENUM_PICKLE_REGISTRY.clear()
