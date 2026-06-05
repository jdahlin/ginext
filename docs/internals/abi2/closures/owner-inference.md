# Owner inference

## Problem

ABI2 needs to decide when a callback has an obvious lifetime owner and when the
user must declare one.

Bound GObject methods have an inferable owner: `callback.__self__`. Plain
functions, lambdas, nested functions, partials, and callable objects do not have
a reliable universal owner.

## Current shape

- `docs/internals/abi2/signals.md` says bound methods infer the owner.
- `docs/internals/abi2/signals.md` also says plain functions, lambdas, nested functions,
  partials, and callable objects must use `owner=`, `goi.static_owner`, or
  `owner.scoped(...)`.
- `src/goi/abi2.py` implements this in `_infer_owner()`.
- Compatibility `connect()` still accepts ownerless callables.

## Why it matters

Implicit ownership is attractive for ergonomics, but wrong inference is worse
than requiring an explicit owner. A callable may capture multiple GObjects, a
service singleton, a temporary model item, or no GObject at all.

Treating every callable as ownerless and immortal recreates the compatibility
cycle problem. Treating every captured object as an owner is ambiguous and
cannot be implemented safely for arbitrary Python callables.

## Issue references

- [#219](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/219):
  bound methods are dangerous because the method object owns `self`.
- [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735):
  `self` captured by callbacks demonstrates why ownerless later-invoked
  callbacks are not a safe ABI2 default.
- [#508](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/508):
  typed signal callback helpers imply a more explicit signal connection API
  surface, including better callback shape and ownership rules.

## Broken example

```python
class Window(Gtk.ApplicationWindow):
    def __init__(self):
        super().__init__()
        self.action = Gio.SimpleAction.new("refresh", None)
        self.action.connect("activate", lambda *_: self.refresh())
```

The lambda has no obvious owner from the outside. It captures `self`, but
introspecting arbitrary Python closures is not a reliable ownership rule:
another lambda might capture a model, a singleton, and a window at the same
time.

ABI2 solves this by making the safe case implicit and the ambiguous case
explicit:

```python
self.action.activate.add(self.on_refresh)
self.action.activate.add(self.scoped(lambda *_: self.refresh()))
self.action.activate.add(module_callback, owner=goi.static_owner)
```

We are solving this so ABI2 can reject ambiguous lifetime at connection time
instead of discovering it later as a leak or delayed finalization bug.

## Needed design

The ABI2 rule should stay conservative:

- infer only bound GObject methods;
- require explicit owner for everything else;
- provide `goi.static_owner` for true process-lifetime callbacks;
- provide `owner.scoped(...)` for lambdas, partials, and helper callables tied
  to a GObject owner.

The final native implementation should enforce the same rule before creating a
later-invoked native closure.
