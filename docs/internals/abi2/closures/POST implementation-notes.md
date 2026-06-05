# Closure Ownership Implementation Notes

This file records the implementation state after moving ABI2 callback
observability and owner-aware signal lifetime into the shared native callback
record registry.

## Implemented

- Added `GoiClosureRecord` in `src/_goi/GObject/Closure-record.c`.
- The raw native inventory API remains `goi._goi._test_list_closures()`.
- The Python debug API is `goi.CallbackRecord._get_current_records()`.
  It returns immutable snapshot records, not live mutable handles.
- ABI2 signal `add()` / `add_after()` now return `goi.Closure` handles
  (`SignalHandler` remains an alias). The handle stores the source weakly,
  exposes `handler_id`, caches the native callback-record `id`, and can return
  its current immutable `record` snapshot while the record is still live.
- Callback records currently expose:
  - `id`
  - `kind`
  - `carrier`
  - `state`
  - `in_flight`
  - `created_at`
  - `state_changed_at`
  - `last_invoked_at`
  - `source`
  - `owner`
  - `weak_target`
  - `handler_id`
  - `callable`
  - `user_callable`
- Signal `GClosure` objects now own a native record.
- Signal dispatch marks the record `in-flight` for the duration of the Python
  callback and restores it to `connected` afterwards.
- Signal connection setup records the source object, handler id, and
  `connect_object()` weak target. Source, owner, and inventory weak-target
  metadata are cleared from native weak-notify hooks.
- ABI2 owner-aware signal connections now attach their logical owner to the
  native record. Owner finalization disconnects through the native record
  state machine instead of a Python-side owner list.
- `Closure.remove()` first asks the native record to disconnect the
  signal handler, so manual removal, owner finalization, one-shot removal, and
  source finalization converge on the same native record path.
- `disconnect_by_func()` now matches the original user callable, not the
  internal user-data trampoline.
- `connect_object()` weak-notify delegates target-death disconnect to the
  native record. The trampoline keeps only the weak target pointer needed for
  swapped call-shape argument replacement.
- FFI callback closures now create records for callback inventory. The current
  classification covers:
  - `async-callback`
  - `binding-transform`
  - `factory`
- `scope=async` callback closures are released after their one-shot callback
  invocation, which drops callback and user-data references.
- `scope=notified` callback closures with GIR destroy metadata pass the native
  closure cookie as omitted user data and install the closure destroy function
  in the paired C destroy-notify slot. The callback trampoline hides that cookie
  from Python while still allowing native destroy to release the closure record.
- `Object.bind_property_full()` adapts the closure-based GIR surface back to
  the expected Python transform callback shape and avoids retaining bound
  method owners.
- Gtk template and `BuilderCScope` callback paths register
  `builder-template` inventory records.
- Vfunc override installation registers `vfunc` records with `class-owned`
  state.

## Still Open

- The record registry intentionally avoids taking strong references to source,
  owner, and weak-target GObjects to prevent ownership cycles. `connect_object()`
  still has trampoline-local weak-target call-shape state, but disconnect and
  inventory metadata now flow through the native record.
- Reported template callback leaks are now pinned by a strict xfail in
  `tests/closure/test_reported_leak_regressions.py`: builder-template records
  still keep a bound callback whose `__self__` is the template widget.
- `scope=forever` callbacks still require an explicit higher-level removal
  operation or are intentionally process-lifetime.

## Tests

Current closure contract status:

```sh
uv run pytest tests/closure -q -n 0
# 33 passed, 1 xfailed
```

Additional regression coverage run:

```sh
uv run pytest tests/test_GObject_Object_signal.py tests/test_GObject_Object_signal_handler.py tests/test_abi2_signals.py tests/test_abi2_signal_handler_invocation.py -q -n 0
# 30 passed, 15 skipped

uv run pytest tests/test_gi_marshalling_tests.py tests/test_abi2_scoped_callbacks.py -q -n 0
# 1090 passed
```
