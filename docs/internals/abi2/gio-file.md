# ABI2 Gio.File

`Gio.File` should be the first large Python-native ABI2 convenience surface. It
is where Python users most often expect `pathlib` ergonomics, but GIO is not
just local filesystem paths: a `GFile` may be a URI, a GVfs mount, a portal
document, a resource, or another backend.

The native API should borrow the useful parts of `pathlib` without pretending
every `GFile` is a local `Path`.

## Construction

ABI2 should use one Python-native vocabulary and avoid exposing both C-style
and Python-style aliases on the native surface.

Recommended native constructors and factories:

```python
file = Gio.File(path)                         # os.PathLike or str path
file = Gio.File.from_uri(uri)
file = Gio.File.from_commandline_arg(arg, cwd=None)
file = Gio.File.from_path_parts(*parts)

tmp = await Gio.File.temporary()
tmp_sync = Gio.File.temporary_sync()

tmp_dir = await Gio.File.temporary_dir()
```

Do not also add `new_tmp()` if `temporary()` is the ABI2 name. The
compatibility surface can keep `new_tmp`, `new_for_path`, and the rest of the
GIR/PyGObject names.

GIR mapping:

- `Gio.File(path)` maps to `g_file_new_for_path()`.
- `from_uri()` maps to `g_file_new_for_uri()`.
- `from_commandline_arg()` maps to `g_file_new_for_commandline_arg()` or
  `g_file_new_for_commandline_arg_and_cwd()`.
- `from_path_parts()` maps to `g_file_new_build_filenamev()`.
- `temporary()` maps to `g_file_new_tmp_async()` /
  `g_file_new_tmp_finish()` and returns a result record containing both the
  file and stream.
- `temporary_sync()` maps to `g_file_new_tmp()`.
- `temporary_dir()` maps to `g_file_new_tmp_dir_async()` /
  `g_file_new_tmp_dir_finish()`.

`temporary_dir_sync()` should not exist unless ABI2 supplies a real sync
implementation or a clear sync GIO/GLib mapping. The GIR async operation has a
finish pair but no `glib:sync-func`.

## Opening Files

ABI2 should provide a Python-style async context manager:

```python
async with file.open() as stream:
    data = await stream.read()

async with file.open("rb") as stream:
    data = await stream.read()

async with file.open("wb") as stream:
    await stream.write(data)

async with file.open("r+b") as stream:
    ...
```

`file.open()` should default to `"rb"` and return an async context-manager
object. Its `__aenter__` performs the GIO async operation, and its `__aexit__`
awaits `stream.close()`. This avoids the awkward but valid spelling:

```python
async with await file.open("rb") as stream:
    ...
```

Mode mapping should be binary-first:

- `"rb"` maps to `read_async()` / `read_finish()`.
- `"wb"` maps to `replace_async()` / `replace_finish()` because Python `open`
  truncates or creates.
- `"xb"` maps to `create_async()` / `create_finish()`.
- `"ab"` maps to `append_to_async()` / `append_to_finish()`.
- `"r+b"` maps to `open_readwrite_async()` / `open_readwrite_finish()`.
- `"w+b"` maps to `replace_readwrite_async()` / `replace_readwrite_finish()`.
- `"x+b"` maps to `create_readwrite_async()` /
  `create_readwrite_finish()`.

These mapped GIR methods are implementation details of `open()`. The native
ABI2 `Gio.File` surface should not also expose public `open_readwrite()`,
`open_readwrite_async()`, `replace_readwrite()`, or `create_readwrite()` methods
unless a separate, non-overlapping use case appears. Keeping them hidden forces
users toward the single Python mode API and prevents drift between competing
spellings. Internally, `open()` can call these through the ABI2
`_internal_invoke()` helper described in [Methods](methods.md).

The blocking spelling is explicit:

```python
with file.open_sync("rb") as stream:
    data = stream.read()
```

Do not support text mode in the first ABI2 slice. Text mode needs encoding,
newline, error handling, and a Pythonic text stream wrapper. Add it only after
binary streams are correct.

## Read And Write Conveniences

Borrow the high-value `pathlib` helpers, but make async the default:

```python
data = await file.read_bytes()
text = await file.read_text(encoding="utf-8")

await file.write_bytes(data)
await file.write_text(text, encoding="utf-8")

data = file.read_bytes_sync()
file.write_bytes_sync(data)
```

GIR mapping:

- `read_bytes()` maps to `load_bytes_async()` / `load_bytes_finish()`.
- `read_text()` maps to `load_contents_async()` / `load_contents_finish()` and
  decodes with Python codec rules.
- `write_bytes()` maps to `replace_contents_async()` /
  `replace_contents_finish()`.
- `write_text()` encodes with Python codec rules and uses `write_bytes()`.

These helpers should return result records where GIO exposes meaningful extra
data, for example an ETag.

## Path-Like Operations To Adopt

These `pathlib`-style operations map cleanly enough to `Gio.File`:

- `file / "child"` and `file.joinpath("child")` map to `get_child()` or
  `resolve_relative_path()`.
- `file.parent` maps to `get_parent()`.
- `file.name` maps to `get_basename()`.
- `file.uri` maps to `get_uri()`.
- `file.path` maps to `get_path()`, returning `None` for non-native files.
- `file.as_uri()` maps to `get_uri()`.
- `file.is_native()` maps to `g_file_is_native()`.
- `file.relative_to(base)` maps to `base.get_relative_path(file)` and raises
  if no relative path exists.
- `file.is_relative_to(base)` maps to `file.has_prefix(base)` or
  `base.get_relative_path(file) is not None`.

`resolve_relative_path()` should remain available for GIO semantics. It is not
the same thing as `pathlib.Path.resolve()`.

## Filesystem Queries

`pathlib` exposes many sync stat predicates. ABI2 should prefer async query
methods for anything that may hit I/O or a remote backend:

```python
info = await file.stat()
exists = await file.exists()
is_file = await file.is_file()
is_dir = await file.is_dir()
```

GIR mapping:

- `stat()` maps to `query_info_async()` / `query_info_finish()`.
- `exists()` can use `query_exists()` for a cheap boolean, but an async form is
  still useful for consistency and cancellability.
- `is_file()`, `is_dir()`, and `is_symlink()` map to file-type queries.
- `filesystem_info()` maps to `query_filesystem_info_async()` /
  `query_filesystem_info_finish()`.

Expose `_sync()` variants for explicit blocking calls:

```python
info = file.stat_sync()
exists = file.exists_sync()
```

## Directory Iteration

`pathlib.iterdir()` should become an async iterator:

```python
async for child in file.iterdir():
    ...
```

GIR mapping:

- `iterdir()` maps to `enumerate_children_async()` /
  `enumerate_children_finish()`.
- The returned enumerator should use `FileEnumerator.next_files_async()` in
  batches.
- Each yielded item should be a `Gio.File`, with optional access to the
  associated `Gio.FileInfo`.

Do not promise full `glob()` / `rglob()` in the first slice. Local-path glob
semantics do not map cleanly to remote GIO backends, and recursive traversal
needs cancellation and error policy.

## Mutation Operations

Use Python names where the semantics are close, but keep GIO-specific options
available.

Recommended mappings:

- `mkdir(parents=False)` maps to `make_directory_async()` or
  `make_directory_with_parents()` when `parents=True`.
- `unlink()` maps to `delete_async()` / `delete_finish()`.
- `trash()` maps to `trash_async()` / `trash_finish()`.
- `rename(target)` should be a convenience over `move()` with no cross-device
  copy semantics promised beyond GIO behavior.
- `replace(target)` conflicts with the existing GIO stream-opening concept.
  Prefer `move_to(target, replace=True)` for file movement, and keep
  `open("wb")` / `write_bytes()` for content replacement.
- `copy_to(target)` maps to `copy_async()` / `copy_finish()`.
- `move_to(target)` maps to `move_async()` / `move_finish()`.

Progress callbacks should use the same owner-aware callback rules as signals.

## Operations To Avoid Or Defer

Do not blindly mirror all of `pathlib`.

- `resolve()` is misleading for `GFile`; GIO has URI, parse-name, relative-path,
  and backend-specific resolution semantics.
- `absolute()` is local-path specific.
- `expanduser()` is local shell/path behavior; use Python `Path` before
  constructing `Gio.File`.
- `owner()`, `group()`, and `chmod()` require file attributes and platform
  policy; expose them later through explicit metadata helpers if needed.
- `samefile()` maps poorly across virtual backends. `GFile.equal()` and
  `hash()` are available but are not POSIX inode identity.
- `symlink_to()`, `hardlink_to()`, and `readlink()` should be deferred until
  ABI2 has a clear cross-platform and remote-backend policy.
- `glob()` and `rglob()` should wait for a cancellable async traversal design.

## Implementation Shape

The file convenience layer should be small Python code over planned ABI2
methods, not a parallel marshalling engine.

Needed wrapper pieces:

- `Gio.File.__call__` / constructor policy for path-like inputs.
- Classmethod factories for URI, command-line args, path parts, temporary file,
  and temporary directory creation.
- `FileOpenContext` async context manager for mode parsing, opening, and
  closing streams.
- Result records for multi-value operations such as `load_contents`,
  `load_bytes`, `replace_contents`, `new_tmp`, and disk-usage measurement.
- Shared cancellable and I/O-priority policy across all async file helpers.
- `_sync()` variants for promoted blocking operations.

The low-level GIR names should remain available in compat mode. ABI2 should
choose one native spelling per concept and avoid exposing both `new_tmp()` and
`temporary()` on the native surface.
