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

"""Filename-string argument/return marshalling.

Filename strings get a distinct encoding policy on some platforms. The
first-pass scope includes them alongside UTF-8.
"""

from __future__ import annotations

import os

import pytest


def test_filename_return_is_str_or_bytes() -> None:
    from ginext import GLib

    if not hasattr(GLib, "get_home_dir"):
        pytest.skip("GLib.get_home_dir not present")
    home = GLib.get_home_dir()
    assert isinstance(home, (str, bytes, os.PathLike))


def test_filename_arg_accepts_str() -> None:
    from ginext import GLib

    if not hasattr(GLib, "path_get_basename"):
        pytest.skip("GLib.path_get_basename not present")
    base = GLib.path_get_basename("/tmp/foo/bar.txt")
    assert base == "bar.txt"


def test_filename_arg_accepts_pathlike() -> None:
    from pathlib import PurePosixPath

    from ginext import GLib

    if not hasattr(GLib, "path_get_basename"):
        pytest.skip("GLib.path_get_basename not present")
    base = GLib.path_get_basename(str(PurePosixPath("/tmp/x/y")))
    assert base == "y"
