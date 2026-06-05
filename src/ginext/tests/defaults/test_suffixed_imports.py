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

"""Suffixed namespace imports pin a specific version.

`from ginext import GLib2` should resolve to GLib version "2.0" regardless
of any defaults, env overrides, or implied versions. Suffix is the
highest-priority resolution source per the plan.
"""

from __future__ import annotations

import pytest


def test_glib2_suffix_resolves_to_2_0() -> None:
    from ginext import GLib2

    assert GLib2.__name__ == "GLib"
    assert GLib2.__version__ == (2, 0)


def test_suffix_returns_same_module_as_unsuffixed_when_versions_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:2.0")

    from ginext import GLib, GLib2

    assert GLib is GLib2


def test_suffix_overrides_env_version(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if env says GLib:9.9 (which doesn't exist), the suffix wins.
    monkeypatch.setenv("GINEXT_VERSIONS", "GLib:9.9")

    from ginext import GLib2

    assert GLib2.__version__ == (2, 0)


def test_unknown_suffixed_version_raises() -> None:
    import ginext

    with pytest.raises((ImportError, AttributeError, ValueError)):
        ginext.GLib999


def test_suffix_is_repeatable_and_cached() -> None:
    from ginext import GLib2 as a
    from ginext import GLib2 as b

    assert a is b


@pytest.mark.parametrize("name,version", [("GLib2", (2, 0)), ("Gio2", (2, 0))])
def test_common_suffixes(name: str, version: tuple[int, int]) -> None:
    import ginext

    mod = getattr(ginext, name)
    assert mod.__version__ == version
