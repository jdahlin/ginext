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

"""gidefaults.py discovery from installed distribution metadata.

The plan: a build step writes `gidefaults.py` into the dist-info of the
distribution. `ginext` loads it via importlib.metadata (not as a normal
module), validates it is data-only, and reads DEFAULT_VERSIONS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pathlib


def test_app_defaults_resolver_is_public() -> None:
    """ginext exposes a way to inspect the loaded app defaults."""
    import ginext

    assert hasattr(ginext.defaults, "load_app_defaults")


def test_app_defaults_default_app_returns_mapping_or_none() -> None:
    """With no GINEXT_APP and no inferable distribution, the loader
    must return either None or an empty mapping — not raise."""
    import ginext

    result = ginext.defaults.load_app_defaults()
    assert result is None or isinstance(result, dict)


def test_app_defaults_validates_data_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """A gidefaults.py with imports/side effects must be rejected."""
    bad = tmp_path / "gidefaults.py"
    bad.write_text("import os\nDEFAULT_VERSIONS = {'Gtk': '4.0'}\n")

    import ginext

    with pytest.raises((ValueError, SyntaxError, RuntimeError)):
        ginext.defaults.load_gidefaults_file(bad)


def test_app_defaults_validates_top_level_keys(tmp_path: pathlib.Path) -> None:
    """Only DEFAULT_VERSIONS is expected at the top level."""
    bad = tmp_path / "gidefaults.py"
    bad.write_text("DEFAULT_VERSIONS = {'Gtk': '4.0'}\nEXTRA = 1\n")

    import ginext

    with pytest.raises((ValueError, RuntimeError)):
        ginext.defaults.load_gidefaults_file(bad)


def test_app_defaults_reads_default_versions(tmp_path: pathlib.Path) -> None:
    good = tmp_path / "gidefaults.py"
    good.write_text("DEFAULT_VERSIONS = {'Gtk': '4.0', 'Gst': '1.0'}\n")

    import ginext

    mapping = ginext.defaults.load_gidefaults_file(good)
    assert mapping == {"Gtk": "4.0", "Gst": "1.0"}


def test_app_defaults_rejects_non_string_values(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "gidefaults.py"
    bad.write_text("DEFAULT_VERSIONS = {'Gtk': 4.0}\n")

    import ginext

    with pytest.raises((TypeError, ValueError)):
        ginext.defaults.load_gidefaults_file(bad)


def test_app_defaults_does_not_register_as_module(tmp_path: pathlib.Path) -> None:
    """gidefaults must be loaded as data, not imported into sys.modules."""
    import sys

    good = tmp_path / "gidefaults.py"
    good.write_text("DEFAULT_VERSIONS = {'Gtk': '4.0'}\n")

    import ginext

    ginext.defaults.load_gidefaults_file(good)

    assert "gidefaults" not in sys.modules
