# Async functions in C

> The `_async`/`_finish` pattern: how to write async functions in C so that goi users can `await` them from Python.

## What this chapter covers

- The pattern: `foo_bar_async(self, ..., cancellable, callback, user_data)` + `foo_bar_finish(self, result, error)`.
- Implementing with `GTask`:
    - `g_task_new(self, cancellable, callback, user_data)`.
    - `g_task_set_task_data` for state.
    - Returning results via `g_task_return_pointer` / `_boolean` / `_int` / `_error`.
- Running work on a thread: `g_task_run_in_thread`, thread-safe completion.
- Cancellation: checking `g_cancellable_is_cancelled`, propagating to nested operations.
- Annotations specific to async:
    - `(scope async)` on the callback parameter.
    - `(closure ...)` linking user_data.
- goi's `await` integration: how it inspects async/finish pairs and exposes them as awaitables.
- Common mistakes:
    - Returning a value without a matching `_finish` signature.
    - Calling the callback synchronously.
    - Ignoring the cancellable.

## What you'll be able to do

- Write `_async`/`_finish` pairs in C that work seamlessly with `await` in goi.
- Run thread-pool work in C and complete cleanly on the main loop.

## Notes for the writer

- Cross-link to [GIO and async](../building/gio-and-async.md) for the Python-side picture.
- One worked example: a "compute the prime factors of N" async function on a thread pool, awaited from Python.
