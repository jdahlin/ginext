# Copyright 2026 Johan Dahlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from __future__ import annotations

from ._gi import CallableInfo
from ._gi import FunctionInfo
from ._gi import ObjectInfo
from ._gi import StructInfo
from ._gi import VFuncInfo


__all__ = [
    "CallableInfo",
    "FunctionInfo",
    "ObjectInfo",
    "StructInfo",
    "VFuncInfo",
]
