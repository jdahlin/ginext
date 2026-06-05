# ABI Modes Design

This document defines how the runtime should support more than one Python
binding ABI at the same time.

Here "ABI" means the Python-visible binding contract, not the platform C ABI.
The first two profiles are:

- `compat-v1`: PyGObject-compatible behavior.
- `native-v2`: a Python-native API that may intentionally break PyGObject
  compatibility for async, signals, properties, and result shaping.

The design goal is simultaneous use:

```python
from gi.repository import Gio as GioCompat
from goi import Gio as GioNative

ok, contents, etag = GioCompat.File.new_for_path(path).load_contents(None)
result = await GioNative.File.new_for_path(path).load_contents()
```

Both wrappers refer to the same underlying `GObject*`, but their Python classes,
method descriptors, signal APIs, property APIs, and return shaping belong to
different ABI profiles.

## Core Rule

ABI profile is a construction-time property.

Do not make hot paths branch on a dynamic "current ABI" global. Instead, build
ABI-specific objects once:

- namespace proxy
- Python type
- method descriptor
- closure/callback plan
- property descriptor
- signal descriptor
- wrapper qdata slot
- type registry entry

After construction, call dispatch should use the already-selected descriptor and
wrapper functions. The steady-state cost for single-ABI users should remain the
current cost: normal Python attribute lookup, vectorcall, and one direct qdata
lookup for object wrapping.

## Terminology

`GoiAbiProfile` is the immutable policy object for one Python ABI:

```c
typedef enum {
  GOI_ABI_COMPAT_V1,
  GOI_ABI_NATIVE_V2,
} GoiAbiKind;

typedef struct {
  GoiAbiKind kind;
  const char *name;
  GQuark wrapper_quark;
  GQuark inst_dict_quark;
  GoiObjectWrapFunc wrap_object;
  GoiClassRegistry *class_registry;
  const GoiAbiPolicy *policy;
} GoiAbiProfile;
```

The profile owns policy, not mutable user state. Good policy examples:

- whether `File.load_contents` means sync `load_contents` or future-returning
  `load_contents_async` plus `load_contents_finish`;
- whether return plus out params become a tuple or a named record;
- whether `obj.connect("clicked", cb)` is the primary signal API or
  `obj.clicked.add(cb)`;
- whether properties are exposed through PyGObject-compatible `props` behavior
  or through native descriptors;
- whether async callbacks receive compat wrappers or native wrappers.

`GoiSurface` from `docs/internals/native-compat-surface-plan.md` is still useful, but the
more precise internal name should be ABI profile. A future `native-v3` or
`strict-v2` can then be added without pretending the only dimension is
compat-vs-native.

## Import Model

Compatibility imports use the compat profile:

```python
from gi.repository import Gio, Gtk
```

Native imports use the native profile:

```python
from goi import Gio, Gtk4
```

This is the chosen public split:

- `from goi import Xxx` builds `native-v2` namespaces and classes.
- `from gi.repository import Xxx` builds `compat-v1` namespaces and classes.
- `goi.repository` remains a compatibility/transition implementation detail,
  not the preferred native import spelling.

Internally the namespace cache must include the ABI:

```text
(abi_profile, namespace, version) -> Namespace
```

The current `_namespace_cache[(name, version)]` shape is therefore a transition
artifact. Once ABI profiles exist, caching only by namespace/version would leak
native descriptors into compat imports or the reverse.

## Implementation Strategy

This is a large change and should be implemented as one coherent ABI boundary,
not as independent tweaks to signals, properties, async, and imports.

The implementation should still be staged internally. The first stage can make
top-level `goi` a mostly empty native import surface implemented in Python:

```python
from goi import GLib2
```

That stage should create separate `native-v2` namespace proxy objects but may
delegate actual class/function construction to the existing compat runtime. It
is useful because tests, documentation, and Python-level ABI2 experiments can
target the right public import path immediately.

The rule is:

```text
Do not document top-level `goi` as production ABI2 until the core boundary is
complete.
```

The core boundary includes:

- profile-specific namespace caches;
- profile-specific Python classes;
- profile-specific object wrapper qdata;
- profile-specific instance dictionaries;
- profile-specific class registry lookups;
- profile-specific method descriptors;
- profile-specific callback and closure marshalling.

Once those are in place, ABI2 features can be filled in behind `goi` without
risking accidental leakage into `gi.repository`.

This is the intended external behavior throughout the transition:

```python
from gi.repository import Gio as GioCompat
from goi import Gio as GioNative

compat_file = GioCompat.File.new_for_path(path)
native_file = GioNative.File.new_for_path(path)

type(compat_file) is type(native_file)  # False
compat_file is native_file              # False
# Both wrappers point at equivalent C state where the underlying API returns
# the same GObject*.
```

Callback behavior must be equally stable:

```python
compat_obj.connect("changed", compat_callback)  # callback sees compat wrappers
native_obj.changed.add(native_callback)         # callback sees native wrappers
```

Importing the other ABI later must not change already-created wrappers,
descriptors, or closures.

## Namespace Resolution

Namespace lookup should remain lazy:

```text
Namespace(abi, name, version).__getattr__(member)
  -> resolve member with ABI-aware overlay metadata
  -> build class/function/constant for this ABI
  -> cache on this namespace proxy
```

The ABI-aware lookup result should look conceptually like:

```c
typedef struct {
  const GoiAbiProfile *abi;
  const char *namespace_name;
  const char *version;
  const char *exported_name;
  GIBaseInfo *info;
  const GoiOverlayEntry *common_overlay;
  const GoiAbiMemberPolicy *abi_policy;
} GoiLookupResult;
```

Common overlay metadata remains for facts that are ABI-independent:

- symbol redirection such as `idle_add -> idle_add_full`;
- callback/user_data packing required to expose a callable safely;
- missing constants or aliases needed by both profiles.

ABI policy metadata is for behavior that can diverge:

- native async replacement of a sync method name;
- native result record shape;
- native signal/property descriptors;
- compat quirks that should not leak into native.

## Descriptor Model

Method descriptors should carry an ABI pointer:

```c
typedef struct {
  PyObject_HEAD
  vectorcallfunc vectorcall;
  const GoiAbiProfile *abi;
  GIFunctionInfo *info;
  const GoiOverlayEntry *overlay_entry;
  const GoiAbiCallablePolicy *abi_policy;
  GoiObjectWrapFunc wrap_object;
  ...
} GoiMethodDescriptor;
```

The important part is `wrap_object` or an equivalent function pointer. Return
marshalling and callback argument marshalling should call the profile-selected
wrapper directly instead of branching on every object result.

For `compat-v1`, `File.load_contents` builds a descriptor for the sync GI
method.

For `native-v2`, `File.load_contents` builds a future descriptor whose policy
points at:

```toml
[Gio.File.native-v2.methods.load_contents]
kind = "async-future"
source = "load_contents_async"
finish = "load_contents_finish"
result = "FileLoadContentsResult"
```

This descriptor is still cached as `File.load_contents`, so repeated calls pay
only the native future descriptor's normal vectorcall cost.

## Async Policy

Current `AsyncCallable` wrapping is useful proof of behavior, but as an ABI
mechanism it is too global: it mutates classes after class construction based
only on GIR async metadata.

Target shape:

- `compat-v1` keeps PyGObject-compatible async method names and callback
  behavior. Await sugar can exist only where PyGObject has it or where it does
  not change the callback contract.
- `native-v2` defaults to the awaitable operation for any method with an
  explicit ABI2 async plan. The blocking operation is exposed with `_sync()`,
  for example `file.load_contents_sync()`.
- The generated async operation object stores the profile's wrapper function,
  so finish results and callback source objects become native or compat objects
  consistently.
- Cancellation and context rules belong to the native async policy, not to a
  loose Python helper.

`Gio.File.load_contents` should be the first vertical slice:

```python
# compat-v1
ok, contents, etag = file.load_contents(None)

# native-v2
result = await file.load_contents()
contents = result.contents
etag = result.etag
sync_result = file.load_contents_sync()
```

Keep `load_contents_async` and `load_contents_finish` available in native mode
as explicit low-level escape hatches unless a later policy intentionally hides
them.

## Signals

Signals are an ABI boundary.

`compat-v1`:

```python
handler_id = obj.connect("notify::title", callback)
obj.disconnect(handler_id)
```

`native-v2`:

```python
button.clicked.add(callback, owner=self)
button.clicked.add_after(callback, owner=self)
button.clicked.emit()

action.activate.add(callback)  # method/signal object
obj.notify("title").add(callback)
```

The connection object must store the ABI profile and its object wrapper
function. A compat signal callback receives compat wrappers. A native signal
callback receives native wrappers. This avoids a subtle mixed-mode bug where a
compat user connects a signal but receives native objects because native was
imported first.

Signal descriptors should be installed on native classes only. Compat classes
can keep `connect`, `connect_after`, `connect_object`, and string detailed
signal names as their primary API.

Native signal names follow the ABI2 attribute policy in
`docs/internals/abi2/shared-namespace.md`:

```text
unconflicted signal    obj.foo.add(...)
method/signal pair     obj.foo.add(...), obj.foo(...)
property conflict      obj.foo_signal.add(...)
```

No conflicted member keeps the short name.

## Closures And Callback Wrapping

Closures must also be ABI-bound.

Every place that turns a Python callable into a C closure must capture the ABI
profile at construction time:

```c
typedef struct {
  PyObject *callable;
  GoiClosurePlan *plan;
  const GoiAbiProfile *abi;
  GoiObjectWrapFunc wrap_object;
  ...
} GoiCallbackClosure;
```

The same applies to signal `GClosure` wrappers:

```c
typedef struct {
  GClosure base;
  PyObject *callable;
  GICallableInfo *signal_info;
  const GoiAbiProfile *abi;
  GoiObjectWrapFunc wrap_object;
} GoiPyClosure;
```

The invariant:

```text
Callback arguments are wrapped for the ABI that created the closure.
```

This is independent of which ABIs are imported later. If a compat object
connects a signal, its callback receives compat wrappers. If a native object
connects a signal, its callback receives native wrappers. If native is imported
after a compat signal handler is already connected, the old closure still uses
compat wrapping.

This affects more than signals:

- signal handlers built by `connect`, `connect_after`, and native
  `signal.add`;
- GIR callback parameters passed to async APIs, sort/filter functions,
  foreach-style APIs, and builders;
- vfunc wrappers that marshal C calls back into Python;
- weak refs or destroy notifiers when they surface live objects to Python.

Implementation rule: callback invoke code must not call a global
`goi_gobject_new(...)` that implicitly means "the current/default ABI". It must
call the captured profile's wrapper function. The same rule should apply to
boxed wrappers and other GI registered types once those are split by ABI.

## Properties

Properties are also an ABI boundary.

`compat-v1` should preserve PyGObject behavior:

```python
obj.props.title = "Title"
title = obj.props.title
obj.get_property("title")
obj.set_property("title", "Title")
```

`native-v2` can expose Python descriptors:

```python
obj.title = "Title"
title = obj.title

widget.has_focus_        # conflicted property
widget.has_focus_func()  # conflicted method
```

This is likely where compatibility pressure is highest. Do not make the native
property model a thin alias of compat `props`; build a separate property
descriptor namespace for native classes. Keep `get_property` and `set_property`
as low-level methods if they are still useful.

Native property names follow the ABI2 attribute policy in
`docs/internals/abi2/shared-namespace.md`:

```text
unconflicted property    obj.foo
conflicted property      obj.foo_
```

Do not return magic scalar proxies from property value access just to expose
binding or notify helpers. Property attributes are values.

## Wrapper Identity And Qdata

Wrapper identity is ABI-local:

```python
native_obj is compat_obj  # False
```

Pointer identity is shared:

```text
native_obj -> same GObject*
compat_obj -> same GObject*
```

Use direct qdata slots:

```text
goi.compat_v1.wrapper
goi.compat_v1.inst_dict
goi.native_v2.wrapper
goi.native_v2.inst_dict
```

For two built-in ABIs this is better than a per-object dictionary. If many ABI
profiles become real later, add an optional profile table then; do not pay that
cost now.

## Class Registry

The reverse registry must include ABI:

```text
(abi, GType) -> PyTypeObject*
(abi, GIBaseInfo/name) -> PyTypeObject*
PyTypeObject* -> { abi, GType, info, orig_getattro }
```

This prevents `GType -> PyTypeObject*` from returning whichever ABI built the
class first.

Python-defined subclasses belong to the ABI of their base class. When wrapping
that object through the same ABI, return the exact subclass wrapper. When
wrapping it through another ABI, return the nearest introspected base class for
that ABI unless/until cross-ABI subclass projection is explicitly designed.

## Overlays And Policy Data

Keep overlays declarative and compiled.

Suggested split:

```toml
[common.GLib.idle_add]
identifier = "idle_add_full"
params = [...]
call = {...}

[compat-v1.Gio.File.methods.load_contents]
kind = "gi"
source = "load_contents"

[native-v2.Gio.File.methods.load_contents]
kind = "async-future"
source = "load_contents_async"
finish = "load_contents_finish"
result = "FileLoadContentsResult"
```

Common metadata changes how a GI symbol is safely exposed. ABI metadata chooses
which public contract to build for a name.

## Zero-Cost Target

If only one ABI is used:

- only that ABI's namespace proxies are created;
- only that ABI's classes and descriptors are built;
- only that ABI's qdata slot is touched for wrapping;
- only that ABI's class registry is populated;
- callbacks close over that ABI's wrapper function once.

If both ABIs are used:

- classes and descriptors are duplicated by ABI;
- the same `GObject*` may carry two wrapper qdata entries;
- callback and signal closures carry profile-specific marshalling;
- conversion helpers can bridge wrappers explicitly.

That is the right cost: pay for both ABIs only when both ABIs are imported.

## Migration Plan

1. Rename the design language from "surface" to "ABI profile" while keeping the
   current behavior unchanged.
2. Add built-in ABI profiles: `compat-v1` and `native-v2`.
3. Change namespace cache keys to include an ABI profile. Treat the existing
   `goi.repository` path as `compat-v1` during transition.
4. Route top-level `from goi import Xxx` through `native-v2`.
5. Keep `from gi.repository import Xxx` routed through `compat-v1`.
6. Add `const GoiAbiProfile *` to lookup results and callable descriptors.
7. Split wrapper qdata names into native/compat names.
8. Split instance dictionaries by ABI.
9. Split class registry reverse lookups by ABI.
10. Move class-built async wrapping behind ABI policy; stop applying it as a
    global class mutation.
11. Add ABI/profile storage to callback closures, signal closures, vfunc
    wrappers, and any callback trampoline that can marshal objects back into
    Python.
12. Implement ABI2 attribute grouping:
    `foo`, method-signal `foo`, and property-conflict escapes
    `foo_`, `foo_func`, `foo_signal`.
13. Add native signal descriptors and keep compat `connect*` behavior isolated.
14. Add native property get/set handling and keep compat `props` behavior
    isolated.
15. Implement the first native async method: `Gio.File.load_contents`.
16. Keep top-level `goi` ABI2 documented as experimental until the coexistence
    test suite passes for object wrapping, callbacks, signals, properties, and
    async.

## Early Tests

- Importing only `goi.Gio` never creates compat qdata for returned objects.
- Importing only `gi.repository.Gio` never creates native qdata for returned
  objects.
- Importing both ABIs can wrap the same `GObject*` as two distinct Python
  objects.
- Passing a native wrapper into a compat descriptor extracts the same pointer.
- Passing a compat wrapper into a native descriptor extracts the same pointer.
- Compat callbacks receive compat wrappers.
- Native callbacks receive native wrappers.
- A compat signal connected before importing native still receives compat
  wrappers after native is imported.
- A native callback passed to a GIR callback parameter receives native wrappers.
- A compat callback passed to the same GIR callback parameter receives compat
  wrappers.
- `compat_file.load_contents(None)` returns the PyGObject-compatible tuple.
- `await native_file.load_contents()` returns a native record.
- Native signal descriptors are absent from compat classes.
- Compat `connect("notify::prop", cb)` does not use native signal objects.
- Native property descriptors do not alter compat `props`.
- Conflicted native names do not expose the short spelling.
- Conflicted native properties use `foo_`.
- Method/signal conflicts use a callable/connectable method-signal object.
- Property-involved native method conflicts use `foo_func`.
- Property-involved native signal conflicts use `foo_signal`.

## Open Decisions

- Whether unsuffixed native imports such as `from goi import Gtk` should use
  the same version resolution rules as compat imports, or whether new native
  code should strongly prefer version-suffixed imports such as `Gtk4`.
- Whether native async result records should be generated lazily per method or
  predeclared per namespace.
- Whether native profiles beyond `native-v2` should be compile-time only or
  dynamically registered.
- How much cross-ABI subclass projection is worth supporting.
