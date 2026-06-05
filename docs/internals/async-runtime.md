# Async Runtime

Implementation notes and decisions for ginext's async support: the awaitable
wrapper for GIO async/finish pairs and the GLib-backed asyncio event loop.

This is the *how it is built* companion to the design docs:
[Async cancellation](async-cancellation.md), [ABI modes](abi-modes.md) (async
policy section), and [ABI2 async inventory](abi2/async.md).

## Status

- Implemented and tested: the async runtime (`ginext/aio.py`,
  `ginext/_aioloop.py`), both cancellation directions, and `aio.EventLoop`.
- Not yet wired: making `*_async` methods *automatically* awaitable on the
  class. That is blocked on the `native-v2` / `compat-v1` ABI profile split
  (see [Blocked: automatic wrapping](#blocked-automatic-wrapping)).

## Components

### `aio._AsyncOperation` — the awaitable

Wraps a GIO `*_async` / `*_finish` pair. `start(callback)` kicks off the async
call with our ready callback; `finish(async_result)` calls the matching
`*_finish` and returns the shaped result (or raises a mapped `GError`). The
operation starts when the op is awaited, not when constructed.

It is asyncio-only: `__await__` calls `asyncio.get_running_loop()`,
`loop.create_future()`, and resolves via `loop.call_soon_threadsafe`. It
requires a running asyncio loop — i.e. `asyncio.run(..., loop_factory=
EventLoop)` or `install()`. (asyncio is imported lazily inside `__await__`, so
`import ginext.aio` stays asyncio-free.)

### `aio.install()`

Installs `EventLoop` as asyncio's default loop (via an event-loop policy, with
the deprecation warning suppressed), so plain `asyncio.run(coro)` and Gio/Gtk
`Application.run()` use the GLib-backed loop. For a single call without a global
install, use `asyncio.run(coro, loop_factory=aio.EventLoop)`.

### `aio.EventLoop` — the GLib-backed asyncio loop

A real asyncio event loop whose work runs on a `GLib.MainLoop`, so GObject/GIO
code and asyncio code share one loop in one thread. Used via the modern entry
point:

```python
import asyncio
from ginext import aio
asyncio.run(main(), loop_factory=aio.EventLoop)
```

It subclasses `asyncio.SelectorEventLoop` and backs the selector with GLib: each
asyncio file descriptor is registered as a `GLib.Source` fd watch
(`add_unix_fd`), and `run_forever` runs a `GLib.MainLoop` that drives one
`_run_once` per dispatch. Inheriting `SelectorEventLoop` means all of asyncio's
machinery works — `call_soon` (via the self-pipe), timers, tasks, futures,
`gather`, transports, `sock_*`, and `create_connection` — so **natively-async
socket libraries (httpx, aiohttp, `asyncio.open_connection`) run on it**, on the
same loop as GObject/GIO. Ported and trimmed from PyGObject's `gi/events.py`
(3.13+ only; no event-loop policy, no win32, no idle-priority tasks).

`EventLoop.run_application(app, argv=None)` is the async story for
`Gio`/`Gtk` `Application.run()`: it marks the loop running (via
`_run_forever_setup`) and then calls `app.run()`, which spins the same GLib
main context the loop schedules onto. So coroutines started with
`asyncio.ensure_future` / `create_task` from signal handlers are driven by the
application's own loop — GTK and asyncio share one loop in one thread, and no
second loop is run.

```python
def on_activate(app):
    asyncio.ensure_future(some_coroutine())   # driven by app.run()
app.activate.connect(on_activate)
aio.EventLoop().run_application(app)
```

Native-async sockets work on the loop (it is a `SelectorEventLoop`), so
`httpx`/`aiohttp`/`asyncio.open_connection` are supported; `asyncio.to_thread`
remains the way to integrate *blocking* libraries. Timer/task asyncio (`sleep`,
`gather`, `wait_for`, `TaskGroup`, `to_thread`) works too.

### `Gio.FileEnumerator` async iteration

`Gio.FileEnumerator` supports `async for`, fetching `Gio.FileInfo` in batches
via `next_files_async` / `next_files_finish`:

```python
enumerator = directory.enumerate_children("standard::name", 0, None)
async for info in enumerator:
    ...
```

`__aiter__` returns a small iterator that awaits a `_AsyncOperation` per batch
(default 16) and yields each `FileInfo`, raising `StopAsyncIteration` when a
batch comes back empty. It mirrors the existing synchronous `__iter__` /
`__next__` (which yield `FileInfo` via `next_file`) and is the building block
for a future `File.iterdir()`. Batch state lives on the per-iteration object,
not on the shared enumerator.

### `GICallableInfo.is_async` (C)

`gi_callable_info_is_async` is surfaced on the callable-info wrapper. It is the
correct, additive gate for future automatic async wrapping (it is `True` for
real async sources and `False` for finish-less legacy `*_async` such as
`replace_contents_bytes_async`). Nothing in dispatch uses it yet.

## Decisions

### asyncio is never imported at namespace load, and stays lazy

`import asyncio` costs ~25-30 ms (self+children). `_AsyncOperation.__await__`
imports asyncio lazily (inside the method), so it is only paid when something is
actually awaited. `aio.EventLoop` lives in a separate module (`_aioloop.py`)
loaded lazily through `aio.__getattr__`, so `import ginext.aio` — and every
non-asyncio user — pays nothing.

### `aio.EventLoop` is a loop, used via `loop_factory`, not a policy

asyncio event-loop *policies* are deprecated and being removed in Python 3.16.
PyGObject's own `gi.events` migrated to support
`asyncio.run(coro, loop_factory=GLibEventLoop)` for exactly this reason
(pygobject commit *"events: Add support to work without an EventLoopPolicy"*).
We build only the loop class and rely on `loop_factory`; no policy.

### Python 3.13+ only; trimmed port

The loop relies on `BaseEventLoop._run_forever_setup` / `_run_forever_cleanup`
(cpython 3.13+) for running-loop bookkeeping. It ports PyGObject's
`gi/events.py` selector integration (including socket reader/writer support) but
drops, with rationale confirmed from its git history:

- **Per-task GLib idle priority** (`_glib_idle_priority`, the second GSource) —
  a nice-to-have (pygobject *"Support setting idle priority for tasks"*).
- **Nested main-context iteration guards** (`paused()`, `set_can_recurse`) —
  defensive handling for code that iterates the main context while the loop
  runs; pygobject's own commit notes *"No one should do this, but it might
  happen when porting."*
- **win32 / ProactorEventLoop** support.
- **The event-loop policy and its `_loops` registry** — superseded by
  `loop_factory`.

### Cancellation has two distinct directions

Per [async cancellation design](async-cancellation.md):

- **asyncio task cancel → `asyncio.CancelledError`.** `_AsyncOperation` takes an
  optional `cancel` callable; in the asyncio branch it registers
  `future.add_done_callback` so a cancelled task cancels the underlying
  `Gio.Cancellable`. The cancel chain is pure asyncio plus a synchronous
  cancel, so it does not require the GLib loop to be pumping.
- **Native / external cancel → `GLib.Error` (`G_IO_ERROR_CANCELLED`).** The GIO
  ready callback delivers a CANCELLED `GError`, `finish` raises it, and the
  await re-raises it — a cancellable cancels the *work*, not the asyncio
  *waiter*.

The two are disambiguated by future state (`future.cancelled()` vs an exception
set on the future); whichever fires first wins, the other no-ops.

### Error-class mapping depends on feature flags

A cancelled op raises `Gio.CancelledError` only when
`GERROR_BUILTIN_EXCEPTIONS` is on. That flag is forced **off** when
`PYGOBJECT_COMPAT` is on, and the test session enables compat
(`conftest.py`), so tests assert on the `GLib.Error` catch-all plus
`err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)`. This is not a
bug; it is the documented catch-all contract.

### No user-facing `cancellable=` yet

The awaitable manages a `Gio.Cancellable` internally (to support task-cancel
propagation). A user-facing `cancellable=` for sharing one token across
operations, and possibly a `.cancel()` on the returned future for the native
runner, are deferred.

### `Gio.Cancellable` is a context-manager cancel scope

`Gio.Cancellable` supports the context-manager protocol so a block can bound a
cancellation scope:

```python
with Gio.Cancellable() as c:
    ...                       # c is the current cancellable inside the block
# leaving the block cancels c (cleanly or via exception), so work tied to it
# stops
```

`__enter__` calls `push_current()` and returns `self`; `__exit__` calls
`pop_current()` and `self.cancel()`. This is the shared-scope use case from
[async cancellation](async-cancellation.md) (a file manager cancelling a
directory's in-flight loads on navigate) and nests naturally — an inner scope
restores the enclosing one on exit.

Decisions:

- **Cancel on every exit**, not only on error. Unlike Django's
  `transaction.atomic()` (commit on success), a cancellable's lifetime is the
  block; a cancel after the work is already awaited is a no-op, and stragglers
  are stopped. For a token that outlives a block, do not use `with` — keep an
  explicit `Gio.Cancellable()` and pass it around.
- **`push_current` (thread-local) is sufficient for the synchronous scope** and
  is GIO's own ambient mechanism. It is *not* enough once async operations
  auto-pick-up the ambient token: coroutines interleave on one thread, so a
  thread-local would leak the scope across coroutines. When async auto-pickup
  lands, the scope must also set a `contextvars.ContextVar` (copied per task,
  as trio/anyio cancel scopes do), and the awaitable reads that — not
  `get_current()`.

Still deferred: async operations inside the scope do **not** yet auto-use the
ambient cancellable (that needs the `cancellable=` plumbing and the contextvar
ambient), and nested scopes are not yet auto-chained via
`g_cancellable_connect` (parent-cancel propagating to children).

## Blocked: automatic wrapping

The goal is for any typelib-async method to become awaitable straight from the
class builder (call without a callback → awaitable; with a callback → legacy
fire-and-forget). A generic wrapper in `make_method` was prototyped and
reverted because the runtime currently has **one** ABI profile: the compat
surface (`gi.repository`) and native surface share the same class objects, so
wrapping `*_async` there breaks PyGObject's locked contract:

- no running loop → returns `None` (not an awaitable);
- wrong thread-default context → returns `None`;
- the callback may be passed positionally with a trailing `user_data`
  (`delete_async(0, None, cb, None)`), which a naive "last arg is callable"
  check misclassifies.

These are genuinely contradictory with the native runner (which wants an
awaitable when no asyncio loop is running). Resolving it cleanly requires the
`native-v2` / `compat-v1` profile split from [ABI modes](abi-modes.md): native
classes get the awaitable wrapping, compat classes keep PyGObject semantics.
`is_async` is the staged gate for when that lands.

## Limitations

- `aio.EventLoop` uses the default main context on the main thread; it does not
  push a thread-default context for worker threads.
- No re-entrancy guard for nested GLib iteration during dispatch.
- No per-task GLib idle priority; no win32/Proactor support.

## Code and tests

- `src/ginext/aio.py` — `_AsyncOperation` (asyncio-only awaitable), `install()`,
  and the lazy `EventLoop` export.
- `src/ginext/_aioloop.py` — `EventLoop`.
- `src/ginext/_overlays/Gio.py` — `Gio.Cancellable.__enter__` / `__exit__`
  (the context-manager cancel scope) and `Gio.FileEnumerator.__aiter__`
  (async iteration over `FileInfo`).
- `src/ginext/private/GIRepository/CallableInfo.c` — `is_async` accessor.
- `src/ginext/tests/gio/test_gfile.py` — await completion, parity with the
  blocking call, both cancellation directions, and async iteration over a
  `Gio.FileEnumerator`, all driven by `asyncio.run(..., loop_factory=EventLoop)`.
- `src/ginext/tests/gio/test_aio_eventloop.py` — `EventLoop` as a real asyncio
  loop: scheduling, timers, exceptions, cancellation, and concurrency with
  other tasks running during GIO I/O.
