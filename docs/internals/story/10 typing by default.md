# Typing By Default

`ginext` should be typed by default. Users should get useful autocomplete,
hover text, and static checks as soon as they import a generated namespace.

Typing is not only `.pyi` generation. The runtime surface, generated docs, and
type stubs should agree on the same ABI2 names.

```python
from ginext import Gio

file = Gio.File("notes.txt")
data: bytes = await file.read_bytes()
```

If that code type-checks but the runtime exposes different names, the generator
has failed. If the runtime works but type checkers see `Any` everywhere, the
binding has also failed.

## Generated Files

The generator should emit:

- Python runtime modules or binding tables;
- `.pyi` files for each generated namespace;
- `py.typed`;
- optional generated Markdown/API fragments later.

Expected package shape:

```text
src/ginext/
  __init__.py
  py.typed
  repository/
  generated/
    Gio2.py
    Gio2.pyi
    GObject2.py
    GObject2.pyi
```

The exact directory names can change, but runtime and stubs should be generated
from the same model.

## Running The Generator

The command should be boring and repeatable:

```sh
goi generate ginext --namespace Gio-2.0
goi generate ginext --namespace GObject-2.0
```

For normal development, provide one command that regenerates all checked-in
namespaces:

```sh
goi generate ginext --all
```

`make ginext-generate` can exist as a build-system convenience, but it should
delegate to the CLI rather than becoming a second public interface.

Generator tests should run without needing a full GTK application:

```sh
uv run pytest tests/test_ginext_generator.py
```

## Checking Types

`ginext` should be tested against more than one checker because they catch
different classes of mistakes.

Suggested commands:

```sh
goi typecheck examples/ginext --checker mypy
goi typecheck examples/ginext --checker pyright
goi typecheck examples/ginext --checker ty
```

The CLI should print the underlying command it runs so failures are easy to
reproduce without the wrapper.

The repository can start with tiny typed examples instead of checking all
tests. Good first targets:

- imports and version selection;
- `Gio.File` construction and async reads;
- `GObject.Property` descriptors;
- signal callback overloads;
- enum and flags arguments.

## Type Checker Contract

The generator should avoid collapsing important APIs to `Any`.

Good:

```python
class File:
    def __init__(self, path: str | os.PathLike[str]) -> None: ...
    async def read_bytes(self) -> bytes: ...
```

Temporary but weaker:

```python
class File:
    def __init__(self, path: Any) -> None: ...
    async def read_bytes(self) -> Any: ...
```

Bad:

```python
File: Any
```

## Signal Typing

Signals should generate overloads for accepted callback shapes:

```python
class Button:
    clicked: Signal[
        Callable[[], None],
        Callable[[Button], None],
    ]
```

The exact generic type can evolve. The important rule is that signal handlers
should not be typed only as `Callable[..., Any]` once the signal's arguments
are known.

## Practical Rule

When ABI2 changes a public spelling, update runtime generation, stubs, docs,
and examples in the same change.

Next: [[11 mapping rules]]
