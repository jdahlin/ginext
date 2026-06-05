# Native connection records

## Problem

ABI2 originally modeled owner-aware signal lifetime in Python, but the closure
owner needs to live in native state so traversal, clearing,
disconnection, weak notifications, and in-flight invocation all share one
authority.

## Current shape

- `src/_goi/GObject/Closure-record.c` has `GoiClosureRecord`.
- Signal records store source weak edge, optional logical owner weak edge,
  handler id, callback identity, in-flight count, and lifecycle state.
- Owner weak notify disconnects through the native record.
- Source weak notify invalidates the native record.
- `connect_object()` target weak notify clears trampoline call-shape state, then
  asks the native record to disconnect or invalidate the signal.
- Builder/template inventory records also store owner/source/target metadata
  weakly so debug snapshots do not retain or wrap finalized GObjects.
- `src/goi/abi2.py` still adapts Python call signatures and weakens owner
  captures, but it no longer owns the signal lifetime record.

## Why it matters

The hard invariant is:

> A closure's Python references may be exposed to Python GC only if the same
> owner can disconnect or invalidate that native closure during clear.

Some callbacks are owned by native APIs that are not ordinary signal
connections, and some teardown paths enter from GObject finalization rather
than Python object finalization. A native record gives those paths one
ownership vocabulary.

## Issue references

- [#1](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/1):
  proposes first-class signal connection reference management.
- [#36](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/36):
  `connect_object()` must not keep its weak target alive.
- [#557](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/557):
  weak-target connections must also disconnect when the target dies.
- [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735):
  owner-scoped closure cleanup only works if the owner can clear the native
  connection.

## Broken example

```python
closure = source.changed.add(owner.on_changed)

del owner
gc.collect()

source.changed.emit()
```

The intended ABI2 behavior is that deleting `owner` disconnects the handler and
releases the callback. The native signal record now stores the logical owner and
disconnects the handler from owner weak notify.
The returned `goi.Closure` handle caches that native record id, but it keeps the
source weakly so holding the handle for later removal does not extend the
source lifetime.

The remaining architecture question is how far to extend the same native record
machinery into non-signal carriers. `connect_object()` still needs a small
trampoline-local pointer for argument replacement, but lifetime state now flows
through the record.

We are solving this so the object that owns the cleanup decision is the same
object that owns the native closure and Python references.

## Needed design

Use one native closure/connection record with explicit ownership fields:

- closure kind;
- source object or native owner;
- optional lifetime owner;
- optional weak target;
- handler id or native removal token;
- Python callable;
- Python user data;
- destroy notify state;
- in-flight invocation count;
- current lifecycle state.

The record must support idempotent `disconnect`, `invalidate`, `release`, and
`finalize` operations.
