# Async Cancellation

Python async code and GIO async code have two different cancellation models:

- `asyncio.Task.cancel()` cancels the Python coroutine that is awaiting.
- `Gio.Cancellable.cancel()` requests cancellation of the underlying GIO work.

Those models overlap, but they are not the same thing.

## Two Layers

### Python task cancellation

Task cancellation is part of `asyncio` control flow.

When `task.cancel()` is called, `asyncio` injects `CancelledError` into the
coroutine at its next suspension point. This means:

- the awaiting coroutine stops unless it catches the exception;
- structured-concurrency helpers such as `TaskGroup` and `asyncio.timeout()`
  work as expected;
- cancellation is scoped to that task, not automatically to unrelated native
  work.

Task cancellation does not by itself tell GIO to stop a file read, D-Bus call,
stream close, or other native operation.

### `Gio.Cancellable`

`Gio.Cancellable` is a GIO cancellation token.

It exists so native operations can share, observe, and react to cancellation.
This means:

- a GIO async or blocking call can poll or subscribe to cancellation;
- one cancellable can cancel several related operations;
- cancellation can be triggered from another thread;
- code that is not using `asyncio` can still participate.

A cancellable does not by itself cancel a Python coroutine or inject
`CancelledError` into an `asyncio.Task`.

## Waiter Versus Work

A useful mental model is:

- task cancellation cancels the waiter;
- cancellable cancellation cancels the work.

Often one task is awaiting one operation, so the distinction is easy to miss.
It becomes important as soon as there are multiple layers, shared operations, or
thread boundaries.

For example, if a coroutine awaits `await file.read_bytes()`, task cancellation
means "this coroutine should stop waiting". A `Gio.Cancellable` means "the
underlying file operation should stop if possible".

A good binding should connect those two layers without forcing users to manage
both for ordinary code.

## Threads And Shared Operations

The difference matters most when the underlying work is not owned by exactly one
Python task.

### Cross-thread cancellation

`asyncio.Task` is tied to one event loop in one thread. Cancelling it affects
that task's coroutine state, but does not automatically signal native work
running elsewhere.

`Gio.Cancellable` is designed for the native side. It can be passed into work
that may complete in another thread or main-context iteration, then cancelled by
another thread that still holds the object.

### Shared cancellation scope

Sometimes several operations should stop together:

- a directory traversal plus child metadata queries;
- a request plus follow-up content reads;
- a UI action that fans out into several GIO calls.

One shared `Gio.Cancellable` models that relationship naturally. A single task
cancellation usually does not.

### Non-`asyncio` callers

GIO callbacks, worker threads, sync wrappers, and compatibility-surface code may
need cancellation even when no Python task exists. `Gio.Cancellable` remains the
common mechanism across those entry points.

## ABI2 Policy

ABI2 should make Python task cancellation the default user model for awaitable
operations.

For an awaitable ABI2 method with a documented async plan:

1. the wrapper creates or acquires a `Gio.Cancellable` for the underlying GIO
   operation;
2. if the awaiting Python task is cancelled, ABI2 cancels that underlying
   cancellable;
3. the await raises `asyncio.CancelledError`;
4. if the underlying `GError` is available, ABI2 may attach it as
   `CancelledError.__cause__`.

This preserves normal Python async behavior while still stopping the native work
when the underlying API supports cancellation.

Advanced callers may still need an explicit `cancellable=` parameter when they
want:

- one cancellation token shared across several operations;
- cancellation initiated from another thread or callback-based API;
- interoperation with existing GIO-style code that already models cancellation
  explicitly.

That explicit parameter should be treated as an advanced escape hatch, not as
the default story for simple `await` usage.

## Error Mapping Rule

ABI2 should keep task-driven cancellation distinct from native cancellation
reported independently by the C API.

- If Python task cancellation caused ABI2 to cancel the underlying operation,
  raise `asyncio.CancelledError`.
- If the native operation reports `G_IO_ERROR_CANCELLED` independently, raise
  the normal GIO error type with cancellation metadata intact.

That distinction keeps `asyncio` semantics correct without hiding genuine native
error information.

## Example

Conceptually, ABI2 should let application code write:

```python
import asyncio
from ginext import Gio


async def main():
    task = asyncio.current_task()
    assert task is not None

    op = asyncio.create_task(Gio.File("/tmp/data.txt").read_bytes())
    op.cancel()

    try:
        await op
    except asyncio.CancelledError:
        print("read cancelled")
```

The user-facing cancellation action is on the task. ABI2 is responsible for
propagating that to the underlying `Gio.Cancellable` when the wrapped GIO call
supports it.

## Design Summary

For ABI2, the default answer to "how do I cancel this awaitable operation?"
should be: cancel the Python task.

For advanced cases involving threads, grouped work, or explicit interoperation,
`Gio.Cancellable` remains the lower-level primitive that ABI2 uses internally
and may expose deliberately.

See also:

- [ABI2 Error Domains](abi2/errors.md)
- [ABI2 Methods](abi2/methods.md)
- [ABI2 Native Surface](abi2/abi2.md)
