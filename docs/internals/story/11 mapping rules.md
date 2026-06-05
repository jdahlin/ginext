# Mapping Rules

This chapter explains how GIR concepts become `ginext` concepts. The goal is
not to mirror C names mechanically. The goal is to expose one Python-native
spelling for each concept while preserving the underlying GObject semantics.

## Namespaces

GIR namespace:

```text
Gio-2.0
```

Native import:

```python
from ginext import Gio
```

Versioned import when needed:

```python
from ginext import Gio2
```

Generated stubs should use the same names.

## Names

GObject and C names are normalized to Python identifiers:

```text
items-changed        -> items_changed
notify::title        -> notify("title")
g_file_new_for_path  -> Gio.File(...) or Gio.File.new_for_path(...)
```

ABI2 should use a Python abstraction when it is clearly better:

```python
file = Gio.File("notes.txt")
data = await file.read_bytes()
```

instead of forcing:

```python
file = Gio.File.new_for_path("notes.txt")
file.load_bytes_async(...)
```

## Method Families

Sync/async/finish families should be mapped deliberately:

```text
load_bytes_async + load_bytes_finish + load_bytes
    -> await file.read_bytes()
    -> file.read_bytes_sync()
```

Do not promote an async method just because it ends in `_async`. Promotion
requires a written plan for finish pairing, cancellation, result shaping, and
error conversion.

## Constructors

Constructors should follow Python expectations:

```python
file = Gio.File("notes.txt")
button = Gtk.Button(label="Save")
```

Named constructors remain when they express distinct meaning:

```python
file = Gio.File.from_uri(uri)
file = Gio.File.from_path_parts("/tmp", "demo.txt")
```

Low-level `new_for_*` names can stay hidden on the native surface when the
native constructor or factory is the intended spelling.

## Properties

GObject properties become plain Python attributes:

```python
action.enabled
action.enabled = False
```

Hyphenated property names normalize to underscores:

```text
parameter-type -> parameter_type
```

Properties do not become magic value proxies. Binding and notify live on
explicit APIs:

```python
item.bind_property(Item.title, label, "label", sync=True)
item.notify(Item.title).add(callback)
```

## Signals

Signals become signal objects:

```python
button.clicked.add(callback)
button.clicked.emit()
```

Detailed signals use indexing:

```python
entry.notify("text").add(callback)
```

Pure method/signal conflicts use `MethodSignal`:

```python
action.activate(None)
action.activate.add(callback)
```

Property-involved conflicts use escaped names:

```python
widget.has_focus_        # property
widget.has_focus_func()  # method
widget.has_focus_signal  # signal
```

## Errors

`GError` maps to generated exception classes while preserving the original
domain, code, and message:

```python
try:
    await Gio.File("missing.txt").read_bytes()
except FileNotFoundError as error:
    assert error.domain == "g-io-error-quark"
    assert error.code_enum is Gio.IOErrorEnum.NOT_FOUND
```

Builtin-compatible bases are used only when the mapping is semantically clear.

## Return Values

Single return values return one Python value:

```python
parent = file.get_parent()
```

Multiple meaningful results should use a named result record when tuple order
would be unclear:

```python
result = await Gio.File.temporary()
result.file
result.stream
```

Simple historical tuple returns can stay tuples when they are obvious and
already common, but new ABI2 APIs should prefer named records for clarity.

Next: [[12 binding member kinds]]
