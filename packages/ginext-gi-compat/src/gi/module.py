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
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

from __future__ import annotations

from typing import Any

import ginext
import ginext.GIRepository as _gir
from ginext import private


_introspection_modules: dict[str, object] = {}


class _InfoWrapperMeta(type):
    """Metaclass for RepositoryInfo subclasses.

    Makes isinstance() and issubclass() work for both Python wrapper instances
    and raw ginext C info objects. Each subclass sets _ctype to the
    corresponding ginext C type.
    """

    _ctype: type = object

    def __init__(cls, name: str, bases: tuple, namespace: dict, **kwargs: object) -> None:
        super().__init__(name, bases, namespace, **kwargs)
        # Python auto-sets __module__ on each class to the defining module name.
        # That would shadow the @property defined on RepositoryInfo. Remove it from
        # subclasses so the property is found in the MRO.
        if bases and any(isinstance(b, _InfoWrapperMeta) for b in bases):
            try:
                type.__delattr__(cls, "__module__")
            except AttributeError:
                pass

    def __instancecheck__(cls, instance: object) -> bool:
        if type.__instancecheck__(cls, instance):
            return True
        ctype = cls.__dict__.get("_ctype") or getattr(cls, "_ctype", None)
        if ctype is not None and ctype is not object:
            return isinstance(instance, ctype)
        return False

    def __subclasscheck__(cls, subclass: type) -> bool:
        if type.__subclasscheck__(cls, subclass):
            return True
        ctype = cls.__dict__.get("_ctype") or getattr(cls, "_ctype", None)
        if ctype is not None and ctype is not object:
            try:
                return issubclass(subclass, ctype)
            except TypeError:
                pass
        return False


def _wrap_info(info: object, container: "RepositoryInfo | None" = None) -> "RepositoryInfo | None":
    """Wrap a ginext GI info object in a RepositoryInfo if it's not already."""
    if info is None:
        return None
    if isinstance(info, RepositoryInfo):
        return info
    ns = getattr(info, "namespace", None) or ""
    name = getattr(info, "name", None) or ""
    # Pick the most specific wrapper class (order: most specific first)
    wrapper_cls: type[RepositoryInfo] = RepositoryInfo
    for c_type, w_cls in _INFO_WRAPPER_MAP:
        if type.__instancecheck__(c_type, info):
            wrapper_cls = w_cls
            break
    kind = type(info).__name__.lower()
    return wrapper_cls(ns, name, kind, info, container=container)


def _wrap_list(infos: list[object]) -> list["RepositoryInfo"]:
    return [w for i in infos if (w := _wrap_info(i)) is not None]


def _wrap_list_with_container(
    infos: list[object], container: "RepositoryInfo"
) -> list["RepositoryInfo"]:
    return [w for i in infos if (w := _wrap_info(i, container)) is not None]


class RepositoryInfo(metaclass=_InfoWrapperMeta):
    """pygobject-compatible wrapper around ginext GI info objects."""

    __slots__ = ("namespace", "name", "kind", "info", "_container")

    _ctype: type = object

    def __init__(
        self,
        namespace: str,
        name: str,
        kind: str,
        info: object,
        container: "RepositoryInfo | None" = None,
    ) -> None:
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "info", info)
        object.__setattr__(self, "_container", container)

    # ---- BaseInfo compat ----

    @property
    def __name__(self) -> str:
        return self.name

    @property
    def __module__(self) -> str:
        return f"gi.repository.{self.namespace}"

    def get_name(self) -> str:
        return getattr(self.info, "get_name", lambda: self.name)()

    def get_name_unescaped(self) -> str:
        return self.get_name()

    def get_namespace(self) -> str:
        return getattr(self.info, "get_namespace", lambda: self.namespace)()

    def get_container(self) -> "RepositoryInfo | None":
        return self._container

    def equal(self, other: object) -> bool:
        if isinstance(other, RepositoryInfo):
            return self.namespace == other.namespace and self.name == other.name
        return False

    def __eq__(self, other: object) -> bool:
        return self.equal(other)

    def __hash__(self) -> int:
        return hash((self.namespace, self.name))

    def is_deprecated(self) -> bool:
        return False

    def get_attribute(self, name: str) -> str | None:
        fn = getattr(self.info, "get_attribute", None)
        if fn is not None:
            return fn(name)
        return None

    # ---- FunctionInfo / CallableInfo compat ----

    def get_arguments(self) -> list["RepositoryInfo"]:
        info = self.info
        n = getattr(info, "get_n_args", lambda: 0)()
        result = []
        for i in range(n):
            arg = info.get_arg(i)  # type: ignore[attr-defined]
            w = RepositoryInfo(
                getattr(arg, "get_namespace", lambda: self.namespace)(),
                getattr(arg, "get_name", lambda: "")(),
                "arg",
                arg,
                container=self,
            )
            result.append(w)
        return result

    def get_return_type(self) -> "RepositoryInfo | None":
        rt = getattr(self.info, "get_return_type", None)
        if rt is not None:
            return _wrap_info(rt())
        return None

    def can_throw_gerror(self) -> bool:
        return getattr(self.info, "can_throw_gerror", lambda: False)()

    def get_finish_func(self) -> "RepositoryInfo | None":
        fn = getattr(self.info, "get_finish_func", None)
        if fn is not None:
            result = fn()
            if result is not None:
                return _wrap_info(result)
        # Fallback 1: use glib:finish-func annotation
        finish_name = self.get_attribute("glib:finish-func")
        if finish_name is None:
            # Fallback 2: convention — replace _async suffix with _finish
            own_name = self.get_name()
            if own_name.endswith("_async"):
                finish_name = own_name[:-6] + "_finish"
        if finish_name:
            container = self._container
            if container is not None:
                return container.find_method(finish_name)
        return None

    def is_async(self) -> bool:
        return getattr(self.info, "is_async", lambda: False)()

    def get_caller_owns(self) -> Any:
        return getattr(self.info, "get_caller_owns", lambda: 0)()

    def may_return_null(self) -> bool:
        return getattr(self.info, "may_return_null", lambda: False)()

    def get_return_attribute(self, name: str) -> str:
        fn = getattr(self.info, "get_return_attribute", None)
        if fn is not None:
            return fn(name)
        raise AttributeError(name)

    @property
    def invoke(self) -> Any:
        return getattr(self.info, "invoke", None)

    def is_method(self) -> bool:
        return getattr(self.info, "is_method", lambda: False)()

    def is_constructor(self) -> bool:
        return getattr(self.info, "is_constructor", lambda: False)()

    def get_symbol(self) -> str:
        return getattr(self.info, "get_symbol", lambda: "")()

    # ---- ArgInfo compat ----

    def is_caller_allocates(self) -> bool:
        return False

    def is_return_value(self) -> bool:
        return False

    def get_ownership_transfer(self) -> Any:
        return getattr(self.info, "get_ownership_transfer", lambda: 0)()

    def get_scope(self) -> Any:
        import ginext.GIRepository as gir
        return gir.ScopeType.INVALID

    def get_direction(self) -> Any:
        return getattr(self.info, "get_direction", lambda: None)()

    def get_type_info(self) -> "RepositoryInfo | None":
        ti = getattr(self.info, "get_type_info", None)
        if ti is not None:
            result = ti()
            if result is None:
                return None
            return RepositoryInfo("", "", "typeinfo", result, container=self)
        return None

    def get_destroy_index(self) -> int:
        return getattr(self.info, "get_destroy_index", lambda: -1)()

    def get_closure_index(self) -> int:
        return getattr(self.info, "get_closure_index", lambda: -1)()

    def may_be_null(self) -> bool:
        return getattr(self.info, "may_be_null", lambda: False)()

    def is_optional(self) -> bool:
        return getattr(self.info, "is_optional", lambda: False)()

    # ---- TypeInfo compat ----

    def get_tag(self) -> Any:
        return getattr(self.info, "get_tag", lambda: None)()

    def get_tag_as_string(self) -> str:
        return getattr(self.info, "get_tag_as_string", lambda: "")()

    def is_pointer(self) -> bool:
        return getattr(self.info, "is_pointer", lambda: False)()

    def get_array_type(self) -> Any:
        return getattr(self.info, "get_array_type", lambda: 0)()

    def get_array_fixed_size(self) -> int:
        return getattr(self.info, "get_array_fixed_size", lambda: -1)()

    def is_zero_terminated(self) -> bool:
        return getattr(self.info, "is_zero_terminated", lambda: False)()

    def get_array_length_index(self) -> int:
        return getattr(self.info, "get_array_length_index", lambda: -1)()

    def get_interface(self) -> "RepositoryInfo | None":
        iface = getattr(self.info, "get_interface", None)
        if iface is not None:
            return _wrap_info(iface())
        return None

    def get_param_type(self, n: int) -> "RepositoryInfo | None":
        pt = getattr(self.info, "get_param_type", None)
        if pt is not None:
            return _wrap_info(pt(n))
        return None

    # ---- ObjectInfo / InterfaceInfo compat ----

    def _object_dict(self) -> dict | None:
        d = getattr(self.info, "object_info", None)
        if d is not None:
            return d()
        return None

    def _record_dict(self) -> dict | None:
        d = getattr(self.info, "record_info", None)
        if d is not None:
            return d()
        return None

    def get_methods(self) -> list["RepositoryInfo"]:
        d = self._object_dict() or self._record_dict()
        if d is not None:
            return _wrap_list_with_container(d.get("methods", []), self)
        # Fallback via C get_n_methods/get_methods()
        fn = getattr(self.info, "get_methods", None)
        if fn is not None:
            return _wrap_list_with_container(fn(), self)
        return []

    def get_fields(self) -> list["RepositoryInfo"]:
        # Try C-level get_fields() first (StructInfo/UnionInfo)
        fn = getattr(self.info, "get_fields", None)
        if fn is not None:
            return _wrap_list(fn())
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("fields", []))
        return []

    def get_interfaces(self) -> list["RepositoryInfo"]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("interfaces", []))
        return []

    def get_constants(self) -> list["RepositoryInfo"]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("constants", []))
        return []

    def get_vfuncs(self) -> list["RepositoryInfo"]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("vfuncs", []))
        return []

    def get_properties(self) -> list["RepositoryInfo"]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("properties", []))
        return []

    def get_signals(self) -> list["RepositoryInfo"]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("signals", []))
        return []

    def get_prerequisites(self) -> list["RepositoryInfo"]:
        info = self.info
        n = getattr(info, "get_n_prerequisites", lambda: 0)()
        result = []
        for i in range(n):
            prereq = info.get_prerequisite(i)  # type: ignore[attr-defined]
            result.append(_wrap_info(prereq))
        return [r for r in result if r is not None]

    def get_abstract(self) -> bool:
        return getattr(self.info, "get_abstract", lambda: False)()

    def get_fundamental(self) -> bool:
        return getattr(self.info, "get_fundamental", lambda: False)()

    def get_class_struct(self) -> "RepositoryInfo | None":
        d = self._object_dict()
        if d is not None:
            cs = d.get("class_struct")
            if cs is not None:
                return _wrap_info(cs)
        return None

    def get_iface_struct(self) -> "RepositoryInfo | None":
        d = self._object_dict()
        if d is not None:
            cs = d.get("class_struct")
            if cs is not None:
                return _wrap_info(cs)
        return None

    def get_type_name(self) -> str:
        return getattr(self.info, "get_type_name", lambda: "")()

    def get_type_init(self) -> str:
        return getattr(self.info, "get_type_init", lambda: "")()

    def get_parent(self) -> "RepositoryInfo | None":
        d = self._object_dict()
        if d is not None:
            parent = d.get("parent")
            if parent is not None:
                return _wrap_info(parent)
        return None

    def find_method(self, name: str) -> "RepositoryInfo | None":
        for m in self.get_methods():
            if m.get_name() == name:
                return m
        return None

    def find_vfunc(self, name: str) -> "RepositoryInfo | None":
        for vf in self.get_vfuncs():
            if vf.get_name() == name:
                return vf
        return None

    def find_signal(self, name: str) -> "RepositoryInfo | None":
        for sig in self.get_signals():
            if sig.get_name() == name:
                return sig
        return None

    def get_vfunc(self) -> "RepositoryInfo | None":
        """For a FunctionInfo, find the matching vfunc."""
        fn = getattr(self.info, "get_vfunc", None)
        if fn is not None:
            return _wrap_info(fn())
        # Fallback: search container
        container = self._container
        if container is None:
            return None
        return container.find_vfunc(self.get_name())

    def get_g_type(self) -> Any:
        return getattr(self.info, "get_g_type", lambda: None)()

    # ---- RegisteredTypeInfo compat ----

    # ---- StructInfo / UnionInfo compat ----

    def get_size(self) -> int:
        return getattr(self.info, "get_size", lambda: 0)()

    def get_alignment(self) -> int:
        return getattr(self.info, "get_alignment", lambda: 0)()

    def is_gtype_struct(self) -> bool:
        return getattr(self.info, "is_gtype_struct", lambda: False)()

    def is_foreign(self) -> bool:
        return getattr(self.info, "is_foreign", lambda: False)()

    def find_field(self, name: str) -> "RepositoryInfo | None":
        fn = getattr(self.info, "find_field", None)
        if fn is not None:
            result = fn(name)
            return _wrap_info(result)
        for f in self.get_fields():
            if f.get_name() == name:
                return f
        return None

    # ---- EnumInfo compat ----

    def get_values(self) -> list["RepositoryInfo"]:
        fn = getattr(self.info, "get_values", None)
        if fn is not None:
            return _wrap_list(fn())
        return []

    def is_flags(self) -> bool:
        return getattr(self.info, "is_flags", lambda: False)()

    def get_storage_type(self) -> int:
        return getattr(self.info, "get_storage_type", lambda: 0)()

    # ---- PropertyInfo compat ----

    def get_flags(self) -> Any:
        return getattr(self.info, "get_flags", lambda: 0)()

    def get_type(self) -> "RepositoryInfo | None":
        ti = getattr(self.info, "get_type_info", None)
        if ti is not None:
            return _wrap_info(ti())
        return None

    # ---- SignalInfo compat ----

    def get_class_closure(self) -> "RepositoryInfo | None":
        return None

    def true_stops_emit(self) -> bool:
        return False

    # ---- VFuncInfo compat ----

    def get_invoker(self) -> "RepositoryInfo | None":
        inv = getattr(self.info, "get_invoker", None)
        if inv is not None:
            return _wrap_info(inv())
        return None

    def get_signal(self) -> "RepositoryInfo | None":
        fn = getattr(self.info, "get_signal", None)
        if fn is not None:
            return _wrap_info(fn())
        return None

    def get_offset(self) -> int:
        return getattr(self.info, "get_offset", lambda: 0)()

    # ---- ObjectInfo fundamental compat ----

    def get_ref_function(self) -> str:
        return getattr(self.info, "get_ref_function_name", lambda: "")()

    def get_unref_function(self) -> str:
        return getattr(self.info, "get_unref_function_name", lambda: "")()

    def get_get_value_function(self) -> str:
        return getattr(self.info, "get_get_value_function_name", lambda: "")()

    def get_set_value_function(self) -> str:
        return getattr(self.info, "get_set_value_function_name", lambda: "")()

    # ---- FieldInfo compat ----

    # get_offset already defined above; get_size too

    # ---- General fallback ----

    def __getattr__(self, name: str) -> Any:
        return getattr(self.info, name)

    def __repr__(self) -> str:
        return f"RepositoryInfo(namespace={self.namespace!r}, name={self.name!r}, kind={self.kind!r})"


# Type-specific subclasses — each paired with its ginext C type for isinstance checks.
# The metaclass _InfoWrapperMeta makes isinstance(obj, SomeWrapper) True for raw C instances.

class BaseInfoWrapper(RepositoryInfo):
    __slots__ = ()
    _ctype = _gir.BaseInfo


class CallableInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.CallableInfo


class FunctionInfoWrapper(CallableInfoWrapper):
    __slots__ = ()
    _ctype = _gir.FunctionInfo


class VFuncInfoWrapper(CallableInfoWrapper):
    __slots__ = ()
    _ctype = _gir.VFuncInfo


class SignalInfoWrapper(CallableInfoWrapper):
    __slots__ = ()
    _ctype = _gir.SignalInfo


class CallbackInfoWrapper(CallableInfoWrapper):
    __slots__ = ()
    _ctype = _gir.CallbackInfo


class RegisteredTypeInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.RegisteredTypeInfo


class ObjectInfoWrapper(RegisteredTypeInfoWrapper):
    __slots__ = ()
    _ctype = _gir.ObjectInfo


class InterfaceInfoWrapper(RegisteredTypeInfoWrapper):
    __slots__ = ()
    _ctype = _gir.InterfaceInfo


class StructInfoWrapper(RegisteredTypeInfoWrapper):
    __slots__ = ()
    _ctype = _gir.StructInfo


class UnionInfoWrapper(RegisteredTypeInfoWrapper):
    __slots__ = ()
    _ctype = _gir.UnionInfo


class EnumInfoWrapper(RegisteredTypeInfoWrapper):
    __slots__ = ()
    _ctype = _gir.EnumInfo


class FieldInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.FieldInfo


class ArgInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.ArgInfo


class TypeInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.TypeInfo


class ConstantInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.ConstantInfo


class PropertyInfoWrapper(BaseInfoWrapper):
    __slots__ = ()
    _ctype = _gir.PropertyInfo


# Ordered most-specific first so _wrap_info picks the right class.
# FlagsInfo is a subclass of EnumInfo in ginext, handle it if present.
def _build_info_wrapper_map() -> list[tuple[type, type[RepositoryInfo]]]:
    pairs: list[tuple[type, type[RepositoryInfo]]] = [
        (_gir.FunctionInfo, FunctionInfoWrapper),
        (_gir.VFuncInfo, VFuncInfoWrapper),
        (_gir.SignalInfo, SignalInfoWrapper),
        (_gir.CallbackInfo, CallbackInfoWrapper),
        (_gir.CallableInfo, CallableInfoWrapper),
        (_gir.ObjectInfo, ObjectInfoWrapper),
        (_gir.InterfaceInfo, InterfaceInfoWrapper),
        (_gir.StructInfo, StructInfoWrapper),
        (_gir.UnionInfo, UnionInfoWrapper),
        (_gir.PropertyInfo, PropertyInfoWrapper),
        (_gir.FieldInfo, FieldInfoWrapper),
        (_gir.ArgInfo, ArgInfoWrapper),
        (_gir.TypeInfo, TypeInfoWrapper),
        (_gir.ConstantInfo, ConstantInfoWrapper),
        (_gir.RegisteredTypeInfo, RegisteredTypeInfoWrapper),
        (_gir.BaseInfo, BaseInfoWrapper),
    ]
    # Insert FlagsInfo before EnumInfo if present
    flags_cls = getattr(_gir, "FlagsInfo", None)
    if flags_cls is not None:
        pairs.insert(pairs.index((_gir.EnumInfo if hasattr(_gir, "EnumInfo") else None, EnumInfoWrapper)), (flags_cls, EnumInfoWrapper))  # type: ignore[arg-type]
    # Insert EnumInfo
    pairs.append((_gir.EnumInfo, EnumInfoWrapper))
    return pairs


# Rebuild to ensure ordering is clean
_INFO_WRAPPER_MAP: list[tuple[type, type[RepositoryInfo]]] = [
    # Most-specific subtypes first within each branch.
    # CallableInfo branch (FunctionInfo/VFuncInfo/SignalInfo/CallbackInfo before CallableInfo):
    (_gir.FunctionInfo, FunctionInfoWrapper),
    (_gir.VFuncInfo, VFuncInfoWrapper),
    (_gir.SignalInfo, SignalInfoWrapper),
    (_gir.CallbackInfo, CallbackInfoWrapper),
    (_gir.CallableInfo, CallableInfoWrapper),
    # RegisteredTypeInfo branch (subtypes before RegisteredTypeInfo):
    (_gir.ObjectInfo, ObjectInfoWrapper),
    (_gir.InterfaceInfo, InterfaceInfoWrapper),
    (_gir.StructInfo, StructInfoWrapper),
    (_gir.UnionInfo, UnionInfoWrapper),
    (_gir.EnumInfo, EnumInfoWrapper),   # EnumInfo/FlagsInfo before RegisteredTypeInfo
    (_gir.RegisteredTypeInfo, RegisteredTypeInfoWrapper),
    # Leaf types:
    (_gir.PropertyInfo, PropertyInfoWrapper),
    (_gir.FieldInfo, FieldInfoWrapper),
    (_gir.ArgInfo, ArgInfoWrapper),
    (_gir.TypeInfo, TypeInfoWrapper),
    (_gir.ConstantInfo, ConstantInfoWrapper),
    # Base catch-all:
    (_gir.BaseInfo, BaseInfoWrapper),
]

# Insert FlagsInfo before EnumInfo if present (FlagsInfo is a subtype of EnumInfo)
_flags_cls = getattr(_gir, "FlagsInfo", None)
if _flags_cls is not None:
    _INFO_WRAPPER_MAP.insert(
        next(i for i, (ct, _) in enumerate(_INFO_WRAPPER_MAP) if ct is _gir.EnumInfo),
        (_flags_cls, EnumInfoWrapper),
    )


class Repository:
    def find_by_name(self, namespace: str, name: str) -> RepositoryInfo | None:
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            return None
        namespace, version = resolved
        try:
            kind, info = private.namespace_find(namespace, version, name)
        except (AttributeError, ImportError, RuntimeError):
            return None
        return _wrap_info(info) or RepositoryInfo(namespace, name, kind, info)

    def is_registered(self, namespace: str, version: str | None = None) -> bool:
        if not isinstance(namespace, str):
            raise TypeError("namespace must be a string")
        return private.namespace_is_registered(namespace, version)

    def require(
        self, namespace: str, version: str | None = None, flags: int = 0
    ) -> object:
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            v = version or ""
        else:
            namespace, v = resolved
            if version is not None:
                v = version
        private.require_namespace(namespace, v)
        from gi import repository as gi_repository

        return getattr(gi_repository, namespace)

    def get_dependencies(self, namespace: str, version: str | None = None) -> list[str]:
        if not isinstance(namespace, str):
            raise TypeError("namespace must be a string")
        return private.namespace_get_dependencies(namespace)

    def get_immediate_dependencies(
        self, namespace: str, version: str | None = None
    ) -> list[str]:
        if not isinstance(namespace, str):
            raise TypeError("namespace must be a string")
        return private.namespace_get_immediate_dependencies(namespace)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


repository = Repository()


def get_introspection_module(namespace: str) -> Any:
    cached = _introspection_modules.get(namespace)
    if cached is not None:
        return cached
    from gi import repository as gi_repository

    module = getattr(gi_repository, namespace)
    _introspection_modules[namespace] = module
    return module
