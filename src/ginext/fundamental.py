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

"""Python-side companion to the C PyGIFundamental type.

The actual base class for all fundamental (non-GObject GTypeInstance) wrappers
is ``private.Fundamental`` — a ``PyTypeObject`` defined in Fundamental.c.  This
module contributes:

* ``FundamentalMeta`` — a Python metaclass used for all Python subclasses of
  ``private.Fundamental`` so that class-level attribute misses trigger lazy
  method installation from the GIR (same pattern as GObjectMeta).
* ``_init_hooks`` — called once at import time to register the Python
  ``__getattr__`` callback into the C type.
"""

from __future__ import annotations

import sys
from typing import Any

from . import private

# Re-export the C base type under its traditional name so that
# ``from ginext.fundamental import Fundamental`` still works in classbuild.py.
Fundamental = private.Fundamental


class FundamentalMeta(type):
    """Metaclass for Python subclasses of ``private.Fundamental``.

    Handles class-level attribute misses by delegating to
    ``classbuild.install_method_for_class``, which lazily installs GIR-derived
    methods on the class and caches them so subsequent accesses are O(1).
    """

    __prepare__ = type.__prepare__  # type: ignore[assignment]

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


def _fundamental_getattr(self: Any, name: str) -> Any:
    """Instance __getattr__ registered into the C type at bootstrap.

    Called by ``Fundamental_getattro`` after field access fails, to perform
    lazy method installation and return a bound method.
    """
    method = sys.modules["ginext.classbuild"].method_for_instance(self, name)
    if method is not None:
        return method
    raise AttributeError(name)


def _init_hooks() -> None:
    """Register Python callbacks into the C PyGIFundamental_Type.

    Must be called once, early in the ginext import sequence, before any
    fundamental wrapper is created.
    """
    private.fundamental_init_hooks(_fundamental_getattr)


_init_hooks()
