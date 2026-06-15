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

import keyword
import types
import warnings
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Self, cast

from . import abi, features, private

if TYPE_CHECKING:
    from ginext.GIRepository import StructInfo, UnionInfo
from .overlay import class_bases_overlay_for, install_class_overlay
from .method import callable_name, make_method


_record_classes_by_key: dict[tuple[str, str, str, str], type[Any]] = {}
_record_classes_by_gtype: dict[tuple[str, int], type[Any]] = {}


# Namespaces whose deprecated-construction warnings should use a category other
# than DeprecationWarning register it here (e.g. the Gtk overlay registers
# Gtk.PyGTKDeprecationWarning). Keeps namespace-specific policy out of core.
_deprecation_warning_categories: dict[str, type[Warning]] = {}


def register_deprecation_warning(namespace: str, category: type[Warning]) -> None:
    _deprecation_warning_categories[namespace] = category


def _record_construction_warning_category(cls: type) -> type[Warning]:
    gimeta = next(
        (
            candidate
            for owner in cls.__mro__
            if (candidate := vars(owner).get("gimeta"))
        ),
        None,
    )
    context = gimeta.namespace if gimeta is not None else None
    if context is None:
        return DeprecationWarning
    # A record of this namespace is being constructed, so the namespace (and its
    # overlay, which registers any non-default category) has already loaded.
    return _deprecation_warning_categories.get(context.name, DeprecationWarning)


class RecordMeta(type):
    gimeta: types.SimpleNamespace
    __prepare__ = type.__prepare__

    def __getattr__(cls, name: str) -> object:
        found = install_method_for_record_class(cast("type[RecordBase]", cls), name)
        if found is None:
            raise AttributeError(name)
        method, has_self = found
        return method

    def __dir__(cls) -> list[str]:
        names = set(type.__dir__(cls))
        names.update(vars(cls.gimeta).get("method_infos", {}))
        return sorted(names)


class RecordBase(private.GBoxed, metaclass=RecordMeta):
    gimeta: ClassVar[types.SimpleNamespace]

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if args or kwargs:
            if not (
                vars(cls.gimeta).get("profile", abi.NATIVE).pygobject_compat
                or features.is_enabled(features.PYGOBJECT_COMPAT)
            ):
                raise TypeError(f"{cls.__name__}() does not accept arguments")
            warnings.warn(
                f"{cls.__name__} positional/keyword construction is deprecated",
                _record_construction_warning_category(cls),
                stacklevel=2,
            )
        found = _lookup_record_method(cls, "new")
        if found is not None:
            method, has_self = found
            if not has_self:
                if args or kwargs:
                    try:
                        return cast("Self", cast("Any", method)(*args, **kwargs))
                    except TypeError:
                        pass
                return cast("Self", cast("Any", method)())
        obj = super().__new__(cls)
        return obj

    def __getattr__(self, name: str) -> object:
        if name in type(self).gimeta.method_infos:
            found = install_method_for_record_class(type(self), name)
            if found is not None:
                method, has_self = found
                if not has_self:
                    return method
                return types.MethodType(cast("Any", method), self)
        if name in type(self).gimeta.hidden_fields:
            raise AttributeError(name)
        found = install_method_for_record_class(type(self), name)
        if found is None:
            raise AttributeError(name)
        method, has_self = found
        if not has_self:
            return method
        return types.MethodType(cast("Any", method), self)

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if name in type(self).gimeta.hidden_fields:
            raise AttributeError(name)
        super().__setattr__(name, value)


class RecordBuilder:
    def __init__(self, context: abi.NamespaceContext):
        self._context = context

    def build_record(self, info: StructInfo | UnionInfo) -> type[Any]:
        data = info.record_info()
        name = data["name"]
        profile = self._context.profile
        # The namespace's __dict__ is the by-name build cache; recover the
        # cached singleton rather than holding a live reference (which would
        # re-form a Namespace <-> builder cycle).
        namespace = self._context.load_namespace()
        key = (profile.name, data["namespace"], data["version"], name)
        gtype = data["gtype"]
        cacheable_gtype = gtype if gtype and data["type_name"] != "void" else 0
        gtype_key = (profile.name, cacheable_gtype)
        if cacheable_gtype:
            cached_by_gtype = _record_classes_by_gtype.get(gtype_key)
            if cached_by_gtype is not None:
                namespace.cache_member(name, cached_by_gtype)
                install_class_overlay(cached_by_gtype, self._context.name, name)
                return cached_by_gtype

        cached_by_key = _record_classes_by_key.get(key)
        if cached_by_key is not None:
            namespace.cache_member(name, cached_by_key)
            install_class_overlay(cached_by_key, self._context.name, name)
            return cached_by_key

        cached = namespace.cached_member(name)
        if cached is not None:
            _record_classes_by_key.setdefault(key, cached)
            if cacheable_gtype:
                _record_classes_by_gtype.setdefault(gtype_key, cached)
            return cached

        attrs: dict[str, object] = {
            "__module__": self._context.module_name(),
            "gimeta": types.SimpleNamespace(
                info=info,
                gtype=gtype,
                type_name=data["type_name"],
                size=data["size"],
                kind=data["kind"],
                namespace=self._context,
                version=data["version"],
                profile=profile,
                hidden_fields=set(),
                method_owner_name=self._context.qualified_name(name),
                method_infos={},
                typelib_methods={},
            ),
        }
        gimeta = cast("Any", attrs["gimeta"])
        for method_info in data["methods"]:
            method_name = callable_name(method_info)
            gimeta.method_infos[method_name] = (
                method_info,
                method_info.is_method(),
            )

        bases: tuple[type, ...] = (RecordBase,)
        extra_bases = class_bases_overlay_for(self._context.name, name)
        if extra_bases:
            bases = (*extra_bases, *bases)
        cls = cast("type[Any]", type(name, bases, attrs))
        private.record_setup_class(cls, info)
        _record_classes_by_key[key] = cls
        if cacheable_gtype:
            _record_classes_by_gtype[gtype_key] = cls
        install_class_overlay(cls, self._context.name, name)
        return cls


def _checked_instance_method(
    cls: type, method: Callable[..., Any]
) -> Callable[..., Any]:
    def wrapper(self: object, *args: object, **kwargs: object) -> object:
        if not isinstance(self, cls):
            raise TypeError(f"expected {cls.__name__}, got {type(self).__name__}")
        return method(self, *args, **kwargs)

    if isinstance(method, types.FunctionType):
        wrapper.__name__ = method.__name__
        wrapper.__qualname__ = method.__qualname__
    else:
        wrapper.__name__ = cls.__name__
        wrapper.__qualname__ = wrapper.__name__
    return wrapper


def _lookup_record_method(
    cls: type[RecordBase], name: str
) -> tuple[Callable[..., Any], bool] | None:
    lookup_name = (
        name[:-1] if name.endswith("_") and keyword.iskeyword(name[:-1]) else name
    )
    method_entry = cls.gimeta.method_infos.get(name)
    if method_entry is None and lookup_name != name:
        method_entry = cls.gimeta.method_infos.get(lookup_name)
    if method_entry is None:
        method_info = cls.gimeta.info.find_method(lookup_name)
        if method_info is None:
            return None
        method_entry = (method_info, method_info.is_method())
    method_info, has_self = method_entry

    namespace = cls.gimeta.namespace.load_namespace()
    try:
        method = make_method(
            namespace,
            f"{cls.__module__.removeprefix('ginext.')}.{cls.__name__}",
            method_info,
            has_self=has_self,
        )
    except NotImplementedError:
        return None
    if has_self:
        return method, True
    return method, False


def install_method_for_record_class(
    cls: type[RecordBase], name: str
) -> tuple[object, bool] | None:
    if not hasattr(cls.gimeta, "info"):
        return None
    found = _lookup_record_method(cls, name)
    if found is None:
        return None
    method, has_self = found
    if has_self:
        method = _checked_instance_method(cls, method)
        setattr(cls, name, method)
    else:
        setattr(cls, name, staticmethod(cast("Any", method)))
    return method, has_self


def reset_for_test() -> None:
    _record_classes_by_key.clear()
    _record_classes_by_gtype.clear()


