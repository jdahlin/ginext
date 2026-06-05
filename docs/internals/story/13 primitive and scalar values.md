# Primitive And Scalar Values

Primitive and scalar values should accept normal Python values at the boundary.
The runtime should be strict enough to catch mistakes, but not so strict that
users need C-shaped wrapper objects for common values.

## Basic Mapping

| GIR / C type | Python type | Accepted arguments |
| --- | --- | --- |
| `gboolean` | `bool` | `bool`; reject arbitrary objects |
| `gint`, `guint`, sized ints | `int` | `int`; range-check for the C type |
| `glong`, `gulong` | `int` | `int`; platform range-check |
| `gsize`, `gssize` | `int` | `int`; range-check signedness |
| `gfloat`, `gdouble` | `float` | `float` or `int` |
| `utf8` | `str` | `str`; encode as UTF-8 |
| `filename` | `str | os.PathLike[str]` | `str`, path-like object |
| `gunichar` | `str` | one Unicode character |
| `gpointer` | low-level only | avoid on native ABI2 unless wrapped |
| `none` | `None` | no return value |

The exact generated type may be narrower for a specific API. For example,
paths should usually accept `os.PathLike[str]`, while general UTF-8 strings
should not.

## Integers

Integer arguments should accept Python `int`:

```python
stream.read_bytes(count=4096)
```

The runtime should range-check before calling C:

```python
stream.read_bytes(count=-1)      # invalid for an unsigned size
stream.read_bytes(count=2 ** 80) # invalid for gsize
```

Do not silently truncate Python integers.

## Booleans

Boolean arguments should accept `bool`:

```python
source.bind_property("enabled", target, "sensitive", sync=True)
```

Avoid accepting arbitrary truthy objects for `gboolean`. Passing `"yes"` should
be an error, not `True`.

## Floats

Floating point arguments should accept `float` and `int`:

```python
adjustment.set_value(10)
adjustment.set_value(10.5)
```

For `gfloat`, conversion can lose precision. That is normal, but type checkers
should still expose the Python-side type as `float`.

## Strings

UTF-8 strings accept `str`:

```python
button.label = "Save"
```

The runtime should reject `bytes` for UTF-8 text unless the API explicitly
handles bytes.

Filename strings are different. They should accept `str` and path-like objects:

```python
file = Gio.File(pathlib.Path("notes.txt"))
```

## Nullable Scalars

If GIR marks a scalar pointer-like value nullable, expose `None`:

```python
Gio.SimpleAction.new("save", None)
```

Do not add `None` to non-nullable scalar arguments just because C could crash or
accept `NULL`.

## Defaults

Generated Python signatures should use defaults only when ABI2 defines a real
default:

```python
Gio.open(path, mode="rb")
```

Do not invent defaults from C examples unless the ABI2 overlay owns that
decision.

## Out Arguments

Hidden scalar out arguments should shape the return value:

```python
ok, value = parser.try_parse()
```

For new ABI2 APIs, prefer named result records when multiple scalar results
would make tuple order unclear.

Next: [[14 non scalar values]]

