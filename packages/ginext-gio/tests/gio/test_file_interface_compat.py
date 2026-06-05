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

"""Port of the Gio.File interface-method assertions from goi."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

# GIO returns OS-native paths; use the native separator so get_path round-trips
# exactly on Windows (\etc\hostname) as well as Unix (/etc/hostname).
_NATIVE_PATH = os.path.join(os.sep, "etc", "hostname")


def test_module_level_file_new_for_path_works() -> None:
    from ginext import Gio

    file = Gio.file_new_for_path("/etc/hostname")

    assert file is not None


def test_gio_file_new_for_path_exists_as_class_method() -> None:
    from ginext import Gio

    assert callable(getattr(Gio.File, "new_for_path", None))


def test_gio_file_get_path_returns_string() -> None:
    from ginext import Gio

    Gio.File
    file = Gio.file_new_for_path(_NATIVE_PATH)

    assert file.get_path() == _NATIVE_PATH


def test_gio_file_get_uri_returns_file_url() -> None:
    from ginext import Gio

    Gio.File
    file = Gio.file_new_for_path("/etc/hostname")
    uri = file.get_uri()

    assert uri.startswith("file://")
    assert uri.endswith("/etc/hostname")


def test_gio_file_load_contents_roundtrips() -> None:
    from ginext import Gio

    # newline="" disables text-mode newline translation, so the file holds a
    # bare "\n" on Windows too (not "\r\n") and the byte round-trip is exact.
    with tempfile.NamedTemporaryFile(
        "w", delete=False, suffix=".pyedit", newline=""
    ) as handle:
        handle.write("hello ginext\n")
        path = handle.name
    try:
        Gio.File
        file = Gio.file_new_for_path(path)
        ok, contents, _etag = file.load_contents(None)

        assert ok is True
        assert bytes(contents).decode("utf-8") == "hello ginext\n"
    finally:
        Path(path).unlink()


def test_gio_file_method_resolves_without_prior_interface_touch() -> None:
    import ginext

    namespace = ginext._load_namespace("Gio", "2.0")
    file = namespace.file_new_for_path(_NATIVE_PATH)

    assert file.get_path() == _NATIVE_PATH


def test_gio_file_replace_contents_writes() -> None:
    from ginext import Gio

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pyedit") as handle:
        path = handle.name
    try:
        Gio.File
        file = Gio.file_new_for_path(path)
        file.replace_contents(
            b"replaced\n",  # type: ignore[arg-type]  # replace_contents accepts bytes at runtime
            None,
            False,
            Gio.FileCreateFlags.NONE,
            None,
        )
        with Path(path).open() as handle:
            assert handle.read() == "replaced\n"
    finally:
        Path(path).unlink()
