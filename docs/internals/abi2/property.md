# ABI2 GObject property API

This note describes the proposed ABI2 direction for Python-defined GObject
properties. ABI2 is allowed to diverge from PyGObject compatibility when the new
shape is clearer, faster, and better suited to data-heavy GTK applications.

## Goals

- Make stored GObject properties annotation-first.
- Keep computed/custom properties possible.
- Keep C/GObject property compatibility: `g_object_get_property()`,
  `g_object_set_property()`, GtkBuilder, bindings, and GTK expressions must keep
  working.
- Make row/data objects for `Gio.ListModel` concise.
- Preserve the native-property fast path for simple stored properties.

## Annotation-first stored properties

The preferred ABI2 syntax should be:

```python
class Song(GObject.Object):
    title: str
    artist: str = ""
    duration: float = 0.0
    selected: bool = False
    id: int = GObject.Property(readonly=True, construct_only=True)
```

Annotations define stored GObject properties. Plain class defaults become
property defaults. `GObject.Property(...)` is used when metadata or flags are
needed.

Equivalent internal shape:

```python
class Song(GObject.Object):
    title = GObject.Property(type=str)
    artist = GObject.Property(type=str, default="")
    duration = GObject.Property(type=float, default=0.0)
    selected = GObject.Property(type=bool, default=False)
    id = GObject.Property(
        type=int,
        readonly=True,
        construct_only=True,
    )
```

Implementation should synthesize the internal descriptors before property
registration. If descriptors are created after Python's normal `__set_name__`
phase, the class machinery must manually assign the property name.

## Declaration rules

### Annotation with no default

```python
title: str
```

Registers a stored property with the type from the annotation and the
type-appropriate default.

For primitive types, defaults follow PyGObject-style zero defaults:

- `str` -> `""`
- `int` -> `0`
- `float` -> `0.0`

Other types default to `None` unless explicitly supplied.

### Annotation with a plain default

```python
title: str = "Untitled"
count: int = 3
```

Registers a stored property with the annotation type and the class value as the
property default.

### Annotation with `GObject.Property(...)`

```python
id: int = GObject.Property(readonly=True, construct_only=True)
```

The annotation fills the property type when `type=` is omitted. Property keyword
arguments customize metadata, defaults, flags, and validation.

If both the annotation and `type=` are present, ABI2 should either:

- require them to agree, or
- explicitly define `type=` as the override.

The safer default is to require agreement and raise a `TypeError` on mismatch.

### Existing descriptor/decorator form

Computed/custom properties still need a descriptor-like form:

```python
class Song(GObject.Object):
    title: str

    @GObject.Property(type=str, readonly=True)
    def display_title(self):
        return self.title.casefold()
```

Stored properties should use annotations. Decorator properties should be treated
as computed/custom accessors and should not use native C storage.

## `GObject.Property(...)` options

The same `GObject.Property` object should be the customization mechanism for
annotation-first properties. Avoid adding a separate `field()` helper unless a
future requirement cannot fit this API.

### Core metadata

```python
title: str = GObject.Property(
    name="wire-title",
    nick="Title",
    blurb="Display title",
)
```

Supported metadata:

- `type`
- `name`
- `nick`
- `blurb`
- `default`
- `default_factory`, optional/later
- `minimum`
- `maximum`

### Friendly flag keywords

Expose common GObject flag combinations as booleans:

```python
name: str
id: int = GObject.Property(readonly=True, construct_only=True)
secret: str = GObject.Property(writeonly=True)
progress: float = GObject.Property(explicit_notify=True)
```

Supported convenience keywords:

- `readonly`
- `writeonly`
- `construct`
- `construct_only`
- `explicit_notify`

Raw `flags=` should still exist for low-level use.

Recommended rule: do not allow raw `flags=` to be mixed with convenience flag
keywords. Raise `TypeError` rather than defining subtle precedence.

## Flag mapping

GObject's relevant property flags:

```text
READABLE
WRITABLE
READWRITE = READABLE | WRITABLE
CONSTRUCT
CONSTRUCT_ONLY
EXPLICIT_NOTIFY
```

Suggested ABI2 mapping:

```python
name: str
```

```text
READWRITE
```

```python
name: str = GObject.Property(readonly=True)
```

```text
READABLE
```

```python
secret: str = GObject.Property(writeonly=True)
```

```text
WRITABLE
```

```python
id: int = GObject.Property(readonly=True, construct_only=True)
```

```text
READABLE | WRITABLE | CONSTRUCT_ONLY
```

This is the useful "readonly after construction" form. `CONSTRUCT_ONLY` is a
modifier on writable construction, so construction still needs a writable
channel.

```python
path: str = GObject.Property(writeonly=True, construct_only=True)
```

```text
WRITABLE | CONSTRUCT_ONLY
```

This is write-only and construct-only from the GObject property perspective.

```python
value: int = GObject.Property(construct=True)
```

```text
READWRITE | CONSTRUCT
```

`construct=True` should ensure the property is writable.

```python
progress: float = GObject.Property(explicit_notify=True)
```

```text
READWRITE | EXPLICIT_NOTIFY
```

With explicit notify, assignment updates storage but does not automatically emit
notify; user code must call:

```python
self.notify("progress")
```

## Dataclass-like mapping

ABI2 can borrow dataclass conventions where they map cleanly.

### `ClassVar`

```python
from typing import ClassVar

class Song(GObject.Object):
    schema_version: ClassVar[int] = 1
```

`ClassVar` should be ignored as a property/field, matching dataclasses.

### `InitVar`

```python
from dataclasses import InitVar

@GObject.DataItem
class Song(GObject.Object):
    path: InitVar[str]

    def __post_init__(self, path: str):
        ...
```

`InitVar` should follow dataclasses: constructor parameter only, passed to
`__post_init__`, not stored as a GObject property.

Do not automatically map every `InitVar` to a write-only GObject property. That
would diverge from dataclasses and make init-only values visible to GObject
introspection in surprising ways. If a write-only GObject property is needed,
use:

```python
path: str = GObject.Property(writeonly=True, construct_only=True)
```

### Readonly fields

Recent dataclasses do not have a per-field readonly mechanism. They only have
class-wide `frozen=True`, and `typing.Final` is not interpreted by dataclasses.

ABI2 should expose readonly through GObject property flags:

```python
id: int = GObject.Property(readonly=True, construct_only=True)
```

`typing.Final[T]` could be considered later as syntax sugar, but it should not
be required for the first implementation.

## `@GObject.DataItem`

Annotation-to-property registration should work on all `GObject.Object`
subclasses. A separate decorator can add dataclass-like generated methods for
small data objects and list-model rows:

```python
@GObject.DataItem
class Song(GObject.Object):
    title: str
    artist: str = ""
    duration: float = 0.0
```

First useful `DataItem` features:

- generated `__init__`
- generated `__repr__`
- optional/generated `__eq__`
- `__post_init__`
- `ClassVar` ignored
- `InitVar` passed to `__post_init__`
- keyword-only support later

`DataItem` should not be required for property registration. It is a convenience
layer for row/data classes.

## Validation rules

Recommended validation:

- `readonly=True` and `writeonly=True` together is invalid.
- `default` and `default_factory` together is invalid.
- `construct=True` and `construct_only=True` together should probably be
  invalid unless GObject explicitly allows and benefits from it.
- `construct=True` implies writable.
- `construct_only=True` implies writable during construction.
- Raw `flags=` cannot be mixed with convenience flag keywords.
- `minimum <= maximum` for numeric properties.
- `minimum <= default <= maximum` for numeric defaults.
- Annotation type and explicit `type=` mismatch raises `TypeError`.
- `ClassVar` annotations are ignored.
- `InitVar` annotations are only handled by `DataItem` constructor generation,
  not by property registration.

## Dynamic lookup and metadata

`obj.props` should remain the explicit property view for code that wants dynamic
property access. Direct attributes still return plain values:

```python
item.title
item.title = "New title"
```

`obj.props` is useful when the property name is not statically known:

```python
item.props["title"]
item.props["title"] = "New title"
```

The ABI2 `props` proxy should support dynamic lookup by name:

```python
item.props["title"]
item.props["item-count"]      # GObject spelling
item.props["item_count"]      # Python spelling, normalized
```

Attribute access on the proxy remains a convenience for identifier-shaped
properties:

```python
item.props.title
item.props.item_count
```

If a property name conflicts with a proxy method such as `items`, code can use
indexing:

```python
item.props["items"]
```

ParamSpec metadata should stay on the existing class-level API:

```python
properties = type(item).list_properties()

for pspec in properties:
    print(pspec.name, pspec.value_type, pspec.flags)

title_pspec = type(item).find_property("title")
```

`list_properties()` should return a read-only snapshot/view, not a mutable
`list`. The concrete type can be a tuple, a dedicated sequence view, or another
small immutable collection, but its behavior should make two facts clear:

- mutating the returned object does not mutate the GObject class;
- the caller is seeing the properties known at the time of the call.

This separates instance values from class metadata:

- `item.props` is the dynamic value view.
- `type(item).list_properties()` returns a read-only ParamSpec collection.
- `type(item).find_property(name)` is the single-ParamSpec lookup.

Do not add a separate `obj.properties` attribute for this. It would live in the
same shared object namespace as imported GObject methods, signals, and
properties. Keeping dynamic lookup under `obj.props` avoids another conflict
point while preserving plain direct property access.

## Native storage and performance

Annotation-first stored properties should lower to the same internal
native-storage property descriptors as the current fast path:

```python
title: str
```

should behave like:

```python
title = GObject.Property(type=str)
```

for registration, direct attribute access, `props`, `get_property()`, and
`set_property()`.

This keeps the API ergonomic without giving up the C fast path. Future storage
or lookup optimizations should happen below the descriptor/annotation surface.
