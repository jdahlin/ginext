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

The runtime metaclass is the C metatype ``private.GObjectMeta`` (built in
``ObjectMeta.c``). Its two slots delegate to the Python bodies below, registered
here at import:

- ``tp_getattro`` → `_gobjectmeta_getattr`: class-level attribute access. Normal
  lookup happens first (in C); only a genuine miss falls here, where an
  introspected method is built and cached on the class. Instance access goes
  through ``GObject.Object``'s own ``tp_getattro``, not the metaclass.
- ``__dir__`` → `_gobjectmeta_dir`.

The ``@dataclass_transform`` view (so ``class Foo(GObject.Object)`` type-checks
like a dataclass) lives in the ``TYPE_CHECKING`` stub.
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING

from .. import features, private
from .gtype import compat_gtype_from_raw
from .resolve import classbuild_module, own_gimeta


def _is_root_gobject_class(cls: type) -> bool:
    return "_gobject_is_root" in cls.__dict__


def _gobjectmeta_getattr(cls: "GObjectMeta", name: str) -> object:
    """Class-level __getattr__: lazily build+install an introspected method on
    first access (the metatype's tp_getattro calls this on a lookup miss)."""
    if name == "__gtype__" and features.is_enabled(features.PYGOBJECT_COMPAT):
        gimeta = own_gimeta(cls)
        if gimeta is not None:
            type_name = gimeta.type_name
            return compat_gtype_from_raw(int(gimeta.gtype), type_name)
    if name == "Signal" and _is_root_gobject_class(cls):
        from ..signal.descriptor import SignalDescriptor
        return SignalDescriptor
    found = classbuild_module().install_method_for_class(cls, name)
    if found is not None:
        method, has_self = found
        return method if has_self else getattr(cls, name)
    raise AttributeError(name)


def _gobjectmeta_dir(cls: "GObjectMeta") -> list[str]:
    names = set(type.__dir__(cls))
    if not _is_root_gobject_class(cls):
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


GObjectMeta = private.GObjectMeta

private.register_hook("ObjectClass.getattr", _gobjectmeta_getattr)
private.register_hook("ObjectClass.dir", _gobjectmeta_dir)
