# Objects, Methods, And Properties

Native `ginext` objects should feel like ordinary Python objects, while still
preserving GObject identity and ownership underneath.

```pycon
>>> from ginext import Gio
>>> action = Gio.SimpleAction.new("save", None)
>>> action.__ginext_abi__
'native-v2'
```

## Methods

Unconflicted methods use their natural Python names:

```pycon
>>> cancellable = Gio.Cancellable.new()
>>> cancellable.cancel()
>>> cancellable.is_cancelled()
True
```

Native object arguments are unwrapped at the call boundary, and returned
GObjects are wrapped back into native objects.

```pycon
>>> store = Gio.ListStore.new(item_type=Gio.FileInfo)
>>> info = Gio.FileInfo()
>>> store.append(info)
>>> store.get_item(0) == info
True
```

## Properties

Properties are plain values, not helper proxies:

```pycon
>>> action = Gio.SimpleAction.new("save", None)
>>> action.enabled
True
>>> action.enabled = False
>>> action.enabled
False
```

Class access to Python-defined properties returns the descriptor. Instance
access returns the value.

```python
class Item(GObject.Object):
    __gtype_name__ = "ExampleItem"
    title = GObject.Property(str, default="")

Item.title      # descriptor
Item().title    # str
```

## Shared Namespace

Methods, properties, and signals share one Python attribute namespace. A name
must never silently prefer one kind over another.

Pure method/signal conflicts use one `MethodSignal` object:

```pycon
>>> action = Gio.SimpleAction.new("save", None)
>>> callable(action.activate)
True
>>> hasattr(action.activate, "add")
True
```

Property-involved conflicts use escaped names:

```python
widget.has_focus_        # property
widget.has_focus_func()  # method
widget.has_focus_signal  # signal, if present
```

The unsuffixed conflicting name should raise a clear `AttributeError`.

## Implementation Notes

- The generator should know each type's visible methods, properties, and
  signals.
- Attribute lookup can be mostly generated metadata plus a small native object
  wrapper.
- `tp_getattro` / `tp_setattro` may need C support for fast and correct
  property access.

Next: [[5 signals and ownership]]
