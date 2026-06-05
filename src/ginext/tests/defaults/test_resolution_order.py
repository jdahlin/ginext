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

"""Version resolution priority order (highest to lowest):

1. Explicit suffixed namespace import (Gtk4)
2. Env override (GINEXT_VERSIONS)
3. Direct project defaults from gidefaults.py
4. Implied defaults from direct project defaults
5. Highest installed typelib fallback

Direct pins always beat implied pins.
"""

from __future__ import annotations

import pytest


from typing import Any, Callable


@pytest.fixture
def fake_gidefaults(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, str]], None]:
    """Install a fake gidefaults.py mapping into ginext.defaults."""

    def _install(mapping: dict[str, str]) -> None:
        import ginext

        # The plan describes loading via importlib.metadata; tests
        # bypass that by setting the in-memory app-defaults cache.
        ginext.defaults.set_app_defaults_for_test(mapping)

    return _install


def test_env_beats_gidefaults(
    monkeypatch: pytest.MonkeyPatch, fake_gidefaults: Any
) -> None:
    fake_gidefaults({"Gtk": "3.0"})
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:4.0")

    import ginext

    assert ginext.defaults.resolve_version("Gtk") == "4.0"


def test_gidefaults_beats_implied(
    monkeypatch: pytest.MonkeyPatch, fake_gidefaults: Any
) -> None:
    # gidefaults pins TestLeaf to 3.0 directly; implied from TestRoot:4.0 says 4.0;
    # direct pin wins.
    fake_gidefaults({"TestRoot": "4.0", "TestLeaf": "3.0"})

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


def test_implied_beats_highest_installed(
    monkeypatch: pytest.MonkeyPatch, fake_gidefaults: Any
) -> None:
    fake_gidefaults({"TestRoot": "3.0"})

    import ginext

    monkeypatch.setattr(
        ginext.defaults,
        "_implied_defaults_map_cache",
        {("TestRoot", "3.0"): {"TestLeaf": "3.0"}},
    )
    monkeypatch.setattr(
        ginext.defaults,
        "_installed_cache",
        {"TestRoot": ["4.0", "3.0"], "TestLeaf": ["4.0", "3.0"]},
    )

    # With TestRoot:3.0, TestLeaf is implied to 3.0 even if 4.0 is the
    # highest installed version.
    assert ginext.defaults.resolve_version("TestLeaf") == "3.0"


def test_no_pin_falls_back_to_highest_installed() -> None:
    import ginext

    # GLib has 2.0 typelib; with no pin and no implied, we should still
    # get a version (the highest installed).
    v = ginext.defaults.resolve_version("GLib")
    assert v is not None
    assert v.split(".")[0].isdigit()


def test_suffix_beats_env_for_that_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:9.9")

    from ginext import GLib2

    assert GLib2.__version__ == (2, 0)


def test_unrelated_env_pin_does_not_affect_other_namespaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "Gtk:3.0")

    import ginext

    # GLib resolution should not pick up "3.0".
    v = ginext.defaults.resolve_version("GLib")
    assert v != "3.0"
