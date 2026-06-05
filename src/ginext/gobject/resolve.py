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

"""Lazy resolution of runtime objects, kept out of the other gobject
submodules so they don't have to import each other (cycle avoidance)."""

from __future__ import annotations

import sys
import types
from typing import Any


# Returns the GIMeta or None; typed Any because callers duck-type the result
# (``own_gimeta(x).pspecs`` inside ``try/except AttributeError``) rather than
# None-checking — a precise ``GIMeta | None`` would force a union-attr cascade.
def own_gimeta(cls: type) -> Any:  # type: ignore[explicit-any]
    """The gimeta a class declares directly in its own __dict__, or None."""
    try:
        return cls.__dict__["gimeta"]
    except KeyError:
        return None


def ginext_root() -> types.ModuleType:
    return sys.modules["ginext"]


def gobject_repo() -> types.ModuleType:
    repo: types.ModuleType = ginext_root().GObject
    return repo


def classbuild_module() -> types.ModuleType:
    module = sys.modules.get("ginext.classbuild")
    if module is not None:
        return module
    from .. import classbuild

    return classbuild
