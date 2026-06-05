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

"""GINEXT_VERSIONS environment overrides.

`GINEXT_VERSIONS=Gtk:3.0,Gst:1.0` pins specific versions per namespace.
It sits below suffixed imports and above project defaults in the
resolution order.
"""

from __future__ import annotations

import pytest


def test_env_pins_single_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:2.0")

    import ginext

    assert ginext.defaults.resolve_version("GLib") == "2.0"


def test_env_pins_multiple_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:2.0,Gio:2.0")

    import ginext

    assert ginext.defaults.resolve_version("GLib") == "2.0"
    assert ginext.defaults.resolve_version("Gio") == "2.0"


def test_env_pin_visible_through_namespace_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:2.0")

    from ginext import GLib

    assert GLib.__version__ == (2, 0)


def test_env_pin_for_unknown_namespace_does_not_crash_until_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "Bogus:9.9")
    import ginext

    # Resolution returns the pin; loading would raise.
    assert ginext.defaults.resolve_version("Bogus") == "9.9"
    with pytest.raises((ImportError, AttributeError, ValueError)):
        ginext.Bogus


@pytest.mark.parametrize(
    "raw",
    [
        "GLib:2.0,",  # trailing comma
        " GLib : 2.0 ",  # whitespace
        "GLib:2.0, Gio:2.0",  # spaces between entries
    ],
)
def test_env_pin_tolerates_whitespace_and_trailing_separator(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", raw)

    import ginext

    assert ginext.defaults.resolve_version("GLib") == "2.0"


@pytest.mark.parametrize(
    "raw",
    [
        "GLib",  # no colon
        "GLib:",  # empty version
        ":2.0",  # empty name
        "GLib=2.0",  # wrong separator
    ],
)
def test_env_pin_rejects_malformed_entries(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", raw)

    import ginext

    with pytest.raises((ValueError, RuntimeError)):
        ginext.defaults.resolve_version("GLib")


def test_env_pin_beats_implied_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Implied defaults are below env overrides in resolution order."""
    # Set up TestRoot via implied-defaults chain, then override one downstream.
    monkeypatch.setenv("GINEXT_VERSIONS", "TestLeaf:3.0,TestRoot:4.0")

    import ginext

    monkeypatch.setattr(
        ginext.defaults,
        "_implied_defaults_map_cache",
        {("TestRoot", "4.0"): {"TestLeaf": "4.0"}},
    )
    monkeypatch.setattr(
        ginext.defaults,
        "_installed_cache",
        {"TestRoot": ["4.0"], "TestLeaf": ["4.0", "3.0"]},
    )

    assert ginext.defaults.resolve_version("TestLeaf") == "3.0"
