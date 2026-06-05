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

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .namespace import Namespace


@dataclass(frozen=True)
class ABIProfile:
    name: str
    module_prefix: str
    pygobject_compat: bool = False

    def module_name(self, namespace: str) -> str:
        return f"{self.module_prefix}{namespace}"


NATIVE = ABIProfile("native", "")
PYGOBJECT = ABIProfile("pygobject", "gi.repository.", pygobject_compat=True)


@dataclass(frozen=True)
class NamespaceContext:
    """Immutable identity of a loaded namespace: ``(name, version, profile)``.

    Builders and built-class ``gimeta`` carry this instead of a live
    :class:`~ginext.namespace.Namespace`, which breaks the ``Namespace`` ↔
    built-class reference cycle. A namespace is a cached singleton keyed by
    exactly this triple, so the live object is recoverable on demand via
    :meth:`load_namespace` — callers that only need identity/config never have to.
    """

    name: str
    version: str
    profile: ABIProfile

    def module_name(self) -> str:
        return self.profile.module_name(self.name)

    def qualified_name(self, member: str) -> str:
        return f"{self.name}.{member}"

    def load_namespace(self) -> Namespace:
        """Recover the cached live namespace for this context.

        This is the ordinary ``sys.modules`` lookup `_load_namespace` performs
        everywhere — a namespace is a singleton keyed by ``(name, version,
        profile)`` — not a fresh import; it only constructs on a cache miss.
        """
        ns = sys.modules["ginext"]._load_namespace(
            self.name, self.version, profile=self.profile
        )
        return cast("Namespace", ns)
