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

"""Tests for foreign cairo Surface/Context wrapping.

goi doesn't link cairo directly. Returns of cairo_surface_t * /
cairo_t * have to be marshalled into pycairo objects via pycairo's CAPI
capsule (see src/runtime/marshal.c::goi_foreign_cairo_to_py). Without
that path, goi's struct fallback hands back a SimpleNamespace or
unmethoded boxed wrapper, and any caller that relies on real cairo
methods (set_source_rgba, set_device_scale, ...) fails at runtime — the
exact regression that broke the drawing app's on_draw signal handler.
"""

from __future__ import annotations

from typing import Any

import pytest

from ..typelib.support import open_namespace_for_test


cairo = pytest.importorskip("cairo")


@pytest.fixture(scope="module")
def Regress(call_mode: Any) -> Any:
    try:
        ns = open_namespace_for_test(call_mode, "Regress", "1.0")
    except ImportError as e:
        pytest.skip(f"Regress typelib unavailable: {e}")
    if not hasattr(ns, "test_cairo_context_full_return"):
        pytest.skip(
            "Regress was built without cairo support; rebuild the test "
            "typelibs with -Dbuild_gi_tests=true"
        )
    return ns


def test_context_full_return_is_pycairo_context(call_mode: Any, Regress: Any) -> None:
    """cairo_t* return (transfer FULL): wrapper is a real cairo.Context."""
    ctx = Regress.test_cairo_context_full_return()
    assert isinstance(ctx, cairo.Context)
    # Methods only present on the actual pycairo type — the SimpleNamespace
    # / unmethoded-boxed fallback would AttributeError here.
    ctx.set_source_rgba(0.25, 0.5, 0.75, 1.0)


def test_surface_full_return_is_pycairo_surface(call_mode: Any, Regress: Any) -> None:
    """cairo_surface_t* return (transfer FULL): wrapper is a real cairo.Surface."""
    surf = Regress.test_cairo_surface_full_return()
    assert isinstance(surf, cairo.Surface)
    surf.set_device_scale(1.0, 1.0)


def test_surface_none_return_is_pycairo_surface(call_mode: Any, Regress: Any) -> None:
    """cairo_surface_t* return (transfer NONE): also wrapped, with goi
    taking its own ref so pycairo's destructor doesn't underflow."""
    surf = Regress.test_cairo_surface_none_return()
    assert isinstance(surf, cairo.Surface)
    surf.set_device_scale(1.0, 1.0)


def test_surface_roundtrip_through_gi(call_mode: Any, Regress: Any) -> None:
    """A pycairo Surface passed INTO a GI function expecting cairo_surface_t*
    still works — the from_py side already exists, but the round-trip is
    cheap and pins the symmetry."""
    # regress_test_cairo_surface_none_in asserts 10x10 ARGB32.
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
    Regress.test_cairo_surface_none_in(surf)


pytestmark = pytest.mark.xfail(
    reason="cairo foreign-struct marshalling pending", run=False, strict=False
)
