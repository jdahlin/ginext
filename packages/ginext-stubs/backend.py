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
import sys
from pathlib import Path
from typing import Any

from hatchling.build import build_editable as _build_editable
from hatchling.build import build_wheel as _build_wheel


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _generated_stub_dir() -> Path:
    # Generate stubs into packages/ginext-stubs/ginext/ so hatchling's
    # force-include picks them up for the wheel.
    return Path(__file__).resolve().parent / "ginext"


def _generate_stubs(*, force: bool = False) -> None:
    generated_dir = _generated_stub_dir()
    if (
        not force
        and (generated_dir / "__init__.pyi").exists()
        and (generated_dir / "py.typed").exists()
    ):
        return
    repo_root = _repo_root()
    stubgen_src = repo_root / "packages" / "ginext-stubgen" / "src"
    if str(stubgen_src) not in sys.path:
        sys.path.insert(0, str(stubgen_src))

    from ginext_stubgen.__main__ import cmd_generate_all

    old_cwd = Path.cwd()
    os.chdir(repo_root)
    try:
        rc = cmd_generate_all(type("Args", (), {"out": generated_dir})())
    finally:
        os.chdir(old_cwd)
    if rc != 0:
        raise RuntimeError(f"ginext_stubgen generate-all failed with exit code {rc}")


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    _generate_stubs()
    return _build_wheel(wheel_directory, config_settings, metadata_directory)


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    _generate_stubs()
    return _build_editable(wheel_directory, config_settings, metadata_directory)
