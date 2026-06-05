# Closure cell weakening

## Problem

`owner.scoped(...)` tries to avoid retaining the owner by weakening direct
references to the owner in callback closure cells and partial arguments.

This handles common lambda patterns, but it is necessarily heuristic. Python
callables can retain an owner through many shapes that are not direct closure
cells.

## Current shape

- `src/goi/abi2.py` implements `_weaken_owner_closure()`.
- Direct closure cells equal to the owner become `weakref.proxy(owner)`.
- Direct partial args or keyword values equal to the owner are weakened.
- Bound methods on the owner are stored as the underlying function plus a weak
  owner reference.

## Cases it cannot fully solve

- owner stored inside a list, tuple, dict, dataclass, or custom object;
- owner reachable through another object captured by the callback;
- callable objects with `self.owner`;
- globals or module singletons that point back at the owner;
- closures that capture aliases that are not equal to the unwrapped owner;
- callbacks whose behavior cannot tolerate `weakref.proxy` after finalization.

## Why it matters

Cell weakening is useful as an ergonomic compatibility layer, but it should not
be treated as the ownership model. It is a best-effort transformation for common
callbacks, not proof that no strong path to the owner remains.

## Issue references

- [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735):
  the motivating modern case for lambdas and callbacks capturing `self`.
- [#596](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/596):
  template and programmatic callbacks can retain objects through callback
  capture paths.
- [#634](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/634):
  factory callbacks can keep UI objects alive after the visible owner closes.

## Broken example

```python
class Page(Gtk.Box):
    def __init__(self):
        super().__init__()
        self.button = Gtk.Button()
        self.button.clicked.add(
            self.scoped(lambda button: self.handle_click(button))
        )
```

Without weakening, the lambda cell holds `self` strongly. The scoped owner
record says the handler should die with `self`, but the callback itself keeps
`self` alive and prevents that owner-death path from running.

The current Python prototype weakens direct cells that contain the owner, which
fixes this common case. It does not fix indirect captures:

```python
state = {"owner": self}
self.button.clicked.add(self.scoped(lambda *_: state["owner"].handle_click()))
```

We are solving this so scoped callbacks are useful for common Python patterns,
while still treating the native owner record as the real cleanup authority.

## Needed design

The native owner record must be the authority. Weakening should remain a helper
that reduces accidental retention, while owner death still disconnects or
invalidates the underlying native closure.

Tests should include both cases:

- common scoped lambdas that should not keep the owner alive;
- unsafely captured owners where explicit cleanup still has to be correct.
