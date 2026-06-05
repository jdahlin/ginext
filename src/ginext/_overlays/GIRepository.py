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

"""Overlay for the GIRepository namespace.

GIRepository types are static C extension types defined in ``_gobject``
(``GIRepository/Info.c``), not classes built from the GIRepository-3.0
typelib — loading from the typelib would be circular.  This overlay
registers them as namespace-level constants so ``ginext.GIRepository.BaseInfo``
etc. resolve correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ginext import GIRepository
from ginext.private import _gobject

if TYPE_CHECKING:
    from ..overlay import OverlayRegistrar

overlay: OverlayRegistrar = GIRepository.overlay

overlay.constant("BaseInfo", _gobject.BaseInfo)
overlay.constant("CallableInfo", _gobject.CallableInfo)
overlay.constant("FunctionInfo", _gobject.FunctionInfo)
overlay.constant("SignalInfo", _gobject.SignalInfo)
overlay.constant("VFuncInfo", _gobject.VFuncInfo)
overlay.constant("CallbackInfo", _gobject.CallbackInfo)
overlay.constant("RegisteredTypeInfo", _gobject.RegisteredTypeInfo)
overlay.constant("ObjectInfo", _gobject.ObjectInfo)
overlay.constant("InterfaceInfo", _gobject.InterfaceInfo)
overlay.constant("StructInfo", _gobject.StructInfo)
overlay.constant("UnionInfo", _gobject.UnionInfo)
overlay.constant("EnumInfo", _gobject.EnumInfo)
overlay.constant("FlagsInfo", _gobject.FlagsInfo)
overlay.constant("ConstantInfo", _gobject.ConstantInfo)
overlay.constant("PropertyInfo", _gobject.PropertyInfo)
overlay.constant("ArgInfo", _gobject.ArgInfo)
overlay.constant("FieldInfo", _gobject.FieldInfo)
overlay.constant("TypeInfo", _gobject.TypeInfo)
overlay.constant("ValueInfo", _gobject.ValueInfo)
overlay.constant("UnresolvedInfo", _gobject.UnresolvedInfo)
