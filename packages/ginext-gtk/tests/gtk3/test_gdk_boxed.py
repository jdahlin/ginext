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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Gdk boxed-type overlays (RGBA constructor shapes, Gdk-3 selection atoms).

Relocated from the core boxed-resource tests: these exercise Gdk-specific boxed
types, so they belong in the Gtk/Gdk suite. The generic GResource boxed tests
stay in core.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.xdist_group("gtk3")


@pytest.fixture
def Gdk() -> Any:
    from ginext import Gdk as _Gdk

    return _Gdk


def test_gdk_rgba_overlay_constructor_kwargs(Gdk: Any) -> None:
    rgba = Gdk.RGBA(red=0.25, green=0.5, blue=0.75, alpha=1.0)
    assert isinstance(rgba, Gdk.RGBA)
    assert rgba.red == pytest.approx(0.25)
    assert rgba.green == pytest.approx(0.5)
    assert rgba.blue == pytest.approx(0.75)
    assert rgba.alpha == pytest.approx(1.0)


def test_gdk_rgba_overlay_constructor_positional(Gdk: Any) -> None:
    # PyGObject accepts positional (red, green, blue, alpha) here; quodlibet's
    # qltk/entry.py uses that shape, so ginext's overlay should accept it too.
    rgba = Gdk.RGBA(0.25, 0.5, 0.75, 1.0)
    assert rgba.red == pytest.approx(0.25)
    assert rgba.green == pytest.approx(0.5)
    assert rgba.blue == pytest.approx(0.75)
    assert rgba.alpha == pytest.approx(1.0)


def test_gdk_selection_clipboard_aliases_exist(Gdk: Any) -> None:
    if Gdk.__version__[0] != 3:
        pytest.skip("Gdk.Atom and SELECTION_* constants are Gdk-3-only")
    clipboard = Gdk.SELECTION_CLIPBOARD
    primary = Gdk.SELECTION_PRIMARY

    assert clipboard is not None
    assert primary is not None
    assert repr(clipboard) == repr(Gdk.atom_intern("CLIPBOARD", True))
    assert repr(primary) == repr(Gdk.atom_intern("PRIMARY", True))
