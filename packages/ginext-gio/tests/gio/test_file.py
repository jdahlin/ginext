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

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable


def _unlink_with_retry(path: str) -> None:
    """Delete a temp file, tolerating a brief window where a GIO async worker
    thread still holds the handle (Windows refuses to unlink an open file)."""
    for _ in range(20):
        try:
            Path(path).unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(0.05)
    with contextlib.suppress(FileNotFoundError, PermissionError):
        Path(path).unlink()


if TYPE_CHECKING:
    from collections.abc import Generator
    from ginext import Gio, GLib
    from ginext.aio import AsyncOperation
    from ginext.Gio import AsyncResult

import pytest


def test_file_supports_os_fspath_for_local_paths() -> None:
    from ginext import Gio

    # GIO returns OS-native paths, so feed it a native path (\tmp on Windows,
    # /tmp on Unix) for an exact round-trip.
    native = os.path.join(os.sep, "tmp")
    file = Gio.File.new_for_path(native)

    assert os.fspath(file) == native


def test_file_os_fspath_rejects_non_local_uris() -> None:
    from ginext import Gio

    file = Gio.File.new_for_uri("https://example.com")

    with pytest.raises(TypeError, match="not backed by a local path"):
        os.fspath(file)


def test_file_div_resolves_relative_path() -> None:
    from ginext import Gio

    parent = Gio.File.new_for_path(os.path.join(os.sep, "tmp"))
    child = parent / "ginext-child"

    assert isinstance(child, Gio.File)
    assert child.peek_path() == os.path.join(os.sep, "tmp", "ginext-child")


def test_new_for_path_and_query_info(tmp_path: Path) -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(str(tmp_path))

    assert isinstance(file, Gio.File)

    info = file.query_info("standard::name", Gio.FileQueryInfoFlags.NONE, None)
    assert isinstance(info, Gio.FileInfo)
    assert info.get_name() == tmp_path.name


def test_query_info_accepts_keyword_arguments(tmp_path: Path) -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(str(tmp_path))
    info = file.query_info(
        attributes="standard::name",
        flags=Gio.FileQueryInfoFlags.NONE,
        cancellable=None,
    )

    assert info.get_name() == tmp_path.name


def test_query_info_keyword_shape_errors() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path("/tmp")
    with pytest.raises(TypeError) as exc_info:
        file.query_info(  # type: ignore[misc]
            "standard::name",
            attributes="standard::type",
            flags=Gio.FileQueryInfoFlags.NONE,
            cancellable=None,
        )

    assert (
        str(exc_info.value)
        == "query_info() got multiple values for keyword argument 'attributes'"
    )


def test_query_info_defaults_flags_and_cancellable(tmp_path: Path) -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(str(tmp_path))
    # flags defaults to NONE, cancellable is an omittable trailing nullable
    info = file.query_info("standard::name")  # type: ignore[call-arg]
    assert info.get_name() == tmp_path.name


def test_query_info_default_flags_matches_explicit(tmp_path: Path) -> None:
    from ginext import Gio

    file = Gio.File.new_for_path(str(tmp_path))
    implicit = file.query_info("standard::name")  # type: ignore[call-arg]
    explicit = file.query_info("standard::name", Gio.FileQueryInfoFlags.NONE, None)
    assert implicit.get_name() == explicit.get_name()


def test_enumerate_children_defaults_flags() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path("./")
    enumerator = file.enumerate_children("standard::name")  # type: ignore[call-arg]
    assert isinstance(enumerator, Gio.FileEnumerator)


def test_default_flags_does_not_break_kwarg_collision_error() -> None:
    from ginext import Gio

    file = Gio.File.new_for_path("/tmp")
    with pytest.raises(TypeError) as exc_info:
        file.query_info("standard::name", attributes="standard::type")  # type: ignore[call-arg, misc]
    assert (
        str(exc_info.value)
        == "query_info() got multiple values for keyword argument 'attributes'"
    )


def test_copy_defaults_flags() -> None:
    from ginext import Gio

    fd, src = tempfile.mkstemp(prefix="ginext-copy-src-")
    os.write(fd, b"copy me")
    os.close(fd)
    dst = src + ".dst"
    try:
        source = Gio.File.new_for_path(src)
        target = Gio.File.new_for_path(dst)
        # flags defaults to NONE; cancellable and progress_callback omitted
        assert source.copy(target) is True  # type: ignore[call-arg]
        assert target.query_exists() is True
    finally:
        Path(src).unlink()
        with contextlib.suppress(FileNotFoundError):
            Path(dst).unlink()


def _enumerator_names(enumerator: Gio.FileEnumerator) -> list[str]:
    names: list[str] = []
    while True:
        info = enumerator.next_file(None)
        if info is None:
            return names
        names.append(info.get_name())


def test_file_enumerator_next_file_matches_repeated_enumeration() -> None:
    from ginext import Gio

    file = Gio.file_new_for_path("./")

    first = _enumerator_names(file.enumerate_children("standard::*", 0, None))
    second = _enumerator_names(file.enumerate_children("standard::*", 0, None))

    assert first == second


def test_file_enumerator_is_typed_wrapper() -> None:
    from ginext import Gio

    file = Gio.file_new_for_path("./")
    enumerator = file.enumerate_children("standard::*", 0, None)

    assert isinstance(enumerator, Gio.FileEnumerator)


@pytest.fixture
def tmp_gfile() -> Generator[tuple[Gio.File, Gio.FileIOStream]]:
    from ginext import Gio

    file, stream = Gio.File.new_tmp("TestGFile.XXXXXX")
    # Close the IOStream immediately: no test uses it, and on Windows an open
    # handle blocks deleting/replacing the file (EINVAL).
    with contextlib.suppress(Exception):
        stream.close(None)
    try:
        yield file, stream
    finally:
        with contextlib.suppress(Exception):
            file.delete(None)


def test_new_tmp_exists(tmp_gfile: tuple[Gio.File, Gio.FileIOStream]) -> None:
    file, _stream = tmp_gfile

    assert file.query_exists(None) is True


def test_replace_contents(tmp_gfile: tuple[Gio.File, Gio.FileIOStream]) -> None:
    from ginext import Gio

    file, _stream = tmp_gfile
    content = b"hello\0world\x7f!"

    success, etag = file.replace_contents(
        content,
        None,
        False,
        Gio.FileCreateFlags.NONE,
        None,
    )
    new_success, new_content, new_etag = file.load_contents(None)

    assert success is True
    assert new_success is True
    assert etag == new_etag
    assert new_content == content


def test_delete(tmp_gfile: tuple[Gio.File, Gio.FileIOStream]) -> None:
    file, _stream = tmp_gfile

    assert file.delete(None) is True
    assert file.query_exists(None) is False


# ---------------------------------------------------------------------------
# Async File operations (ginext.aio AsyncOperation over GIO async/finish
# pairs), driven by asyncio.run(..., loop_factory=aio.EventLoop).
# ---------------------------------------------------------------------------


@pytest.fixture
def hello_file() -> Generator[tuple[Gio.File, bytes]]:
    from ginext import Gio

    payload = b"hello\0world\x7f!"
    fd, path = tempfile.mkstemp(prefix="ginext-async-")
    os.write(fd, payload)
    os.close(fd)
    try:
        yield Gio.File.new_for_path(path), payload
    finally:
        _unlink_with_retry(path)


def _load_bytes_op(file: Gio.File, cancellable: Any = None) -> AsyncOperation[bytes]:
    """An AsyncOperation over g_file_load_bytes_async / _finish."""
    from ginext import aio

    def start(callback: Callable[[object, AsyncResult], None]) -> None:
        file.load_bytes_async(cancellable, callback)

    def finish(result: AsyncResult) -> bytes:
        raw = file.load_bytes_finish(result)
        gb: GLib.Bytes = raw[0]
        return bytes(gb.get_data())

    return aio.AsyncOperation(
        start,
        finish,
        cancel=cancellable.cancel if cancellable else None,
    )


def test_await_resolves_with_contents(hello_file: tuple[Gio.File, bytes]) -> None:
    from ginext import aio

    file, payload = hello_file

    async def main() -> object:
        return await _load_bytes_op(file)

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == payload


def test_await_matches_blocking_load_bytes(hello_file: tuple[Gio.File, bytes]) -> None:
    from ginext import aio

    file, _payload = hello_file
    gb: GLib.Bytes = file.load_bytes(None)[0]
    blocking = bytes(gb.get_data())

    async def main() -> object:
        return await _load_bytes_op(file)

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == blocking


def test_native_cancellation_surfaces_gio_error(
    hello_file: tuple[Gio.File, bytes],
) -> None:
    """Native side cancels the work -> the await raises a GLib.Error that
    matches G_IO_ERROR_CANCELLED (the catch-all; the Gio.CancelledError
    subclass only exists when GERROR_BUILTIN_EXCEPTIONS is on)."""
    from ginext import Gio, GLib, aio

    file, _payload = hello_file
    cancellable = Gio.Cancellable()
    cancellable.cancel()  # pre-cancel: the op completes with CANCELLED

    async def main() -> object:
        return await _load_bytes_op(file, cancellable)

    with pytest.raises(GLib.Error) as excinfo:
        asyncio.run(main(), loop_factory=aio.EventLoop)

    assert excinfo.value.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)


def test_asyncio_task_cancel_propagates_to_cancellable(
    hello_file: tuple[Gio.File, bytes],
) -> None:
    """asyncio task cancellation -> the underlying Gio.Cancellable is
    cancelled and the await raises asyncio.CancelledError. Runs under a plain
    asyncio loop (no GLib policy needed for the cancel path)."""
    import asyncio

    from ginext import Gio

    file, _payload = hello_file
    cancellable = Gio.Cancellable()
    op = _load_bytes_op(file, cancellable)

    async def main() -> bool:
        async def runner() -> object:
            return await op

        task = asyncio.ensure_future(runner())
        await asyncio.sleep(0)  # let the task start and suspend on the op
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return bool(cancellable.is_cancelled())

    assert asyncio.run(main()) is True


def test_await_completes_under_aio_eventloop(
    hello_file: tuple[Gio.File, bytes],
) -> None:
    """AsyncOperation's asyncio branch resolves to completion when driven by the
    native aio.EventLoop. Exercises the loop.create_future() /
    call_soon_threadsafe path the native runner tests don't reach."""
    import asyncio

    from ginext import aio

    file, payload = hello_file

    async def main() -> object:
        return await _load_bytes_op(file)

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == payload


@pytest.fixture
def populated_dir() -> Generator[tuple[Gio.File, set[str]]]:
    from ginext import Gio

    path = tempfile.mkdtemp(prefix="ginext-iterdir-")
    names = {f"file-{i}.txt" for i in range(3)}
    for name in names:
        Path(path, name).touch()
    try:
        yield Gio.File.new_for_path(path), names
    finally:
        for name in names:
            Path(path, name).unlink()
        os.rmdir(path)


def test_file_enumerator_async_iteration_yields_all_entries(
    populated_dir: tuple[Gio.File, set[str]],
) -> None:
    from ginext import aio

    directory, names = populated_dir

    async def main() -> list[str]:
        enumerator: Any = directory.enumerate_children("standard::name", 0, None)
        found = [info.get_name() async for info in enumerator]
        return found

    assert sorted(asyncio.run(main(), loop_factory=aio.EventLoop)) == sorted(names)


def test_file_enumerator_async_iteration_matches_sync(
    populated_dir: tuple[Gio.File, set[str]],
) -> None:
    from ginext import aio

    directory, _names = populated_dir
    sync_names = sorted(
        info.get_name()
        for info in directory.enumerate_children("standard::name", 0, None)
    )

    async def main() -> list[str]:
        enumerator: Any = directory.enumerate_children("standard::name", 0, None)
        return sorted([info.get_name() async for info in enumerator])

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == sync_names


def test_file_enumerator_async_iteration_empty_directory() -> None:
    from ginext import Gio, aio

    path = tempfile.mkdtemp(prefix="ginext-iterdir-empty-")
    try:
        directory = Gio.File.new_for_path(path)

        async def main() -> list[object]:
            enumerator: Any = directory.enumerate_children("standard::name", 0, None)
            return [info async for info in enumerator]

        assert asyncio.run(main(), loop_factory=aio.EventLoop) == []
    finally:
        os.rmdir(path)


def test_file_enumerator_async_iteration_crosses_batches() -> None:
    """More entries than one next_files_async batch must all be yielded."""
    from ginext import Gio, aio

    path = tempfile.mkdtemp(prefix="ginext-iterdir-batch-")
    names = {f"f{i:03d}" for i in range(40)}
    for name in names:
        Path(path, name).touch()
    try:
        directory = Gio.File.new_for_path(path)

        async def main() -> set[str]:
            enumerator: Any = directory.enumerate_children(
                "standard::name", 0, None
            )
            return {info.get_name() async for info in enumerator}

        assert asyncio.run(main(), loop_factory=aio.EventLoop) == names
    finally:
        for name in names:
            Path(path, name).unlink()
        os.rmdir(path)


def test_file_enumerator_async_iteration_under_eventloop(
    populated_dir: tuple[Gio.File, set[str]],
) -> None:
    import asyncio

    from ginext import aio

    directory, names = populated_dir

    async def main() -> set[str]:
        enumerator: Any = directory.enumerate_children("standard::name", 0, None)
        return {info.get_name() async for info in enumerator}

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == names
