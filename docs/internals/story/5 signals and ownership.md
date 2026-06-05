# Signals And Ownership

Signals should be visible as native signal objects:

```pycon
>>> from ginext import Gio, static_owner
>>> cancellable = Gio.Cancellable.new()
>>> seen = []
>>> handler = cancellable.cancelled.add(lambda obj: seen.append(obj),
...                                     owner=static_owner)
>>> cancellable.cancel()
>>> seen == [cancellable]
True
```

This avoids stringly code for common signal use:

```python
button.clicked.add(self.on_clicked)
entry.notify("text").add(self.on_text_changed)
```

## Owner-Aware By Default

Callback APIs must not store an unowned Python callable for later C invocation.
Bound methods infer their owner:

```python
button.clicked.add(self.on_clicked)
```

Plain functions, lambdas, nested functions, partials, and callable objects need
an explicit owner unless they are wrapped by `owner.scoped(...)`:

```python
button.clicked.add(lambda button: self.save(), owner=self)
button.clicked.add(self.scoped(lambda button: self.save()))
```

Module-level callbacks use `static_owner`:

```python
button.clicked.add(log_click, owner=static_owner)
```

## Argument Adaptation

Signal callbacks may accept a positional prefix of runtime arguments:

```python
button.clicked.add(lambda: self.save())
button.clicked.add(lambda button: self.save(button))
entry.notify("text").add(lambda entry, pspec: self.sync_title())
```

The adapter should be computed when the handler is connected, not on every
signal emission.

## Handler API

Handlers are explicit objects:

```python
handler = button.clicked.add(self.on_clicked)

with handler.blocked():
    button.clicked.emit()

handler.remove()
```

`signal.remove(handler)` should require the handler object, not the original
callback.

## Native Closure Records

Signals are the first client of the closure system, but the record model should
be shared with:

- async callbacks;
- property binding transforms;
- Builder and template callbacks;
- vfunc callbacks;
- list item factory callbacks;
- expression callbacks.

Each closure record needs a kind, state, source, owner, weak target when
relevant, handler id when relevant, user callable, trampoline callable, and
in-flight state.

Next: [[6 files async and errors]]
