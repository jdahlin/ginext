# GObject.Property optimization notes

This note records the current state of the `GObject.Property` fast-path work and
the measurements that guided the implementation.

## Goal

Python-defined `GObject.Property` is a hot path for GTK model rows and list
factories. The important case is a plain descriptor:

```python
class Row(GObject.Object):
    value = GObject.Property(type=int, default=0)
```

When there is no Python getter/setter, the property does not need to bounce
through Python descriptor storage on normal reads and writes. It can stay in C
and only convert at the edge:

- Python direct attribute read/write: `row.value`, `row.value = 42`
- Python property API: `row.get_property("value")`, `row.set_property(...)`
- C GObject API: `g_object_get_property()`, `g_object_set_property()`
- GTK bindings/expressions/property machinery

The C compatibility requirement is important: `g_object_get_property()` must
continue to work for C callers and GTK internals.

## Current implementation

Implemented in commit `2ce47c8 Add fast paths for native GObject properties`.

The current implementation:

- Marks plain `GObject.Property(...)` descriptors as native-storage properties
  when they have no Python `fget`/`fset`.
- Keeps custom getter/setter properties on the old Python descriptor path.
- Stores native values in a per-object qdata store keyed by `GParamSpec *`.
- Short-circuits `obj.value` and `obj.value = x` from `tp_getattro` /
  `tp_setattro`.
- Caches Python attribute name to native property metadata on the Python type,
  avoiding repeated underscore-to-dash conversion and
  `g_object_class_find_property()` for the direct attribute path.
- Keeps `g_object_get_property()` and `g_object_set_property()` working through
  the class `get_property` / `set_property` vfuncs.

The direct path is intentionally limited to native-storage properties. If a
property has a Python accessor, the descriptor semantics are preserved.

## Gio.ListModel conclusion

`Gio.ListModel.get_item()` does not itself read GObject properties. It calls the
`GListModel` interface `get_item` vfunc and returns the row object.

The property cost happens after the item is fetched, for example:

```python
row = model.get_item(position)
label.set_label(row.title)
```

or through GTK property machinery such as bindings and expressions.

That means list-model benchmarks need to separate:

- item retrieval cost: `model.get_item(0)`
- row property cost on an already-fetched row: `row.value`
- combined app pattern: `model.get_item(0).value`

The benchmark now includes a `Gio.ListModel row property fetch` section in
`examples/draw-bench/microbench.py`.

## Measurements

Representative focused JIT measurements after `2ce47c8`:

```text
plain attr get:          ~126 ns
plain attr set:          ~123 ns
props.value get:         ~327 ns
get_property("value"):   ~336 ns
set_property("value"):   ~402 ns
get_item(0):             ~1000 ns
cached row attr get:     ~123 ns
get_item(0).value:       ~1140 ns
```

A noop invocation-plan baseline in the same environment is roughly tens of
nanoseconds, commonly around `25-50 ns` depending on run noise. Direct property
access is still roughly `3x` a minimal call baseline, but most of the original
GObject property overhead has been removed for the direct attribute case.

The remaining direct-read cost is mostly:

- CPython attribute dispatch through `tp_getattro`
- Python type hidden-map lookup for property metadata
- wrapper to `GObject *` validation
- qdata store lookup
- stored `GValue` read
- Python object creation, e.g. `PyLong_FromLong`

`props.value` and `get_property()` are still slower because they go through
additional proxy/method/name paths.

## Dense slot experiment

An experimental dense-slot implementation was tried after `2ce47c8`.

Design:

- Store `slot_index` and storage kind in per-property metadata.
- Store per-instance native properties in a dense qdata array.
- Use typed union storage for primitive values.
- Materialize `GValue` only when `g_object_get_property()` or
  `g_object_set_property()` needs the C API bridge.

This preserved C compatibility, but the measurements did not justify keeping
the added complexity.

Observed result:

```text
dense slots obj.value best:       ~128 ns
dense slots obj.value = 42 best:  ~138-170 ns
dense slots get_property:         not improved, often worse
```

The best direct read was roughly tied with the committed GValue-backed fast
path, while set and generic property paths were worse. The reason is that dense
slots removed the qdata hash/GValue storage cost, but added enough metadata,
slot, default, and dispatch work that it did not move the total hot path.

Conclusion: do not keep dense slots until the higher-level lookup overhead has
been reduced.

## Likely next win

The next useful optimization is a monomorphic inline cache for direct attribute
access:

```text
(Py_TYPE(self), attr_name) -> native property metadata
```

The current implementation still looks up the hidden per-type dict on every
direct read/write. A small cache in `goi_gobject_property_fast_get()` and
`goi_gobject_property_fast_set()` could avoid that for hot loops and GTK list
factory code that repeatedly reads the same property name.

A good first version would cache:

- `PyTypeObject *type`
- `PyObject *name`
- `GParamSpec *pspec`

and invalidate conservatively by falling back when either pointer differs.

This should be lower risk than dense slots because it does not change storage
semantics or the C property bridge.
