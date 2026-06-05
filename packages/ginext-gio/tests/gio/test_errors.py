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

"""GLib.Error → Python built-in filesystem exception mapping.

When GLib raises a GError in the g-io-error-quark domain, ginext raises an
exception that inherits from both ``GLib.Error`` and the appropriate Python
built-in (``FileNotFoundError``, ``PermissionError``, etc.) so callers can
write ordinary Python exception handling:

    try:
        Gio.File.new_for_path(missing).load_bytes(None)
    except FileNotFoundError:
        ...

Each error code is exercised through a real GIO operation so the full
C → Python raise path is covered, not just the factory function.
"""

from __future__ import annotations

import asyncio

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

_MISSING = "/nonexistent-ginext-test-path-xyzzy"

# POSIX file-permission tests: skipped for root (which bypasses permission
# bits) and on Windows, where chmod(0o000) does not deny access and os.getuid
# does not exist. The win32 check short-circuits before os.getuid is called.
_skip_no_unix_perms = pytest.mark.skipif(
    sys.platform == "win32" or os.getuid() == 0,
    reason="POSIX file permissions not enforced for root / on Windows",
)


@pytest.fixture(autouse=True)
def _enable_builtin_gerror_exceptions(monkeypatch: pytest.MonkeyPatch) -> Any:
    import ginext

    monkeypatch.setenv("GINEXT_GERROR_BUILTIN_EXCEPTIONS", "true")
    ginext.features.reset_for_test()
    yield
    ginext.features.reset_for_test()


# ── FileNotFoundError ─────────────────────────────────────────────────────────


def test_load_bytes_missing_file_raises_file_not_found() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(_MISSING)
    with pytest.raises(FileNotFoundError):
        file.load_bytes(None)


def test_file_not_found_is_also_catchable_as_glib_error() -> None:
    from ginext import Gio, GLib

    file = Gio.File.new_for_path(_MISSING)
    with pytest.raises(GLib.Error):
        file.load_bytes(None)


def test_file_not_found_is_also_catchable_as_os_error() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(_MISSING)
    with pytest.raises(OSError):
        file.load_bytes(None)


def test_file_not_found_carries_gio_attributes() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(_MISSING)
    with pytest.raises(FileNotFoundError) as exc_info:
        file.load_bytes(None)

    e = exc_info.value
    assert e.domain == "g-io-error-quark"  # type: ignore[attr-defined]
    assert e.matches(Gio.IOErrorEnum.NOT_FOUND)  # type: ignore[attr-defined]
    assert isinstance(e.message, str) and len(e.message) > 0  # type: ignore[attr-defined]


def test_query_info_missing_file_raises_file_not_found() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(_MISSING)
    with pytest.raises(FileNotFoundError):
        file.query_info("standard::name")  # type: ignore[call-arg]  # overlay provides default for flags


def test_load_bytes_async_missing_file_raises_file_not_found() -> None:
    from ginext import Gio, aio

    file = Gio.File.new_for_path(_MISSING)

    async def main() -> Any:
        def start(cb: Any) -> None:
            file.load_bytes_async(None, cb)

        def finish(r: Any) -> Any:
            return file.load_bytes_finish(r)

        return await aio._AsyncOperation(start, finish)

    with pytest.raises(FileNotFoundError):
        asyncio.run(main(), loop_factory=aio.EventLoop)


# ── IsADirectoryError ─────────────────────────────────────────────────────────


def test_load_bytes_on_directory_raises_is_a_directory() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path("/tmp")
    with pytest.raises(IsADirectoryError):
        file.load_bytes(None)


def test_is_a_directory_is_also_catchable_as_glib_error() -> None:
    from ginext import Gio, GLib

    file = Gio.File.new_for_path("/tmp")
    with pytest.raises(GLib.Error):
        file.load_bytes(None)


def test_is_a_directory_carries_gio_attributes() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path("/tmp")
    with pytest.raises(IsADirectoryError) as exc_info:
        file.load_bytes(None)

    assert exc_info.value.matches(Gio.IOErrorEnum.IS_DIRECTORY)  # type: ignore[attr-defined]


# ── NotADirectoryError ───────────────────────────────────────────────────────


def test_enumerate_children_on_file_raises_not_a_directory(tmp_path: Path) -> None:
    from ginext import Gio

    regular = tmp_path / "file"
    regular.write_text("x")
    file = Gio.File.new_for_path(str(regular))
    with pytest.raises(NotADirectoryError):
        file.enumerate_children("standard::name", 0, None)


def test_not_a_directory_is_also_catchable_as_glib_error(tmp_path: Path) -> None:
    from ginext import Gio, GLib

    regular = tmp_path / "file"
    regular.write_text("x")
    file = Gio.File.new_for_path(str(regular))
    with pytest.raises(GLib.Error):
        file.enumerate_children("standard::name", 0, None)


def test_not_a_directory_carries_gio_attributes(tmp_path: Path) -> None:
    from ginext import Gio

    regular = tmp_path / "file"
    regular.write_text("x")
    file = Gio.File.new_for_path(str(regular))
    with pytest.raises(NotADirectoryError) as exc_info:
        file.enumerate_children("standard::name", 0, None)

    assert exc_info.value.matches(Gio.IOErrorEnum.NOT_DIRECTORY)  # type: ignore[attr-defined]


# ── FileExistsError ──────────────────────────────────────────────────────────


def test_create_existing_file_raises_file_exists(tmp_path: Path) -> None:
    """Gio.File.create() on an existing path raises FileExistsError."""
    from ginext import Gio

    existing = tmp_path / "file"
    existing.write_text("x")
    file = Gio.File.new_for_path(str(existing))
    with pytest.raises(FileExistsError):
        file.create(Gio.FileCreateFlags.NONE, None)


def test_file_exists_is_also_catchable_as_glib_error(tmp_path: Path) -> None:
    from ginext import Gio, GLib

    existing = tmp_path / "file"
    existing.write_text("x")
    file = Gio.File.new_for_path(str(existing))
    with pytest.raises(GLib.Error):
        file.create(Gio.FileCreateFlags.NONE, None)


def test_copy_to_existing_dest_without_overwrite_raises_file_exists() -> None:
    from ginext import Gio

    fd, src_path = tempfile.mkstemp(prefix="ginext-err-src-")
    os.write(fd, b"hello")
    os.close(fd)
    fd, dst_path = tempfile.mkstemp(prefix="ginext-err-dst-")
    os.close(fd)
    try:
        src = Gio.File.new_for_path(src_path)
        dst = Gio.File.new_for_path(dst_path)
        with pytest.raises(FileExistsError):
            src.copy(dst, Gio.FileCopyFlags.NONE, None, None, None)  # type: ignore[call-arg]  # testing runtime rejection: extra progress_callback_data arg
    finally:
        Path(src_path).unlink()
        Path(dst_path).unlink()


# ── PermissionError ──────────────────────────────────────────────────────────


@_skip_no_unix_perms
def test_load_bytes_no_permission_raises_permission_error() -> None:
    from ginext import Gio

    fd, path = tempfile.mkstemp(prefix="ginext-err-perm-")
    os.close(fd)
    os.chmod(path, 0o000)
    file = Gio.File.new_for_path(path)
    try:
        with pytest.raises(PermissionError):
            file.load_bytes(None)
    finally:
        os.chmod(path, 0o600)
        Path(path).unlink()


@_skip_no_unix_perms
def test_permission_error_is_also_catchable_as_glib_error() -> None:
    from ginext import Gio, GLib

    fd, path = tempfile.mkstemp(prefix="ginext-err-perm2-")
    os.close(fd)
    os.chmod(path, 0o000)
    file = Gio.File.new_for_path(path)
    try:
        with pytest.raises(GLib.Error):
            file.load_bytes(None)
    finally:
        os.chmod(path, 0o600)
        Path(path).unlink()


@_skip_no_unix_perms
def test_permission_error_carries_gio_attributes() -> None:
    from ginext import Gio

    fd, path = tempfile.mkstemp(prefix="ginext-err-perm3-")
    os.close(fd)
    os.chmod(path, 0o000)
    file = Gio.File.new_for_path(path)
    try:
        with pytest.raises(PermissionError) as exc_info:
            file.load_bytes(None)
        assert exc_info.value.matches(Gio.IOErrorEnum.PERMISSION_DENIED)  # type: ignore[attr-defined]
    finally:
        os.chmod(path, 0o600)
        Path(path).unlink()


# ── isinstance and subclass checks ───────────────────────────────────────────


def test_file_not_found_is_subclass_of_glib_error() -> None:
    from ginext import Gio, GLib

    assert issubclass(Gio.NotFoundError, GLib.Error)


def test_file_not_found_is_subclass_of_file_not_found_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.NotFoundError, FileNotFoundError)


def test_file_not_found_is_subclass_of_os_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.NotFoundError, OSError)


def test_permission_error_is_subclass_of_glib_error() -> None:
    from ginext import Gio, GLib

    assert issubclass(Gio.PermissionDeniedError, GLib.Error)


def test_permission_error_is_subclass_of_permission_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.PermissionDeniedError, PermissionError)


def test_is_a_directory_error_is_subclass_of_glib_error() -> None:
    from ginext import Gio, GLib

    assert issubclass(Gio.IsADirectoryError, GLib.Error)


def test_is_a_directory_error_is_subclass_of_is_a_directory_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.IsADirectoryError, IsADirectoryError)


def test_not_a_directory_error_is_subclass_of_not_a_directory_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.NotADirectoryError, NotADirectoryError)


def test_file_exists_error_is_subclass_of_file_exists_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.FileExistsError, FileExistsError)


def test_timed_out_error_is_subclass_of_timeout_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.TimedOutError, TimeoutError)


def test_broken_pipe_error_is_subclass_of_broken_pipe_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.BrokenPipeError, BrokenPipeError)


def test_connection_refused_error_is_subclass_of_connection_refused_error() -> None:
    from ginext import Gio

    assert issubclass(Gio.ConnectionRefusedError, ConnectionRefusedError)
