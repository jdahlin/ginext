---
title: Overlays
description: Writing overlays and understanding the overlay authoring model.
sidebar_position: 1
---

# Overlays

Overlays are the mechanism `ginext` uses to improve the raw typelib surface in
targeted ways. This page is about writing them.

Instead of rewriting a whole namespace by hand, an overlay can adjust specific
parts of the API shape where the generated result is awkward for Python users.

## When to write an overlay

An overlay is the right tool when the generated API is technically correct but
not the right Python surface.

Typical reasons include:

- shortening repetitive call shapes
- adding Python protocol behavior such as iteration or indexing
- naming structured async results
- exposing a better constructor or helper method
- attaching a mixin or interface-like Python base
- exporting a compatibility alias without changing the underlying typelib

## Overlay building blocks

The overlay registrar supports several kinds of changes:

- `replace` for replacing an existing module-level callable
- `add` for adding a new module-level helper
- `method` for injecting or replacing class methods
- `property` for adding descriptor-style class properties
- `constructor` for custom constructor behavior
- `defaults` for supplying omitted argument defaults such as `flags` or
  `cancellable`
- `async_result` for naming async out-values on awaited results
- `bases` for adding useful Python base classes or mixins
- `constant` and `deprecated` for exported values and compat aliases
- `hide_attribute` for removing attributes from the public surface
- `on_first_access` for namespace lifecycle hooks

## Choosing the right primitive

- Use `replace` when the symbol already exists in the typelib and you want a
  different Python call shape.
- Use `add` when you are introducing a new helper name.
- Use `method` when the improvement belongs on a class.
- Use `property` when the class should expose a computed descriptor-like
  attribute.
- Use `constructor` when `__new__` or `__init__` behavior needs to be
  controlled directly.
- Use `defaults` when the raw method is fine but too noisy in normal code.
- Use `async_result` when async out-values should be named rather than left as
  tuple positions.
- Use `bases` when Python MRO behavior should reflect interface or mixin
  semantics.

## Writing an overlay module

Most overlay modules follow the same pattern:

```python
from ginext import Gio

overlay = Gio.overlay


@overlay.method("ListModel")
def __len__(self):
    return self.get_n_items()
```

The overlay module imports the namespace, takes its `overlay` registrar, and
registers changes through decorators or registrar methods.

## Authoring examples

These are the main authoring shapes used in the current tree:

- `defaults("File", "copy", flags=..., cancellable=None)` for omitted argument
  defaults
- `async_result("DBusProxy", "call_with_unix_fd_list", "", "out_fd_list")` for
  named async results
- `@overlay.method("ListModel")` for Python protocol methods
- `@overlay.property("Object")` for descriptor-style access like `notify`
- `overlay.bases("DesktopAppInfo", ["Gio.AppInfo"])` for interface-style bases
- `overlay.constant("Template", Template)` for exported namespace helpers
- `overlay.on_first_access(...)` for first-use lifecycle hooks

## Design guidance

The important idea is not "monkey patching". Overlays are part of the binding
surface itself, so they should be written with the same design standard as the
rest of the public API.

Good overlays tend to:

- make common call shapes shorter
- give collection-like types Python protocol methods
- turn awkward tuple returns into named results
- preserve the meaning of the underlying API while improving the surface
- stay narrow and targeted instead of replacing large areas at once

## User-facing namespace guides

The user-facing effects of many of these overlays are documented under
[Guides](../../guides/index.md) in the namespace pages such as `Gio`, `Gtk`, `Gdk`, and
`Pango`.
