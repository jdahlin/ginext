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

import importlib

import pytest


def test_from_ginext_import_cairo_aliases_pycairo() -> None:
    pycairo = pytest.importorskip("cairo")

    import ginext
    from ginext import cairo as ginext_cairo

    assert ginext_cairo is pycairo
    assert ginext.cairo is pycairo


def test_import_ginext_cairo_returns_pycairo_module() -> None:
    pycairo = pytest.importorskip("cairo")

    assert importlib.import_module("ginext.cairo") is pycairo
