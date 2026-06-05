---
title: Subclassing
description: Defining GObject subclasses, overriding vfuncs, and type naming.
sidebar_position: 6
---

# Subclassing

`ginext` lets you define Python subclasses of GObject-based types and use them
like normal GTK or Gio objects. This is where Python-defined properties,
signals, and virtual function overrides come together.

## Defining a subclass

The basic shape is a normal Python class that inherits from a GObject-based
type.

```python
from ginext import Gio
from ginext.gobject import GObject


class Item(GObject):
    title: str = GObject.Property(default="")


class App(Gio.Application):
    pass
```

You can add Python-defined properties and signals on the subclass, and you can
override virtual methods when the parent type exposes them.

## Automatic type name generation

Every GObject subclass needs its own registered type name.

In native `ginext`, the normal case is automatic type-name generation from the
Python class name. You only need to provide an explicit `type_name=...` when
you have a real naming reason, such as avoiding a collision or matching an
existing convention.

That keeps the common case simple while still allowing explicit control when it
is actually needed.

## Signals on subclasses

Python-defined signals use `GObject.Signal(...)`:

```python
from ginext.gobject import GObject


class Source(GObject):
    activated = GObject.Signal(int)

    def do_activated(self, value):
        print("default handler", value)
```

`do_<signal>()` is the default handler for a Python-defined signal. Use the
signal object for connection and emission:

```python
source = Source()
source.activated.connect(on_activated, owner=source)
source.activated.emit(42)
```

For more about signal objects and signal connections, see [Signals](./signals.md).

## Overriding vfuncs

Virtual functions, or vfuncs, are the override points provided by many GObject
types. In Python, they are exposed as `do_<name>` methods on your subclass.

```python
from ginext import Gio


class App(Gio.Application):
    def do_startup(self) -> None:
        super().do_startup()
        print("startup")

    def do_activate(self) -> None:
        print("activate")
```

This is the usual pattern:

- implement `do_<vfunc>()` on the subclass
- chain up to the parent implementation when the parent behavior should still
  run
- keep ordinary public methods and vfunc overrides separate

## Chaining up to the parent implementation

When you override a vfunc, you often still want the parent behavior.

```python
class App(Gio.Application):
    def do_startup(self) -> None:
        super().do_startup()
        self._build_actions()
```

Using `super().do_startup()` is the clearest form. Parent-qualified calls such
as `Gio.Application.do_startup(self)` are also part of the model when you need
them.

## Signals vs vfuncs

Signals and vfuncs are related but not the same thing:

- signals are emitted events that other code can connect to
- vfuncs are override points on a class

The `do_<name>` spelling appears in both areas:

- for Python-defined signals, `do_<signal>()` is the default handler
- for native virtual methods, `do_<vfunc>()` is the override itself

That shared naming is useful, but the concepts are still different and should
be documented separately in code and in API design.
