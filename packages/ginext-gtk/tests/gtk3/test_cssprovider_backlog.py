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

"""Gtk.CssProvider.load_from_data signature.

PyGObject accepts bytes-like objects for the first arg and figures out
the length from the buffer. Goi should match that contract.

Goi currently rejects bytes here:

    TypeError: argument 2 must be str, not bytes

This test pins the bytes-accepting contract.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


needs_display = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="Gtk.CssProvider construction in headless mode is flaky",
)


@pytest.fixture
def Gtk() -> Any:
    from ginext import Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    return Gtk


def test_load_from_data_accepts_str(Gtk: Any) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data("textview { font-family: monospace; }", -1)


@needs_display
def test_load_from_data_accepts_bytes(Gtk: Any) -> None:
    """str/bytes/bytearray all accepted for GIR utf8 params — see
    marshal/string.c::borrow_as_c_string and the matching arg-type checks
    in marshal/marshal.c and jit/helpers.c."""
    provider = Gtk.CssProvider()
    css = b"textview { font-family: monospace; }"
    provider.load_from_data(css, len(css))


@needs_display
def test_load_from_data_accepts_bytes_with_neg_length(Gtk: Any) -> None:
    """length=-1 means 'figure it out from a NUL-terminated string'."""
    provider = Gtk.CssProvider()
    provider.load_from_data(b"textview { color: red; }", -1)


@needs_display
def test_load_from_data_accepts_bytearray(Gtk: Any) -> None:
    """bytearray also flows through the utf8 marshaller."""
    provider = Gtk.CssProvider()
    provider.load_from_data(bytearray(b"textview { color: blue; }"), -1)


pytestmark = [
    pytest.mark.xdist_group("gtk3"),
]
