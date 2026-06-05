# Disconnect identity

## Problem

Disconnect APIs need stable identity for Python callables and generated
trampolines. The current compatibility implementation can disconnect handlers
by the exact callable pointer stored in the `GClosure`, but wrappers make that
identity less direct.

## Current shape

- `src/_goi/GObject/Closure-signal.c` stores the callable pointer in
  `closure->data`.
- `goi_closure_disconnect_by_callable()` uses
  `g_signal_handlers_disconnect_matched(..., G_SIGNAL_MATCH_DATA, callable)`.
- Plain `connect(signal, handler)` stores `handler`.
- `connect(signal, handler, user_data)` stores a generated trampoline.
- `connect_object()` stores a generated trampoline.
- ABI2 owner-aware connections store a generated invoker over an
  owner-scoped callback adapter, with owner/source lifetime tracked by the
  native closure record.

## Why it matters

Users expect identity operations to be coherent:

- `disconnect_by_func(handler)` should disconnect handlers registered with that
  handler;
- removing a returned handler should release the exact native connection;
- connecting the same function twice should produce two removable connections;
- wrapper/trampoline layers should not make user-visible identity impossible.

If the native closure only knows the generated trampoline, then matching by the
original Python function requires extra metadata.

## Issue references

- [#106](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/106):
  `disconnect_by_func` must disconnect all matching handlers, not just one
  wrapper instance.
- [#102](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/102):
  a shared destroy notifier cannot be used as the sole callback identity.
- [#70](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/70):
  Builder user-data objects are part of signal handler identity and invocation
  semantics.
- [#746](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/746):
  swapped Builder handlers make callable/user-data identity more explicit.

## Broken example

```python
def on_notify(obj, pspec, marker):
    ...


obj.connect("notify", on_notify, "first")
obj.connect("notify", on_notify, "second")
obj.disconnect_by_func(on_notify)
```

The user thinks both connections were made with `on_notify`, but the native
closures may actually store generated trampolines because trailing user data
has to be appended at invocation time. If matching only sees the trampoline,
`disconnect_by_func(on_notify)` cannot reliably find the user-facing callable.

We are solving this so generated wrappers do not erase the identity that Python
APIs expose to users.

## Needed design

The native closure record should store both:

- the actual callable invoked by the marshaller;
- the user-facing callable identity used for disconnect matching.

For connections with trailing user data or generated ABI2 invokers, the record
should also store user data identity when the API promises function+data style
matching.
