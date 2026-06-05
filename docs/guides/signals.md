---
title: Signals
description: Signal connections, conflicts, and Python-defined signals.
sidebar_position: 5
---

# Signals

Signals are documented as a distinct surface rather than a variation of method
calls.

## Connecting to signals

The native API uses signal objects instead of `obj.connect(...)`:

```python
obj.signal_name.connect(callback)
```

This makes signal access more explicit, improves completion, and leaves room
for connection policies such as owner-aware lifetimes.

## Method and signal name conflicts

Some APIs have both a method and a signal with the same normalized Python name.
The main example is `Gio.SimpleAction.activate`.

```python
from ginext import Gio

action = Gio.SimpleAction.new("save", None)

action.activate.connect(on_activate, owner=action)
action.activate(None)
```

This imported-style callable signal object should stay a documented special case
rather than the general pattern for Python-defined classes.

## Defining new signals

Python-defined signals use `GObject.Signal(...)`:

```python
from ginext.gobject import GObject


class Source(GObject):
    activated = GObject.Signal(int)

    def do_activated(self, value):
        print("default handler", value)
```

Use the signal object for connection and emission:

```python
source = Source()
source.activated.connect(on_activated, owner=source)
source.activated.emit(42)
```

Prefer `do_<signal>()` for default behavior instead of giving a public method
and a signal the same name.

## More signal topics

This guide is also the right home for:

- callback parameter truncation rules
- connection lifetime and leakage behavior
- owner-aware connection policies

For subclassing, vfunc overrides, and type naming, see [Subclassing](./subclassing.md).
