---
title: Properties
description: What GObject properties are and how to use them in ginext.
sidebar_position: 3
---

# Properties

GObject properties are named values attached to an object type. They are part
of the runtime type system, which means they can be introspected, observed,
bound in UI code, and used consistently across Python and C-backed objects.

In `ginext`, properties are meant to feel like normal Python attributes in
everyday code, while still keeping the parts that make GObject properties
useful.

## Using properties on existing objects

Imported GTK and Gio objects expose their introspected properties directly as
attributes.

```python
from ginext import Gtk

button = Gtk.Button(label="Open")

assert button.label == "Open"
button.label = "Save"
```

This is the normal way to work with properties in `ginext`. You should not
need `obj.props.label` or `obj.get_property("label")` for ordinary code.

Dashed GObject property names are surfaced as underscored Python attributes. If
the underlying property is called `parameter-type`, the Python attribute is
`parameter_type`.

## Python attributes vs GObject properties

A normal Python attribute only lives in Python. A GObject property is richer:

- it has a declared type
- it can be introspected by other tooling
- it can participate in bindings and UI expressions
- it emits change notifications
- it exists on both imported native types and Python-defined GObject types

That is why `ginext` uses plain attribute syntax for both reading and writing,
but still treats properties as part of the object's declared API surface rather
than just instance-dict state.

## Defining properties in Python

Python-defined GObject subclasses declare properties with `GObject.Property`.

```python
from ginext.gobject import GObject


class Document(GObject):
    title: str = GObject.Property(default="")
    modified: bool = GObject.Property(default=False)
```

Instances then use those properties as plain attributes:

```python
doc = Document()
doc.title = "Notes"
doc.modified = True
```

This is the native `ginext` property model: a declared property descriptor with
value-backed storage.

:::note Current limitation
Native `ginext` properties currently use stored values. PyGObject-style
decorator forms and custom `getter=` or `setter=` hooks are not part of the
native property API yet.

If you need computed behavior today, keep that logic in normal Python methods
or `@property` attributes and use `GObject.Property(...)` only for actual
GObject properties.
:::

## Listening for property changes

Property changes emit `notify` signals, which lets other code react when a
value changes.

```python
from ginext import Gtk

button = Gtk.Button(label="Open")


def on_label_changed(source, prop):
    print(prop.name, source.label)

button.notify("label").connect(on_label_changed)
button.label = "Save"
```

For a full explanation of signal connections, see [Signals](./signals.md).

The property name passed to `notify(...)` uses the GObject property name, but
`ginext` accepts the common Python-spelled form as well when they differ.

## When to use a property instead of a Python attribute

Use a GObject property when the value is part of the object's public model and
should work with the wider GObject or GTK ecosystem.

Typical reasons include:

- GTK widgets already expose the value as a property
- other code needs change notification
- the value should participate in bindings or expressions
- the value should be visible through introspection and type metadata

Use a normal Python attribute when the value is only private implementation
state and does not need any of those behaviors.

## `GObject.Value`

`GObject.Value` should mostly disappear from normal Python usage. The intended
surface is that the bindings box and unbox values for you in more places, so
manual value wrapping is much less common than in older binding styles.
