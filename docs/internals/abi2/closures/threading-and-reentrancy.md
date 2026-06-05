# Threading and reentrancy

## Problem

Closure teardown can happen through several paths: Python GC, GObject weak
notify, signal disconnect, native destroy notify, source finalization, owner
finalization, and callback invocation itself. These paths can be reentrant and
may eventually need to work without relying on the GIL as the only serializer.

## Current shape

- Signal closure marshal and finalize paths acquire the GIL.
- libffi callback invocation acquires the GIL unless the caller already holds it
  for `scope=call`.
- `connect_object()` weak notify disconnects the source handler.
- ABI2 Python records call back into source disconnect and weak-ref unref paths.

## Risks

- disconnect while a callback is in flight;
- owner finalization during callback invocation;
- source destruction during callback invocation;
- weak notify running while Python references are being released;
- double cleanup through both explicit handler removal and native invalidation;
- future free-threaded Python removing assumptions that the GIL serializes all
  closure bookkeeping.

## Issue references

- [#158](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/158):
  closure list memory corruption around cross-thread GC and disconnect.
- [#694](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/694):
  CPython refcounting changes show why lifetime tests should assert semantic
  cleanup rather than incidental refcounts.
- [#235](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/235):
  GLib async callbacks can surprise users with thread/main-context behavior.
- [#382](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/382):
  async buffer lifetime failures are a concrete callback lifetime and
  in-flight ownership risk.

## Broken example

```python
def on_changed(source):
    handler.remove()
    owner.close()


handler = source.changed.add(on_changed, owner=owner)
source.changed.emit()
```

The callback removes its own connection and may trigger owner/source teardown
while the native closure is still in the invocation stack. Another path might
also be running a weak notify or explicit disconnect. Without an in-flight
state and idempotent teardown, the implementation can release Python references
too early, leak them forever, or release them twice.

We are solving this so every teardown path can safely converge on the same
record state, even when cleanup happens during callback invocation.

## Needed design

The native closure record needs an explicit state machine and idempotent
cleanup. It should support at least:

- connected;
- disconnecting;
- disconnected;
- invalidated;
- finalized;
- in-flight invocation count.

Destroy and disconnect paths should be safe to call repeatedly and in any
order. Final Python reference release should happen after the record is no
longer reachable from native invocation paths.
