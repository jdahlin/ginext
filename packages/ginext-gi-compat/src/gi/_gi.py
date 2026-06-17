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

import signal
from types import ModuleType
from typing import Any, SupportsIndex

import ginext.GIRepository as _GIRepo
from ginext import GObject as _GObject_namespace
from ginext.gobject.gobjectclass import GObject
from ginext.gobject.gtype import (
    GType as GType,
    compat_gtype_from_raw as _compat_gtype_from_raw,
)
from . import _repository_helpers

# Ensure GTypeMeta/GType compat patches (including GType.INVALID) are applied
# before we access them below. This is done here rather than in gi/__init__.py
# to avoid a circular-import race: gi is partially initialized when __init__.py
# runs, but by the time _gi.py is first imported, gi is fully initialized.
# Use a relative import so this works in subprocess environments where gi may
# be found at a different sys.path location than the parent process.
try:
    from ._gtype_compat import ensure_installed as _ensure_gi_compat

    _ensure_gi_compat()
except ImportError:
    # Stale build: ensure_installed not yet present — call _install directly.
    try:
        from ._gtype_compat import _install as _ensure_gi_compat  # type: ignore[assignment]

        _ensure_gi_compat()
    except ImportError:
        pass
try:
    del _ensure_gi_compat
except NameError:
    pass

# Last-resort fallback: if _install() was skipped or returned early without
# setting INVALID (e.g. stale build cache with mismatched _gi_compat_installed
# state), create the constant directly so the rest of _gi.py can load.
if not hasattr(GType, "INVALID"):
    import types as _types
    from ginext import abi as _abi

    _invalid_cls = type(
        "TYPE_INVALID",
        (GType,),
        {
            "__module__": "ginext.gobject.gtype",
            "gimeta": _types.SimpleNamespace(gtype=0, profile=_abi.NATIVE),
            "gtype_name": "",
        },
    )
    GType.INVALID = _invalid_cls  # type: ignore[attr-defined]
    del _types, _abi, _invalid_cls

# Enum/flags types re-exported from GIRepository
Direction = _GIRepo.Direction
Transfer = _GIRepo.Transfer
ScopeType = _GIRepo.ScopeType
ArrayType = _GIRepo.ArrayType
TypeTag = _GIRepo.TypeTag
FieldInfoFlags = _GIRepo.FieldInfoFlags
FunctionInfoFlags = _GIRepo.FunctionInfoFlags
VFuncInfoFlags = _GIRepo.VFuncInfoFlags

# GType convenience constant
TYPE_INVALID = GType.INVALID

SIGNAL_RUN_FIRST = _GObject_namespace.SignalFlags.RUN_FIRST


class RepositoryError(Exception):
    pass


class ResultTuple(tuple):
    _field_names: tuple[str | None, ...] = ()

    @classmethod
    def _new_type(cls, names: list[str | None]) -> type[ResultTuple]:
        return type(
            "ResultTuple",
            (cls,),
            {"_field_names": tuple(names), "__module__": cls.__module__},
        )

    def __getattr__(self, name: str) -> object:
        try:
            index = self._field_names.index(name)
        except ValueError as exc:
            raise AttributeError(name) from exc
        return self[index]

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | {n for n in self._field_names if n})

    def __repr__(self) -> str:
        parts = []
        for index, value in enumerate(self):
            name = self._field_names[index] if index < len(self._field_names) else None
            rendered = repr(value)
            parts.append(f"{name}={rendered}" if name else rendered)
        return f"({', '.join(parts)})"

    def __reduce_ex__(self, protocol: SupportsIndex, /) -> tuple[type, tuple[Any, ...]]:
        return tuple, (tuple(self),)


class Warning(RuntimeWarning):
    pass


# Alias used by pygobject's overrides
PyGIWarning = Warning


# --------------------------------------------------------------------------
# Info wrapper types
# These wrap ginext's raw C info objects with a pygobject-compatible API.
# --------------------------------------------------------------------------

import ginext
import ginext.GIRepository as _gir
from ginext import private as _private


class InfoWrapperMeta(type):
    _ctype: type = object

    def __init__(
        cls, name: str, bases: tuple, namespace: dict, **kwargs: object
    ) -> None:
        super().__init__(name, bases, namespace, **kwargs)
        if bases and any(isinstance(b, InfoWrapperMeta) for b in bases):
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


def _wrap_info(
    info: object, container: RepositoryInfo | None = None
) -> RepositoryInfo | None:
    if info is None:
        return None
    if isinstance(info, RepositoryInfo):
        return info
    ns = getattr(info, "namespace", None) or ""
    name = getattr(info, "name", None) or ""
    wrapper_cls: type[RepositoryInfo] = RepositoryInfo
    for c_type, w_cls in _INFO_WRAPPER_MAP:
        if type.__instancecheck__(c_type, info):
            wrapper_cls = w_cls
            break
    kind = type(info).__name__.lower()
    return wrapper_cls(ns, name, kind, info, container=container)


def _wrap_list(infos: list[object]) -> list[RepositoryInfo]:
    return [w for i in infos if (w := _wrap_info(i)) is not None]


def _wrap_list_with_container(
    infos: list[object], container: RepositoryInfo
) -> list[RepositoryInfo]:
    return [w for i in infos if (w := _wrap_info(i, container)) is not None]


class RepositoryInfo(metaclass=InfoWrapperMeta):
    __slots__ = ("namespace", "name", "kind", "info", "_container")
    _ctype: type = object

    def __init__(
        self,
        namespace: str,
        name: str,
        kind: str,
        info: object,
        container: RepositoryInfo | None = None,
    ) -> None:
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "info", info)
        object.__setattr__(self, "_container", container)

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

    def get_container(self) -> RepositoryInfo | None:
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

    def get_arguments(self) -> list[RepositoryInfo]:
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

    def get_return_type(self) -> RepositoryInfo | None:
        rt = getattr(self.info, "get_return_type", None)
        if rt is not None:
            return _wrap_info(rt())
        return None

    def can_throw_gerror(self) -> bool:
        return getattr(self.info, "can_throw_gerror", lambda: False)()

    def get_finish_func(self) -> RepositoryInfo | None:
        fn = getattr(self.info, "get_finish_func", None)
        if fn is not None:
            result = fn()
            if result is not None:
                return _wrap_info(result)
        finish_name = self.get_attribute("glib:finish-func")
        if finish_name is None:
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

    def is_caller_allocates(self) -> bool:
        return False

    def is_return_value(self) -> bool:
        return False

    def get_ownership_transfer(self) -> Any:
        return getattr(self.info, "get_ownership_transfer", lambda: 0)()

    def get_scope(self) -> Any:
        return _gir.ScopeType.INVALID

    def get_direction(self) -> Any:
        return getattr(self.info, "get_direction", lambda: None)()

    def get_type_info(self) -> RepositoryInfo | None:
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

    def get_interface(self) -> RepositoryInfo | None:
        iface = getattr(self.info, "get_interface", None)
        if iface is not None:
            return _wrap_info(iface())
        return None

    def get_param_type(self, n: int) -> RepositoryInfo | None:
        pt = getattr(self.info, "get_param_type", None)
        if pt is not None:
            return _wrap_info(pt(n))
        return None

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

    def get_methods(self) -> list[RepositoryInfo]:
        d = self._object_dict() or self._record_dict()
        if d is not None:
            return _wrap_list_with_container(d.get("methods", []), self)
        fn = getattr(self.info, "get_methods", None)
        if fn is not None:
            return _wrap_list_with_container(fn(), self)
        return []

    def get_fields(self) -> list[RepositoryInfo]:
        fn = getattr(self.info, "get_fields", None)
        if fn is not None:
            return _wrap_list(fn())
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("fields", []))
        return []

    def get_interfaces(self) -> list[RepositoryInfo]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("interfaces", []))
        return []

    def get_constants(self) -> list[RepositoryInfo]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("constants", []))
        return []

    def get_vfuncs(self) -> list[RepositoryInfo]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("vfuncs", []))
        return []

    def get_properties(self) -> list[RepositoryInfo]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("properties", []))
        return []

    def get_signals(self) -> list[RepositoryInfo]:
        d = self._object_dict()
        if d is not None:
            return _wrap_list(d.get("signals", []))
        return []

    def get_prerequisites(self) -> list[RepositoryInfo]:
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

    def get_class_struct(self) -> RepositoryInfo | None:
        d = self._object_dict()
        if d is not None:
            cs = d.get("class_struct")
            if cs is not None:
                return _wrap_info(cs)
        return None

    def get_iface_struct(self) -> RepositoryInfo | None:
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

    def get_parent(self) -> RepositoryInfo | None:
        d = self._object_dict()
        if d is not None:
            parent = d.get("parent")
            if parent is not None:
                return _wrap_info(parent)
        return None

    def find_method(self, name: str) -> RepositoryInfo | None:
        for m in self.get_methods():
            if m.get_name() == name:
                return m
        return None

    def find_vfunc(self, name: str) -> RepositoryInfo | None:
        for vf in self.get_vfuncs():
            if vf.get_name() == name:
                return vf
        return None

    def find_signal(self, name: str) -> RepositoryInfo | None:
        for sig in self.get_signals():
            if sig.get_name() == name:
                return sig
        return None

    def get_vfunc(self) -> RepositoryInfo | None:
        fn = getattr(self.info, "get_vfunc", None)
        if fn is not None:
            return _wrap_info(fn())
        container = self._container
        if container is None:
            return None
        return container.find_vfunc(self.get_name())

    def get_g_type(self) -> Any:
        raw = getattr(self.info, "get_g_type", lambda: None)()
        if raw is None:
            return TYPE_INVALID
        if isinstance(raw, int):
            from ginext import GObject as _GO

            name = _GO.type_name(raw) or ""
            return _compat_gtype_from_raw(raw, name)
        return raw

    def get_size(self) -> int:
        return getattr(self.info, "get_size", lambda: 0)()

    def get_alignment(self) -> int:
        return getattr(self.info, "get_alignment", lambda: 0)()

    def is_gtype_struct(self) -> bool:
        return getattr(self.info, "is_gtype_struct", lambda: False)()

    def is_foreign(self) -> bool:
        return getattr(self.info, "is_foreign", lambda: False)()

    def find_field(self, name: str) -> RepositoryInfo | None:
        fn = getattr(self.info, "find_field", None)
        if fn is not None:
            result = fn(name)
            return _wrap_info(result)
        for f in self.get_fields():
            if f.get_name() == name:
                return f
        return None

    def get_values(self) -> list[RepositoryInfo]:
        fn = getattr(self.info, "get_values", None)
        if fn is not None:
            return _wrap_list(fn())
        return []

    def is_flags(self) -> bool:
        return getattr(self.info, "is_flags", lambda: False)()

    def get_storage_type(self) -> int:
        return getattr(self.info, "get_storage_type", lambda: 0)()

    def get_flags(self) -> Any:
        return getattr(self.info, "get_flags", lambda: 0)()

    def get_type(self) -> RepositoryInfo | None:
        ti = getattr(self.info, "get_type_info", None)
        if ti is not None:
            return _wrap_info(ti())
        return None

    def get_class_closure(self) -> RepositoryInfo | None:
        return None

    def true_stops_emit(self) -> bool:
        return False

    def get_invoker(self) -> RepositoryInfo | None:
        inv = getattr(self.info, "get_invoker", None)
        if inv is not None:
            return _wrap_info(inv())
        return None

    def get_signal(self) -> RepositoryInfo | None:
        fn = getattr(self.info, "get_signal", None)
        if fn is not None:
            return _wrap_info(fn())
        return None

    def get_offset(self) -> int:
        return getattr(self.info, "get_offset", lambda: 0)()

    def get_ref_function(self) -> str:
        return getattr(self.info, "get_ref_function_name", lambda: "")()

    def get_unref_function(self) -> str:
        return getattr(self.info, "get_unref_function_name", lambda: "")()

    def get_get_value_function(self) -> str:
        return getattr(self.info, "get_get_value_function_name", lambda: "")()

    def get_set_value_function(self) -> str:
        return getattr(self.info, "get_set_value_function_name", lambda: "")()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.info, name)

    def __repr__(self) -> str:
        return f"RepositoryInfo(namespace={self.namespace!r}, name={self.name!r}, kind={self.kind!r})"


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


_INFO_WRAPPER_MAP: list[tuple[type, type[RepositoryInfo]]] = [
    (_gir.FunctionInfo, FunctionInfoWrapper),
    (_gir.VFuncInfo, VFuncInfoWrapper),
    (_gir.SignalInfo, SignalInfoWrapper),
    (_gir.CallbackInfo, CallbackInfoWrapper),
    (_gir.CallableInfo, CallableInfoWrapper),
    (_gir.ObjectInfo, ObjectInfoWrapper),
    (_gir.InterfaceInfo, InterfaceInfoWrapper),
    (_gir.StructInfo, StructInfoWrapper),
    (_gir.UnionInfo, UnionInfoWrapper),
    (_gir.EnumInfo, EnumInfoWrapper),
    (_gir.RegisteredTypeInfo, RegisteredTypeInfoWrapper),
    (_gir.PropertyInfo, PropertyInfoWrapper),
    (_gir.FieldInfo, FieldInfoWrapper),
    (_gir.ArgInfo, ArgInfoWrapper),
    (_gir.TypeInfo, TypeInfoWrapper),
    (_gir.ConstantInfo, ConstantInfoWrapper),
    (_gir.BaseInfo, BaseInfoWrapper),
]

_flags_cls = getattr(_gir, "FlagsInfo", None)
if _flags_cls is not None:
    _INFO_WRAPPER_MAP.insert(
        next(i for i, (ct, _) in enumerate(_INFO_WRAPPER_MAP) if ct is _gir.EnumInfo),
        (_flags_cls, EnumInfoWrapper),
    )

# Pygobject-compatible aliases
BaseInfo = BaseInfoWrapper
CallableInfo = CallableInfoWrapper
FunctionInfo = FunctionInfoWrapper
VFuncInfo = VFuncInfoWrapper
SignalInfo = SignalInfoWrapper
CallbackInfo = CallbackInfoWrapper
RegisteredTypeInfo = RegisteredTypeInfoWrapper
ObjectInfo = ObjectInfoWrapper
InterfaceInfo = InterfaceInfoWrapper
StructInfo = StructInfoWrapper
UnionInfo = UnionInfoWrapper
EnumInfo = EnumInfoWrapper
FieldInfo = FieldInfoWrapper
ArgInfo = ArgInfoWrapper
TypeInfo = TypeInfoWrapper
ConstantInfo = ConstantInfoWrapper
PropertyInfo = PropertyInfoWrapper


# --------------------------------------------------------------------------
# Repository
# --------------------------------------------------------------------------


class Repository:
    _instance: Repository | None = None

    @classmethod
    def get_default(cls) -> Repository:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def find_by_name(self, namespace: str, name: str) -> RepositoryInfo | None:
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            return None
        namespace, version = resolved
        try:
            kind, info = _private.namespace_find(namespace, version, name)
        except (AttributeError, ImportError, RuntimeError):
            return None
        return _wrap_info(info) or RepositoryInfo(namespace, name, kind, info)

    def is_registered(self, namespace: str, version: str | None = None) -> bool:
        if not isinstance(namespace, str):
            raise TypeError("namespace must be a string")
        if version == "":
            return False
        return bool(_repository_helpers.repository().is_registered(namespace, version))

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
        _private.require_namespace(namespace, v)
        _repository_helpers.require(namespace, v)
        from gi import repository as gi_repository

        return getattr(gi_repository, namespace)

    def get_dependencies(self, namespace: str, version: str | None = None) -> list[str]:
        if not isinstance(namespace, str):
            raise TypeError("namespace must be a string")
        return list(_repository_helpers.repository().get_dependencies(namespace))

    def get_immediate_dependencies(
        self, namespace: str, version: str | None = None
    ) -> list[str]:
        if not isinstance(namespace, str):
            raise TypeError("namespace must be a string")
        return list(
            _repository_helpers.repository().get_immediate_dependencies(namespace)
        )

    def get_version(self, namespace: str) -> str:
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            return ""
        _, version = resolved
        return version

    def get_typelib_path(self, namespace: str) -> str:
        try:
            version = self.get_version(namespace) or None
            return _repository_helpers.typelib_path(namespace, version) or ""
        except (AttributeError, RuntimeError):
            return ""

    def get_infos(self, namespace: str) -> list[RepositoryInfo]:
        try:
            names = _private.namespace_dir(namespace)
        except (AttributeError, RuntimeError):
            return []
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            return []
        _, version = resolved
        result = []
        for name in names:
            try:
                kind, info = _private.namespace_find(namespace, version, name)
                w = _wrap_info(info) or RepositoryInfo(namespace, name, kind, info)
                result.append(w)
            except (AttributeError, ImportError, RuntimeError):
                pass
        return result

    def enumerate_versions(self, namespace: str) -> list[str]:
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            return []
        return [resolved[1]]

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


# --------------------------------------------------------------------------
# Base types for GI-wrapped objects (pygobject compat)
# --------------------------------------------------------------------------


class Struct:
    """Base class for GI-wrapped struct types."""

    __slots__ = ()


class Boxed(Struct):
    """Base class for GI-wrapped boxed types."""

    __slots__ = ()


class Fundamental:
    """Base class for GI-wrapped fundamental types."""

    __slots__ = ()


class GInterface:
    """Base class for GI-wrapped interface types."""

    __slots__ = ()


class CCallback:
    """Base class for GI-wrapped callback types."""

    __slots__ = ()


# --------------------------------------------------------------------------
# Stubs for C-level operations (implemented progressively)
# --------------------------------------------------------------------------

_API = None  # capsule stub


def pygobject_new_full(ptr: object, steal: bool, gtype: object = None) -> object:
    """Wrap a raw GObject pointer as a Python object."""
    raise NotImplementedError("pygobject_new_full is not yet implemented")


def type_register(cls: type, type_name: str | None = None) -> None:
    """Register a new Python GObject subclass with the GType system."""
    from ginext.gobject.subclass import register_python_subclass

    try:
        register_python_subclass(cls, type_name=type_name)
    except Exception:
        pass


def _install_metaclass(metaclass_base: type) -> None:
    """Install pygobject's metaclass on the C GObject type. Stub."""
    pass


def register_interface_info(gtype: object) -> None:
    """Register interface info for a GType. Stub."""
    pass


def hook_up_vfunc_implementation(
    vfunc_info: object, gtype: object, py_callable: object
) -> None:
    """Hook up a virtual function implementation. Stub."""
    pass


# --------------------------------------------------------------------------
# enum_add / flags_add
# --------------------------------------------------------------------------


def enum_add(module: ModuleType, name: str, gtype: object, info: object) -> type:
    if not isinstance(module, ModuleType):
        raise TypeError("first argument must be a module")
    from ginext import features

    if features.is_enabled(features.PYGOBJECT_COMPAT):
        try:
            from ginext import GObject as _GO

            int_gtype = int(gtype)  # type: ignore[arg-type]
            ns_name = _GO.type_name(int_gtype) or name
            ns = (
                getattr(module, "_namespace", None)
                or module.__name__.rsplit(".", 1)[-1]
            )
            import importlib

            repo_mod = importlib.import_module(f"gi.repository.{ns}")
            attr = getattr(repo_mod, name, None)
            if attr is not None:
                return attr  # type: ignore[return-value]
        except Exception:
            pass
    raise NotImplementedError(
        f"enum_add({name!r}) - enum registration is provided by the repository loader"
    )


def flags_add(module: ModuleType, name: str, gtype: object, info: object) -> type:
    if not isinstance(module, ModuleType):
        raise TypeError("first argument must be a module")
    from ginext import features

    if features.is_enabled(features.PYGOBJECT_COMPAT):
        try:
            ns = (
                getattr(module, "_namespace", None)
                or module.__name__.rsplit(".", 1)[-1]
            )
            import importlib

            repo_mod = importlib.import_module(f"gi.repository.{ns}")
            attr = getattr(repo_mod, name, None)
            if attr is not None:
                return attr  # type: ignore[return-value]
        except Exception:
            pass
    raise NotImplementedError(
        f"flags_add({name!r}) - flags registration is provided by the repository loader"
    )


# --------------------------------------------------------------------------
# Signal / OS helpers
# --------------------------------------------------------------------------


def variant_type_from_string(type_string: str) -> object:
    from ginext import GLib

    return GLib.VariantType.new(type_string)


def pyos_getsig(sig_num: int) -> int:
    handler = signal.getsignal(sig_num)
    if handler is signal.SIG_DFL:
        return 0
    if handler is signal.SIG_IGN:
        return 1
    return id(handler)


def pyos_setsig(sig_num: int, handler_ptr: int) -> int:
    old_handler = signal.getsignal(sig_num)
    if handler_ptr == 0:
        new_handler = signal.SIG_DFL
    elif handler_ptr == 1:
        new_handler = signal.SIG_IGN
    else:
        new_handler = signal.default_int_handler
    signal.signal(sig_num, new_handler)
    if old_handler is signal.SIG_DFL:
        return 0
    if old_handler is signal.SIG_IGN:
        return 1
    return id(old_handler)


__all__ = [
    "GInterface",
    "GObject",
    "GType",
    "Repository",
    "RepositoryError",
    "ResultTuple",
    "SIGNAL_RUN_FIRST",
    "TYPE_INVALID",
    # Info types
    "BaseInfo",
    "CallableInfo",
    "CallbackInfo",
    "ConstantInfo",
    "EnumInfo",
    "FieldInfo",
    "FunctionInfo",
    "InterfaceInfo",
    "ObjectInfo",
    "PropertyInfo",
    "RegisteredTypeInfo",
    "SignalInfo",
    "StructInfo",
    "TypeInfo",
    "UnionInfo",
    "VFuncInfo",
    "ArgInfo",
    # Base types
    "Struct",
    "Boxed",
    "Fundamental",
    "CCallback",
    # Functions
    "_install_metaclass",
    "enum_add",
    "flags_add",
    "hook_up_vfunc_implementation",
    "pygobject_new_full",
    "pyos_getsig",
    "pyos_setsig",
    "register_interface_info",
    "type_register",
    "variant_type_from_string",
    # Warnings
    "PyGIWarning",
    "Warning",
]
