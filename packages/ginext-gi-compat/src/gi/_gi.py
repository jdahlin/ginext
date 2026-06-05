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
from enum import IntEnum
from typing import Any, SupportsIndex

from ginext import GObject as _GObject_namespace
from ginext.gobject.gobjectclass import GObject


class CallableInfo:
    pass


class FunctionInfo(CallableInfo):
    pass


class VFuncInfo(CallableInfo):
    pass


class ObjectInfo:
    pass


class StructInfo:
    pass


class Direction(IntEnum):
    IN = 0
    OUT = 1
    INOUT = 2


class TypeTag(IntEnum):
    VOID = 0
    BOOLEAN = 1
    INT8 = 2
    UINT8 = 3
    INT16 = 4
    UINT16 = 5
    INT32 = 6
    UINT32 = 7
    INT64 = 8
    UINT64 = 9
    FLOAT = 10
    DOUBLE = 11
    GTYPE = 12
    UTF8 = 13
    FILENAME = 14
    ARRAY = 15
    INTERFACE = 16
    GLIST = 17
    GSLIST = 18
    GHASH = 19
    ERROR = 20
    UNICHAR = 21


class ResultTuple(tuple):
    _field_names: tuple[str | None, ...] = ()

    @classmethod
    def _new_type(cls, names: list[str | None]) -> type["ResultTuple"]:
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


SIGNAL_RUN_FIRST = _GObject_namespace.SignalFlags.RUN_FIRST


def enum_add(module: ModuleType, name: str, gtype: object, info: object) -> type:
    if not isinstance(module, ModuleType):
        raise TypeError("first argument must be a module")
    raise NotImplementedError("enum registration is provided by the repository loader")


def flags_add(module: ModuleType, name: str, gtype: object, info: object) -> type:
    if not isinstance(module, ModuleType):
        raise TypeError("first argument must be a module")
    raise NotImplementedError("flags registration is provided by the repository loader")


def variant_type_from_string(type_string: str):
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
    "GObject",
    "CallableInfo",
    "Direction",
    "FunctionInfo",
    "ObjectInfo",
    "ResultTuple",
    "SIGNAL_RUN_FIRST",
    "StructInfo",
    "TypeTag",
    "VFuncInfo",
    "Warning",
    "enum_add",
    "flags_add",
    "variant_type_from_string",
    "pyos_getsig",
    "pyos_setsig",
]
