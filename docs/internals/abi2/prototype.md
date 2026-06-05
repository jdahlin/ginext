# ABI2 Prototype Plan

The first prototype should prove one user-facing flow:

```python
try:
    f = Gio.File(path)
    contents = await f.read_bytes()
except FileNotFoundError:
    print("Could not read content")
except PermissionError:
    print("Access denied")
```

and the streaming form:

```python
try:
    f = Gio.File(path)
    async with f.open() as stream:
        contents = await stream.read()
except FileNotFoundError:
    print("Could not read content")
except PermissionError:
    print("Access denied")
```

Do not make `Gio.File` itself an owning context manager. A `GFile` is a locator,
not an open file handle, so `with Gio.File(path) as f:` would not have a useful
resource to close. The context manager belongs on `Gio.open(...)` or
`file.open(...)`. Also avoid opening a stream and then ignoring it:
`async with f.open(): contents = await f.read_bytes()` should just be
`contents = await f.read_bytes()`.

## Prototype Slices

### 1. Internal Invocation

Add a private runtime helper, provisionally named `_internal_invoke()`, for
calling GIR methods hidden from the public ABI2 surface.

Target shape:

```python
stream = await _abi2._internal_invoke(
    file,
    "Gio.File.open_readwrite_async",
    finish="Gio.File.open_readwrite_finish",
    args=(priority, cancellable),
)
```

Initial scope:

- call a method by fully qualified GIR name;
- bind the supplied native wrapper as the instance argument;
- optionally pair async and finish functions;
- return ABI2-native wrappers and ABI2-native errors;
- remain unavailable as a user-object attribute.

This helper is what lets `file.open("r+b")` use
`g_file_open_readwrite_async()` without exposing `file.open_readwrite_async()`.

### 2. Hide Low-Level GIR Methods

Add a TOML-level hide flag for native ABI2, separate from compatibility mode.

Possible TOML shape:

```toml
[File.open_readwrite]
native = { hidden = true }

[File.open_readwrite_async]
native = { hidden = true }
```

or, if the overlay grammar wants top-level flags:

```toml
[File.open_readwrite]
hide_native = true
```

Current status: the overlay system has `shadows`, `internal`, `synthetic`,
`alias`, properties, and class-method overlays, but not an obvious first-class
hide flag. The prototype should add one rather than abusing `internal`, because
`internal` currently means "return an internal registered class", not "suppress
this GI member from public lookup".

Required behavior:

- `goi.repository.Gio.File.open_readwrite` remains available in compatibility
  mode;
- `goi.abi2.Gio.File.open_readwrite` raises `AttributeError`;
- `_internal_invoke()` can still call the hidden method;
- docs and stubs omit hidden native methods.

### 3. Simple Event Loop Integration

Keep the first event-loop integration deliberately small and Python 3.13+.

Recommended first step:

- reuse the existing `AsyncCallable` machinery for callback-to-`Future`
  conversion;
- provide an explicit `GLibEventLoop` / loop-factory entry point compatible
  with `asyncio.run(..., loop_factory=...)`;
- avoid global event-loop policies because Python 3.14 warns about policy APIs
  and Python 3.16 removes them;
- drive the GLib main context enough for GIO async callbacks to complete;
- postpone full selector coverage until after file I/O works.

Prototype API:

```python
asyncio.run(main(), loop_factory=GLib.EventLoop)
```

If that name conflicts with introspected `GLib.EventLoop`, use a goi-owned
module-level helper:

```python
asyncio.run(main(), loop_factory=goi.GLibEventLoop)
```

Do not start by implementing every `add_reader()` / `add_writer()` edge case.
The known Python 3.13 selector issues matter, but the first ABI2 file prototype
only needs GIO async completion, cancellation, and exception propagation.

### 4. `Gio.File` Construction And Factories

Prototype the native constructor and high-value factories:

```python
file = Gio.File(path)
file = Gio.File.from_uri(uri)
file = Gio.File.from_commandline_arg(arg, cwd=None)
file = Gio.File.from_path_parts(*parts)

tmp = await Gio.File.temporary()
tmp_sync = Gio.File.temporary_sync()
tmp_dir = await Gio.File.temporary_dir()
```

The native surface should not also expose `new_for_path()`, `new_for_uri()`, or
`new_tmp()` unless compatibility mode is being used.

### 5. Awaitable Methods And Explicit Sync

For methods with a real async/finish pair and an ABI2 plan:

```python
contents = await file.read_bytes()
contents = file.read_bytes_sync()
```

Prototype only a small allow-list first:

- `Gio.File.read_bytes()` from `load_bytes_async()` /
  `load_bytes_finish()`;
- `Gio.File.read_text()` from `load_contents_async()` /
  `load_contents_finish()` plus Python codec decoding;
- `Gio.File.write_bytes()` from `replace_contents_async()` /
  `replace_contents_finish()`;
- `Gio.File.open()` from mode-to-GIR mapping.

Do not auto-promote every `*_async` method in the first prototype. Promotion
needs result shaping, cancellation, and error mapping.

### 6. `Gio.open(...)`

Add a top-level high-level helper as the most familiar spelling for streaming:

```python
async with Gio.open(path) as stream:
    contents = await stream.read()
```

`Gio.open(path, mode="rb", *, encoding=None, errors=None, cancellable=None,
priority=GLib.PRIORITY_DEFAULT)` should:

- coerce `path` to `Gio.File(path)` if needed;
- delegate to `file.open(mode, ...)`;
- return an async context manager;
- use binary mode first;
- reject text mode until text stream wrappers are implemented.

### 7. Exceptions

Wire thrown `GError` through the domain-aware ABI2 exception registry.

For the prototype, implement only:

- `Gio.IOErrorEnum.NOT_FOUND` -> `Gio.errors.FileNotFoundError` with builtin
  base `FileNotFoundError`;
- `Gio.IOErrorEnum.PERMISSION_DENIED` -> `Gio.errors.PermissionError` with
  builtin base `PermissionError`;
- `GLib.Error` catch-all compatibility;
- `error.domain`, `error.code`, `error.message`, `error.code_enum`;
- identical behavior for sync and awaitable paths.

This is enough to prove:

```python
try:
    f = Gio.File(path)
    contents = await f.read_bytes()
except FileNotFoundError:
    print("Could not read content")
except PermissionError:
    print("Access denied")
```

## First Demo Checklist

The first end-to-end demo is done when all of these pass:

- `await Gio.File("/missing").read_bytes()` raises `FileNotFoundError`;
- `await Gio.File("/root/secret").read_bytes()` raises `PermissionError` when
  the platform reports permission denied;
- `Gio.File(path).read_bytes_sync()` returns the same bytes as the async form;
- `async with Gio.open(path, "rb") as stream:` closes the stream on exit;
- `Gio.File(path).open_readwrite` raises `AttributeError` on ABI2;
- `_internal_invoke()` can still call the hidden read/write GIR methods;
- the same low-level methods remain available on the compatibility surface.

## Commander As Integration Target

`examples/commander` is a good second-stage integration test for the ABI2 file
API, but it is too broad for the first smoke test.

Why it is useful:

- it already uses `Gio.File` throughout panes, location choices, quick-view
  providers, archive entry, and lister code;
- it exercises directory locations, parent navigation, URI/path display,
  `query_info()`, `query_filesystem_info()`, file reads, and stream reads;
- copy, move, mkdir, and delete actions are already present in the UI but still
  placeholder actions, so they are natural places to prototype the mutation
  API;
- it has real user-facing error surfaces where `FileNotFoundError` and
  `PermissionError` should produce useful messages instead of generic
  `GLib.Error` strings.

Why it should not be the first test:

- it mixes file API work with GTK widgets, panes, providers, archive handling,
  lister rendering, content-type decisions, and app state;
- current code is mostly synchronous, for example `query_info()`,
  `load_contents()`, `file.read()`, and `stream.read_bytes()`;
- making the UI async-safe will require task scheduling and cancellation policy,
  not only nicer `Gio.File` methods.

Recommended staging:

1. Add small unit tests for `Gio.File(path)`, `read_bytes()`,
   `read_bytes_sync()`, `open()`, `Gio.open()`, hidden methods, and exception
   mapping.
2. Add a tiny non-UI example that reads, writes, opens, and catches builtin
   exceptions.
3. Port commander read-only paths:
   `file_new_for_path()` / `file_new_for_uri()` -> `Gio.File(...)` /
   `Gio.File.from_uri(...)`, `load_contents()` -> `read_bytes()` /
   `read_text()`, `file.read()` -> `file.open()`.
4. Implement commander operations one by one:
   mkdir, delete/trash, copy, move.
5. Add dialogs around those operations only after the operation helpers have
   stable return values, progress callbacks, cancellation, and exception
   mapping.

A good commander milestone is:

```python
try:
    source = pane.selected_file()
    target = other_pane.current_dir / source.name
    await source.copy_to(target)
except FileExistsError:
    ...
except PermissionError:
    ...
except GLib.Error as error:
    ...
```

That milestone tests the API in a realistic UI without making commander the
place where the low-level ABI2 semantics are first debugged.
