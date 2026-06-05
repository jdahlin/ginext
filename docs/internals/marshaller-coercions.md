# Marshaller coercion reference

This document describes what Python types are accepted and returned by ginext's
C marshaller for each GI type tag.  It is generated from a manual audit of:

- `src/ginext/private/marshal/string.c` — UTF8 / FILENAME
- `src/ginext/private/marshal/c-array.c` — C-array / GArray / GPtrArray
- `src/ginext/private/marshal/container-element.c` — container element dispatch
- `src/ginext/private/invoke/bind.c` — fast-path input type checks
- `src/ginext/private/invoke/plan.c` — `PYGI_TYPE_*` / `PYGI_MARSHAL_*` resolution
- `src/ginext/private/GLib/List.c` — GList / GSList

---

## PYGI_TYPE_* enumeration

Resolved once during call planning from the GIR type info:

```
PYGI_TYPE_VOID              GI_TYPE_TAG_VOID, non-pointer
PYGI_TYPE_POINTER           GI_TYPE_TAG_VOID, is_pointer
PYGI_TYPE_BOOLEAN           GI_TYPE_TAG_BOOLEAN
PYGI_TYPE_INT8              GI_TYPE_TAG_INT8
PYGI_TYPE_UINT8             GI_TYPE_TAG_UINT8
PYGI_TYPE_INT16             GI_TYPE_TAG_INT16
PYGI_TYPE_UINT16            GI_TYPE_TAG_UINT16
PYGI_TYPE_INT32             GI_TYPE_TAG_INT32
PYGI_TYPE_UINT32            GI_TYPE_TAG_UINT32
PYGI_TYPE_INT64             GI_TYPE_TAG_INT64
PYGI_TYPE_UINT64            GI_TYPE_TAG_UINT64
PYGI_TYPE_FLOAT             GI_TYPE_TAG_FLOAT
PYGI_TYPE_DOUBLE            GI_TYPE_TAG_DOUBLE
PYGI_TYPE_UNICHAR           GI_TYPE_TAG_UNICHAR
PYGI_TYPE_UTF8              GI_TYPE_TAG_UTF8
PYGI_TYPE_FILENAME          GI_TYPE_TAG_FILENAME
PYGI_TYPE_GTYPE             GI_TYPE_TAG_GTYPE
PYGI_TYPE_ENUM              GI_TYPE_TAG_INTERFACE + EnumInfo
PYGI_TYPE_FLAGS             GI_TYPE_TAG_INTERFACE + FlagsInfo
PYGI_TYPE_OBJECT            GI_TYPE_TAG_INTERFACE + ObjectInfo
PYGI_TYPE_BOXED             GI_TYPE_TAG_INTERFACE + Struct/Union
PYGI_TYPE_VARIANT           GI_TYPE_TAG_INTERFACE + GVariant
PYGI_TYPE_INTERFACE         GI_TYPE_TAG_INTERFACE, other
PYGI_TYPE_CALLBACK          GI_TYPE_TAG_INTERFACE + CallbackInfo
PYGI_TYPE_ARRAY             GI_TYPE_TAG_ARRAY
PYGI_TYPE_GLIST             GI_TYPE_TAG_GLIST
PYGI_TYPE_GSLIST            GI_TYPE_TAG_GSLIST
PYGI_TYPE_GHASH             GI_TYPE_TAG_GHASH
PYGI_TYPE_ERROR             GI_TYPE_TAG_ERROR
```

## PYGI_MARSHAL_* fast-path kinds (bind.c)

A second resolution for `direction=in`, `role=NORMAL` arguments that avoids
repeated tag-tree walks on every call:

```
PYGI_MARSHAL_GENERIC        all other shapes
PYGI_MARSHAL_BOOL
PYGI_MARSHAL_INT8 … PYGI_MARSHAL_UINT64
PYGI_MARSHAL_FLOAT, PYGI_MARSHAL_DOUBLE
PYGI_MARSHAL_GOBJECT        transfer=NOTHING
PYGI_MARSHAL_GOBJECT_OWNED  transfer=EVERYTHING
PYGI_MARSHAL_GBYTES         GLib.Bytes only
PYGI_MARSHAL_UTF8           transfer≠EVERYTHING
PYGI_MARSHAL_UTF8_OWNED     transfer=EVERYTHING  (also covers FILENAME)
PYGI_MARSHAL_GTYPE
PYGI_MARSHAL_ENUM_INT32
PYGI_MARSHAL_FLAGS_UINT32
```

---

## Scalar primitives

| GI tag | Python in (accepted) | Python out | Notes |
|---|---|---|---|
| `gboolean` | any object (`PyObject_IsTrue`) | `bool` | truthy/falsy coercion — no TypeError |
| `gint8` | `int`, `float`, `bytes[1]`, `str[1]` | `int` | single-char str/bytes → code point |
| `guint8` | `int`, `float`, `bytes[1]`, `str[1]` | `int` | |
| `gint16` | `int`, `float` | `int` | range-checked |
| `guint16` | `int`, `float` | `int` | |
| `gint32` | `int`, `float` | `int` | |
| `guint32` | `int`, `float` | `int` | |
| `gint64` | `int`, `float` | `int` | |
| `guint64` | `int`, `float` | `int` | explicit `PyLong_Check` before number coercion |
| `gfloat` | `int`, `float` | `float` | `PyNumber_Check` |
| `gdouble` | `int`, `float` | `float` | `PyNumber_Check` |
| `gunichar` | `str[1]`, `int` | `int` | code-point integer, both input forms accepted |
| `GType` | `int`, Python class with `.gimeta`, `.__gtype__`, builtin types | `int` | builtin map: `int`→`G_TYPE_INT`, `bool`→`G_TYPE_BOOLEAN`, `float`→`G_TYPE_DOUBLE`, `str`→`G_TYPE_STRING`, `object`→`G_TYPE_PYOBJECT` |

---

## String types

| GI tag | Python in (accepted) | Python out | `None` | Notes |
|---|---|---|---|---|
| `utf8` | `str`, `bytes`, `bytearray` | `str` (fallback `bytes` on decode error) | NULL | borrowed pointer; Python object kept alive by caller |
| `filename` | `str`, `bytes`, `bytearray`, `os.PathLike` | `str` | NULL | `PathLike` via `PyOS_FSPath()`; embedded NUL → `ValueError` |

**Transfer ownership effects:**
- `transfer=nothing` — borrow the Python pointer; C must not free it
- `transfer=everything` — `g_strdup()` before passing so C can `g_free()` later
- `transfer=container` — same as nothing for strings (rare)

---

## Interface types

| PYGI kind | Python in | Python out | `None` | Notes |
|---|---|---|---|---|
| `ENUM` | `int`, `IntEnum` instance | `IntEnum` or raw `int` | — (scalar) | value must be a declared enum member; `TypeError` otherwise |
| `FLAGS` | `int`, `IntFlag` instance | `IntFlag` or raw `int` | — (scalar) | any bit pattern accepted, no validation |
| `OBJECT` | GObject wrapper | GObject wrapper | NULL | GType narrowing check; ref-counted per `transfer=` |
| `BOXED` | Boxed/Struct/Union wrapper | Boxed wrapper | NULL | ref-counted per `transfer=` |
| `CALLBACK` | `Callable`, `None` | — (not returned) | NULL | wrapped in closure; user_data via `closure=`/`destroy=` GIR attrs |
| `GBYTES` (fast path) | `bytes`, `bytearray`, memoryview, `GLib.Bytes` wrapper | `bytes` | NULL | zero-copy path for large buffers via free-func callback |

**Object transfer ownership effects:**
- `transfer=nothing` — pass raw pointer; caller retains reference
- `transfer=everything` — `g_object_ref()` before passing; C will `g_unref()` later

---

## Container types

| GI tag | Python in | Python out | Empty / `None` | Notes |
|---|---|---|---|---|
| `GLib.List`, `GLib.SList` | sequence, `None` | `list` | `[]` | element dispatch: strings, pointer-encoded ints, objects |
| `GLib.HashTable` | `dict`, `None` | `dict` | `{}` | key/value types dispatched independently; wide types (int64, float) heap-allocated |
| C-array | sequence, `None` | `list` | `[]` | length companion: `BEFORE`, `AFTER`, `FIXED`, or `ZERO_TERMINATED` |
| `GArray` / `GPtrArray` | sequence, `None` | `list` | `[]` | same element rules as C-array |
| `GByteArray` | `bytes`, `bytearray`, sequence of int | `bytes` | `b""` | byte sequence special case |

**Container transfer ownership effects:**
- `transfer=nothing` — borrow container and elements
- `transfer=container` — C owns container shell; caller owns elements
- `transfer=everything` — C owns everything; strings `g_free`'d, objects `g_unref`'d

---

## NULL / None rules

| Type family | `None` input | NULL output |
|---|---|---|
| Scalars (bool, int, float, enum, flags) | **rejected** — TypeError | never NULL |
| Strings (utf8, filename) | → NULL (always, even without `nullable` GIR attr — legacy compat) | → `None` |
| Pointers (object, boxed, callback) | → NULL if `nullable` or `allow-none` in GIR; else TypeError | → `None` |
| Containers (array, list, hash) | → NULL / empty container | → `[]` / `{}` |
| `GError` (out-only) | — | NULL → no exception; non-NULL → raises `GLib.Error` |

---

## Transfer ownership summary

| `transfer=` | Caller → C | C → caller |
|---|---|---|
| `nothing` | borrow (C must not free) | borrow (caller still owns) |
| `container` | C owns container, borrows elements | C frees container; caller owns elements |
| `everything` | strings: `g_strdup`; objects: `g_object_ref` | strings: `g_free`; objects: `g_unref` |

---

## Array length conventions

C-arrays pair with a companion integer parameter that carries the element count:

| Convention | Meaning |
|---|---|
| `BEFORE_ARRAY` | length arg immediately precedes the array arg in the C signature |
| `AFTER_ARRAY` | length arg immediately follows the array arg |
| `FIXED` | fixed-size array; no length arg in the GI signature |
| `ZERO_TERMINATED` | NULL/0 sentinel at the end; no explicit length arg |

The length arg is elided from the Python signature; ginext fills it in automatically.

---

## Relationship to stubs

The stub generator (`packages/ginext-stubgen`) uses a subset of this information
to emit Python type annotations:

- `PRIMITIVES` dict maps GI tags to Python type strings for return values and
  output parameters.
- `_resolve_type()` with `allow_pathlike=True` widens `filename` input params
  to `str | bytes | os.PathLike[str] | os.PathLike[bytes]`.
- Enum/flags widening: input params emit `EnumType | int`; signal callback
  params emit just `EnumType` (`widen_enums=False`).
- `GLib.Bytes` → `bytes` (Python builtin); `GLib.ByteArray` → `bytes`.
- `cairo.Context` → `cairo.Context[cairo.Surface]` (pycairo generic form).
