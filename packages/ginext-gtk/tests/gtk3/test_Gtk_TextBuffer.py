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

"""Gtk.TextBuffer.get_iter_at_line return shape.

The GIR signature is:

    gtk_text_buffer_get_iter_at_line(buffer, &out_iter, line_number) -> gboolean

The first param is out, the return is gboolean. PyGObject collapses
this to: returns `(bool, Gtk.TextIter)` — a 2-tuple.

In goi the shape isn't stable: some call paths give back a bare
Gtk.TextIter, others a `(bool, iter)` tuple. Callers end up writing:

    result = buf.get_iter_at_line(line)
    if isinstance(result, tuple):
        ok, it = result
    else:
        it = result

That defensive unpack is the kind of papercut the pygobject-compat
surface should hide. Pin pygobject's `(bool, iter)` tuple shape.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


pytestmark = [
    pytest.mark.xdist_group("gtk3"),
]

needs_display = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="GtkTextBuffer needs an initialized GTK runtime",
)


@pytest.fixture
def Gtk() -> Any:
    from ginext import Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    return Gtk


@needs_display
def test_get_iter_at_line_returns_value_we_can_use(Gtk: Any) -> None:
    """Whatever goi returns, it must produce an iter we can read."""
    buf = Gtk.TextBuffer()
    buf.set_text("alpha\nbeta\ngamma\n", -1)
    _ok, it = buf.get_iter_at_line(0)
    assert it.get_line() == 0


@needs_display
def test_get_iter_at_line_returns_bool_iter_tuple(Gtk: Any) -> None:
    """`(bool, iter)` shape — pygobject parity. Closed by the shape_return
    bool-no-throws branch now including OUTs."""
    buf = Gtk.TextBuffer()
    buf.set_text("alpha\nbeta\ngamma\n", -1)
    result = buf.get_iter_at_line(0)
    assert isinstance(result, tuple)
    assert len(result) == 2
    ok, it = result
    assert ok is True
    assert it.get_line() == 0
