# Files, Async, And Errors

`Gio.File` is the first user-facing vertical slice. It proves constructors,
generated overlays, hidden GIR methods, async finish pairing, result shaping,
stream context managers, and error mapping.

```python
from ginext import Gio

file = Gio.File("notes.txt")
contents = await file.read_bytes()
```

## Construction

The native constructor should accept paths:

```pycon
>>> from ginext import Gio
>>> file = Gio.File("/tmp/ginext-demo.txt")
>>> file.path
'/tmp/ginext-demo.txt'
```

Factories cover non-path construction:

```python
Gio.File.from_uri("file:///tmp/ginext-demo.txt")
Gio.File.from_path_parts("/tmp", "ginext-demo.txt")
```

The low-level GIR constructors remain internal to the binding plan.

## Async By Plan, Not By Name

ABI2 should promote async only when the operation has an explicit call plan:

```python
data = await file.read_bytes()
data = file.read_bytes_sync()
```

The plan must name:

- source async callable;
- matching finish callable;
- sync callable when available;
- cancellation behavior;
- result shape;
- nullable behavior;
- error conversion.

## Streams

Opening a file returns an async context manager:

```python
async with Gio.File("notes.txt").open("rb") as stream:
    data = await stream.read()
```

The top-level helper is the familiar spelling:

```python
async with Gio.open("notes.txt", "rb") as stream:
    data = await stream.read()
```

## Errors

`GError` must keep domain, code, and message while mapping obvious codes to
builtin-compatible exceptions:

```python
try:
    await Gio.File("missing.txt").read_bytes()
except FileNotFoundError as error:
    assert error.domain == "g-io-error-quark"
```

The same mapping should be used by sync methods, async finish functions,
callbacks, and vfuncs.

## Hidden Low-Level Methods

High-level ABI2 APIs may use low-level GIR callables internally without
exposing them as public attributes:

```python
file.open_readwrite_async  # AttributeError on ginext
```

The internal invoker or generated binding table can still call the hidden
method.

Next: [[7 property bindings]]

