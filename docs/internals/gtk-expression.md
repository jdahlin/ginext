# GTK Expression Mapping

`Gtk.Expression` is GTK's deferred value lookup mechanism. It describes how GTK
should obtain a value later, usually from a current object called `this`.

In Python terms:

```python
lambda row: row.name
```

is close to:

```python
Gtk.PropertyExpression.new(Row, None, "name")
```

but the GTK expression is declarative: GTK can evaluate it from C, use it in
list widgets, search/filter/sort machinery, bindings, and `.ui` files.

## Goals

- Keep the concrete GTK expression classes visible and usable.
- Avoid adding generic helpers such as `Gtk.attr()` or `Gtk.const()` to the
  global `Gtk` namespace.
- Allow high-level APIs such as `Gtk.DropDown(model, expression)` to accept
  common Python values and coerce them to `Gtk.Expression`.
- Keep ambiguous Python container types available for future expression values.
- Make closure-backed Python expressions explicit when the mapping is not a
  plain property lookup.

## Concrete Classes

ABI2 should keep these classes as the primary explicit API:

```python
Gtk.Expression
Gtk.PropertyExpression
Gtk.ConstantExpression
Gtk.ObjectExpression
Gtk.ClosureExpression
Gtk.CClosureExpression
Gtk.TryExpression
```

Their constructors can be made nicer, but their names should remain the
discoverable spelling for advanced users.

## Recommended Explicit API

Do not add global helpers like:

```python
Gtk.attr("name")
Gtk.const("Untitled")
Gtk.try_expr("display_name", "name")
```

If helper constructors are needed, put them under `Gtk.Expression`:

```python
Gtk.Expression.coerce(value, *, this_type=None, value_type=None)
Gtk.Expression.property(Row.name)
Gtk.Expression.constant("Untitled")
Gtk.Expression.object(obj)
Gtk.Expression.closure(lambda name: name.upper(), "name")
Gtk.Expression.try_(
    Row.display_name,
    Row.name,
    Gtk.Expression.constant("Untitled"),
)
```

The concrete-class spelling should also work:

```python
Gtk.PropertyExpression(Row.name)
Gtk.PropertyExpression(Row.file, File.display_name)
Gtk.ConstantExpression("Untitled")
Gtk.ObjectExpression(obj)
Gtk.ClosureExpression(lambda name: name.upper(), "name")
Gtk.TryExpression(Row.display_name, Row.name)
```

Class-level `GObject.Property` access returns the Python property descriptor,
not the installed `GObject.ParamSpec`. The installed ParamSpec should still be
available as `Row.name.pspec` for lower-level APIs, but expression construction
should accept the property descriptor directly. Bare property strings still work
when the surrounding API can infer a `this_type`, for example from a
`Gio.ListModel.get_item_type()` result.

## Coercion Rules

High-level APIs may accept a broad `expression` argument and convert it with a
single coercion function.

```python
def coerce_expression(value, *, this_type=None, value_type=None) -> Gtk.Expression:
    match value:
        case Gtk.Expression():
            return value

        case Property() as prop:
            return Gtk.PropertyExpression(prop.pspec)

        case GObject.ParamSpec() as pspec:
            return Gtk.PropertyExpression(pspec)

        case str() as path:
            # In expression position, a string is a property path, not a
            # constant string.
            return property_expression(path, this_type=this_type)

        case GObject.Object() as obj:
            return Gtk.ObjectExpression(obj)

        case _ if is_attrgetter(value):
            return property_expression(attrgetter_path(value), this_type=this_type)

        case _ if callable(value):
            return callable_expression(value, this_type=this_type, value_type=value_type)

        case _:
            raise TypeError(f"Cannot convert {type(value).__name__} to Gtk.Expression")
```

Do not automatically convert arbitrary literals to constants in generic
expression position. A string already means "property path", and automatic
literal conversion makes the API harder to reason about. Use explicit constants:

```python
Gtk.ConstantExpression("Untitled")
Gtk.Expression.constant("Untitled")
```

## Property Expressions

Property expressions should support dotted property paths:

```python
Gtk.PropertyExpression(Row.name)
Gtk.PropertyExpression(Row.file, File.display_name)
```

These map to `Gtk.PropertyExpression.new_for_pspec()` calls, chained when
multiple ParamSpecs are given:

```python
file_expression = Gtk.PropertyExpression.new_for_pspec(None, Row.file.pspec)
Gtk.PropertyExpression.new_for_pspec(file_expression, File.display_name.pspec)
```

String paths remain available where a type context exists:

```python
Gtk.Expression.property("file.display_name", this_type=Row)
```

Property name normalization should try the exact property name first, then a
GObject-style conversion:

```python
"display_name" -> "display-name"
```

This keeps Python spelling pleasant without losing compatibility with GObject
property names.

## Lambda and Callable Expressions

Simple attribute lambdas can be compiled to `Gtk.PropertyExpression`:

```python
lambda row: row.name
lambda row: row.file.display_name
```

For Python 3.13+ ABI2, using `dis` is preferable to `inspect.getsource()`:

- It works from the function object without source files.
- It avoids fragile REPL/editor source extraction.
- It is still a CPython bytecode contract, so the supported subset must remain
  deliberately small and tested.

Supported bytecode subset:

```python
RESUME
LOAD_FAST* row
LOAD_ATTR name
RETURN_VALUE
```

and repeated `LOAD_ATTR` for dotted paths.

Anything beyond simple property lookup should become a closure expression:

```python
lambda row: f"{row.icon} {row.name}"
lambda row: row.display_name or row.name
lambda row: row.display_name if row.display_name else row.name
```

These should eventually map to `Gtk.ClosureExpression`, ideally with
dependencies extracted from bytecode and passed as sub-expressions:

```python
Gtk.ClosureExpression(
    lambda icon, name: f"{icon} {name}",
    Gtk.PropertyExpression("icon"),
    Gtk.PropertyExpression("name"),
)
```

This is better than passing the whole row to an opaque Python callback because
the dependency expressions remain watchable by GTK.

Until Python-callable `Gtk.ClosureExpression` ownership is implemented,
unsupported callables should raise a clear `TypeError` and ask the user to build
or wait for explicit closure-expression support.

## `operator.attrgetter`

`operator.attrgetter("name")` can be accepted as optional sugar:

```python
from operator import attrgetter

Gtk.DropDown(rows, attrgetter("name"))
Gtk.DropDown(rows, attrgetter("file.display_name"))
```

This should map to the same property-path expression as a string.

Be critical here: `operator.attrgetter` describes Python attribute access, not
GObject property lookup. If CPython does not expose the path in a stable way, the
supported implementation must be guarded and tested, or ABI2 should prefer its
own explicit constructors.

## Try Expressions

`Gtk.TryExpression` is fallback on evaluation failure, not Python truthiness.

```python
Gtk.TryExpression(
    Row.display_name,
    Row.name,
    Gtk.ConstantExpression("Untitled"),
)
```

means:

1. Try evaluating `display_name`.
2. If that expression cannot evaluate, try `name`.
3. If that also cannot evaluate, use `"Untitled"`.

It does not mean:

```python
row.display_name or row.name
```

An empty string, `False`, or `0` is still a successful value. Truthiness fallback
must use `Gtk.ClosureExpression`.

## Avoid Sequence Shorthand

Do not use bare `list` or `tuple` as an alias for `Gtk.TryExpression`.

This shorthand is tempting:

```python
Gtk.DropDown(rows, ("display_name", "name"))
```

but it consumes Python's sequence shape for fallback and may conflict with
future expression meanings:

- tuple-valued expressions
- list-valued expressions
- closure argument lists
- multi-column sort keys
- literal tuple/list constants

Keep fallback explicit:

```python
Gtk.TryExpression(Row.display_name, Row.name)
Gtk.Expression.try_(Row.display_name, Row.name)
```

If list-valued expressions become useful later, add explicit constructors:

```python
Gtk.Expression.tuple("first_name", "last_name")
Gtk.Expression.list("first_name", "last_name")
```

but do not reserve `list` or `tuple` in the generic coercion path now.

## Operators

`Gtk.Expression("display_name" | "name")` cannot work because Python evaluates
the string union before calling `Gtk.Expression()`, and `str` does not implement
`|`.

This could work:

```python
Gtk.Expression("display_name") | "name"
```

but `|` is not a great primary fallback spelling because it reads as union/set
or, not "try this, then that". If supported at all, it should be optional sugar
on expression objects only, with `Gtk.TryExpression(...)` as the documented API.

## DropDown Mapping

Raw GTK-shaped API:

```python
Gtk.DropDown(model, expression)
```

Pythonic ABI2 API:

```python
Gtk.DropDown(["Factory", "Home", "Subway"])
Gtk.DropDown(rows, "name", search=True)
Gtk.DropDown(rows, lambda row: row.name, search=True)
Gtk.DropDown(rows, lambda row: f"{row.icon} {row.name}")
Gtk.DropDown(rows, Gtk.TryExpression("display_name", "name"))
```

Rules:

- A sequence of strings as the first argument becomes `Gtk.StringList`.
- A `Gio.ListModel` is used directly.
- A second `expression` argument is coerced through `Gtk.Expression.coerce()`.
- For `Gtk.StringList`, no expression is required; GTK already knows how to
  obtain strings from `Gtk.StringObject`.
- `get_selected_item()` remains the raw GTK method returning a `GObject.Object`.
- ABI2 may add a `selected_value` convenience that unwraps `Gtk.StringObject`
  to `str`.

## Class Mapping Summary

| Python input | GTK expression                           |
| -------------------------------------- | ---------------------------------------- |
| `Gtk.Expression` | returned as-is                           |
| `Row.name` | `Gtk.PropertyExpression` from `GObject.Property` descriptor |
| `Row.name.pspec` | `Gtk.PropertyExpression` from `ParamSpec` |
| `"name"` | `Gtk.PropertyExpression`                 |
| `"file.display_name"` | chained `Gtk.PropertyExpression`         |
| `operator.attrgetter("name")` | `Gtk.PropertyExpression`, optional       |
| `lambda row: row.name` | `Gtk.PropertyExpression`, via bytecode subset |
| `lambda row: f"{row.icon} {row.name}"` | `Gtk.ClosureExpression`                  |
| `GObject.Object` | `Gtk.ObjectExpression`                   |
| `Gtk.ConstantExpression("x")` | constant expression                      |
| `Gtk.TryExpression("a", "b")` | try expression                           |
| arbitrary literal | reject in generic expression position    |
| `list` / `tuple` | reject in generic expression position    |

`Gtk.CClosureExpression` should remain low-level or internal for now. Python
users should normally use `Gtk.ClosureExpression` for callback-backed
expressions.
