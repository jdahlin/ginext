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

"""Gtk-3.0/Gdk-3.0 atom coverage ported from PyGObject tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="module")
def gtk3_modules() -> tuple[Any, Any]:
    from ginext import Gdk, Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    Gtk.init([])  # type: ignore[call-arg]  # Gtk3 init() accepts argv list; Gtk4 stubs have no-arg variant
    return Gtk, Gdk


def test_atom_name_round_trip(gtk3_modules: tuple[Any, Any]) -> None:
    _Gtk, Gdk = gtk3_modules

    atom = Gdk.Atom.intern("my_string", False)

    assert atom.name() == "my_string"


def test_targets_include_empty_lists(gtk3_modules: tuple[Any, Any]) -> None:
    Gtk, _Gdk = gtk3_modules

    assert Gtk.targets_include_text([]) is False
    assert Gtk.targets_include_image([], False) is False


def test_atom_repr_is_parseable(gtk3_modules: tuple[Any, Any]) -> None:
    _Gtk, Gdk = gtk3_modules

    atom = Gdk.Atom.intern("my_string", False)

    assert repr(atom) == 'Gdk.Atom.intern("my_string", False)'


def test_targets_include_atom_arrays(gtk3_modules: tuple[Any, Any]) -> None:
    Gtk, Gdk = gtk3_modules

    plain = Gdk.Atom.intern("text/plain", False)
    html = Gdk.Atom.intern("text/html", False)
    jpeg = Gdk.Atom.intern("image/jpeg", False)

    assert Gtk.targets_include_text([plain, html]) is True
    assert Gtk.targets_include_text([jpeg]) is False
    assert Gtk.targets_include_image([jpeg], False) is True
