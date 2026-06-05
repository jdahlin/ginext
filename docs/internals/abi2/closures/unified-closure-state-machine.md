# Unified closure state machine

## Problem

goi currently has multiple closure implementations and callback wrappers with
different lifetime rules:

- libffi GIR callback closures;
- GObject signal closures;
- `connect_object()` trampolines;
- ABI2 owner-aware signal records;
- overlay packed callbacks;
- vfunc callbacks;
- async callbacks;
- Builder/template callbacks;
- binding and factory callbacks.

Each path solves part of the problem, but the ownership rules are not yet one
shared model.

## Why it matters

Callback argument shaping can be shared, but ownership cannot be hidden behind a
generic callback path. A signal connection, async operation, vfunc, property
binding transform, and template callback all have different native owners and
different teardown triggers.

Without one state model, fixes tend to be local:

- leak rather than free too early;
- store raw `GObject *` in one path but Python refs in another;
- disconnect by callable identity in one path but by handler object elsewhere;
- weaken closures in ABI2 but not in Builder or factory callbacks.

## Issue references

- [#43](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/43):
  marshaling leak cleanup spans ordinary calls, closures, and vfunc reverse
  marshalling.
- [#69](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/69):
  callable cache for signal and vfunc closures argues for shared callable
  infrastructure while preserving different ownership classes.
- [#102](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/102):
  cleanup must distinguish native callback slots, not just callback/destroy
  function pairs.
- [#158](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/158):
  closure registries need thread-aware invalidation.
- [#614](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/614),
  [#634](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/634), and
  [#736](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/736):
  bindings, factories, and templates show that signal connections are only one
  closure owner class.

## Broken example

```python
class View(Gtk.Box):
    def __init__(self):
        super().__init__()
        self.button.clicked.add(self.on_clicked)
        self.model.bind_model(self.create_row)
        self.bind_property(
            "title",
            self.label,
            "label",
            transform_to=lambda binding, value: self.format_title(value),
        )

    def on_clicked(self, button):
        ...

    def create_row(self, item):
        ...
```

These callbacks are all "Python callable stored for later native invocation",
but today they naturally fall into different implementation paths: signal
closure, factory callback, and binding transform. Fixing only one path leaves
the others with the same retention and cleanup problems.

We are solving this so each callback kind can have specialized native removal
operations while sharing one lifecycle vocabulary: owner, source, target,
state, in-flight count, Python refs, and destroy notify.

## Needed design

Define one internal closure record shape with pluggable ownership operations.

Core fields:

- kind;
- state;
- Python callable;
- user-facing callable identity;
- Python user data;
- native closure pointer or function pointer;
- source/storage owner;
- logical owner;
- weak target;
- handler id or removal token;
- destroy notify state;
- in-flight count.

Core operations:

- invoke;
- disconnect;
- invalidate;
- release Python references;
- native destroy notify;
- source finalized;
- owner finalized;
- weak target finalized.

The implementation can still have specialized fast paths, but they should all
map onto this lifecycle model.

## Debug inspection API

The unified record should expose a debug live inventory API so ownership tests
and debugger sessions can assert state directly instead of inferring it from
weakrefs, refcounts, or handler side effects.

Internal native shape:

```python
goi._goi._test_list_closures() -> list[dict[str, object]]
```

Python snapshot shape:

```python
goi.CallbackRecord._get_current_records() -> list[goi.CallbackRecord]
```

Signal connections also return a weak-source handle backed by the same record:

```python
closure = source.changed.add(owner.on_changed)
closure.id         # GoiClosureRecord id
closure.handler_id # GSignal handler id
closure.record     # current goi.CallbackRecord snapshot, or None
closure.remove()
```

Each snapshot record should include at least:

- `id`;
- `kind`;
- `carrier`;
- `state`;
- `in_flight`;
- `created_at`;
- `state_changed_at`;
- `last_invoked_at`;
- `source`;
- `owner`;
- `weak_target`;
- `handler_id`;
- `callable`;
- `user_callable`.

This API should be private-ish, unstable, and intended only for tests and
debugger work. `CallbackRecord` values are immutable snapshots, not handles
back into the native registry.
