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

"""ginext.aio.EventLoop: a GLib-backed asyncio event loop.

Exercises it as a real asyncio loop driven through the modern
``asyncio.run(coro, loop_factory=aio.EventLoop)`` entry point (no event-loop
policy): scheduling, timers, exceptions, cancellation, and — importantly —
multiple tasks running concurrently while GIO I/O is in flight.
"""

from __future__ import annotations

import asyncio
import asyncio.streams
import contextlib
import time
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Coroutine, Generator
    from pathlib import Path

    from ginext.aio import _AsyncOperation

import pytest

_T = TypeVar("_T")


def _run(coro: Coroutine[object, object, _T]) -> _T:
    from ginext import aio

    return asyncio.run(coro, loop_factory=aio.EventLoop)


def _load_bytes_op(file: object) -> _AsyncOperation:
    """An _AsyncOperation over g_file_load_bytes_async / _finish."""
    from ginext import aio

    def start(callback: object) -> None:
        getattr(file, "load_bytes_async")(None, callback)

    def finish(result: object) -> bytes:
        raw = getattr(file, "load_bytes_finish")(result)
        return bytes(getattr(raw[0], "get_data")())

    return aio._AsyncOperation(start, finish)


@pytest.fixture
def host_file(tmp_path: Path) -> Generator[tuple[object, bytes], None, None]:
    from ginext import Gio

    path = tmp_path / "host_file"
    expected = b"127.0.0.1\tlocalhost\n"
    path.write_bytes(expected)
    file = Gio.File.new_for_path(str(path))
    yield file, expected


# -- basic loop behavior ------------------------------------------------------


def test_run_until_complete_returns_result() -> None:
    async def main() -> int:
        return 42

    assert _run(main()) == 42


def test_exception_propagates_out_of_run() -> None:
    async def main() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        _run(main())


def test_await_gio_op_completes(host_file: tuple[object, bytes]) -> None:
    file, expected = host_file

    async def main() -> object:
        return await _load_bytes_op(file)

    assert _run(main()) == expected


def test_sleep_actually_waits() -> None:
    async def main() -> float:
        start = time.monotonic()
        await asyncio.sleep(0.05)
        return time.monotonic() - start

    elapsed = _run(main())
    assert elapsed >= 0.04  # the GLib timeout source fired, not a busy spin


def test_call_soon_runs_callback() -> None:
    from ginext import aio

    seen: list[str] = []
    loop = aio.EventLoop()
    try:
        loop.call_soon(seen.append, "ran")

        async def main() -> None:
            # Yield once so the queued call_soon handle gets dispatched.
            await asyncio.sleep(0)

        loop.run_until_complete(main())
    finally:
        loop.close()
    assert seen == ["ran"]


# -- concurrency: other tasks running -----------------------------------------


def test_gather_runs_two_coroutines_to_completion(host_file: tuple[object, bytes]) -> None:
    file, expected = host_file

    async def counter(n: int) -> int:
        total = 0
        for _ in range(n):
            await asyncio.sleep(0)
            total += 1
        return total

    async def main() -> tuple[object, int]:
        data, count = await asyncio.gather(_load_bytes_op(file), counter(100))
        return data, count

    data, count = _run(main())
    assert data == expected
    assert count == 100


def test_background_task_progresses_while_awaiting_io(
    host_file: tuple[object, bytes],
) -> None:
    """A background task keeps running while the foreground awaits real GIO
    I/O — proves the loop interleaves tasks, not just drains one."""
    file, expected = host_file

    async def main() -> tuple[int, list[object]]:
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.001)
                ticks += 1

        task = asyncio.ensure_future(ticker())
        results: list[object] = []
        for _ in range(5):
            results.append(await _load_bytes_op(file))
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return ticks, results

    ticks, results = _run(main())
    assert ticks >= 1  # the background task ran during the foreground's I/O
    assert all(r == expected for r in results)


def test_many_concurrent_gio_ops(host_file: tuple[object, bytes]) -> None:
    file, expected = host_file

    async def main() -> list[object]:
        return list(await asyncio.gather(*[_load_bytes_op(file) for _ in range(10)]))

    results = _run(main())
    assert results == [expected] * 10


def test_create_task_then_await(host_file: tuple[object, bytes]) -> None:
    file, expected = host_file

    async def main() -> tuple[object, int]:
        task = asyncio.ensure_future(_wrap(_load_bytes_op(file)))
        other = 0
        while not task.done():
            await asyncio.sleep(0)
            other += 1
        return task.result(), other

    async def _wrap(awaitable: _AsyncOperation) -> object:
        return await awaitable

    data, other = _run(main())
    assert data == expected
    assert other >= 1  # the loop ran the polling coroutine while the task ran


# -- cancellation under the real loop -----------------------------------------


def test_task_cancellation_raises_cancelled_error(host_file: tuple[object, bytes]) -> None:
    from ginext import Gio

    file, _expected = host_file
    cancellable = Gio.Cancellable()

    def start(callback: object) -> None:
        getattr(file, "load_bytes_async")(cancellable, callback)

    def finish(result: object) -> object:
        return getattr(file, "load_bytes_finish")(result)

    from ginext import aio

    op = aio._AsyncOperation(start, finish, cancel=cancellable.cancel)

    async def main() -> object:
        async def runner() -> object:
            return await op

        task = asyncio.ensure_future(runner())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return cancellable.is_cancelled()

    assert _run(main()) is True


def test_wait_for_timeout_cancels_slow_work() -> None:
    async def main() -> str:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.sleep(10), timeout=0.05)
        return "timed-out"

    assert _run(main()) == "timed-out"


def test_socket_round_trip_on_glib_loop() -> None:
    """asyncio sockets (start_server + open_connection) work on the GLib-backed
    loop — the capability natively-async HTTP clients (httpx/aiohttp) need."""
    from ginext import aio

    async def main() -> bytes:
        async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            writer.write(b"echo:" + await reader.readline())
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        host, port = server.sockets[0].getsockname()[:2]
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(b"ping\n")
        await writer.drain()
        line = await reader.readline()
        writer.close()
        server.close()
        await server.wait_closed()
        return line

    assert asyncio.run(main(), loop_factory=aio.EventLoop) == b"echo:ping\n"


def test_run_application_drives_async_tasks() -> None:
    """app.run() spins the GLib loop; a coroutine scheduled with ensure_future
    from a signal handler is driven by it (no second loop)."""
    from ginext import Gio, aio

    app = Gio.Application(
        application_id="org.ginext.test.RunApp",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    seen: list[str] = []

    async def work() -> None:
        seen.append("start")
        await asyncio.sleep(0.01)
        seen.append("after-sleep")
        app.quit()

    def on_activate(_app: object) -> None:
        app.hold()
        asyncio.ensure_future(work())

    app.activate.connect(on_activate, owner=app)
    loop = aio.EventLoop()
    try:
        rc = loop.run_application(app, [])
    finally:
        loop.close()

    assert rc == 0
    assert seen == ["start", "after-sleep"]
