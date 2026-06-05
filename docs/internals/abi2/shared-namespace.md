# ABI2 Shared Namespace

ABI2 objects expose GObject methods, properties, and signals in one Python
attribute namespace. The lookup policy must be deterministic: a name must never
silently prefer a method over a property, a property over a signal, or a signal
over a method.

Names are normalized to Python identifiers:

```text
activate            -> activate
items-changed       -> items_changed
notify::title       -> not a direct attribute; represented through notify API
```

For a given object type, ABI2 collects all visible members for each normalized
name:

- methods, constructors, and static functions;
- GObject properties;
- GObject signals.

Inherited members count. If `Gtk.Widget` has both a method and signal named
`show`, every subclass that inherits both sees a conflict.

## No Conflict

If exactly one member kind owns a normalized name, the short spelling is used.

```python
obj.foo              # property value
obj.foo = value      # property assignment

obj.foo(...)         # method call

obj.foo.connect(cb)                # signal connection
obj.foo.connect(cb, after=True)
obj.foo.emit(...)
```

The short spelling is only available when it is unambiguous.

## Method/Signal Conflict

If a method and signal share a normalized name, the short spelling returns a
`MethodSignal` object. It is callable like the method and connectable like the
signal:

```python
action.activate(None)              # Gio.Action.activate() method
action.activate.connect(callback)  # Gio.SimpleAction::activate signal

GObject.Object.notify(obj, "title")  # explicit notification method
obj.notify("title").connect(cb)      # notify::title detailed signal
```

This keeps one spelling for the common GObject pattern where a method and its
corresponding signal intentionally share a name.

See [Methods](methods.md) for the callable side and [Signals](signals.md) for
the signal side.

## Property-Involved Conflict

If a property participates in the conflict, the property must remain a plain
value, so no member gets the short spelling.

The escaped spellings are:

```text
property    obj.foo_
method      obj.foo_func
signal      obj.foo_signal
```

Examples:

```python
widget.has_focus_              # Gtk.Widget:has-focus property
widget.has_focus_func()        # Gtk.Widget.has_focus() method

connection.closed_             # Gio.DBusConnection:closed property
connection.closed_signal.connect(cb)
```

The unsuffixed property-involved conflict should raise a clear ambiguity error
in the native ABI2 surface:

```text
AttributeError:
  'Gtk.Widget.has_focus' is ambiguous in ABI2.
  Use has_focus_ for the property or has_focus_func for the method.
```

Compatibility APIs may continue to expose legacy names where required, but the
ABI2 surface should not have two native spellings for the same member.

## Why Properties Use `foo_`

Conflicted properties use the Python keyword-escape style:

```python
obj.foo_
```

This matches established Python spelling such as `class_` and `from_`. It also
avoids magic value proxies. A property attribute should return the property
value, not an object that tries to behave like `bool`, `str`, `int`, a GObject,
and a property-binding helper at the same time.

For example, this must remain ordinary value access:

```python
if widget.has_focus_:
    ...
```

## Why Methods Use `foo_func`

Methods, constructors, and static functions are callable members. When a
property participates in the conflict, they use:

```python
obj.foo_func(...)
```

This preserves the callable shape while keeping property access as a plain
value.

## Why Signals Use `foo_signal`

Signals are not values and should be visibly signal objects when escaped
because a property participates in the same conflict:

```python
obj.foo_signal.connect(cb)
obj.foo_signal.connect(cb, after=True)
obj.foo_signal.emit(...)
```

The suffix avoids confusing callback-style attribute names such as `on_foo`.
At attribute level, `on_foo` reads like a handler function, not like the
signal object itself. As a constructor kwarg the spelling reads correctly
(`Gtk.Button(on_clicked=handler)`) — see
[Signals](signals.md#constructor-handler-kwargs).

## Defining Properties

ABI2 property declaration follows the spirit of builtin `property`, with
GObject registration metadata attached:

```python
class Item(GObject.Object):
    __gtype_name__ = "ExampleItem"

    title = GObject.Property(str, default="")
    count = GObject.Property(int, default=0)

    @GObject.Property(int)
    def computed(self):
        return self._computed

    @computed.setter
    def computed(self, value):
        self._computed = value
```

The first positional argument is the property type. Class access returns the
descriptor, and instance access returns the plain value:

```python
Item.count      # property descriptor
item.count      # int value
item.count = 3
```

Assignment through an ABI2 property descriptor routes through GObject's
property system. The descriptor stores the value when GObject calls back into
Python, and GObject emits the corresponding detailed notify signal once:

```python
item.notify(Item.count).connect(callback, owner=self)
item.count = 3
item.set_property("count", 4)
```

Names normalize like imported properties:

```text
item_count -> item-count
```

The descriptor is also valid as a detailed notify key:

```python
item.notify(Item.count).connect(callback, owner=self)
```

The first ABI2 bootstrap property slice was deliberately smaller than the final
property model:

```python
action.enabled
action.enabled = False
action.parameter_type
```

It only covered direct property get/set on the native object. The fuller ABI2
property model keeps direct property access as plain values, uses `obj.props`
for dynamic property lookup, and uses `type(obj).list_properties()` for
ParamSpec metadata.

## Implementation Notes

ABI2 lookup needs type-level member metadata:

1. Normalize all visible method, property, and signal names.
2. Group members by normalized Python attribute name.
3. If a group has one member kind, expose the short spelling.
4. If a group has exactly method plus signal, expose a method-signal object at
   the short spelling.
5. If a group includes a property and another member kind, expose only escaped
   spellings: `foo_`, `foo_func`, and `foo_signal`.
6. Make the unsuffixed property-involved conflicted name raise a diagnostic
   ambiguity error.

This likely belongs in the C attribute lookup path, because `obj.foo = value`
and lazy method lookup are controlled by `tp_getattro` / `tp_setattro`.
