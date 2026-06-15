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

from __future__ import annotations

from typing import SupportsIndex, cast

from . import private


class ResultTuple(tuple[object, ...]):
    _field_names: tuple[str | None, ...] = ()

    @classmethod
    def _new_type(cls, names: list[str | None]) -> "type[ResultTuple]":
        return cast(
            "type[ResultTuple]",
            type(
                "ResultTuple",
                (cls,),
                {"_field_names": tuple(names), "__module__": cls.__module__},
            ),
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

    def __reduce_ex__(self, protocol: SupportsIndex) -> tuple[object, ...]:
        return tuple, (tuple(self),)


private.register_hook("result_tuple_new_type", ResultTuple._new_type)
