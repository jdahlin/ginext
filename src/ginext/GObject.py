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

import ginext

from . import defaults


def _namespace() -> object:
    return ginext._load_namespace(
        "GObject",
        defaults.resolve_version("GObject") or "2.0",
        _module_name_override=f"{__name__}._namespace",
    )


def __getattr__(name: str) -> object:
    return getattr(_namespace(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_namespace())))
