# Subclassing Later

Subclassing should not be the first ginext milestone. It composes too many
runtime pieces:

- GType registration;
- Python-defined properties;
- Python-defined signals;
- vfunc discovery and invocation;
- closure records;
- class initialization ordering;
- template callbacks;
- interface vtables.

The first implementation should make imported objects excellent before asking
Python classes to participate fully in GObject type registration.

## Minimal Early Shape

The earliest useful subclassing story is properties plus signals:

```python
from ginext import GObject

class Item(GObject.Object):
    __gtype_name__ = "ExampleItem"

    title = GObject.Property(str, default="")
    changed = GObject.Signal(str)
```

Expected usage:

```python
item = Item()
item.title = "Hello"
item.changed.emit(item.title)
```

## Defer Vfuncs Until Closure Records Are Solid

Vfuncs are callback ownership with class lifetime. They should use the same
argument conversion, exception policy, and closure inventory as signals and
async callbacks, but with a different owner class.

Do not implement vfuncs as a side path.

## Templates And Builder

Templates need explicit policy for:

- callback lookup in parent classes;
- external callback scopes;
- unused callback handling;
- async template callbacks;
- clearer missing-child errors;
- property bindings in XML.

Templates should wait until closure records have proven signal, async, and
binding-transform clients.

Next: [[9 tests and doctests]]

