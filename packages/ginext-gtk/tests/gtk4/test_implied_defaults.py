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

"""Implied defaults: pinning Gtk implies the GTK-family namespaces.

The Gtk-family map lives in ``ginext_gtk._defaults`` and reaches core through the
``ginext.implied_defaults`` entry point (core itself carries no Gtk config). A
direct pin for an implied namespace always overrides the implied value.
Relocated from the core test suite when the map moved into ginext-gtk.
"""

from __future__ import annotations

import pytest


def test_gtk_family_map_declared() -> None:
    from ginext_gtk import _defaults

    assert ("Gtk", "4.0") in _defaults.IMPLIED_DEFAULTS
    assert ("Gtk", "3.0") in _defaults.IMPLIED_DEFAULTS


def test_implied_defaults_reach_core_via_entry_point() -> None:
    import ginext

    table = ginext.defaults.implied_defaults_map()
    assert isinstance(table, dict)
    assert ("Gtk", "4.0") in table
    assert ("Gtk", "3.0") in table


def test_gtk_4_implied_block_contains_gtksource() -> None:
    import ginext

    assert "GtkSource" in ginext.defaults.implied_defaults_map()[("Gtk", "4.0")]


def test_gtk_3_implied_block_contains_gtksource() -> None:
    import ginext

    assert "GtkSource" in ginext.defaults.implied_defaults_map()[("Gtk", "3.0")]


def test_gtk_4_implies_gdk_4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0")

    import ginext
    assert ginext.defaults.resolve_version("Gdk") == "4.0"


def test_gtk_4_implies_gsk_4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0")

    import ginext
    assert ginext.defaults.resolve_version("Gsk") == "4.0"


def test_gtk_3_implies_gdk_3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:3.0")

    import ginext
    assert ginext.defaults.resolve_version("Gdk") == "3.0"


def test_direct_pin_overrides_implied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct pins always beat implied pins."""
    # Gtk:4.0 would imply Gdk:4.0, but explicit Gdk:3.0 wins.
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0,Gdk:3.0")

    import ginext
    assert ginext.defaults.resolve_version("Gdk") == "3.0"


def test_implied_default_only_used_without_direct_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0")

    import ginext
    # Nothing else direct-pinned; implied chain applies.
    assert ginext.defaults.resolve_version("Gdk") == "4.0"

    # Same env plus a direct override.
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0,Gdk:3.0")
    assert ginext.defaults.resolve_version("Gdk") == "3.0"


def test_implied_default_not_used_for_unrelated_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Implied chain should not bleed into unrelated namespaces."""
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0")

    import ginext
    # GLib is not in the implied table; resolution should fall back to
    # gidefaults / highest-installed, not to "4.0".
    assert ginext.defaults.resolve_version("GLib") != "4.0"
