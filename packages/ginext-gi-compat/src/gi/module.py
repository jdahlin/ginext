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
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

from __future__ import annotations

from typing import Any


# Import everything from _gi (our C-shim layer) so callers can use either module.
from ._gi import (
    Repository,
)

_introspection_modules: dict[str, object] = {}

repository = Repository.get_default()


def get_introspection_module(namespace: str) -> Any:
    import sys

    cached = _introspection_modules.get(namespace)
    if cached is not None:
        return cached
    # Trigger namespace loading via the proxy (which populates sys.modules with
    # the raw namespace).  We then return the raw namespace, not the proxy, so
    # callers like gi.overrides.load_overrides() see the typelib values.
    from gi import repository as gi_repository

    getattr(gi_repository, namespace)
    raw = sys.modules.get(f"gi.repository.{namespace}")
    if raw is not None:
        _introspection_modules[namespace] = raw
        return raw
    # Fallback (should not normally happen)
    module = getattr(gi_repository, namespace)
    _introspection_modules[namespace] = module
    return module
