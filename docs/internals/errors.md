# GError Exception Mapping

`GError` is represented as a real Python exception, not as a boxed struct or a plain `RuntimeError`. Every raised error must be catchable as `GLib.Error` and must preserve the original GLib fields:

- `message`: the C `GError.message` text;
- `domain`: the quark string, such as `g-io-error-quark`;
- `code`: the raw integer code;
- `matches(domain, code)`: compatibility with existing PyGObject-style checks.

Unknown domains raise `GLib.Error` directly. The fallback must never drop domain or code information.

## Builtin-Compatible Gio Errors

Native ginext maps selected `Gio.IOErrorEnum` codes to multiple-inheritance exception classes. For example, `Gio.IOErrorEnum.NOT_FOUND` raises `Gio.NotFoundError`, and that class subclasses both `GLib.Error` and Python `FileNotFoundError`.

This lets application code use normal Python handlers while still retaining GLib detail:

```python
try:
    GLib.Variant.parse(None, "abc", None, None)
except GLib.Error as error:
    print(error.domain, error.code, error.message)
```

```python
try:
    file.read(None)
except FileNotFoundError as error:
    assert isinstance(error, GLib.Error)
```

The initial builtin mapping is intentionally narrow. Codes are mapped only when the GLib meaning and Python builtin meaning line up clearly. Current Gio mappings include not-found, exists, directory/not-directory, permission denied, cancellation/interruption, broken pipe, refused connection, timeout, and no-space conditions.

## Feature Flag

Builtin-compatible subclasses are controlled by `gerror_builtin_exceptions`. The default is native-friendly:

- normal ginext: `gerror_builtin_exceptions=True`;
- `pygobject_compat`: `gerror_builtin_exceptions=False`, unless explicitly overridden.

The flag can be set through either feature mechanism:

```sh
GINEXT_FEATURES=pygobject_compat,gerror_builtin_exceptions=1
GINEXT_GERROR_BUILTIN_EXCEPTIONS=true
```

The direct environment variable wins over the implicit `pygobject_compat` default. This keeps compatibility mode conservative while allowing tests and migrations to opt into the native behavior.

## Implementation Notes

The C invoke paths call `pygi_raise_gerror()`, which now asks `ginext.errors` to construct the Python exception from `(domain, code, message)`. Return/out-slot marshalling uses the same factory so returned `GError*` values have the same shape as thrown errors.

`GLib.Error` is installed by the GLib overlay as a pure-Python exception class. Gio-specific subclasses are installed by the Gio overlay and are also created lazily when a thrown Gio error is converted before `Gio` has been imported explicitly.
