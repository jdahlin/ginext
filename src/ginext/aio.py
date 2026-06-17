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

"""Async support for ginext: a GLib-backed asyncio event loop and the awaitable
for GIO async/finish pairs.

Async work runs on asyncio, two ways:

- ``asyncio.run(coro, loop_factory=aio.EventLoop)`` — explicit, per-call.
- ``aio.install()`` then plain ``asyncio.run(coro)`` / ``Application.run()`` —
  installs the GLib-backed loop as asyncio's default.

Importing this module does not import asyncio; ``EventLoop`` and the awaitable
pull it in lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generator, cast

if TYPE_CHECKING:
    import asyncio

__all__ = ["AsyncCallable", "EventLoop", "NamedReturn", "install"]


class NamedReturn(tuple[Any, ...]):
    """A return tuple that also exposes its OUT-param values by name.

    ginext packages a method's ``(return-value, out1, out2, …)`` as a plain
    tuple. Some APIs (``Gio.DBusProxy.call_with_unix_fd_list`` returning
    ``(GVariant, GUnixFDList)``) read nicer with pygobject's named shape::

        result = await proxy.call_with_unix_fd_list(...)
        fd = result.out_fd_list.get(0)

    Indexing, ``len``, and unpacking behave exactly like a tuple; attribute
    access resolves to the first index whose name matches. ``names`` has one
    entry per item; ``""`` means "no name" (e.g. the bare return-value slot).
    """

    _names: tuple[str, ...]

    def __new__(cls, items: tuple[Any, ...], names: tuple[str, ...]) -> NamedReturn:
        obj = super().__new__(cls, items)
        obj._names = tuple(names)
        return obj

    def __getattr__(self, name: str) -> Any:
        try:
            index = self._names.index(name)
        except AttributeError, ValueError:
            raise AttributeError(name) from None
        return self[index]


def __getattr__(name: str) -> Any:
    # EventLoop pulls in asyncio, so it is loaded lazily to keep
    # `import ginext.aio` free of an asyncio import for callers that never await.
    if name == "EventLoop":
        from ._aioloop import EventLoop

        return EventLoop
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def install() -> None:
    """Install the GLib-backed ``EventLoop`` as asyncio's default loop.

    After this, plain ``asyncio.run(coro)`` and ``Gio.Application.run()``
    use the GLib-backed loop, so GObject/GIO and asyncio share one loop. For a
    single call without global install, use
    ``asyncio.run(coro, loop_factory=aio.EventLoop)`` instead.

    Implemented with an asyncio event-loop policy (deprecated in 3.13, removed
    in 3.16, but still the only global hook); the deprecation warning is
    suppressed. New code should prefer ``loop_factory``.
    """
    import asyncio
    import warnings

    from ._aioloop import EventLoop

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        base_policy = type(asyncio.get_event_loop_policy())

        def new_event_loop(self: object) -> EventLoop:
            return EventLoop()

        policy_cls = type(
            "_GLibEventLoopPolicy",
            (base_policy,),
            {"new_event_loop": new_event_loop},
        )

        try:
            asyncio.set_event_loop_policy(policy_cls())
        except AttributeError:
            pass


def _set_result(future: asyncio.Future[object], value: object) -> None:
    if not future.done():
        future.set_result(value)


def _set_exception(future: asyncio.Future[object], exc: BaseException) -> None:
    if not future.done():
        future.set_exception(exc)


def _coerce_async_value(value: object) -> object:
    """Normalize async finish results to match ginext's sync Python surface."""
    import sys

    ginext = sys.modules.get("ginext")
    if ginext is None:
        return value
    glib = getattr(ginext, "GLib", None)
    if glib is None:
        return value
    bytes_type = getattr(glib, "Bytes", None)
    if bytes_type is not None and isinstance(value, bytes_type):
        return bytes(value.get_data() or b"")
    if isinstance(value, NamedReturn):
        items = tuple(_coerce_async_value(item) for item in value)
        return NamedReturn(items, value._names)
    if isinstance(value, tuple):
        return tuple(_coerce_async_value(item) for item in value)
    return value


class _AsyncOperation:
    """Awaitable wrapping a GIO async operation and its finish function.

    ``start(callback)`` kicks off the GIO ``*_async`` call with our ready
    callback; ``finish(async_result)`` calls the matching ``*_finish`` and
    returns the shaped result (or raises a mapped GError). The operation starts
    when the op is awaited.

    Requires a running asyncio loop (use ``asyncio.run(..., loop_factory=
    EventLoop)`` or ``install()``). ``cancel`` is an optional zero-argument
    callable invoked when the awaiting task is cancelled (typically
    ``Gio.Cancellable.cancel``), propagating task cancellation to the GIO work.
    """

    __slots__ = ("_start", "_finish", "_cancel")

    def __init__(
        self,
        start: Callable[[Callable[[object, object], None]], None],
        finish: Callable[[object], object],
        cancel: Callable[[], None] | None = None,
    ) -> None:
        self._start = start
        self._finish = finish
        self._cancel = cancel

    def __await__(self) -> Generator[Any, None, object]:
        import asyncio

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        if self._cancel is not None:
            cancel = self._cancel

            def on_future_done(fut: asyncio.Future[object]) -> None:
                if fut.cancelled():
                    cancel()

            future.add_done_callback(on_future_done)

        def on_ready(_source: object, result: object) -> None:
            if future.done():
                return
            try:
                value = _coerce_async_value(self._finish(result))
            except Exception as exc:
                loop.call_soon_threadsafe(_set_exception, future, exc)
            else:
                loop.call_soon_threadsafe(_set_result, future, value)

        self._start(on_ready)
        return (yield from future.__await__())


def _bind(fn: Callable[..., Any], obj: object, objtype: object) -> Callable[..., Any]:
    """Bind ``fn`` to ``obj`` via the descriptor protocol, falling back to a
    ``functools.partial`` when the descriptor refuses (e.g. an interface
    method whose owning class is not in the instance's MRO)."""
    from functools import partial

    try:
        descriptor_get = cast("Any", type(fn)).__get__
    except AttributeError:
        return partial(fn, obj)
    try:
        bound = descriptor_get(fn, obj, objtype)
    except AttributeError, TypeError, SystemError:
        bound = None
    if bound is None or bound is fn:
        return partial(fn, obj)
    return cast("Callable[..., Any]", bound)


def _loop_drives_current_context(loop: object) -> bool:
    """True if ``loop`` is a GLib-backed asyncio loop whose GLib MainContext is
    the current thread-default. pygobject only returns an awaitable from an
    async method when this holds; otherwise the call is fire-and-forget."""
    # GLib-backed loops (ginext's EventLoop, gi.events) store their context as
    # the instance attribute ``_context``; read it via __dict__ to avoid both a
    # private-attribute access and a defaulted getattr.
    try:
        ctx = loop.__dict__.get("_context")
    except AttributeError:
        return False
    if ctx is None:
        return False
    import sys

    glib = sys.modules["ginext"].GLib
    current = glib.MainContext.get_thread_default() or glib.MainContext.default()
    return bool(ctx == current)


async def _completed_awaitable() -> None:
    """Immediately-completed awaitable for the no-running-loop fallback (a
    coroutine torn down by GC runs ``finally:`` blocks with no loop attached).
    A coroutine survives ``coro.close()``'s GeneratorExit cleanly, unlike a
    Future which needs a loop."""
    return None


class AsyncCallable:
    """Wraps a GIR ``*_async`` method so calling it returns an ``asyncio.Future``.

    We supply the ``AsyncReadyCallback`` the GIR method expects; when GIO
    invokes it with ``(source, result)`` we call the paired ``*_finish`` method
    and resolve the Future with its return value (or its raised ``GLib.Error``).
    Passing an explicit callback (at the callback slot, as a trailing callable,
    or ``callback=``) falls back to pygobject-style fire-and-forget.

    Acts as a descriptor: when bound to an instance, the underlying async and
    finish callables are bound too, so ``instance.method(…)`` keeps its ``self``.
    ``cb_position`` is the Python-positional index of the callback argument;
    omitted trailing args before it (typically a defaulted ``cancellable``) are
    padded with ``None``.
    """

    __slots__ = ("_async_fn", "_finish_fn", "_cb_position", "_has_self", "_owner_repr")

    def __init__(
        self,
        async_fn: Callable[..., Any],
        finish_fn: Callable[..., Any],
        cb_position: int = -1,
        *,
        has_self: bool = True,
        owner_repr: str = "",
    ) -> None:
        self._async_fn = async_fn
        self._finish_fn = finish_fn
        self._cb_position = cb_position
        self._has_self = has_self
        self._owner_repr = owner_repr

    def __repr__(self) -> str:
        return f"<AsyncCallable {self._owner_repr}>"

    def __get__(self, obj: object, objtype: object = None) -> AsyncCallable:
        if obj is None or not self._has_self:
            return self
        return AsyncCallable(
            _bind(self._async_fn, obj, objtype),
            _bind(self._finish_fn, obj, objtype),
            self._cb_position,
            has_self=self._has_self,
            owner_repr=self._owner_repr,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        import asyncio

        from . import features

        cb_at_slot = 0 <= self._cb_position < len(args) and callable(
            args[self._cb_position]
        )
        if (
            cb_at_slot
            or (args and callable(args[-1]))
            or callable(kwargs.get("callback"))
        ):
            return self._async_fn(*args, **kwargs)

        compat = features.is_enabled(features.PYGOBJECT_COMPAT)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop. Under pygobject-compat this is fire-and-forget
            # (return None, matching pygobject). Natively — typically a
            # coroutine being closed by GC whose `finally:` awaits an async
            # method — hand back a pre-completed awaitable so `await` survives.
            self._async_fn(*args, None, **kwargs)
            return None if compat else _completed_awaitable()

        # pygobject only awaits async methods when the running loop drives the
        # current thread-default GLib context; otherwise it fires-and-forgets.
        if compat and not _loop_drives_current_context(loop):
            self._async_fn(*args, None, **kwargs)
            return None

        future: asyncio.Future[Any] = loop.create_future()
        finish_fn = self._finish_fn

        def _cb(_source: object, result: object, _user_data: object = None) -> None:
            if future.done() or loop.is_closed():
                return
            try:
                value = _coerce_async_value(finish_fn(result))
            except BaseException as exc:
                if not loop.is_closed():
                    loop.call_soon_threadsafe(_set_exception, future, exc)
            else:
                if not loop.is_closed():
                    loop.call_soon_threadsafe(_set_result, future, value)

        if self._cb_position >= 0 and len(args) < self._cb_position:
            pad = [None] * (self._cb_position - len(args))
            args = (*args, *pad, _cb)
        else:
            args = (*args, _cb)
        self._async_fn(*args)
        return future
