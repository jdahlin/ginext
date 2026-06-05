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

import os
from pathlib import Path
import pytest

from ginext.namespace import Namespace


def _find_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() and (cwd / "src" / "ginext").exists():
        return cwd

    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (
            parent / "src" / "ginext"
        ).exists():
            return parent
    return cwd


ROOT = _find_root()


def _find_gi_tests_builddir() -> Path | None:
    explicit = os.environ.get("GINEXT_GI_TESTS_BUILDDIR")
    if explicit:
        path = Path(explicit)
        return path if path.is_dir() else None

    candidates = [
        ROOT / "build" / "packages" / "typelib",
    ]
    candidates.extend(
        path / "packages" / "typelib"
        for path in sorted((ROOT / "build").glob("*"))
        if path.is_dir()
    )
    for candidate in candidates:
        if (candidate / "GIMarshallingTests-1.0.typelib").exists():
            return candidate
    return None


def load_test_namespace(name: str, version: str = "1.0") -> Namespace:
    builddir = _find_gi_tests_builddir()
    if builddir is None:
        pytest.skip("gi-tests not built")

    builddir_s = str(builddir)
    typelib_path = os.environ.get("GI_TYPELIB_PATH", "")
    if builddir_s not in typelib_path.split(os.pathsep):
        os.environ["GI_TYPELIB_PATH"] = (
            f"{builddir_s}{os.pathsep}{typelib_path}" if typelib_path else builddir_s
        )

    import ginext

    return ginext._load_namespace(name, version)
