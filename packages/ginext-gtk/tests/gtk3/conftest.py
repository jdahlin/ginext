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

import pytest


@pytest.fixture(autouse=True)
def _require_gtk3() -> None:
    # These tests target Gtk 3 (the Makefile's gtk3 phase runs them with
    # GINEXT_VERSIONS=Gtk:3.0). A bare `pytest`/`uv run pytest` run has no such
    # pin, so Gtk resolves to its default (4.0) and the Gtk3-only calls here
    # (e.g. init_check([])) would crash. Skip instead, mirroring the gtk4
    # conftest's version guard. Gtk is a per-process singleton, so gtk3 and
    # gtk4 tests cannot share a process anyway.
    from ginext import Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip(
            "requires Gtk-3.0 (run via `make test` or set GINEXT_VERSIONS=Gtk:3.0)"
        )
