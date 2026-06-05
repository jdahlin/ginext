# ABI2 Signals

ABI2 signal attributes should expose signal objects instead of requiring string
signal names for normal Python code.

The verb is `connect` to align with PySide, Vala, gtkmm, and every existing
GObject doc. There is one connect method; modifiers are composable
keyword-only flags (`after`, `once`, `owner`). Unconflicted signal names use
the short spelling:

```python
handle = obj.clicked.connect(callback)
handle = obj.clicked.connect(callback, after=True)
handle = obj.clicked.connect(callback, once=True)
obj.clicked.emit()
```

If a signal participates in a pure method/signal conflict, the short spelling
is a `MethodSignal` object:

```python
action.activate(None)
action.activate.connect(callback)
```

If a property participates in the conflict, the signal uses `foo_signal`:

```python
connection.closed_signal.connect(callback)
```

The full conflict policy is in [Shared Namespace](shared-namespace.md).

## Signal Lifetime

Signal objects returned by ABI2 attributes should implement the owner-aware
native signal API:

```python
handle = obj.foo_signal.connect(callback)
handle = obj.foo_signal.connect(callback, after=True, once=True)
obj.foo_signal.disconnect(handle)
handle.disconnect()                       # equivalent
```

The same API is used for unconflicted signal names:

```python
handle = obj.clicked.connect(callback)
```

The handle (`ginext.SignalConnection`) exposes `handler_id`, `source` (weak),
`callback`, `is_connected`, `disconnect()`, and a `blocked()` context manager.
Both `signal.disconnect(handle)` and `handle.disconnect()` work; the handle
form is preferred for bound-method connections so callers do not need to
re-name the signal object.

Owner inference, the warn-on-unowned policy, and ambiguity rejection are
described under [Callback Ownership](#callback-ownership). The important ABI2
constraint is that the naming rules do not create hidden duplicate spellings.

## Connect Flags

There is one `connect()` method on every signal object. Modifiers are
keyword-only and compose freely:

```text
signal.connect(callback, *, after=False, once=False, owner=...)
```

- `after=True` — connect with `G_CONNECT_AFTER`, so the handler runs after the
  class default handler instead of before. Maps directly onto the GLib flag.
- `once=True` — disconnect automatically after the first invocation. Binding
  sugar; not a GLib API. Useful for one-shot bootstraps and to avoid the
  disconnect-in-handler pattern.
- `owner=...` — see [Callback Ownership](#callback-ownership). Supplants the
  `connect_object` family from older bindings.

The single-method rule avoids the combinatorial sprawl seen in older bindings
(`connect_object_after`, etc.). One spelling per intent: a method name names a
GObject operation, a flag names a modifier on that operation.

The `ginext.SignalConnection` handle exposes `after`, `once`, and `owner`
attributes so users can introspect what was connected.

## Optional Signal Arguments

ABI2 signal invocation supports ignored signal arguments. A callback may accept
all runtime signal arguments, a positional prefix of them, or none. For a signal
emitted as `source, arg1, ..., argN`, accepted callback shapes are positional
prefixes:

```python
button.clicked.connect(lambda: self.save())
button.clicked.connect(lambda button: self.save(button))
entry.notify(Item.title).connect(lambda: self.update_title())
entry.notify(Item.title).connect(lambda entry, pspec: self.update_title())
```

This is intentional API behavior, not a compatibility mode. UI code often has
the widget already available through `self`, especially with Gtk.Template and
Builder-style autoconnection, so forcing handlers to spell unused `button`,
`action`, or `pspec` arguments adds noise without improving correctness:

```python
@Gtk.Template.Callback()
def on_save_clicked(self):
    self.save()
```

The rule is one-way only: emitted arguments may be dropped from the end, but
missing required handler arguments are never synthesized. If a handler requires
more positional arguments than the signal emission supplies, Python raises the
normal `TypeError` for the missing argument. Defaults behave like ordinary
Python defaults:

```python
button.clicked.connect(lambda button, mode="save": self.run(mode))
```

The connect layer should use Python signature information to choose a call
shape once when the handler is connected. The resulting runtime signal-argument
limit is per connection, because it depends on the callback and any extra
arguments. The native closure marshal applies that cached limit before
converting and calling into Python. Extra arguments supplied through the API or
through `owner.scoped(...)` are intentional and are appended after any retained
signal arguments; they must not be silently discarded.

Generated ABI2 stubs should model these accepted callback shapes exactly. Do
not collapse native signal handlers to `Callable[..., Any]` except as a
temporary bootstrap fallback. For a signal with runtime arguments
`source, arg1, ..., argN`, generated overloads should accept:

```text
Callable[[], R]
Callable[[Source], R]
Callable[[Source, Arg1], R]
...
Callable[[Source, Arg1, ..., ArgN], R]
```

For void-return signals, `R` is `None` and async callback variants may be added
where the async policy allows them. Return-value signals must preserve the
signal return type in every overload.

## Callback Ownership

ABI2 callback APIs prefer owner-aware connections. Bound methods infer the
owner; explicit ownership is supported via `owner=`, a process-lifetime
sentinel, or a scoped wrapper:

```python
button.clicked.connect(self.on_clicked)
item.notify(Item.title).connect(self.on_title_changed)

button.clicked.connect(module_callback, owner=ginext.static_owner)

entry.changed.connect(
    self.scoped(lambda entry: self.update_title(entry.text))
)

button.clicked.connect(
    self.scoped(self.run_action, "save")
)
```

`owner.scoped(callback, *extra_args, **extra_kwargs)` returns a callback object
whose lifetime is scoped to `owner`. Runtime callback arguments are passed
first; extra arguments are appended after them:

```python
button.clicked.connect(self.scoped(self.run_action, "save"))

def run_action(self, button, action_name):
    ...
```

Unowned callables (plain functions, lambdas, nested functions, partials, and
callable objects) are accepted but emit `ginext.UnownedSignalHandlerWarning`
(a `ResourceWarning` subclass). The handler is stored in a process-lifetime
slot and stays connected until the source is finalized; the warning names the
source, signal, and the suggested fix (`owner=`, `ginext.static_owner`, or
`self.scoped(...)`).

A lambda that closes over more than one `GObject` is ambiguous: owner
inference cannot pick one, and the silent-leak path would hide the mistake.
This case raises `TypeError` and lists the candidate owners. Pass `owner=`
explicitly to resolve it.

For common lambdas that close over `self`, the scoped wrapper weakens closure
cells that point at the owner so the C-side closure does not keep the owner
alive. When the owner is finalized, the signal handler is removed.

The native record models the owner-side bookkeeping:

```text
PyGISignalRecord
  -> callback
  -> arg_adapter
  -> weak_owner
  -> weak_source
  -> handler_id
  -> after
```

The record holds the source and owner weakly, clears `handler_id` when the
source dies (so `disconnect()` is a safe no-op), and calls
`g_signal_handler_disconnect` when the owner dies or the user disconnects.
`connect()` returns a `ginext.SignalConnection` handle that owns the record;
it exposes `handler_id`, `source` (weak), `callback`, `is_connected`,
`disconnect()`, and a `blocked()` context manager.

## Defining Signals

ABI2 should support Python-defined GObject signals without forcing users back
to string-based connection calls.

Native code should be able to write:

```python
from ginext import GObject

class Source(GObject.Object):
    __gtype_name__ = "ExampleSource"

    pinged = GObject.Signal()
    item_changed = GObject.Signal(object)
    pair_changed = GObject.Signal(object, object)

source = Source()
source.pinged.connect(callback, owner=self)
source.pinged.emit()
source.item_changed.emit(item)
source.pair_changed.emit(left, right)
```

Signal names follow the same Python-to-GObject normalization as imported
signals:

```text
item_changed -> item-changed
```

An explicit name is still allowed when the GObject signal name should not be
derived from the Python attribute:

```python
changed = GObject.Signal(name="changed-explicit")
```

During the Python bootstrap stage, the native signal descriptor can register
itself by populating the class' `__gsignals__` dictionary before the existing C
subclass registration hook runs. Instance access then returns the same ABI2
signal object shape as imported signals:

```python
source.pinged.connect(...)
source.pinged.emit(...)
```

The compatibility path remains valid for the same class:

```python
source.connect("pinged", callback)
source.emit("pinged")
```

but native ABI2 code should prefer the attribute signal object.

## Property Notify

Do not make property values magic just to expose notify handlers.

Property values remain values:

```python
obj.title
obj.title = "New title"
```

Property notify uses the method-signal object for GObject's built-in `notify`
method/signal pair:

```python
obj.notify("title").connect(callback)
GObject.Object.notify(obj, "title")
```

For properties declared in Python, the property descriptor can be used as the
detail key:

```python
class Item(GObject.Object):
    __gtype_name__ = "ExampleItem"

    count = GObject.Property(int, default=0)

item = Item()
item.notify(Item.count).connect(callback, owner=self)
GObject.Object.notify(item, "count")
item.count = 3  # emits notify::count through GObject
```

Do not hang notify handlers off property values themselves. That would make
ordinary value access unpredictable.

## Constructor Handler Kwargs

ABI2 constructors accept `on_<signal>=callback` kwargs that connect a handler
in the same call that creates the object. Property kwargs and handler kwargs
mix freely:

```python
button = Gtk.Button(label="OK", on_clicked=self.on_ok)
```

- Keys are split on the `on_` prefix; the remainder is normalized to a signal
  name with the same `_`→`-` rule as attribute lookup.
- The owner of the connection defaults to the newly-constructed instance, so
  the handler stays connected for the lifetime of the object.
- The value must be a plain callable. Connect-after, scoped wrappers, and
  explicit owners use the post-construction `obj.signal.connect(...)` form.
- Notify and other detailed signals are intentionally not supported through
  this sugar; use `obj.notify("prop").connect(...)` after construction.
- An unknown `on_<name>` kwarg raises `TypeError` listing the closest signal
  names on the class.

The `on_foo` spelling is rejected as an attribute name (see
[Shared Namespace](shared-namespace.md)) because at attribute level it reads
as "the handler" rather than "the signal object." As a constructor kwarg the
opposite is true: `on_clicked=handler` literally is "the handler called on
clicked," so the spelling matches the meaning.

## Implementation Notes

The owner-aware signal connection machinery can initially be implemented behind
the ABI2 signal object, but creation of lazy `obj.foo_signal` objects should be
part of the same lookup policy as methods and properties.
