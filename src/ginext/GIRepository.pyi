# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Type stubs for the ``ginext.GIRepository`` namespace (internal C view).

ginext's ``GIRepository`` namespace does NOT expose the upstream
GIRepository-3.0 typelib API. It exposes ginext's own C-implemented
introspection wrapper types (``src/ginext/private/GIRepository/*.c``),
registered as namespace constants by the GIRepository overlay
(``_overlays/GIRepository.py``). Those wrappers deliberately present a
Pythonic surface (e.g. ``EnumInfo.members``, ``RegisteredTypeInfo.gtype``,
``ObjectInfo.object_info()``) rather than the raw ``gi_*`` getters.

This stub re-exports those C types from ``ginext.private._gobject`` so
``from ginext.GIRepository import EnumInfo`` type-checks against the real
runtime types instead of resolving to ``Any``. The end-user (introspectable)
view ships separately as ``ginext-stubs``.
"""

from ginext.overlay.registrar import OverlayRegistrar
from ginext.private._gobject import (
    ArgInfo as ArgInfo,
    BaseInfo as BaseInfo,
    CallableInfo as CallableInfo,
    CallbackInfo as CallbackInfo,
    ConstantInfo as ConstantInfo,
    EnumInfo as EnumInfo,
    FieldInfo as FieldInfo,
    FlagsInfo as FlagsInfo,
    FunctionInfo as FunctionInfo,
    InterfaceInfo as InterfaceInfo,
    ObjectInfo as ObjectInfo,
    PropertyInfo as PropertyInfo,
    RegisteredTypeInfo as RegisteredTypeInfo,
    SignalInfo as SignalInfo,
    StructInfo as StructInfo,
    TypeInfo as TypeInfo,
    UnionInfo as UnionInfo,
    UnresolvedInfo as UnresolvedInfo,
    VFuncInfo as VFuncInfo,
    ValueInfo as ValueInfo,
)

# Like every ginext namespace, GIRepository carries the overlay registrar.
overlay: OverlayRegistrar
