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

"""Gtk.TreePath coverage ported from PyGObject override tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="module")
def Gtk() -> Any:
    from ginext import Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    Gtk.init([])  # type: ignore[call-arg]  # Gtk3 init() accepts argv list; Gtk4 stubs have no-arg variant
    return Gtk


def test_tree_path_new_first(Gtk: Any) -> None:
    path = Gtk.TreePath.new_first()

    assert isinstance(path, Gtk.TreePath)
    assert path.to_string() == "0"
    assert path.get_depth() == 1
    assert path.get_indices() == [0]


def test_tree_path_new_from_string(Gtk: Any) -> None:
    path = Gtk.TreePath.new_from_string("1:2:3")

    assert isinstance(path, Gtk.TreePath)
    assert path.to_string() == "1:2:3"
    assert path.get_depth() == 3
    assert path.get_indices() == [1, 2, 3]


def test_tree_path_new_from_indices(Gtk: Any) -> None:
    path = Gtk.TreePath.new_from_indices([1, 2, 3])

    assert isinstance(path, Gtk.TreePath)
    assert path.to_string() == "1:2:3"
    assert path.get_depth() == 3
    assert path.get_indices() == [1, 2, 3]


def test_tree_path_empty(Gtk: Any) -> None:
    path = Gtk.TreePath.new()

    assert path.to_string() is None
    assert path.get_depth() == 0
    assert path.get_indices() == []


def test_tree_path_sequence_protocol(Gtk: Any) -> None:
    path = Gtk.TreePath.new_from_string("1:2:3")

    assert str(path) == "1:2:3"
    assert len(path) == 3
    assert tuple(path) == (1, 2, 3)
    assert path[0] == 1
