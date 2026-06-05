# Generated Bindings

`ginext` should generate bindings from GIR and ABI2 overlays from the start.
The generator is part of the product, not a later stub-only tool.

The public entry point should be the `goi` CLI:

```sh
goi generate ginext --namespace Gio-2.0
```

The Python module that implements generation is an internal detail. Users and
contributors should learn one command surface.

The generated surface should include:

- namespace modules;
- classes and interfaces;
- constructors, methods, functions, and constants;
- enums and flags;
- GObject properties;
- GObject signals;
- `.pyi` files with the same ABI2 names;
- internal binding tables used by the runtime.

## One Source Of Truth

The generator should emit both runtime metadata and type stubs from the same
model. If `Gio.File.open_readwrite_async` is hidden on ABI2, it should be hidden
from runtime attribute lookup and omitted from the ABI2 stub.

```python
# Generated public surface
class File:
    def __init__(self, path: str | os.PathLike[str]) -> None: ...
    async def read_bytes(self) -> bytes: ...
    def read_bytes_sync(self) -> bytes: ...
    def open(self, mode: str = "rb", **kwargs: Any) -> FileOpenContext: ...
```

```python
# Not public on ABI2
file.open_readwrite_async
```

## Overlay Jobs

ABI2 overlays should handle decisions GIR cannot express:

- hide a low-level member from native lookup;
- add a Python-native constructor or factory;
- define async/finish/sync families;
- shape multi-return records;
- map `GError` domains and codes to exception classes;
- resolve naming conflicts;
- attach documentation notes to generated APIs.

## First Generator Milestone

The first generator milestone is not "all of GTK". It is:

- `GLib` constants and errors;
- `GObject.Object`, `Property`, `Signal`, `Binding`;
- `Gio.Cancellable`, `SimpleAction`, `File`, `InputStream`, `ListStore`;
- enough generated `.pyi` to make examples and tests type-check in spirit.

## Test Shape

Generated output should be tested as text and as runtime behavior:

```pycon
>>> from ginext import Gio
>>> Gio.File("/tmp/demo.txt").__ginext_abi__
'native-v2'
```

The stub test should parse generated files with `ast.parse()` and assert
specific ABI2 signatures for the story APIs.

Related reference chapters:

- [[10 typing by default]]
- [[15 goi cli]]
- [[11 mapping rules]]
- [[12 binding member kinds]]
- [[13 primitive and scalar values]]
- [[14 non scalar values]]

Next: [[4 objects methods and properties]]
