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

import sys
from typing import Any

from . import private


class FundamentalMeta(type):
    __prepare__ = type.__prepare__

    def __getattr__(cls, name: str) -> object:
        found = sys.modules["ginext.classbuild"].install_method_for_class(cls, name)
        if found is not None:
            method, has_self = found
            return method if has_self else getattr(cls, name)
        raise AttributeError(name)

    def __dir__(cls) -> list[str]:
        names = set(type.__dir__(cls))
        for base in cls.__mro__:
            gimeta = vars(base).get("gimeta")
            if gimeta is not None:
                names.update(gimeta.method_infos)
        return sorted(names)


class Fundamental(metaclass=FundamentalMeta):
    _pointer: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(f"{type(self).__name__} constructor is not available")

    @classmethod
    def _from_gobject_pointer(cls, ptr: int) -> "Fundamental":
        obj = object.__new__(cls)
        object.__setattr__(obj, "_pointer", ptr)
        return obj

    def __getattr__(self, name: str) -> Any:
        method = sys.modules["ginext.classbuild"].method_for_instance(self, name)
        if method is not None:
            return method
        raise AttributeError(name)

    def __del__(self) -> None:
        try:
            ptr = self._pointer
        except AttributeError:
            return
        if ptr is None or ptr == 0:
            return
        self._pointer = 0
        private.instantiatable_unref(ptr)
