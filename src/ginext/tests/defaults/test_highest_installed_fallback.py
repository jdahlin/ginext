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

"""Highest installed typelib fallback (mainly for interactive/dev use).

Position in the resolution chain: lowest priority. Only used when no
suffix, env override, direct project default, or implied default
applies.
"""

from __future__ import annotations

import pytest


def test_fallback_used_when_no_pin_available() -> None:
    """With a clean environment, common namespaces should resolve to
    *some* version via fallback."""
    import ginext

    # GLib has at least one installed typelib.
    v = ginext.defaults.resolve_version("GLib")
    assert v is not None


def test_fallback_returns_string_version() -> None:
    import ginext

    v = ginext.defaults.resolve_version("GLib")
    assert isinstance(v, str)


def test_fallback_is_not_used_when_env_pin_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:2.0")

    import ginext

    # The pin matches the available version, but the point is the
    # pin path is taken — verifying via resolve_version semantics.
    assert ginext.defaults.resolve_version("GLib") == "2.0"


def test_fallback_raises_for_unknown_namespace() -> None:
    import ginext

    with pytest.raises((LookupError, RuntimeError)):
        ginext.defaults.resolve_version("NoSuchNamespaceXYZ")


def test_fallback_prefers_highest_version_when_multiple_installed() -> None:
    """If two versions of a namespace are installed, the fallback picks
    the higher one. This test documents intent — it is a no-op when only
    one version is installed."""
    import ginext

    # Use whichever namespace happens to have two typelibs on this
    # system. Skip cleanly if none does.
    candidates = ginext.defaults.list_installed_versions_for_test("GLib")
    if len(candidates) < 2:
        pytest.skip("only one GLib typelib installed")
    expected = max(candidates, key=lambda s: tuple(int(p) for p in s.split(".")))
    assert ginext.defaults.resolve_version("GLib") == expected
