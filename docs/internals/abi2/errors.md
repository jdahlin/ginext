# ABI2 Error Domains

GObject libraries report recoverable failures through `GError`: a domain
quark, an integer code, and a message. ABI2 should not collapse that structure
into a generic `RuntimeError`, and it should not force users to string-match
messages.

This policy follows Python's built-in exception hierarchy where the mapping is
semantically clear, and GLib's documented error-domain enums where the domain
needs to remain visible.

## Base Shape

All raised `GError` values should be catchable as `GLib.Error`:

```python
try:
    data = await file.read_bytes()
except GLib.Error as error:
    print(error.domain, error.code, error.message)
```

`GLib.Error` is the compatibility and fallback base class. It must preserve:

- `domain`: the domain string from the GQuark, for example
  `"g-io-error-quark"`;
- `code`: the raw integer error code;
- `message`: the human-readable message from the library;
- `matches(domain, code)`: compatibility with existing PyGObject code;
- `copy()`: a structurally equivalent error object.

Unknown domains still raise `GLib.Error`. ABI2 should never drop domain/code
information just because no generated domain wrapper exists.

## Generated Domain Exceptions

GIR exposes many error domains on enum types through `glib:error-domain`.
Generate one exception class per error-domain enum, but do not put that class
at the enum's top-level name because that name is already the enum:

```python
try:
    data = await file.read_bytes()
except Gio.errors.IOError as error:
    if error.code_enum is Gio.IOErrorEnum.NOT_FOUND:
        ...
except GLib.Error:
    ...
```

Recommended native shape:

- `Gio.errors.IOError` for `Gio.IOErrorEnum`;
- `Gio.errors.DBusError` for `Gio.DBusError`;
- `Gtk.errors.BuilderError` for `Gtk.BuilderError`;
- `GLib.errors.FileError` for `GLib.FileError`;
- all generated classes subclass `GLib.Error`;
- `except GLib.Error` remains the catch-all for every `GError`.

This avoids the bad choices of either overwriting enum classes such as
`Gio.IOErrorEnum` / `Gtk.BuilderError`, or inventing awkward names like
`Gtk.BuilderErrorException`.

Each generated domain exception should expose:

- `domain_enum`: the enum class that defines the domain's codes;
- `domain_quark`: the integer GQuark for the domain;
- `domain_name`: the quark string;
- `code_enum`: the enum member for `code`, or `None` if the code is unknown;
- `matches(code_or_domain, code=None)`: accepts the old `(domain, code)` pair
  and the ABI2 shorthand `error.matches(Gio.IOErrorEnum.NOT_FOUND)`.

`code` should remain the raw integer for compatibility and stable serialization.
`code_enum` is the Python-friendly view.

## Builtin-Compatible Code Exceptions

Some error codes correspond directly to Python's built-in exception hierarchy.
ABI2 should generate code-specific subclasses for those cases, so ordinary
Python handlers work:

```python
try:
    text = await Gio.File("/missing").read_text()
except FileNotFoundError:
    ...
```

The raised object should still be a `GLib.Error`:

```python
try:
    text = await Gio.File("/missing").read_text()
except FileNotFoundError as error:
    assert isinstance(error, GLib.Error)
    assert isinstance(error, Gio.errors.IOError)
    assert error.code_enum is Gio.IOErrorEnum.NOT_FOUND
```

Recommended class shape:

```python
class Gio.errors.IOError(GLib.Error):
    domain_enum = Gio.IOErrorEnum

class Gio.errors.FileNotFoundError(
    Gio.errors.IOError,
    builtins.FileNotFoundError,
):
    code_enum = Gio.IOErrorEnum.NOT_FOUND
```

This is multiple exception inheritance, so keep it narrow. Python documents
that multiple built-in exception bases can conflict because of `args` handling
and CPython memory layouts. ABI2 should only combine one pure-Python `GLib.Error`
lineage with one built-in exception class, and should test every generated
builtin-compatible class on every supported Python version.

Do not generate builtin-compatible subclasses from names alone. Only map when
the GLib/GIO meaning and the Python builtin meaning line up clearly.

Initial mappings worth generating:

| Domain code | ABI2 class | Builtin base |
| --- | --- | --- |
| `Gio.IOErrorEnum.NOT_FOUND` | `Gio.errors.FileNotFoundError` | `FileNotFoundError` |
| `Gio.IOErrorEnum.EXISTS` | `Gio.errors.FileExistsError` | `FileExistsError` |
| `Gio.IOErrorEnum.IS_DIRECTORY` | `Gio.errors.IsADirectoryError` | `IsADirectoryError` |
| `Gio.IOErrorEnum.NOT_DIRECTORY` | `Gio.errors.NotADirectoryError` | `NotADirectoryError` |
| `Gio.IOErrorEnum.PERMISSION_DENIED` | `Gio.errors.PermissionError` | `PermissionError` |
| `Gio.IOErrorEnum.TIMED_OUT` | `Gio.errors.TimeoutError` | `TimeoutError` |
| `Gio.IOErrorEnum.WOULD_BLOCK` | `Gio.errors.BlockingIOError` | `BlockingIOError` |
| `Gio.IOErrorEnum.BROKEN_PIPE` | `Gio.errors.BrokenPipeError` | `BrokenPipeError` |
| `Gio.IOErrorEnum.CONNECTION_REFUSED` | `Gio.errors.ConnectionRefusedError` | `ConnectionRefusedError` |
| `GLib.FileError.NOENT` | `GLib.errors.FileNotFoundError` | `FileNotFoundError` |
| `GLib.FileError.EXIST` | `GLib.errors.FileExistsError` | `FileExistsError` |
| `GLib.FileError.ISDIR` | `GLib.errors.IsADirectoryError` | `IsADirectoryError` |
| `GLib.FileError.NOTDIR` | `GLib.errors.NotADirectoryError` | `NotADirectoryError` |
| `GLib.FileError.ACCES` | `GLib.errors.PermissionError` | `PermissionError` |
| `GLib.FileError.PERM` | `GLib.errors.PermissionError` | `PermissionError` |
| `GLib.FileError.AGAIN` | `GLib.errors.BlockingIOError` | `BlockingIOError` |
| `GLib.FileError.INTR` | `GLib.errors.InterruptedError` | `InterruptedError` |
| `GLib.FileError.PIPE` | `GLib.errors.BrokenPipeError` | `BrokenPipeError` |

Keep these as domain-specific classes rather than reusing the builtin classes
directly. `Gio.errors.FileNotFoundError` and `GLib.errors.FileNotFoundError`
both satisfy `except FileNotFoundError`, but they keep different domains,
codes, and enum metadata.

Cases to avoid initially:

- `INVALID_ARGUMENT` / `INVAL`: do not map to `ValueError`; argument binding
  mistakes should be raised before calling C, and a library-returned invalid
  argument is still a domain error.
- `NOT_SUPPORTED` / `NOSYS`: do not map to `NotImplementedError`; Python uses
  that for abstract or unfinished methods, not runtime platform capability.
- `CANCELLED`: do not map to `asyncio.CancelledError` except for task-driven
  cancellation; see [Async Cancellation](#async-cancellation).
- `NO_SPACE`, `FILENAME_TOO_LONG`, `TOO_MANY_OPEN_FILES`, `READ_ONLY`,
  `HOST_NOT_FOUND`, `NETWORK_UNREACHABLE`, and similar cases should remain
  domain-specific until ABI2 has a clear builtin target.

## Raising Policy

When a callable throws `GError`, ABI2 should:

1. Convert the GQuark to a domain string and keep the raw integer code.
2. Look up a generated domain exception by quark.
3. If the code has a builtin-compatible class, instantiate that class.
4. Otherwise instantiate the generated domain exception if available, or
   `GLib.Error` as the fallback.
5. Set `__cause__` only when wrapping another Python exception; the original
   `GError` fields live on the exception itself.
6. Use the same conversion for sync calls, `_finish()` calls, and awaitable
   ABI2 async wrappers.

The current slow and JIT invocation paths already route thrown `GError` through
one helper. ABI2 should keep that central point and make the helper consult the
generated domain registry.

## Async Cancellation

Cancellation needs one special rule because Python users expect task
cancellation to behave like Python task cancellation:

See also [Async cancellation](../async-cancellation.md) for the broader task
vs `Gio.Cancellable` design.

- If a Python task is cancelled and ABI2 cancels the underlying
  `Gio.Cancellable`, the await should raise `asyncio.CancelledError`.
- If a C API independently reports `G_IO_ERROR_CANCELLED`, raise the normal
  `Gio.errors.IOError` with `code_enum is Gio.IOErrorEnum.CANCELLED`.
- If the underlying `GError` is available when translating Python cancellation,
  attach it as `CancelledError.__cause__`.

This keeps `asyncio` semantics correct without losing GIO error detail for
non-task-driven cancellation.

## GDBus Remote Errors

GDBus errors need to preserve both the normal `GError` domain/code and the
remote D-Bus error name.

For `Gio.DBusError` domains, generated exceptions should expose:

- `remote_name`: `Gio.dbus_error_get_remote_error(error)`;
- `is_remote`: `Gio.dbus_error_is_remote_error(error)`;
- `strip_remote()`: returns a copy with the remote wrapper stripped, matching
  `g_dbus_error_strip_remote_error()` semantics.

Do not strip remote errors automatically. The remote name is often the only
stable application-level detail.

## Core Domains Found In Installed GIR

Representative generated domains from the installed GIR files:

- `GLib.errors.BookmarkFileError`
- `GLib.errors.ConvertError`
- `GLib.errors.FileError`
- `GLib.errors.IOChannelError`
- `GLib.errors.KeyFileError`
- `GLib.errors.MarkupError`
- `GLib.errors.OptionError`
- `GLib.errors.RegexError`
- `GLib.errors.ShellError`
- `GLib.errors.SpawnError`
- `GLib.errors.UriError`
- `GLib.errors.VariantParseError`
- `Gio.errors.DBusError`
- `Gio.errors.IOError`
- `Gio.errors.ResolverError`
- `Gio.errors.ResourceError`
- `Gio.errors.TlsChannelBindingError`
- `Gio.errors.TlsError`
- `Gdk.errors.GLError`
- `Gdk.errors.TextureError`
- `Gdk.errors.VulkanError`
- `GdkPixbuf.errors.PixbufError`
- `Gtk.errors.BuilderError`
- `Gtk.errors.CssParserError`
- `Gtk.errors.DialogError`
- `Gtk.errors.FileChooserError`
- `Gtk.errors.IconThemeError`
- `Gtk.errors.PrintError`
- `Gtk.errors.RecentManagerError`
- `Gtk.errors.SvgError`

The generator should apply this to every loaded namespace, not only this list.
GStreamer domains should be generated the same way when `Gst-*.gir` is present.

## Implementation Notes

- Build a process-wide domain registry keyed by GQuark, populated when a
  namespace is loaded.
- Register domains from enum metadata with `glib:error-domain`.
- Attach an `errors` namespace object to each loaded GI namespace.
- Keep `GLib.Error.new_literal(domain, code, message)` for compatibility.
- Update `goi_raise_gerror()` to instantiate the registered domain class.
- Keep return-slot `GError` values as structured `GLib.Error` objects, not
  `(domain, code, message)` tuples, on ABI2 native surfaces.
- Compatibility mode can keep PyGObject-shaped behavior where existing tests
  require it.

## References

- [Python built-in exceptions](https://docs.python.org/3/library/exceptions.html)
- [GLib.FileError](https://docs.gtk.org/glib/error.FileError.html)
