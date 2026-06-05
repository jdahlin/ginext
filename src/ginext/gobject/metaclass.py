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

"""`GObjectMeta` — the metaclass shared by every ginext GObject class.

Kept separate from `base` so the `@dataclass_transform` decoration and the
class-level attribute lookup (`Foo.method`, `dir(Foo)`) live apart from the
instance-level machinery on `GObject`. The metaclass references no GObject
symbol at runtime, so it stays below `base` in the import graph.
"""

from __future__ import annotations

import types
from typing import dataclass_transform

from .. import features, private
from .gtype import compat_gtype_from_raw
from .properties import Property
from .resolve import classbuild_module, own_gimeta


@dataclass_transform(field_specifiers=(Property,))
class GObjectMeta(type):
    """Metaclass for every ginext GObject class.

    The runtime work — registering a GType, populating signal tables,
    binding `GObject.Signal` descriptors — happens in
    `GObject.__init_subclass__`. This metaclass exists for the
    `@dataclass_transform` decoration, which tells type checkers that
    `class Foo(GObject)` with `Property` field specifiers behaves like
    a dataclass declaration.
    """

    gimeta: private.GIMeta

    @staticmethod
    def _is_root_gobject_class(cls: type) -> bool:
        return (
            cls.__module__ == "ginext.gobject.gobjectclass"
            and cls.__name__ == "GObject"
        )

    def __getattribute__(cls, name: str) -> object:
        if name == "Signal" and not GObjectMeta._is_root_gobject_class(cls):
            raise AttributeError(name)
        return super().__getattribute__(name)

    def __getattr__(cls, name: str) -> object:
        if name == "__gtype__" and features.is_enabled(features.PYGOBJECT_COMPAT):
            gimeta = own_gimeta(cls)
            if gimeta is not None:
                type_name = gimeta.type_name
                return compat_gtype_from_raw(int(gimeta.gtype), type_name)
        found = classbuild_module().install_method_for_class(cls, name)
        if found is not None:
            method, has_self = found
            return method if has_self else getattr(cls, name)
        raise AttributeError(name)

    def __dir__(cls) -> list[str]:
        names = set(type.__dir__(cls))
        if not GObjectMeta._is_root_gobject_class(cls):
            names.discard("Signal")
        for base in cls.__mro__:
            base_gimeta = own_gimeta(base)
            if base_gimeta is not None:
                names.update(base_gimeta.method_infos)
            if not isinstance(base, GObjectMeta):
                continue
            struct_name = base._class_struct_name
            if isinstance(struct_name, str):
                if base_gimeta is None:
                    continue
                context = base_gimeta.namespace
                if context is None:
                    continue
                namespace = context.load_namespace()
                try:
                    struct_cls = getattr(namespace, struct_name)
                except AttributeError:
                    struct_cls = None
                if struct_cls is None:
                    continue
                struct_gimeta = own_gimeta(struct_cls)
                if struct_gimeta is not None:
                    names.update(struct_gimeta.method_infos)
        attr = cls.__dict__.get("new")
        func = attr.__func__ if isinstance(attr, staticmethod | classmethod) else None
        func_name = func.__name__ if isinstance(func, types.FunctionType) else None
        if func_name == "_non_inherited_constructor" or (
            attr is None and "new" in cls.gimeta.method_infos
        ):
            names.discard("new")
        return sorted(names)
