# Property Bindings

Property binding should expose `GBinding` without turning property values into
helper objects.

Property access stays plain:

```python
item.title
item.title = "New title"
```

Bindings are created from the source object:

```python
binding = item.bind_property(Item.title, label, "label", sync=True)
binding.unbind()
```

## Native Signature

The ABI2-native API should use named options instead of raw binding flags:

```python
binding = source.bind_property(
    Source.enabled,
    target,
    "sensitive",
    sync=True,
    bidirectional=False,
    invert_bool=False,
)
```

Supported property keys:

- `str`, normalized from Python spelling to GObject spelling;
- `GObject.Property` descriptor;
- `GObject.ParamSpec`.

## Transform Callbacks

Transforms receive Python values, not raw `GValue` objects:

```python
scale.bind_property(
    Scale.value,
    label,
    "label",
    sync=True,
    transform_to=lambda binding, value: f"{value:.0f}%",
)
```

Bidirectional transforms require `bidirectional=True`:

```python
entry.bind_property(
    Entry.text,
    adjustment,
    "value",
    bidirectional=True,
    transform_to=lambda binding, text: float(text),
    transform_from=lambda binding, value: str(value),
)
```

`transform_from` without `bidirectional=True` should raise `TypeError`.

## Lifetime

Transform callbacks need native closure records. The binding object is the
cleanup handle, and `unbind()` must be idempotent.

The transform closure should hold the Python callable while the binding is
active and release it when:

- `binding.unbind()` runs;
- the source or target is finalized;
- the native binding is finalized.

Next: [[8 subclassing later]]

