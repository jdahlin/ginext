# GIO and async

> GIO is the I/O and concurrency layer underneath GTK: files, streams, network, processes, tasks. This is also where goi's `async`/`await` bridge to GIO async methods lives.

## What this chapter covers

- The GLib main loop: who runs it, what runs *on* it, why almost all UI code is single-threaded.
- `Gio.File` and `Gio.Stream`: opening, reading, writing, copying, monitoring.
- Sync vs async APIs: every blocking GIO function has an `_async` / `_finish` pair.
- The goi `await` bridge: how `await some_method_async(...)` works and what it returns.
- `Gio.Task` and writing your own async operations.
- `Gio.Cancellable`: cooperative cancellation propagated through async chains.
- Timers and idle work: `GLib.timeout_add`, `GLib.idle_add`, source priorities.
- Threading the right way: `GLib.Thread`, `Gio.ThreadPool`, marshaling results back to the main context.
- Subprocesses: `Gio.Subprocess`, capturing output, async wait.
- File monitoring: `Gio.FileMonitor`.
- Sockets and networking (brief; point at `libsoup` for HTTP).
- Common pitfalls: blocking the main loop, busy loops, forgetting to chain cancellables.

## What you'll be able to do

- Do file I/O without blocking the UI.
- Compose async operations with `await`.
- Wire up cancellation across long-running operations.
- Run CPU-bound work on a thread without freezing the UI.

## Notes for the writer

- The goi `await` integration is a major selling point — show it early in the chapter.
- Include a "main loop fairness" sidebar: how to keep the UI responsive during big jobs.
- Cross-link to [Dialogs](dialogs.md) (which uses the same async patterns) and to Part III ([DBus](../system/dbus.md)) where async really pays off.
