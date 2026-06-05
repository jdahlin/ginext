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

"""Lazy shim to the canonical pycairo module."""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("cairo")
_parent_name, _, _child_name = __name__.rpartition(".")
if _parent_name:
    _parent = sys.modules.get(_parent_name)
    if _parent is not None:
        setattr(_parent, _child_name, _module)
sys.modules[__name__] = _module
