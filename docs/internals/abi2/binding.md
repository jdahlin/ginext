# ABI2 GObject property binding API

ABI2 property bindings should expose a small Python-native API over
`GBinding` without turning property values into helper objects.

Property access remains plain value access:

```python
item.title
item.title = "New title"
```

Bindings are created from the source object:

```python
binding = item.bind_property(Item.title, label, "label", sync=True)
binding.unbind()
```

## Goals

- Keep `GBinding` semantics: automatic updates, weak source/target ownership,
  bidirectional bindings, inversion, transforms, and explicit unbind.
- Accept ABI2 `GObject.Property` descriptors as property keys.
- Keep strings usable for imported or dynamic properties.
- Avoid magic property-value proxies such as `item.title.bind(...)`.
- Avoid raw `BindingFlags` on the native ABI2 API. Compatibility APIs may keep
  the GIR/PyGObject-shaped flags argument.

## Basic API

```python
binding = source.bind_property(
    Source.enabled,
    target,
    "sensitive",
    sync=True,
)
```

Suggested signature:

```python
def bind_property(
    self,
    source_property,
    target,
    target_property,
    *,
    sync: bool = False,
    bidirectional: bool = False,
    invert_bool: bool = False,
    transform_to=None,
    transform_from=None,
):
    ...
```

There is deliberately no `flags=` escape hatch on the ABI2-native API. The
supported options are the stable, named concepts ABI2 wants users to reach for:

- `sync=True` maps to `GBindingFlags.SYNC_CREATE`.
- `bidirectional=True` maps to `GBindingFlags.BIDIRECTIONAL`.
- `invert_bool=True` maps to `GBindingFlags.INVERT_BOOLEAN`.
- `transform_to=` supplies the source-to-target transform.
- `transform_from=` supplies the target-to-source transform and requires
  `bidirectional=True`.

Low-level callers that need arbitrary raw flags should use the compatibility
surface or a deliberately named low-level helper, not the native ABI2 method.

## Property Keys

`source_property` and `target_property` should accept:

- `str`: normalized from Python spelling to GObject spelling
  (`"item_count"` -> `"item-count"`).
- `GObject.Property` descriptor: `Item.item_count`.
- `GObject.ParamSpec`: usually from `type(obj).find_property("item-count")` or
  `type(obj).list_properties()`.

Descriptors are preferred for Python-defined properties because they survive
renames better and match notify detail usage:

```python
item.notify(Item.title).connect(callback, owner=self)
item.bind_property(Item.title, label, "label", sync=True)
```

Target properties often come from imported GTK/GIO classes, so string target
keys remain first-class:

```python
settings.bind_property("dark_mode", switch, "active", sync=True)
```

## Binding Object

The returned object should stay close to `GBinding`, but avoid exposing raw
flags as the primary metadata shape:

```python
binding.unbind()
binding.source
binding.target
binding.source_property
binding.target_property
binding.sync
binding.bidirectional
binding.invert_bool
```

`unbind()` is the only lifecycle operation. Do not add a `remove()` alias unless
another ABI2 lifetime API proves it needs uniform cleanup spelling.

The named boolean metadata mirrors the creation options. Do not expose a raw
`flags` property on the ABI2-native binding wrapper; compatibility callers can
still use `GBinding.get_flags()` on the low-level object when they need the
GObject-shaped view.

## Transform Callbacks

Simple transforms should read like ordinary Python functions:

```python
scale.bind_property(
    Scale.value,
    label,
    "label",
    sync=True,
    transform_to=lambda binding, value: f"{value:.0f}%",
)
```

For bidirectional bindings:

```python
entry.bind_property(
    Entry.text,
    adjustment,
    "value",
    bidirectional=True,
    sync=True,
    transform_to=lambda binding, text: float(text),
    transform_from=lambda binding, value: str(value),
)
```

`transform_from` without `bidirectional=True` should raise `TypeError`; it is
otherwise silently unused by GObject.

Transform callbacks should not expose `GValue` by default. They should receive
the binding object plus the source property value, and return the target
property value. This keeps compatibility with existing PyGObject callback
shapes:

```python
def transform_to(binding, value):
    ...
```

A transform failure should leave the target value unchanged and report the
Python exception through the normal callback exception path.

## Implementation Shape

The first implementation can split into two layers:

1. A Python ABI2 wrapper normalizes property keys, builds flags from named
   booleans, and wraps the returned `GObject.Binding`.
2. A small C helper handles transform callbacks via `g_object_bind_property_full`
   so Python callables have explicit lifetime state and do not rely on the raw
   introspected function-pointer API.

The transform helper should own:

- strong references to Python transform callables while the binding is active;
- weak refs to `source` and `target`;
- an idempotent clear path shared by `unbind()`, source/target finalization, and
  binding finalization.

This is the same lifetime class described for binding/factory closures in
`docs/newapi-signals.md`, but property binding does not need signal-style
`owner=`. The binding object is the handle users keep when they need explicit
cleanup.

## Compatibility Boundary

Compatibility mode may keep:

```python
source.bind_property("title", target, "label", GObject.BindingFlags.SYNC_CREATE)
```

The ABI2-native surface should instead require:

```python
source.bind_property("title", target, "label", sync=True)
```

This gives ABI2 one clear spelling for common application code while preserving
the low-level GObject-shaped call where compatibility requires it.
