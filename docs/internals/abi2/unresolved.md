# ABI2 unresolved design areas

This note tracks ABI2 questions that still need design work. It is grounded in
the local PyGObject GitLab and GNOME Discourse issue corpora, not only in the
current ABI2 prototype surface.

## 1. Closure ownership

Closure lifetime is the largest unresolved area. The issue summaries show this
as a cross-cutting problem, not just a signal API problem:

- signals;
- property binding transforms;
- Builder and template callbacks;
- async callbacks;
- vfunc callbacks;
- `Gtk.Expression` / closure expressions;
- list item factory callbacks.

These all need native closure state, but their owners are not identical. ABI2
needs one shared closure representation with explicit lifecycle classes: signal
connection, binding transform, template instance callback, async in-flight
callback, vfunc/class-owned callback, expression callback, and factory callback.

Cleanup must be idempotent and thread-aware. Callback argument shaping should be
shared, but ownership rules should not be hidden behind one generic callback
path.

## 2. Async policy

The async inventory and `Gio.File` prototype define direction, but the policy is
not complete. Remaining decisions include:

- main-context and `asyncio` loop ownership;
- cancellation mapping to `Gio.Cancellable`;
- finish functions that are constructors;
- nullable async results;
- async callbacks in templates;
- preserving `GError` shape through `await`;
- callback-compatible escape hatches for code that cannot use `await`.

Async should not be promoted from naming alone. Each awaitable operation needs a
call plan for finish pairing, cancellation, result shaping, and error
propagation.

## 3. Subclassing, vfuncs, interfaces, and GType registration

Properties and signals are only part of Python-defined GObject types. ABI2 still
needs a dedicated subclassing plan covering:

- interface inheritance and vfunc discovery;
- lazy versus eager vfunc registration;
- `do_constructed` and Builder-created object behavior;
- Python-defined interfaces;
- abstract and final type handling;
- template setup ordering;
- interaction between property installation, vfuncs, and class registration.

The issue corpora show subclass creation, GType registration, interface vtables,
vfunc resolution, property installation, and templates behaving as one system.
ABI2 should document and implement them as one system.

## 4. Property edge cases

The annotation-first property model is mostly shaped, but several details still
need policy:

- exact immutable return type for `list_properties()`;
- `default_factory`;
- mutable defaults and notify behavior;
- self-referential object properties;
- array/list properties;
- enum, flags, and Python type mapping;
- `construct` / `construct_only` interaction;
- whether raw `flags=` remains compatibility-only or also gets a deliberately
  named low-level native escape hatch.

Discourse property questions repeatedly hit these cases: self-typed properties,
enum properties, array properties, Python types as property types, and notify on
mutable/list-like property values.

## 5. Binding API completeness

The native `bind_property()` spelling is close:

```python
source.bind_property(
    source_property,
    target,
    target_property,
    sync=True,
    bidirectional=True,
    invert_bool=True,
    transform_to=...,
    transform_from=...,
)
```

Remaining questions:

- exact ABI2 `Binding` wrapper type;
- whether raw flags are only available through compatibility APIs;
- `BindingGroup` API parity;
- transform exception behavior;
- whether transform callbacks always use `(binding, value)`;
- whether `GObject.ParamSpec` property keys should be supported immediately.

Real application callsites use transforms and stored binding handles, so
`unbind()` and transform lifetime are part of the core design, not optional
polish.

## 6. Gtk.Template and Builder

Templates and Builder XML need their own ABI2 policy. Open areas:

- callback lookup in parent classes;
- external/shared callbacks;
- unused callback handling;
- async template callbacks;
- `GtkBuilderListItemFactory` callback scopes;
- property bindings in templates;
- clearer resource-path and missing-child errors.

Template callbacks should use the same closure machinery as signals, bindings,
and async callbacks, but their owner is the template instance.

## 7. Gtk.Expression and ListModel ergonomics

ABI2 only lightly covers GTK expression and model ergonomics. Likely future
design areas:

- Pythonic `Gtk.Expression` constructors;
- closure expression lifetime;
- property expression helpers;
- `Gio.ListModel[T]` and generated generic typing;
- iterable/list-like model helpers without breaking GIO semantics.

Existing issues mention `Gtk.Expression` overrides, `ListModel` iteration, and
generic typing for `Gio.ListStore` and `GObject.Property`.

## 8. Error model integration

`errors.md` defines the target exception shape, but every call path must use it
consistently:

- direct method invocation;
- async finish;
- callbacks;
- signal handlers with return values;
- vfuncs;
- DBus remote errors.

The issue corpus shows that errors often get lost or flattened when they cross
callback, closure, or async boundaries. ABI2 should centralize error conversion
so direct calls, callback `_finish()` calls, and awaitable APIs preserve the same
domain/code/message structure.

## Overall risk

The remaining ABI2 risk is less about user-facing spelling and more about the
shared runtime model below it. Signals, bindings, async operations, templates,
vfuncs, and expressions all need the same marshalling and exception policy, but
not the same lifetime owner. That distinction should drive the implementation.
