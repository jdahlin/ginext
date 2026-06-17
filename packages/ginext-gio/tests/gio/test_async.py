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

"""Gio async callback signature.

Gio async APIs (file_new_tmp_async, GtkFileDialog.open(), …) call a
finish callback whose C prototype is:

    void cb(GObject *source, GAsyncResult *result, gpointer user_data);

pygobject's convention drops the trailing `user_data` (closure cookie)
when invoking the Python callback. Apps write 2-arg callbacks. Goi
matches via the self-closure marker in closure.c — the trampoline
hides cookie slots unless a Python `user_data` was registered at call
time (in which case it surfaces).

The Gio.Task test below is the deterministic repro of the same gap.
"""

from __future__ import annotations

import types
import contextlib
from collections.abc import Generator
from pathlib import Path
import asyncio
from typing import Any

import pytest

from ginext.namespace import Namespace


@pytest.fixture(scope="module", autouse=True)
def _setup() -> Generator[object]:
    import ginext
    from ginext import features

    ginext.private.require_namespace("Gio", "2.0")
    ginext.private.require_namespace("GLib", "2.0")
    was = features.is_enabled(features.PYGOBJECT_COMPAT)
    features.set_enabled(features.PYGOBJECT_COMPAT, False)
    try:
        yield ginext
    finally:
        features.set_enabled(features.PYGOBJECT_COMPAT, was)


@pytest.fixture
def Gio(_setup: object) -> types.ModuleType:
    from ginext import Gio

    return Gio


@pytest.fixture
def GLib(_setup: object) -> types.ModuleType:
    from ginext import GLib

    return GLib


def _run_loop_with_timeout(loop: Namespace, timeout_ms: int = 1500) -> None:
    from ginext import GLib

    GLib.timeout_add(timeout_ms, loop.quit)
    loop.run()


def test_async_callback_two_args(GLib: Namespace, Gio: Namespace) -> None:
    """When the call site doesn't supply user_data, the Python callback
    fires with exactly 2 positional args (source, result). Matches
    pygobject."""
    arities: list[int] = []
    loop = GLib.MainLoop.new(None, False)

    def cb(*args: Any) -> None:
        arities.append(len(args))
        loop.quit()

    Gio.file_new_tmp_async("pyedit-XXXXXX", GLib.PRIORITY_DEFAULT, None, cb)
    _run_loop_with_timeout(loop)
    assert arities == [2], f"expected [2], got {arities!r}"


def test_async_callback_named_params(GLib: Namespace, Gio: Namespace) -> None:
    """The 2-arg form with named parameters works — same shape as
    real pygobject apps use for `def on_done(source, result):`."""
    captured: dict[str, object] = {}
    loop = GLib.MainLoop.new(None, False)

    def cb(source: object, result: object) -> None:
        captured["source"] = source
        captured["result"] = result
        loop.quit()

    Gio.file_new_tmp_async("pyedit-XXXXXX", GLib.PRIORITY_DEFAULT, None, cb)
    _run_loop_with_timeout(loop)
    assert "result" in captured, "callback didn't fire"
    # result should be a GAsyncResult (or implementer)
    assert captured["result"] is not None


def test_async_ready_callback_drops_user_data(GLib: Namespace, Gio: Namespace) -> None:
    """Gio.Task.new(source, cancellable, callback) → completion fires
    `callback` as AsyncReadyCallback. The Python callable must see
    exactly 2 args (source, result)."""
    received: dict[str, object] = {}

    def cb(source: object, result: object) -> None:
        received["nargs"] = 2
        received["source"] = source
        received["result"] = result

    task = Gio.Task.new(None, None, cb)
    task.return_int(42)
    ctx = GLib.MainContext.default()
    for _ in range(30):
        if "nargs" in received:
            break
        ctx.iteration(False)

    assert received.get("nargs") == 2, (
        f"callback fired with wrong arity (or didn't fire): {received!r}"
    )


def test_interface_async_method_is_wrapped(Gio: Namespace) -> None:
    """`Gio.File.query_info_async` should land as an AsyncCallable on
    the interface class itself, not stay a plain method."""
    from ginext.aio import AsyncCallable

    assert isinstance(Gio.File.query_info_async, AsyncCallable), (
        f"interface async wrap missed: {type(Gio.File.query_info_async).__name__}"
    )


def test_async_call_during_coro_close_returns_awaitable(
    GLib: Namespace, Gio: Namespace
) -> None:
    """A coroutine whose `finally:` awaits an async method must not crash
    when the coroutine is closed by GC."""
    import os
    import tempfile

    class _YieldOnce:
        """Minimal awaitable that suspends the coroutine once without
        needing a running asyncio loop."""

        def __await__(self) -> Generator[None]:
            yield None

    fd, path = tempfile.mkstemp()
    os.close(fd)
    f = Gio.File.new_for_path(path)
    ostream = f.replace(None, False, Gio.FileCreateFlags.NONE, None)

    async def body() -> None:
        try:
            await _YieldOnce()
        finally:
            await ostream.close_async(GLib.PRIORITY_DEFAULT)

    coro = body()
    with contextlib.suppress(StopIteration):
        coro.send(None)
    coro.close()

    Path(path).unlink()


def test_interface_async_returns_future_under_asyncio(
    GLib: Namespace, Gio: Namespace
) -> None:
    """Calling it from inside an asyncio loop should return an
    awaitable asyncio.Future."""

    async def main() -> None:
        f = Gio.File.new_for_path("/tmp")
        fut = f.query_info_async(
            Gio.FILE_ATTRIBUTE_STANDARD_TYPE,
            Gio.FileQueryInfoFlags.NONE,
            GLib.PRIORITY_DEFAULT_IDLE,
        )
        assert isinstance(fut, asyncio.Future)
        assert hasattr(fut, "__await__")
        fut.cancel()

    asyncio.run(main())


def test_static_async_finish_name_with_c_prefix(_setup: object) -> None:
    """Some GIRs spell `glib:finish-func` as the fully-qualified C
    identifier; async wrapping must still find the finish method."""
    import ginext
    from ginext.aio import AsyncCallable

    try:
        ginext.private.require_namespace("GdkPixbuf", "2.0")
    except ImportError:
        pytest.skip("GdkPixbuf typelib not available on this platform")
    from ginext import GdkPixbuf

    assert isinstance(GdkPixbuf.Pixbuf.new_from_stream_async, AsyncCallable), (
        "GdkPixbuf.Pixbuf.new_from_stream_async should be AsyncCallable; "
        "typelib async metadata lookup missed the finish function"
    )
    assert isinstance(GdkPixbuf.Pixbuf.new_from_stream_at_scale_async, AsyncCallable)
    assert isinstance(GdkPixbuf.PixbufAnimation.new_from_stream_async, AsyncCallable)


def test_static_async_under_asyncio_returns_future(_setup: object) -> None:
    """The full path: under an asyncio loop, the static-method async
    call returns an awaitable Future."""
    import ginext

    try:
        ginext.private.require_namespace("GdkPixbuf", "2.0")
    except ImportError:
        pytest.skip("GdkPixbuf typelib not available on this platform")
    from ginext import GdkPixbuf, Gio, GLib

    async def main() -> None:
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(b"not an image"))
        fut = GdkPixbuf.Pixbuf.new_from_stream_async(stream)
        assert isinstance(fut, asyncio.Future)
        assert hasattr(fut, "__await__")
        fut.cancel()

    asyncio.run(main())


def test_inherited_async_method_on_concrete_subclass(
    GLib: Namespace, Gio: Namespace
) -> None:
    """`InputStream.close_async` is wrapped as an AsyncCallable; a
    concrete subclass like `MemoryInputStream` needs to inherit the
    wrap so `istream.close_async(...)` returns a Future."""
    from ginext.aio import AsyncCallable

    assert isinstance(Gio.InputStream.close_async, AsyncCallable)
    assert isinstance(Gio.OutputStream.close_async, AsyncCallable)

    istream = Gio.MemoryInputStream.new_from_data(b"hello")
    assert isinstance(type(istream).close_async, AsyncCallable)

    async def main() -> None:
        fut = istream.close_async(GLib.PRIORITY_DEFAULT)
        assert isinstance(fut, asyncio.Future)
        fut.cancel()

    asyncio.run(main())


def test_concrete_input_stream_async_finish_binding(GLib: Any, Gio: Any) -> None:
    """Concrete Gio.InputStream async methods should await through the generic
    wrapper without rebinding the AsyncResult as ``self``."""
    from ginext import aio

    async def main() -> None:
        data = GLib.Bytes.new(b"hello world")
        stream = Gio.MemoryInputStream.new_from_bytes(data)
        chunk = await stream.read_bytes_async(5, GLib.PRIORITY_DEFAULT)
        assert chunk == b"hello"
        await stream.close_async(GLib.PRIORITY_DEFAULT)

    asyncio.run(main(), loop_factory=aio.EventLoop)
