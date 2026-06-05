# Strong callback retention

## Problem

GObject signal closures strongly retain the Python callable. That is correct
for compatibility, but it creates cross-runtime cycles when the callable owns or
captures an object that is also part of the native graph owning the signal.

Common shapes:

- `button.connect("clicked", self.on_clicked)`;
- `button.connect("clicked", lambda *_: self.save())`;
- `source.connect("changed", functools.partial(self.update, item))`;
- Builder/template callback lookup that stores a bound method;
- factory or binding transform callbacks that capture the widget/controller.

The C signal system owns the `GClosure`; the `GClosure` owns the Python
callable; the callable may own `self`; `self` may own the source or the native
graph that keeps the closure alive.

## Current shape

- `src/_goi/GObject/Closure-signal.c` stores a new ref to the Python callable
  in `GoiPyClosure.callable`.
- Compatibility `connect()` deliberately accepts any callable and optional
  trailing user data.
- ABI2 `BoundSignal.add()` rejects unowned non-method callbacks, but this is a
  Python policy layer on top of compatibility `connect()`.

## Why it matters

This is not just a memory leak. If `self` stays alive because a native closure
captures it, Python-level finalization and `do_dispose()` timing can change.
The native graph may also hold resources that users expect to be released when
the visible object is removed.

The risk is highest for UI code because GTK object graphs commonly have native
ownership edges that Python GC cannot see.

## Issue references

- [#42](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/42):
  `TreeSelection` callbacks kept references after the apparent widget lifetime
  ended.
- [#136](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/136):
  Builder signal hookup created `self -> builder -> callback -> self` cycles.
- [#219](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/219):
  storing bound methods as callbacks retained the application object.
- [#596](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/596):
  template callbacks and signal callbacks kept objects alive until shutdown.
- [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735):
  callbacks capturing `self` blocked expected `do_dispose()` behavior.

## Broken example

```python
class Page(Gtk.Box):
    def __init__(self):
        super().__init__()
        self.button = Gtk.Button(label="Save")
        self.append(self.button)
        self.button.connect("clicked", self.on_clicked)

    def on_clicked(self, button):
        self.save()
```

The native button owns the signal closure. The closure owns the bound method.
The bound method owns `self`. `self` owns the button. Removing the page from the
UI may not release the page because the closure closes the ownership loop.

We are solving this so later-invoked callbacks do not silently become lifetime
owners of widget/controller objects unless the API says they should.

## Needed design

ABI2 should keep compatibility `connect()` behavior, but native ABI2 callback
APIs should not store an unowned callable for later C invocation.

For owner-aware APIs, strong callback retention must be mediated by an explicit
owner record. That record needs authority to disconnect or invalidate the native
closure when the owner dies or is cleared.
