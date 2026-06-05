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

from dataclasses import dataclass
from typing import Any

import ginext
from ginext import private


_introspection_modules: dict[str, object] = {}


@dataclass(frozen=True)
class RepositoryInfo:
    namespace: str
    name: str
    kind: str
    info: object

    def get_signals(self) -> tuple[object, ...]:
        return ()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.info, name)


class Repository:
    def find_by_name(self, namespace: str, name: str) -> RepositoryInfo | None:
        resolved = ginext.defaults.resolve_namespace_name(namespace)
        if resolved is None:
            return None
        namespace, version = resolved
        try:
            kind, info = private.namespace_find(namespace, version, name)
        except (AttributeError, ImportError, RuntimeError):
            return None
        return RepositoryInfo(namespace, name, kind, info)

    def is_registered(self, namespace: str, version: str | None = None) -> bool:
        raise NotImplementedError

    def require(
        self, namespace: str, version: str | None = None, flags: int = 0
    ) -> object:
        raise NotImplementedError

    def get_dependencies(self, namespace: str, version: str | None = None) -> list[str]:
        raise NotImplementedError

    def get_immediate_dependencies(
        self, namespace: str, version: str | None = None
    ) -> list[str]:
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


repository = Repository()


def get_introspection_module(namespace: str) -> Any:
    cached = _introspection_modules.get(namespace)
    if cached is not None:
        return cached
    from gi import repository as gi_repository

    module = getattr(gi_repository, namespace)
    _introspection_modules[namespace] = module
    return module
