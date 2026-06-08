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

"""Build Python classes for GIR-imported GObject types.

The class created here uses `GObject` (from gobject.py) as its base.
Imported classes pre-populate `gimeta` and the signal tables in the
`type(...)` attrs dict, so `GObject.__init_subclass__` detects the
path and short-circuits the Python-defined-subclass registration.
"""

from __future__ import annotations

import sys
import types
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Protocol,
    TypeVar,
    cast,
    runtime_checkable,
)

from . import abi, private
from .aio import AsyncCallable, NamedReturn

if TYPE_CHECKING:
    from .namespace import Namespace
    from ginext.GIRepository import (
        CallableInfo,
        InterfaceInfo,
        ObjectInfo,
        SignalInfo,
        VFuncInfo,
    )

    @runtime_checkable
    class _InterfaceInfoWithPrerequisites(Protocol):
        def get_n_prerequisites(self) -> int: ...
        def get_prerequisite(self, index: int) -> ObjectInfo | InterfaceInfo: ...
from .fundamental import Fundamental
from .gobject.gobjectclass import (
    GInterface,
    GObject,
    GObjectMeta,
    _wrap_preallocated_construction,
    wrap_existing_pointer_for_class,
)
from .gobject.resolve import own_gimeta
from .method import attach_owner_metadata, callable_name, make_method
from .overlay import (
    async_result_names_for,
    class_bases_overlay_for,
    install_class_overlay,
)
from .signal.descriptor import SignalDescriptor

_V = TypeVar("_V")

_classes_by_gtype: dict[tuple[str, int], type[Any]] = {}


@runtime_checkable
class _HasProfile(Protocol):
    _profile: abi.ABIProfile


def _non_inherited_constructor(*args: object, **kwargs: object) -> object:
    raise TypeError("constructor is not available on this type")


def _merge_class_dict_attr(
    bases: tuple[type, ...], attr_name: str
) -> dict[str, object]:
    merged: dict[str, object] = {}
    for base in reversed(bases):
        value = base.__dict__.get(attr_name)
        if isinstance(value, dict):
            merged.update(value)
    return merged


def _merge_gimeta_attr(bases: tuple[type, ...], attr_name: str) -> dict[str, _V]:
    merged: dict[str, _V] = {}
    for base in reversed(bases):
        gimeta = own_gimeta(base)
        if gimeta is None:
            continue
        value = getattr(gimeta, attr_name, None)
        if isinstance(value, dict):
            merged.update(value)
    return merged


class ClassBuilder:
    def __init__(self, context: abi.NamespaceContext):
        self._context = context

    def _namespace_for_data(self, data: dict[str, Any]) -> "Namespace":
        ns = sys.modules["ginext"]._load_namespace(
            data["namespace"], data["version"], profile=self._context.profile
        )
        return cast("Namespace", ns)

    def _bases_for_data(
        self,
        data: dict[str, Any],
        name: str,
        *,
        is_interface: bool,
        info: "ObjectInfo | InterfaceInfo",
    ) -> tuple[type, tuple[type, ...]]:
        parent_info = data["parent"]
        parent_cls: type
        if is_interface:
            parent_cls = GInterface
        elif parent_info is not None:
            parent_cls = self.class_for_info(parent_info)
        elif data.get("is_instantiatable") and not data.get("is_gobject"):
            parent_cls = Fundamental
        else:
            parent_cls = GObject
        parent_mro = parent_cls.__mro__

        interface_bases: list[type] = []
        for interface_info in data.get("interfaces", ()):
            interface_cls = self.class_for_info(interface_info)
            if interface_cls in parent_mro or interface_cls in interface_bases:
                continue
            interface_bases.append(interface_cls)
        if is_interface:
            interface_info = cast("_InterfaceInfoWithPrerequisites", info)
            for index in range(interface_info.get_n_prerequisites()):
                prerequisite_info = interface_info.get_prerequisite(index)
                interface_cls = self.class_for_info(prerequisite_info)
                if interface_cls in parent_mro or interface_cls in interface_bases:
                    continue
                interface_bases.append(interface_cls)

        extra_bases = list(
            class_bases_overlay_for(
                self._context.name, name, profile=self._context.profile
            )
        )
        seen = set(extra_bases)
        for interface_cls in interface_bases:
            if interface_cls not in seen:
                extra_bases.append(interface_cls)
                seen.add(interface_cls)
        extra_bases = _prune_redundant_bases(extra_bases)

        return parent_cls, (*extra_bases, parent_cls)

    def build_object_or_interface(
        self, info: "ObjectInfo | InterfaceInfo"
    ) -> type[Any]:
        from ginext.GIRepository import InterfaceInfo

        data = info.object_info()
        name = data["name"]
        gtype = data["gtype"]
        profile = self._context.profile
        # The namespace's __dict__ is the by-name build cache; recover the
        # cached singleton rather than holding a live reference (which would
        # re-form a Namespace <-> builder cycle).
        namespace = self._context.load_namespace()
        gtype_key = (profile.name, gtype)
        if gtype:
            cached_by_gtype = _classes_by_gtype.get(gtype_key)
            if cached_by_gtype is not None:
                namespace.cache_member(name, cached_by_gtype)
                install_class_overlay(cached_by_gtype, self._context.name, name)
                return cached_by_gtype

        cached = namespace.cached_member(name)
        if cached is not None:
            if gtype:
                _classes_by_gtype.setdefault(gtype_key, cached)
            return cached

        # The root GObject base is a single shared class object, not one class
        # per profile. Once adopted, every profile resolves GObject.Object to
        # it rather than re-running adoption (which would re-derive the signal
        # and method tables non-deterministically across profiles).
        if (
            data["namespace"] == "GObject"
            and name == "Object"
            and "_gobject_root_adopted" in GObject.__dict__
        ):
            if gtype:
                _classes_by_gtype.setdefault(gtype_key, GObject)
            namespace.cache_member(name, GObject)
            install_class_overlay(GObject, self._context.name, name)
            return GObject

        parent_cls, bases = self._bases_for_data(
            data, name, is_interface=isinstance(info, InterfaceInfo), info=info
        )

        gimeta = private.GIMeta.from_type_name(data["type_name"], info)
        gimeta.profile = profile
        attrs: dict[str, object] = {
            "__module__": self._context.module_name(),
            "gimeta": gimeta,
            "_class_struct_name": None,
        }
        method_infos: dict[str, tuple[CallableInfo, bool]] = {}
        signal_method_backings: dict[str, Callable[..., object]] = _merge_gimeta_attr(
            bases, "signal_method_backings"
        )
        own_method_names: set[str] = set()
        for method_info in data["methods"]:
            method_name = callable_name(method_info)
            own_method_names.add(method_name)
            if (
                data["namespace"] == "GObject"
                and name == "Object"
                and method_name in {"connect", "disconnect"}
            ):
                continue
            has_self = method_info.is_method()
            method_infos[method_name] = (method_info, has_self)
        if "new" not in own_method_names and _class_has_method(parent_cls, "new"):
            attrs["new"] = staticmethod(_non_inherited_constructor)
        class_struct_info = data.get("class_struct")
        if class_struct_info is not None:
            class_struct_data = class_struct_info.record_info()
            attrs["_class_struct_name"] = class_struct_data["name"]

        # Signal table + method/signal collision handling. A signal whose
        # normalized python name matches a method has the method moved into
        # gimeta.signal_method_backings; the attribute name itself stays unset
        # so the lazy __getattr__ produces a Signal whose __call__ forwards
        # to the backing method.
        #
        # Inherit the parent class's tables so subclasses see their parent's
        # signals (notably GObject::notify reaches every subclass). Plain
        # MRO attribute lookup wouldn't merge dicts — each class would see
        # only its own — so the merge has to happen explicitly here.
        signal_infos: dict[str, SignalInfo | SignalDescriptor] = _merge_gimeta_attr(
            bases, "signal_infos"
        )
        vfunc_infos: dict[str, VFuncInfo] = _merge_gimeta_attr(bases, "vfunc_infos")
        for signal_info in data["signals"]:
            sig_name = callable_name(signal_info)
            signal_infos[sig_name] = signal_info
            method_entry = method_infos.pop(sig_name, None)
            method = None
            if method_entry is not None:
                method_info, has_self = method_entry
                try:
                    method = make_method(
                        namespace,
                        self._context.qualified_name(name),
                        method_info,
                        has_self=has_self,
                    )
                except NotImplementedError:
                    pass
            else:
                method = cast(
                    "Callable[..., object] | None", _method_from_bases(bases, sig_name)
                )
            if method is not None:
                signal_method_backings[sig_name] = method
                attrs[sig_name] = SignalDescriptor.imported(
                    sig_name, signal_info, cast("Any", method)
                )
        for vfunc_info in data["vfuncs"]:
            vfunc_infos[callable_name(vfunc_info)] = vfunc_info
        for property_info in data.get("properties", ()):
            gimeta.register_property_type_info(property_info.get_name(), property_info)

        owner_name = self._context.qualified_name(name)
        gimeta.namespace = self._context
        gimeta.method_owner_name = owner_name
        gimeta.method_infos = method_infos
        gimeta.signal_infos = signal_infos
        gimeta.signal_method_backings = signal_method_backings
        gimeta.vfunc_infos = vfunc_infos

        if data["namespace"] == "GObject" and name == "Object":
            # Merge the introspected root into the hand-written Python base
            # instead of stacking a separate subclass on top of it: there is
            # one canonical base class, reachable as GObject.Object.
            cls = GObject
            for attr_name, attr_value in attrs.items():
                if attr_name == "__module__":
                    continue
                setattr(cls, attr_name, attr_value)
            cls.__name__ = "Object"
            cls.__qualname__ = "Object"
            cls.__module__ = cast("str", attrs["__module__"])
            cls._gobject_root_adopted = True
        else:
            cls = cast("type[Any]", type(name, bases, attrs))
        if data["vfuncs"]:
            gimeta.install_native_vfunc_attrs(cls, info)
        if data["gtype"]:
            _classes_by_gtype[(profile.name, data["gtype"])] = cls
        install_class_overlay(cls, self._context.name, name)
        return cls

    def class_for_info(self, info: ObjectInfo | InterfaceInfo) -> type[Any]:
        data = info.object_info()
        namespace = self._namespace_for_data(data)
        return cast("type[Any]", getattr(namespace, data["name"]))


_interface_impl_cache: dict[int, type] = {}


def _concrete_impl_for_interface(iface_cls: type) -> type:
    """A GObject.Object-layout wrapper class for an interface-typed value.

    GInterface classes are layout-free mixins (no PyGIGObject storage), so a
    returned object whose static type is an interface can't be allocated through
    the interface class directly. Wrap it with a synthesized
    ``(GObject.Object, iface)`` class instead: it has the C layout from
    GObject.Object and the interface's methods via the iface mixin. Cached per
    interface class.
    """
    key = id(iface_cls)
    impl = _interface_impl_cache.get(key)
    if impl is None:
        impl = GObjectMeta(
            iface_cls.__name__,
            (GObject, iface_cls),
            {
                "gimeta": iface_cls.gimeta,
                "_class_struct_name": None,
                "__module__": iface_cls.__module__,
            },
        )
        _interface_impl_cache[key] = impl
    return cast("type", impl)


def wrap_object_from_c(ptr: int, gtype: int, context: object | None = None) -> GObject:
    profile = context._profile if isinstance(context, _HasProfile) else abi.NATIVE
    cached = _cached_class_for_gtype(profile.name, gtype)
    if cached is None:
        cached = _cached_python_defined_class_for_gtype(gtype)
    if cached is not None:
        if issubclass(cached, GObject):
            return cast("GObject", wrap_existing_pointer_for_class(cached, ptr))
        if issubclass(cached, GInterface):
            impl = _concrete_impl_for_interface(cached)
            return cast("GObject", wrap_existing_pointer_for_class(impl, ptr))
        return cast("GObject", cast("Any", cached)._from_gobject_pointer(ptr))
    data = private.GIMeta.info_by_gtype(gtype).object_info()
    namespace = sys.modules["ginext"]._load_namespace(
        data["namespace"],
        data["version"],
        profile=profile,
    )
    cls = getattr(namespace, data["name"])
    if issubclass(cls, GObject):
        return cast("GObject", wrap_existing_pointer_for_class(cls, ptr))
    if issubclass(cls, GInterface):
        impl = _concrete_impl_for_interface(cls)
        return cast("GObject", wrap_existing_pointer_for_class(impl, ptr))
    return cast("GObject", cls._from_gobject_pointer(ptr))


def wrap_preallocated_object_from_c(
    ptr: int, gtype: int, context: object | None = None
) -> GObject:
    profile = context._profile if isinstance(context, _HasProfile) else abi.NATIVE
    cached = _cached_class_for_gtype(profile.name, gtype)
    if cached is None:
        cached = _cached_python_defined_class_for_gtype(gtype)
    if cached is not None:
        if issubclass(cached, GObject):
            gimeta = own_gimeta(cached)
            if gimeta is not None and getattr(gimeta, "gi_info", None) is None:
                return _wrap_preallocated_construction(cached, ptr)
            return wrap_existing_pointer_for_class(cached, ptr, owns_ref=False)
        if issubclass(cached, GInterface):
            impl = _concrete_impl_for_interface(cached)
            return cast(
                "GObject", wrap_existing_pointer_for_class(impl, ptr, owns_ref=False)
            )
        return cast("GObject", cast("Any", cached)._from_gobject_pointer(ptr))
    data = private.GIMeta.info_by_gtype(gtype).object_info()
    namespace = sys.modules["ginext"]._load_namespace(
        data["namespace"],
        data["version"],
        profile=profile,
    )
    cls = getattr(namespace, data["name"])
    if issubclass(cls, GObject):
        return wrap_existing_pointer_for_class(
            cast("type[GObject]", cls), ptr, owns_ref=False
        )
    if issubclass(cls, GInterface):
        impl = _concrete_impl_for_interface(cls)
        return cast(
            "GObject", wrap_existing_pointer_for_class(impl, ptr, owns_ref=False)
        )
    return cast("GObject", cls._from_gobject_pointer(ptr))


def register_class_for_gtype(cls: type) -> None:
    gimeta = own_gimeta(cls)
    gtype = int(gimeta.gtype) if gimeta is not None else 0
    if gtype:
        profile = gimeta.profile if gimeta is not None else abi.NATIVE
        _classes_by_gtype[(profile.name, gtype)] = cls


def _cached_class_for_gtype(profile_name: str, gtype: int) -> type[Any] | None:
    # Profile-exact only. An introspected class differs per profile (native vs
    # pygobject-compat overlays), so a wrap requested in one profile must NOT
    # reuse another profile's class — doing so returns a wrong-profile wrapper
    # that fails isinstance against the requested profile's class. On a miss the
    # callers build the profile-correct class (and cache it), so missing here is
    # cheap and correct.
    return _classes_by_gtype.get((profile_name, gtype))


def _cached_python_defined_class_for_gtype(gtype: int) -> type[Any] | None:
    matches = [
        cls
        for (_registered_profile, registered_gtype), cls in _classes_by_gtype.items()
        if registered_gtype == gtype
        and (gimeta := own_gimeta(cls)) is not None
        and getattr(gimeta, "gi_info", None) is None
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _prune_redundant_bases(bases: list[type]) -> list[type]:
    pruned: list[type] = []
    for index, base in enumerate(bases):
        if any(
            other is not base and issubclass(other, base)
            for other in bases[index + 1 :]
        ):
            continue
        pruned.append(base)
    return pruned


def reset_for_test() -> None:
    pass


def _class_has_method(cls: type, name: str) -> bool:
    for base in cls.__mro__:
        if name in base.__dict__:
            return True
        gimeta = own_gimeta(base)
        if name in getattr(gimeta, "method_infos", {}):
            return True
    return False


def _method_from_bases(bases: tuple[type, ...], name: str) -> object | None:
    for base in bases:
        for owner in base.__mro__:
            gimeta = own_gimeta(owner)
            method_infos = getattr(gimeta, "method_infos", {})
            method_entry = method_infos.get(name)
            if method_entry is None:
                continue
            method_info, has_self = method_entry
            try:
                return make_method(
                    gimeta.namespace.load_namespace(),
                    gimeta.method_owner_name,
                    method_info,
                    has_self=has_self,
                )
            except NotImplementedError:
                pass
    return None


def _maybe_async_callable(
    owner: type,
    gimeta: Any,
    name: str,
    async_method: Callable[..., Any],
    method_info: CallableInfo,
    has_self: bool,
) -> object | None:
    """Wrap a GIR ``*_async`` method as an :class:`ginext.aio.AsyncCallable`.

    Returns ``None`` for non-async methods, or when the paired ``*_finish``
    method cannot be built — callers fall back to the plain method.
    """
    async_info = private.callable_async_info(method_info)
    if async_info is None:
        return None
    finish_name, cb_position = async_info
    method_infos = getattr(gimeta, "method_infos", {})
    # The typelib may not record the finish function (e.g. GdkPixbuf); fall
    # back to the *_async -> *_finish naming convention. Variants often share
    # one finish (new_from_stream_at_scale_async -> new_from_stream_finish), so
    # accept the longest *_finish whose stem is a prefix of the async base.
    if not finish_name:
        if not name.endswith("_async"):
            return None
        base = name[: -len("_async")]
        if f"{base}_finish" in method_infos:
            finish_name = f"{base}_finish"
        else:
            best = ""
            for key in method_infos:
                if not key.endswith("_finish"):
                    continue
                stem = key[: -len("_finish")]
                if (base == stem or base.startswith(f"{stem}_")) and len(stem) > len(
                    best
                ):
                    finish_name, best = key, stem
            if not finish_name:
                return None
    finish_entry = method_infos.get(finish_name)
    if finish_entry is None:
        return None
    finish_info, finish_has_self = finish_entry
    try:
        finish_method = make_method(
            gimeta.namespace.load_namespace(),
            gimeta.method_owner_name,
            finish_info,
            has_self=finish_has_self,
        )
    except NotImplementedError:
        return None
    ns_name = gimeta.namespace.name
    result_names = async_result_names_for(ns_name, owner.__name__, name)
    if result_names is not None:
        real_finish = finish_method

        def _wrapped_finish(*args: object, **kwargs: object) -> object:
            result = real_finish(*args, **kwargs)
            items = result if isinstance(result, tuple) else (result,)
            return NamedReturn(items, result_names)

        finish_method = _wrapped_finish

    return AsyncCallable(
        async_method,
        finish_method,
        cb_position,
        has_self=has_self,
        owner_repr=f"{owner.__module__}.{owner.__name__}.{name}",
    )


def install_method_for_class(cls: type, name: str) -> tuple[object, bool] | None:
    for owner in cls.__mro__:
        gimeta = own_gimeta(owner)
        if not hasattr(gimeta, "gi_info"):
            continue
        method_infos = getattr(gimeta, "method_infos", {})
        if not method_infos:
            continue
        method_entry = method_infos.get(name)
        if method_entry is None:
            continue
        method_info, has_self = method_entry
        try:
            method = make_method(
                gimeta.namespace.load_namespace(),
                gimeta.method_owner_name,
                method_info,
                has_self=has_self,
            )
        except NotImplementedError:
            method_infos.pop(name, None)
            return None
        async_wrapped = _maybe_async_callable(
            owner, gimeta, name, method, method_info, has_self
        )
        if async_wrapped is not None:
            attach_owner_metadata(async_wrapped, owner)
            setattr(owner, name, async_wrapped)
            return async_wrapped, has_self
        attach_owner_metadata(method, owner)
        setattr(owner, name, method if has_self else staticmethod(method))
        return method, has_self
    # For user-defined GObject subclasses that inherit only from the Python root
    # GObject (which has no method_infos), fall back to the typelib GObject.Object.
    if issubclass(cls, GObject):
        found = _install_gobject_typelib_method(name)
        if found is not None:
            return found
    struct_found = install_class_struct_method_for_class(cls, name)
    if struct_found is not None:
        return struct_found, True
    return None


def _install_gobject_typelib_method(name: str) -> tuple[object, bool] | None:
    _ginext = sys.modules.get("ginext")
    if _ginext is None:
        return None
    try:
        obj_cls = _ginext.GObject.Object
    except AttributeError:
        return None
    if not isinstance(obj_cls, type):
        return None
    gimeta = own_gimeta(obj_cls)
    if gimeta is None:
        return None
    method_entry = gimeta.method_infos.get(name)
    if method_entry is None:
        return None
    method_info, has_self = method_entry
    try:
        method = make_method(
            gimeta.namespace.load_namespace(),
            gimeta.method_owner_name,
            method_info,
            has_self=has_self,
        )
    except NotImplementedError:
        return None
    attach_owner_metadata(method, GObject)
    setattr(GObject, name, method if has_self else staticmethod(method))
    return method, has_self


def install_class_struct_method_for_class(cls: type, name: str) -> object | None:
    for owner in cls.__mro__:
        if not isinstance(owner, GObjectMeta):
            continue
        struct_name = owner._class_struct_name
        if not isinstance(struct_name, str):
            continue
        owner_gimeta = own_gimeta(owner)
        if owner_gimeta is None:
            continue
        context = owner_gimeta.namespace
        if context is None:
            continue
        namespace = context.load_namespace()
        try:
            struct_cls = getattr(namespace, struct_name)
        except AttributeError:
            struct_cls = None
        if not isinstance(struct_cls, type):
            continue
        struct_gimeta = own_gimeta(struct_cls)
        if struct_gimeta is None:
            continue
        method_entry = struct_gimeta.method_infos.get(name)
        if method_entry is None:
            continue
        method_info, has_self = method_entry
        if not has_self:
            continue
        assert namespace is not None
        assert struct_cls is not None
        assert isinstance(struct_cls, type)
        method = make_method(
            namespace,
            f"{namespace.__name__}.{struct_name}",
            method_info,
            has_self=True,
        )

        def class_method(
            inner_cls: type,
            /,
            *args: object,
            _method: Callable[..., Any] = method,
            _struct_cls: type = struct_cls,
            **kwargs: object,
        ) -> object:
            self_obj = private.class_struct_wrapper(inner_cls, _struct_cls)
            try:
                return _method(self_obj, *args, **kwargs)
            finally:
                del self_obj

        class_method.__name__ = name
        class_method.__qualname__ = f"{cls.__qualname__}.{name}"
        setattr(cls, name, classmethod(class_method))
        return cast("object", getattr(cls, name))
    return None


def method_for_instance(obj: object, name: str) -> object | None:
    found = install_method_for_class(type(obj), name)
    if found is None:
        return None
    method, has_self = found
    if not has_self:
        return method
    descriptor_get = getattr(type(method), "__get__", None)
    if descriptor_get is not None:
        try:
            bound = descriptor_get(method, obj, type(obj))
        except AttributeError, TypeError, SystemError:
            bound = None
        if bound is not None:
            return cast("object", bound)
    return types.MethodType(cast("Any", method), obj)
