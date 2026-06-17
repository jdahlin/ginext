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

"""A GLib-backed asyncio event loop with socket support.

`EventLoop` subclasses `asyncio.SelectorEventLoop`, so it inherits all of
asyncio's machinery — `call_soon`, timers, futures, tasks, transports,
`sock_*`, `create_connection` — and therefore runs natively-async socket
libraries (httpx, aiohttp, `asyncio.open_connection`). The difference is the
backend: instead of running a selector, it runs a `GLib.MainLoop` and registers
asyncio's file descriptors as GLib watch sources. One loop, one thread, drives
both GObject/GIO work and asyncio.

Used three ways (all policy-free, the Python 3.13+ approach):

- ``asyncio.run(main, loop_factory=EventLoop)`` — scripts.
- ``EventLoop().run_until_complete(coro)`` — direct.
- ``EventLoop().run_application(app)`` — drive a Gio Application; the
  application's ``run()`` spins the same context, so coroutines started from
  signal handlers are driven by it.

Ported and trimmed from PyGObject's ``gi/events.py`` selector integration
(3.13+ only; no event-loop policy, no win32, no idle-priority tasks).
"""

from __future__ import annotations

import asyncio
import collections
import selectors
import sys
import weakref
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Protocol

from . import GLib, private


class SupportsFileno(Protocol):
    def fileno(self) -> int: ...


# A raw file descriptor or an object exposing one. Defined locally rather than
# imported from `_typeshed.FileDescriptorLike`, which does not exist at runtime
# — and this alias is used as a ``Mapping[...]`` base, which is evaluated
# eagerly even under PEP 563.
FileDescriptorLike = int | SupportsFileno

__all__ = ["EventLoop"]


def _fileobj_to_fd(fileobj: FileDescriptorLike) -> int:
    return fileobj if isinstance(fileobj, int) else fileobj.fileno()


class _EventSource(GLib.Source):
    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return private.glib_event_source_new(cls)


class Source(_EventSource):
    """A GSource that polls the loop's registered fds and dispatches one
    asyncio `_run_once` iteration when fds are ready or a timeout is due."""

    def __init__(self, selector: Selector) -> None:
        super().__init__()
        self._dispatching = False
        self.set_can_recurse(False)
        self.set_name("ginext asyncio integration")
        self._selector = weakref.ref(selector)
        self._ready: list[tuple[selectors.SelectorKey, int]] = []

    def _loop(self) -> EventLoop:
        selector = self._selector()
        assert selector is not None
        return selector._loop

    def prepare(self) -> tuple[bool, int]:
        # FDs are queried in check(); just hand GLib the timeout for the next
        # scheduled asyncio callback.
        return False, self._loop()._get_timeout_ms()

    def check(self) -> bool:
        ready: list[tuple[selectors.SelectorKey, int]] = []
        selector = self._selector()
        assert selector is not None
        for key in selector._fd_to_key.values():
            condition = self.query_unix_fd(selector._fd_to_tag[key.fd])
            events = 0
            if condition & ~GLib.IOCondition.OUT:
                events |= selectors.EVENT_READ
            if condition & ~GLib.IOCondition.IN:
                events |= selectors.EVENT_WRITE
            if events:
                ready.append((key, events))
        self._ready = ready
        if self._loop()._get_timeout_ms() == 0:
            return True
        return bool(ready)

    def dispatch(self, callback: object, args: object) -> bool:
        self._dispatching = True
        try:
            self._loop()._glib_dispatch()
        finally:
            self._dispatching = False
        return GLib.SOURCE_CONTINUE

    def get_ready(self) -> list[tuple[selectors.SelectorKey, int]]:
        ready = self._ready
        self._ready = []
        return ready


class FileObjectMapping(Mapping[FileDescriptorLike, selectors.SelectorKey]):
    def __init__(self, fd_to_key: dict[int, selectors.SelectorKey]) -> None:
        self._fd_to_key = fd_to_key

    def __len__(self) -> int:
        return len(self._fd_to_key)

    def __getitem__(self, fileobj: FileDescriptorLike) -> selectors.SelectorKey:
        value = self._fd_to_key.get(_fileobj_to_fd(fileobj))
        if value is None:
            raise KeyError(f"{fileobj!r} is not registered")
        return value

    def __iter__(self) -> Iterator[int]:
        return iter(self._fd_to_key)


class Selector(selectors.BaseSelector):
    """A selector that registers asyncio's fds with GLib instead of polling."""

    def __init__(self, loop: EventLoop) -> None:
        self._loop = loop
        self._fd_to_key: dict[int, selectors.SelectorKey] = {}
        self._fd_to_tag: dict[int, int] = {}
        self._source: Source | None = Source(self)
        self._map: FileObjectMapping = FileObjectMapping(self._fd_to_key)

    def attach(self) -> None:
        assert self._source is not None
        self._source.attach(self._loop._context)

    def detach(self) -> None:
        if self._source is not None and hash(self._source):
            self._source.destroy()
        self._source = Source(self)
        self._fd_to_tag.clear()
        for key in self._fd_to_key.values():
            self._register_key(key)

    def close(self) -> None:
        if self._source is not None and hash(self._source):
            self._source.destroy()
        self._source = None
        self._fd_to_key.clear()
        self._fd_to_tag.clear()

    def _register_key(self, key: selectors.SelectorKey) -> None:
        assert self._source is not None
        condition = GLib.IOCondition(0)
        if key.events & selectors.EVENT_READ:
            condition |= GLib.IOCondition.IN
        if key.events & selectors.EVENT_WRITE:
            condition |= GLib.IOCondition.OUT
        self._fd_to_tag[key.fd] = self._source.add_unix_fd(key.fd, condition)

    def register(
        self, fileobj: FileDescriptorLike, events: int, data: object = None
    ) -> selectors.SelectorKey:
        if (not events) or (events & ~(selectors.EVENT_READ | selectors.EVENT_WRITE)):
            raise ValueError(f"Invalid events: {events!r}")
        fd = _fileobj_to_fd(fileobj)
        if fd in self._fd_to_key:
            raise KeyError(f"{fileobj!r} (FD {fd}) is already registered")
        key = selectors.SelectorKey(fileobj, fd, events, data)
        self._register_key(key)
        self._fd_to_key[fd] = key
        return key

    def unregister(self, fileobj: FileDescriptorLike) -> selectors.SelectorKey:
        fd = _fileobj_to_fd(fileobj)
        key = self._fd_to_key.pop(fd)
        tag = self._fd_to_tag.pop(fd, None)
        if self._source is not None and hash(self._source) and tag is not None:
            self._source.remove_unix_fd(tag)
        return key

    def select(
        self, timeout: float | None = None
    ) -> list[tuple[selectors.SelectorKey, int]]:
        assert self._source is not None
        return self._source.get_ready()

    def get_key(self, fileobj: FileDescriptorLike) -> selectors.SelectorKey:
        return self._map[fileobj]

    def get_map(self) -> Mapping[FileDescriptorLike, selectors.SelectorKey]:
        return self._map


class EventLoop(asyncio.SelectorEventLoop):
    if TYPE_CHECKING:
        # Private asyncio.BaseEventLoop internals not in typeshed stubs.
        _ready: collections.deque[asyncio.Handle]
        _scheduled: list[asyncio.TimerHandle]
        _selector: Selector

        def _run_forever_setup(self) -> None: ...
        def _run_forever_cleanup(self) -> None: ...
        def _run_once(self) -> None: ...

    def __init__(self) -> None:
        if sys.platform == "win32":
            # The selector integration registers asyncio's fds with the GLib
            # main loop via g_source_add_unix_fd, which is POSIX-only. A win32
            # port would need a different mechanism (e.g. a wakeup socket /
            # WSAEventSelect-backed GPollFD). Not yet implemented.
            raise NotImplementedError(
                "ginext's GLib-backed asyncio EventLoop is not yet supported "
                "on Windows (it relies on the POSIX g_source_add_unix_fd)"
            )
        self._glib = GLib
        self._context = GLib.MainContext.default()
        self._main_loop = GLib.MainLoop.new(self._context, False)
        self._may_iterate = False
        self._quit_funcs: list[Callable[[], object]] = []
        super().__init__(Selector(self))
        # _run_once floors timeouts to 0; keep a small resolution so we do not
        # busy-loop on sub-millisecond timers.
        self._clock_resolution = 1e-3

    # -- clock ----------------------------------------------------------------

    def time(self) -> float:
        return float(self._glib.get_monotonic_time()) / 1_000_000

    def _get_timeout_ms(self) -> int:
        if self._ready:
            return 0
        scheduled = self._scheduled
        if scheduled:
            timeout = int((scheduled[0]._when - self.time()) * 1000)
            return max(timeout, 0)
        return -1

    # -- running --------------------------------------------------------------

    @contextmanager
    def running(self, quit_func: Callable[[], object]) -> Generator[None]:
        self._quit_funcs.append(quit_func)
        if self.is_running():
            try:
                yield
            finally:
                self._quit_funcs.pop()
            return
        self._run_forever_setup()
        try:
            self._may_iterate = True
            self._selector.attach()
            yield
        finally:
            self._may_iterate = False
            self._selector.detach()
            self._run_forever_cleanup()
            self._quit_funcs.pop()

    def _glib_dispatch(self) -> None:
        self._may_iterate = False
        try:
            self._run_once()
        finally:
            self._may_iterate = True

    def run_forever(self) -> None:
        with self.running(self._main_loop.quit):
            self._main_loop.run()

    def run_application(self, app: Any, argv: object = None) -> int:
        """Run a Gio Application with this loop as the running asyncio loop.

        ``app.run()`` spins the same GLib main context, so coroutines started
        with ``asyncio.ensure_future`` / ``create_task`` (e.g. from signal
        handlers) are driven by the application's loop — no second loop runs.
        """
        with self.running(self._main_loop.quit):
            return int(app.run(argv))

    def stop(self) -> None:
        if self._quit_funcs:
            self._quit_funcs[-1]()
        else:
            self._main_loop.quit()
