# Copyright (C) 2005-2009 Johan Dahlin <johan@gnome.org>
#
#   types.py: base types for introspected items.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# Adapted from pygobject for use with ginext.

from __future__ import annotations

import re
import warnings

from ._constants import TYPE_INVALID
from ._gi import (
    InterfaceInfo,
    ObjectInfo,
    StructInfo,
    VFuncInfo,
    register_interface_info,
    hook_up_vfunc_implementation,
    GInterface,
    PyGIWarning,
)
from . import _gi

# Keep StructInfo and GInterface accessible for re-export
StructInfo, GInterface

from . import _propertyhelper as propertyhelper
from . import _signalhelper as signalhelper


def snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class MetaClassHelper:
    def _setup_methods(cls):
        for method_info in cls.__info__.get_methods():
            name = method_info.__name__
            if method_info.is_constructor():
                method_info = classmethod(method_info)
            elif not method_info.is_method():
                method_info = staticmethod(method_info)
            setattr(cls, name, method_info)

    def _setup_class_methods(cls):
        info = cls.__info__
        class_struct = info.get_class_struct()
        if class_struct is None:
            return
        for method_info in class_struct.get_methods():
            name = method_info.__name__
            if not hasattr(cls, name):
                setattr(cls, name, classmethod(method_info))

    def _setup_fields(cls):
        for field_info in cls.__info__.get_fields():
            name = field_info.get_name().replace("-", "_")
            setattr(cls, name, property(field_info.get_value, field_info.set_value))

    def _setup_constants(cls):
        for constant_info in cls.__info__.get_constants():
            name = constant_info.get_name()
            value = constant_info.get_value()
            setattr(cls, name, value)

    def _setup_vfuncs(cls):
        for vfunc_name, py_vfunc in cls.__dict__.items():
            if not vfunc_name.startswith("do_") or not callable(py_vfunc):
                continue

            skip_ambiguity_check = False

            vfunc_info = None
            for base in cls.__mro__:
                method = getattr(base, vfunc_name, None)
                method = getattr(method, "__func__", method)
                if method is not None and isinstance(method, VFuncInfo):
                    vfunc_info = method
                    break

                if not hasattr(base, "__info__") or not hasattr(
                    base.__info__, "get_vfuncs"
                ):
                    continue

                base_name = snake_case(base.__info__.get_type_name())

                for v in base.__info__.get_vfuncs():
                    if vfunc_name == f"do_{base_name}_{v.get_name()}":
                        vfunc_info = v
                        skip_ambiguity_check = True
                        break

                if vfunc_info:
                    break

            if vfunc_info is None:
                vfunc_info = find_vfunc_info_in_interface(
                    cls.__bases__, vfunc_name[len("do_"):]
                )

            if vfunc_info is not None:
                if not skip_ambiguity_check:
                    ambiguous_base = find_vfunc_conflict_in_bases(
                        vfunc_info, cls.__bases__
                    )
                    if ambiguous_base is not None:
                        base_info = vfunc_info.get_container()
                        raise TypeError(
                            f"Method {vfunc_name}() on class {cls.__info__.get_namespace()}.{cls.__info__.get_name()} is ambiguous "
                            f"with methods in base classes {base_info.get_namespace()}.{base_info.get_name()} and {ambiguous_base.__info__.get_namespace()}.{ambiguous_base.__info__.get_name()}"
                        )
                hook_up_vfunc_implementation(vfunc_info, cls.__gtype__, py_vfunc)

    def _setup_native_vfuncs(cls):
        class_info = cls.__dict__.get("__info__")
        if class_info is None or not isinstance(class_info, ObjectInfo):
            return

        if cls.__module__ == "gi.repository.GObject" and cls.__name__ == "Object":
            return

        for vfunc_info in class_info.get_vfuncs():
            name = f"do_{vfunc_info.__name__}"
            setattr(cls, name, vfunc_info)


def find_vfunc_info_in_interface(bases, vfunc_name):
    for base in bases:
        if (
            base is GInterface
            or not issubclass(base, GInterface)
            or not hasattr(base, "__info__")
        ):
            continue

        if isinstance(base.__info__, InterfaceInfo):
            for vfunc in base.__info__.get_vfuncs():
                if vfunc.get_name() == vfunc_name:
                    return vfunc

        vfunc = find_vfunc_info_in_interface(base.__bases__, vfunc_name)
        if vfunc is not None:
            return vfunc

    return None


def find_vfunc_conflict_in_bases(vfunc, bases):
    for klass in bases:
        if not hasattr(klass, "__info__") or not hasattr(klass.__info__, "get_vfuncs"):
            continue
        vfuncs = klass.__info__.get_vfuncs()
        vfunc_name = vfunc.get_name()
        for v in vfuncs:
            if v.get_name() == vfunc_name and v != vfunc:
                return klass

        aklass = find_vfunc_conflict_in_bases(vfunc, klass.__bases__)
        if aklass is not None:
            return aklass
    return None


class _GObjectMetaBase(type):
    """Metaclass for automatically registering GObject classes."""

    def __new__(cls, name, bases, namespace, **kwargs):
        if "__slots__" in namespace:
            warnings.warn(
                f"GObject derived class {name} shouldn't use __slots__.",
                PyGIWarning,
                stacklevel=2,
            )
            del namespace["__slots__"]

        return super().__new__(cls, name, bases, namespace, **kwargs)

    def __init__(cls, name, bases, dict_):
        type.__init__(cls, name, bases, dict_)
        propertyhelper.install_properties(cls)
        signalhelper.install_signals(cls)
        cls._type_register(cls.__dict__)

    def _type_register(cls, namespace):
        if "__gtype__" in namespace:
            return

        if cls.__module__.startswith("gi.overrides."):
            return

        _gi.type_register(cls, namespace.get("__gtype_name__"))


_gi._install_metaclass(_GObjectMetaBase)


class GObjectMeta(_GObjectMetaBase, MetaClassHelper):
    """Meta class used for GI GObject based types."""

    def __init__(cls, name, bases, dict_):
        super().__init__(name, bases, dict_)
        is_gi_defined = False
        info = cls.__dict__.get("__info__")
        if info is not None and hasattr(info, "get_namespace"):
            if cls.__module__ == "gi.repository." + info.get_namespace():
                is_gi_defined = True

        is_python_defined = False
        if not is_gi_defined and cls.__module__ != GObjectMeta.__module__:
            is_python_defined = True

        if is_python_defined:
            if info is not None:
                cls._setup_vfuncs()
        elif is_gi_defined:
            if isinstance(info, ObjectInfo):
                cls._setup_class_methods()
            cls._setup_methods()
            cls._setup_constants()
            if info is not None:
                cls._setup_native_vfuncs()

            if isinstance(info, ObjectInfo):
                cls._setup_fields()
            elif isinstance(info, InterfaceInfo):
                register_interface_info(info.get_g_type())

    def mro(cls):
        return mro(cls)

    @property
    def __doc__(cls):
        if cls == GObjectMeta:
            return ""

        doc = cls.__dict__.get("__doc__", None)
        if doc is not None:
            return doc

        try:
            from .docstring import generate_doc_string
            if cls.__module__.startswith(("gi.repository.", "gi.overrides")):
                return generate_doc_string(cls.__info__)
        except (AttributeError, ImportError):
            pass

        return None


def mro(C):
    """Compute the class precedence list (mro) according to C3, with GObject
    interface considerations.
    """
    bases = []
    bases_of_subclasses = [[C]]

    if C.__bases__:
        for base in C.__bases__:
            bases_of_subclasses += [list(base.__mro__)]
        bases_of_subclasses += [list(C.__bases__)]

    while bases_of_subclasses:
        for subclass_bases in bases_of_subclasses:
            candidate = subclass_bases[0]
            not_head = [s for s in bases_of_subclasses if candidate in s[1:]]
            if not_head and GInterface not in candidate.__bases__:
                candidate = None
            else:
                break

        if candidate is None:
            raise TypeError("Cannot create a consistent method resolution order (MRO)")

        bases.append(candidate)

        for subclass_bases in bases_of_subclasses[:]:
            if subclass_bases and subclass_bases[0] == candidate:
                del subclass_bases[0]
                if not subclass_bases:
                    bases_of_subclasses.remove(subclass_bases)

    return bases


def nothing(*args, **kwargs):
    pass


class StructMeta(type, MetaClassHelper):
    """Meta class used for GI Struct based types."""

    def __init__(cls, name, bases, dict_):
        super().__init__(name, bases, dict_)

        g_type = cls.__info__.get_g_type()
        if g_type != TYPE_INVALID and g_type.pytype is not None:
            return

        cls._setup_fields()
        cls._setup_methods()

        for method_info in cls.__info__.get_methods():
            if (
                method_info.is_constructor()
                and method_info.__name__ == "new"
                and (not method_info.get_arguments() or cls.__info__.get_size() == 0)
            ):
                cls.__new__ = staticmethod(method_info)
                cls.__init__ = nothing
                break

    @property
    def __doc__(cls):
        if cls == StructMeta:
            return ""
        try:
            from .docstring import generate_doc_string
            return generate_doc_string(cls.__info__)
        except (AttributeError, ImportError):
            return None


__all__ = [
    "GObjectMeta",
    "StructMeta",
    "MetaClassHelper",
    "find_vfunc_info_in_interface",
    "find_vfunc_conflict_in_bases",
    "mro",
    "nothing",
    "snake_case",
]
