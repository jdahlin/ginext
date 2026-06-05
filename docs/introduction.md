## Rationale

- PyGObject is old and has implemented GObject concepts in a way that is non-straight forward for new users.

Major API changes:

### GObject default constructors

### GObject properties: defining new

### GObject properties: accessing existing

### Signal connections

`obj.connect("signal-name", callback)` becomes `obj.signal_name.connect(callback)`

Rationale: 
- signal connections are a different concept than method calls
- the shared namespace policy means that signals must be accessed through an explicit attribute. 
- The new API is more discoverable, supports IDE completion, and allows for owner-aware connections.

#### Method/signal name conflicts

Some APIs have a method and a signal with the same normalized Python name. The
main example is `Gio.SimpleAction.activate`: `Gio.Action.activate()` is a
method, while `GSimpleAction::activate` is a signal.

Ginext exposes this as a callable signal object:

```python
from ginext import Gio

action = Gio.SimpleAction.new("save", None)

action.activate.connect(on_activate, owner=action)  # signal connection
action.activate(None)                              # method call
```

This shape is reserved for real imported method/signal conflicts. For
Python-defined classes, prefer a separate signal descriptor and a `do_signal`
default handler.

### Defining new signals

Declare Python-defined signals with `GObject.Signal(...)`:

```python
from ginext.gobject import GObject


class Source(GObject, type_name="ExampleSource"):
    activated = GObject.Signal(int)

    def do_activated(self, value):
        print("default handler", value)
```

Use the signal through the signal object:

```python
source = Source()
source.activated.connect(on_activated, owner=source)
source.activated.emit(42)
```

Prefer `do_<signal>()` for default behavior. Avoid giving the public method and
signal the same name unless you are intentionally modelling an imported-style
method/signal conflict.

### GObject subclass type names

Native `ginext` subclassing should not use `__gtype_name__`. The preferred API
is the existing `type_name=...` class header, and if that is omitted the
default should be `cls.__name__`.

If the same resolved type name is registered twice, registration should fail
with a location-aware error that points to both class definitions, for example:

```python
TypeError(
    "Could not register type for Window in foo.py, it has already be "
    "registered at bar.py:34"
)
```

This is intentionally different from the `gi` compatibility layer, which should
keep PyGObject's legacy `__gtype_name__` behavior.

### Signal callbacks parameter auto truncation

### Signal connections and leakage

### Shared namespace


- obj.prop = x
- obj.signal.connect(...)
- obj.method()

### GObject.Value

Is hidden and no longer needed in Python code, the bindings create and unwrap them in more places than PyGObject so no longer needed
### Async: Awaitable methods and explicit sync

The normal functions are now async version is the natural default for new users, this is a framework depending on an event loop, 
where normal operation is to avoid blocking.

```python
import asyncio
import pathlib
from ginext import Gio

async def main(): 
    try:
        file = Gio.File(path="/tmp/test.txt")
        content = await file.load_contents()
    except FileNotFoundError:
        print("File not found")
    except PermissionError:
        print("Permission denied")
    else:
        print(f"File content for: {file} is {content[:30]!r}")

asyncio.run(main())
```

The sync version exists as `Gio.File.tmp_sync()`:

### Async: Event loop integration

### Gtk-specific APIs

### Gtk.Expression

See [[gtk-expression]]
### Free threading

### Exception handling

### Error messages

### Type annotations

### CLI tool

### Internals: Unit tests

### Internals: Accessing state

  `__grefcount__ -> _meta.refcount`
  `__gproperties__ -> _meta.props and _meta.pspecs`
  `__gsignals__ -> _meta.signals`
  `__gtype__ -> _meta.gtype`

### Internals: Overlays

### Internals: Customization

If you are unhappy about a specific API, default values, constructor, missing function. You can change it via overlay, this can be done inside your application as well.

- Disabling an existing overlay provided by ginext
- Adding a new method
- Adding a new constructor
- Adding a new default value
- Reordering arguments
- Coercing of parameters
- Wrapping return values

#### Included

Shipped with ginext as examples

`pip install ginext`
`pip install ginext-gi-compat`
`pip install ginext[gio-async-pathlib]`

#### Externally maintained
`pip install ginext-gtk-objectview`
`pip install ginext-enum-str-value`

## Migration guide

### Full PyGObject compatibility mode

### Selectively opting into ABI2 features
