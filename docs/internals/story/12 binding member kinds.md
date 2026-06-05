# Binding Member Kinds

GIR describes several kinds of things. `ginext` should map each kind to a clear
Python object shape and keep those shapes consistent in runtime, stubs, and
docs.

## Namespace

A namespace is a generated module-like object:

```python
from ginext import Gio

Gio.File
Gio.Cancellable
Gio.IOErrorEnum
Gio.PRIORITY_DEFAULT
```

Namespace objects expose constants, functions, classes, interfaces, records,
unions, enums, flags, and error modules.

## Class

A GObject class becomes a Python class-like object:

```python
file = Gio.File("notes.txt")
action = Gio.SimpleAction.new("save", None)
```

The class owns constructors, static methods, class methods, properties,
signals, and type metadata.

Expected class metadata:

```python
Gio.File.gimeta.gtype
Gio.File.__ginext_namespace__
Gio.File.__ginext_abi__
```

## Interface

Interfaces should look class-like for typing and inheritance, but instances are
normally concrete objects implementing the interface:

```python
def read_file(file: Gio.File) -> bytes:
    ...
```

The runtime still needs interface metadata for method lookup, vfuncs, and
`Gio.ListStore.new(item_type=...)` style APIs.

## Function

A namespace function is called from the namespace:

```python
Gio.content_type_guess("image.png")
```

It has no implicit instance argument. Arguments and return values follow the
same marshalling rules as methods.

## Constructor

A constructor creates an object:

```python
file = Gio.File("notes.txt")
```

Named factories are class methods when they are not the default constructor:

```python
file = Gio.File.from_uri(uri)
```

Async factories should also be class methods:

```python
tmp = await Gio.File.temporary()
tmp_sync = Gio.File.temporary_sync()
```

## Method

A method is bound to an instance:

```python
cancellable.cancel()
parent = file.get_parent()
```

The runtime passes the underlying GObject instance as the native `self`
argument. Native object arguments are unwrapped before the C call.

## Static Method

A static method belongs to a class but has no instance:

```python
variant_type = GLib.VariantType.new("s")
```

If the method is really a named constructor, the generator should expose it as
a constructor or class method instead of preserving an awkward C spelling.

## Class Method

A class method receives the class or GType conceptually:

```python
Gio.ListStore.new(item_type=Gio.FileInfo)
```

Some GIR static functions are better modeled as class methods when they create
or query a specific type.

## Property

A property is an attribute on instances and a descriptor on Python-defined
classes:

```python
action.enabled
action.enabled = False
Item.title
```

The property value should be the value itself.

## Signal

A signal is a connectable object:

```python
handler = button.clicked.add(callback)
button.clicked.emit()
```

Signal objects also carry typing information for generated callback overloads.

## Enum

Enums are integer-compatible named values:

```python
Gio.IOErrorEnum.NOT_FOUND
```

They should type as the generated enum class, not as plain `int`, while still
marshalling to the underlying C integer.

## Flags

Flags are bitwise-combinable enum values:

```python
flags = Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS
```

They should type as an `IntFlag`-like generated class.

## Boxed, Record, Union

Boxed values are non-GObject native values with copy/free semantics:

```python
rect = Gdk.Rectangle(x=0, y=0, width=10, height=10)
```

Records and unions may be boxed or unboxed depending on GIR metadata. The
runtime should hide that distinction where Python ownership can be made clear.

Next: [[13 primitive and scalar values]]
