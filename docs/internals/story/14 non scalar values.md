# Non-Scalar Values

Non-scalar values need explicit ownership rules. The user should work with
Python objects, while the runtime handles GObject references, boxed copies,
container ownership, and enum conversions.

## GObject Instances

GObject instances are native Python wrappers around GObject pointers:

```python
file = Gio.File("notes.txt")
parent = file.get_parent()
```

Rules:

- one live Python wrapper should represent one underlying GObject identity per
  ABI surface;
- passing a native wrapper to a method unwraps the GObject pointer;
- returned GObjects are wrapped back into native wrappers;
- transfer annotations decide whether the runtime refs, sinks, or borrows.

```python
store.append(info)
same = store.get_item(0)
assert same == info
```

## Interfaces

Interface-typed arguments accept any object implementing the interface:

```python
def load(file: Gio.File) -> bytes:
    ...
```

At runtime, the wrapper should validate the object's GType/interface support
before calling C.

## Boxed Values

Boxed values have copy/free semantics instead of reference-counted object
identity:

```python
rectangle = Gdk.Rectangle(x=0, y=0, width=10, height=10)
```

Rules:

- construct from Python values where fields are known;
- copy when C transfer rules require ownership;
- expose fields as Python attributes when safe;
- keep mutable boxed semantics explicit.

Boxed values should not pretend to be GObjects. They do not have signals,
properties, or object identity.

## Records And Structs

Records may be boxed, plain structs, or opaque structs. The generator should
classify them:

```text
boxed record     -> Python boxed class
opaque record    -> handle object with explicit methods
plain record     -> field-backed Python wrapper when safe
```

Opaque records should not expose fake fields.

## Unions

Unions need care. If GIR plus overlays define a discriminator, expose the active
arm:

```python
event.button.x
```

or provide a safe convenience when the active arm is known:

```python
event.x
```

Do not expose arbitrary inactive union arms as if they were valid Python
attributes.

## Enums

Enums map to generated integer-compatible classes:

```python
if error.code_enum is Gio.IOErrorEnum.NOT_FOUND:
    ...
```

Accepted arguments:

- the generated enum member;
- possibly `int` for low-level compatibility helpers;
- not arbitrary strings on the native ABI2 surface.

Prefer:

```python
file.query_info(attributes, flags=Gio.FileQueryInfoFlags.NONE)
```

over:

```python
file.query_info(attributes, flags=0)
```

## Flags

Flags map to bitwise-combinable generated classes:

```python
flags = Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS
```

Accepted arguments:

- generated flag members;
- bitwise combinations of the same flag class;
- `0` or a generated `NONE` member when the API permits no flags.

Reject mixing unrelated flag classes.

## GType

GType arguments should accept generated class objects:

```python
store = Gio.ListStore.new(item_type=Gio.FileInfo)
```

Raw GType values should still be accepted when callers already have one:

```python
gtype = Gio.FileInfo.gimeta.gtype
```

## GValue

`GValue` is a low-level container. Native ABI2 APIs should avoid exposing it
unless the API is truly about dynamic values.

Property get/set should use Python values:

```python
action.enabled = False
```

Binding transforms should use Python values:

```python
transform_to=lambda binding, value: str(value)
```

## Containers

Arrays, lists, hash tables, and variants should map to Python containers when
ownership and element types are known:

```python
names: list[str]
metadata: dict[str, GLib.Variant]
```

The generator should preserve element types in stubs where GIR provides them.
When element ownership is unclear, prefer a conservative runtime error over a
leaky partial conversion.

## Variants And Bytes

`GLib.Variant` should stay a distinct type because it carries a runtime type
signature. Convenience constructors can accept normal Python values when the
target variant type is known.

`GLib.Bytes` can expose Python bytes-like behavior, but ownership should still
follow `GBytes` immutability and lifetime rules.

## Callbacks

Callbacks are non-scalar values with lifetime. Any callback that can be invoked
after the call returns must create a closure record.

Examples:

- signal handlers;
- async callbacks;
- binding transforms;
- template callbacks;
- factory callbacks;
- vfuncs.

The accepted callable shape belongs in generated stubs. The lifetime owner
belongs in the runtime closure record.

Next: [[15 goi cli]]
