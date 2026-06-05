# ginext namespace -> class -> method -> invoke plan

This is the working plan for the next `src/ginext` layer.

The important split:

- Python owns the non-hot parts: namespace resolution, class construction,
  method placement, defaults, import/cache policy, and error shape policy.
- C owns the hot call path: vectorcall, argument binding, marshalling,
  invocation, return marshalling, and optional JIT/FFI dispatch.

Initial scope is deliberately narrow: support scalars and concrete GObject
classes only. Parent class inheritance is in scope. Interfaces, enums, flags,
boxed types, structs, unions, arrays, lists, hash tables, callbacks, `GValue`,
`GVariant`, and other container/compound values come later.

The public API should feel like normal GI namespaces:

```python
from ginext import GLib, Gio, GObject, Gtk

GLib.get_user_name()
cancellable = Gio.Cancellable()
button = Gtk.Button(label="Save")
```

Do not expose a public `repository`, `open_namespace()`, `require_version()`,
base classes, info objects, or method descriptors from `ginext`. All user API
should be reached through a namespace object.

## Package defaults

Native `ginext` code should not require users to call `require_version()`.
Projects declare versions in `pyproject.toml`:

```toml
[tool.ginext.versions]
Gtk = "4.0"
```

The packaging step writes a Python metadata sidecar into the installed
distribution:

```text
myapp-1.0.dist-info/
  gidefaults.py
```

```python
DEFAULT_VERSIONS = {
    "Gtk": "4.0",
}
```

`ginext` reads `gidefaults.py` from distribution metadata. It should not import
it as a normal module. Load the file via `importlib.metadata`, validate that it
is data-only, and read the `DEFAULT_VERSIONS` literal.

App distribution selection:

1. `GINEXT_APP=myapp` selects the distribution explicitly.
2. Otherwise infer from `__main__.__spec__.name`, then map top-level package to
   a distribution with `importlib.metadata.packages_distributions()`.
3. If inference is ambiguous, raise a clear error for unsuffixed imports or
   require an env override.

Version resolution order:

1. Explicit suffixed namespace import if supported, e.g. `Gtk4`.
2. Env override, e.g. `GINEXT_VERSIONS=Gtk:3.0,Gst:1.0`.
3. Direct project defaults from `gidefaults.py`.
4. Implied defaults from direct project defaults.
5. Highest installed typelib fallback, mainly for interactive/dev use.

Direct pins always beat implied pins.

## Implied defaults

`Gtk = "4.0"` should imply the matching GTK-family namespaces without requiring
the project to spell every one out.

Keep this as a runtime mapping shipped with `ginext`, not extra metadata:

```python
IMPLIED_DEFAULTS = {
    ("Gtk", "4.0"): {
        "Gdk": "4.0",
        "Gsk": "4.0",
        "GtkSource": "5",
        "WebKit": "6.0",
    },
    ("Gtk", "3.0"): {
        "Gdk": "3.0",
        "GtkSource": "4",
        "WebKit2": "4.1",
    },
}
```

The exact mapping can grow over time. The rule is stable: an implied version is
only used when there is no direct pin or env override for that namespace.

No `implied-by` marker is needed in `gidefaults.py`; it is an internal debug
concept at most.

## Python module layout

Avoid leading underscores in filenames. Keep the public surface clean through
`ginext.__getattr__`, `__all__`, and documentation rather than file names.

Proposed layout:

```text
src/ginext/
  __init__.py        # namespace gateway only
  defaults.py        # gidefaults.py discovery, env, implied defaults
  namespace.py       # Namespace object
  info.py            # GI metadata wrappers
  classbuild.py      # Python-owned class construction
  method.py          # method/constructor/static descriptor placement
  private/           # private C runtime and Python facade
  gobject.py         # current Python GObject/property support
```

Implementation modules may be importable, but they are not the public user API.

## Namespace pipeline

Top-level namespace access:

```text
ginext.__getattr__("Gtk")
  -> defaults.resolve_version("Gtk")
  -> runtime.require_namespace("Gtk", "4.0")
  -> Namespace("Gtk", "4.0")
  -> cache on ginext.Gtk
```

The namespace object owns member lookup and caching:

```text
Gtk.Button
  -> namespace resolves member metadata
  -> ObjectInfo for Gtk.Button
  -> classbuild builds Python class
  -> class cached by namespace/version/name and by GType where applicable
```

The namespace should be module-like enough for normal Python behavior, but it is
not exposed through a separate `ginext.repository` package.

## Class pipeline

Python builds classes from info objects:

```text
ObjectInfo(Gtk.Button)
  -> determine parent/base classes
  -> create Python type with type(...)
  -> install constructors/static methods
  -> install instance method descriptors
  -> install scalar/GObject constructors and methods
  -> install properties/signals later
  -> cache class
```

Base classes should be reached through namespaces:

```python
class MyObject(GObject.Object):
    ...
```

not through `ginext.GObjectBase` or any other top-level runtime class.

## Method pipeline

Python decides method placement and binding policy:

```text
FunctionInfo / MethodInfo
  -> exported Python name
  -> owner name
  -> constructor/static/instance classification
  -> has_self
  -> qualified name, e.g. "Gtk.Button.set_label"
  -> runtime.build_method_descriptor(...)
```

The descriptor itself is a C object implementing descriptor binding and
vectorcall. Once installed on a class or namespace, repeated calls should not
re-enter Python lookup machinery except for normal descriptor access.

## Constructor Surface

The default native class call should be property construction:

For concrete GObject classes in the first pass:

```python
cancellable = Gio.Cancellable()
button = Gtk.Button(label="Save")
```

This maps to `g_object_new_with_properties()`, using Python keyword arguments
as GObject construct properties. It is the normal, boring path and should work
for every concrete GObject type whose construction can be expressed through
properties.

GIR constructors should still be exposed explicitly as class methods using
their natural Pythonized names, so callers can choose the exact C constructor
when property construction is not what they want:

```python
obj = SomeObject.new()
obj = SomeObject.new_with_foo(foo)
obj = SomeObject.new_for_bar(bar)
```

For later interface/factory work, this means `Gio.File` can expose the GIR
factories as class methods even though the interface itself is not directly
constructible:

```python
file = Gio.File.new_for_path("notes.txt")
file = Gio.File.new_for_uri(uri)
file = Gio.File.new_for_commandline_arg(arg)
```

Constructor placement rules:

- The default class call, `Cls(...)`, is property-based GObject construction.
- GIR constructors become class methods: `new()`, `new_with_foo()`,
  `new_for_bar()`.
- Async constructor-like operations are class methods/factories, not
  `__init__` or `__call__`: `await Gio.File.temporary()`,
  `Gio.File.temporary_sync()`.
- Python constructors stay synchronous.

The first constructor allow-list should include only concrete GObject classes:

```text
Gio.Cancellable()                 -> g_object_new_with_properties()
Gtk.Button(label="Save")          -> g_object_new_with_properties()
```

Later, once constructor descriptors are in scope, add:

```text
Gio.File.new_for_path(path)       -> g_file_new_for_path()
Gio.File.new_for_uri(uri)         -> g_file_new_for_uri()
Gio.File.new_for_commandline_arg(...) -> g_file_new_for_commandline_arg*()
```

Generic GObject construction remains property-based:

```python
obj = SomeObject(prop_name=value)
```

Property keywords normalize Python spelling to GObject spelling:
`use_underline=True` maps to `"use-underline"`.

For the first pass, construct properties should accept only scalar values and
concrete GObject values. Reject unsupported property value types clearly rather
than falling into interface, boxed, array, or container handling.

## GObject construction

The current `ginext.private.object_new(gtype)` used by `ginext.gobject.GObject` is
too small for imported native classes:

```c
g_object_new ((GType)gtype_arg, NULL)
```

It returns a raw pointer as a Python integer and leaves Python to attach
`weakref.finalize(object_unref, ptr)`. That is enough for the current property
tests, but not for the namespace -> class -> method pipeline. It misses:

- keyword construct properties;
- construct-only properties;
- Python keyword to GObject property-name normalization;
- GValue conversion targeted to each `GParamSpec`;
- abstract-type rejection;
- `GInitiallyUnowned` floating ref sinking;
- wrapper identity through GObject qdata;
- returning an existing wrapper if the C instance is already wrapped;
- return-value wrapping from invoked constructors/methods;
- template instance hooks;
- non-GObject fundamental handling.

`ginext` should reuse/copy the existing `goi` construction/wrap model:

```text
src/goi/_goi/GObject/Object-construct.c
src/goi/_goi/GObject/Object-wrap.c
src/goi/_goi/GObject/Object-lifecycle.c
src/goi/_goi/GObject/Object-properties.c
```

Copy only the pieces needed for scalar and GObject construction first. Do not
carry over boxed, array, enum/flags, `GValue`, `GVariant`, or callback
marshalling until the corresponding `ginext` surface is in scope.

The native base type should allocate only the Python object in `tp_new`.
Construction should happen once in `tp_init` or an equivalent runtime helper:

```text
tp_new
  -> allocate Python wrapper only

tp_init(args, kwargs)
  -> reject unsupported positional args for generic property construction
  -> resolve class GType from class registry
  -> validate non-abstract
  -> convert kwargs to (names, GValue[]) using GParamSpec target types
  -> g_object_new_with_properties(gtype, n_props, names, values)
  -> sink floating refs when needed
  -> register wrapper qdata and ownership
```

Class-specific Python constructors can intercept positional arguments before the
generic GObject property path. In the first pass this should only be used for
concrete GObject classes. Later, when interfaces are in scope, `Gio.File(path)`
should dispatch to the hidden `g_file_new_for_path()` constructor descriptor,
then wrap the returned `GFile`, rather than trying to construct the interface
with `g_object_new_with_properties()`.

Suggested split:

```text
classbuild
  -> installs __new__/__init__ policy or class-level constructor adapter

runtime.construct_gobject(cls, kwargs)
  -> property-based g_object_new_with_properties path

runtime.invoke_constructor(callable_plan, args, kwargs)
  -> GIR constructor/factory path such as g_file_new_for_path()

runtime.wrap_gobject(ptr, transfer)
  -> qdata identity, class lookup by GType, floating-ref/ownership handling
```

Imported GObject classes and Python-defined subclasses should share the same
wrapper identity machinery. Returning a `GObject*` from invoke and constructing
one from Python should install the same qdata key, so repeated wrapping of the
same C instance returns the same Python object.

Changes needed from the current `ginext.private` shape:

1. Replace or supplement `object_new(gtype)` with a constructor helper that
   accepts a Python class/GType and keyword dict.
2. Move construction out of `ginext.gobject.GObject.__new__`; `__new__` should
   allocate the Python wrapper, while initialization constructs/registers the C
   instance.
3. Add a qdata-backed wrapper registry, not only `_gobject_ptr` plus
   `weakref.finalize`.
4. Reuse targeted `GValue` marshalling for construct properties.
5. Ensure constructor descriptors that return `GObject*` call the same
   `wrap_gobject()` path as method returns.
6. Preserve the existing Python-defined property/subclass registration tests
   while adding imported-class construction.
7. Keep unsupported construct-property value types out of scope with explicit
   `TypeError`s.

## Reusing invoke

Reuse/copy the existing `goi` invoke and marshalling implementation, but start
with a reduced marshalling surface. It has already been refactored around
descriptor-time planning and cached call-time facts.

Candidate source to carry over with `pygi_` naming:

```text
src/goi/_goi/invoke/
  plan.c / plan.h
  frame.c / frame.h
  bind.c
  return.c / return.h
  arg-cleanup.c
  ffi/invoke.c
  jit/invoke.c
  jit/plan.c

src/goi/_goi/marshal/
  scalar.*
  string.*          # only scalar string handling
  marshal.*         # trim to scalar + GObject dispatch
```

Initial invoke support:

- boolean and integer scalar types;
- floating-point scalar types;
- UTF-8/filename strings;
- `GType` if needed for common constructors such as `Gio.ListStore`;
- concrete GObject arguments and returns;
- `void` and scalar/GObject returns.

Explicitly out of scope for the first pass:

- interfaces;
- enums and flags;
- boxed types;
- structs and unions;
- arrays, lists, hash tables, and other containers;
- callbacks and closures;
- `GValue`;
- `GVariant`;
- multi-out result shaping;
- GError convenience mapping beyond preserving/raising the raw error path if
  already available from copied invoke code.

Prefer source sharing/copying at first over linking `ginext` against `_goi`
symbols. A shared internal C library can come later if duplication becomes a
real maintenance problem.

Use `PyGI` in C/runtime type names, not `Ginext`:

```c
PyGIInvokePlan
PyGIArgPlan
PyGIReturnPlan
PyGIMethodDescriptor
pygi_invoke_plan()
pygi_method_descriptor_dispatch()
```

## Invoke plan invariant

This is a hard performance invariant:

> Descriptor construction may call `gi_*`. Invocation must not call `gi_*` on
> the hot path.

Build the invoke plan when the descriptor is created. Cache every GI-derived
fact needed for binding, marshalling, invocation, and return conversion.

Descriptor build time may do:

```text
GIRepository / GIBaseInfo lookup
gi_callable_info_get_arg()
gi_arg_info_get_type_info()
gi_type_info_get_tag()
closure/destroy/length analysis
return type analysis
dlsym / target lookup
JIT or FFI path selection
```

Call time should do only:

```text
vectorcall
bind Python args from cached plan
marshal from cached type facts
invoke
marshal return from cached return facts
cleanup
```

No hot-path calls to:

```text
gi_callable_info_get_arg()
gi_arg_info_get_type_info()
gi_type_info_get_tag()
gi_base_info_unref()
```

If an unsupported path still needs GI metadata at call time, mark that path as
not optimized and add tests so it cannot silently become the normal path.

The method descriptor should own something like:

```c
typedef struct {
    char *qualified_name;
    int has_self;
    PyGIInvokePlan plan;
    PyGICallableTarget target;
    vectorcallfunc vectorcall;

    /* Optional: kept for repr/debug only, not used by hot invocation. */
    GICallableInfo *debug_info;
} PyGIMethodDescriptor;
```

Argument plans should copy primitive facts into our own structs:

```c
typedef struct {
    uint16_t gi_index;
    uint16_t py_index;
    uint8_t direction;
    uint8_t role;
    uint8_t transfer;
    uint8_t nullable;
    uint8_t type_kind;
    uint8_t storage_tag;
    uint8_t marshal_kind;
    int16_t length_arg;
    int16_t closure_arg;
    int16_t destroy_arg;
    uint8_t array_type;
    uint8_t array_elem_kind;
    size_t array_elem_size;
    uint64_t gtype;
    char *namespace_name;
    char *type_name;
} PyGIArgPlan;
```

The return plan should follow the same rule: copy the facts needed at call time
instead of walking `GITypeInfo` during return marshalling.

For the first pass, most of the role/length/closure/array fields should remain
unused. They are shown to keep the plan layout compatible with later work, but
unsupported roles and type kinds should fail during descriptor construction.

## First vertical slice

Start narrow and prove the whole path:

```python
from ginext import GLib

assert isinstance(GLib.get_user_name(), str)
```

Then add class/static/instance method coverage:

```python
from ginext import Gio

cancellable = Gio.Cancellable()
cancellable.cancel()
assert cancellable.is_cancelled()
```

This validates:

- app/default version resolution
- namespace import
- top-level function descriptor
- class construction
- Pythonic constructor adapter
- instance method
- GObject wrapping/unwrapping
- return marshalling
- descriptor plan caching

It intentionally does not validate interface, enum, boxed, array, callback, or
multi-return handling.

## Verification

Add runtime stats for GI metadata calls used by invoke planning and call paths.
Tests should reset stats after descriptor construction and assert repeated calls
do not perform metadata walks.

Example intent:

```python
from ginext import GLib
from ginext import runtime

fn = GLib.get_user_name
runtime.reset_stats()

fn()
fn()

stats = runtime.stats()
assert stats["invoke_gi_metadata_calls"] == 0
```

The exact stats API can stay implementation-facing, but the invariant should be
tested.

## Next implementation slice

The first vertical path should stay small. The next implementation slice should
make imported concrete GObject construction real enough for common widgets and
services without adding interfaces, boxed values, arrays, enums, or callbacks.

Target user-facing behavior:

```python
from ginext import Gtk, Gio

cancellable = Gio.Cancellable()
button = Gtk.Button(label="Save", visible=True)
button.set_label("Open")
assert button.get_label() == "Open"
```

Keep positional constructor adapters out of scope except for hand-picked
concrete GObject constructors when there is an obvious Python spelling.
Interfaces such as `Gio.File("path")` remain out of scope for this slice.

Implementation order:

1. Add `ginext.private.construct_gobject(gtype, kwargs)` next to the existing
   `object_new(gtype)` helper. Keep `object_new()` temporarily for the current
   Python-defined GObject tests, but route imported namespace classes through
   the new helper.
2. In C, reject abstract types before calling `g_object_new*`.
3. Normalize Python keyword names from underscore to dash in Python before
   passing them to C, and validate that every property exists on the target
   class.
4. Convert construct kwargs through each property `GParamSpec`, supporting only:
   `bool`, integer scalar types, floating-point scalar types, UTF-8 strings,
   `GType`, and concrete `GObject` instances.
5. Call `g_object_new_with_properties()` with prepared names and `GValue`s.
6. Sink floating refs for `GInitiallyUnowned`.
7. Wrap the returned object through the same pointer/GType path used by invoke
   returns.
8. Add qdata wrapper identity after the basic construction path works. Until
   qdata exists, repeated wrapping of a returned pointer may produce distinct
   Python wrappers; once qdata is in place, construction and method returns
   should share identity.

The qdata identity step should use one process-wide key and should not expose
any public base class from `ginext`. Ownership rules:

- wrappers created by construction own one strong ref;
- wrappers created from transfer-none method returns take a ref before
  wrapping;
- wrappers created from transfer-full method returns consume the returned ref;
- on failed wrapping, release the owned/ref'd pointer before raising.

Tests for this slice should stay focused on concrete classes:

```python
from ginext import Gio

c1 = Gio.Cancellable()
c2 = c1.ref()
assert type(c2) is Gio.Cancellable

from ginext import Gtk

button = Gtk.Button(label="Save")
assert button.get_label() == "Save"
```

Do not make broad `src/ginext/tests` expectations the driver yet; many of those
files describe later slices. Keep the accepted test set tied to this slice's
scope.

## Expansion order

After the first vertical slice:

1. More scalar/GObject method coverage.
2. More GObject construction paths.
3. Properties for scalar/GObject values.
4. Constants.
5. Enums and flags.
6. Boxed/struct/union types.
7. Arrays and containers.
8. Signals and callbacks.
9. Async helpers.
10. Overlays.

Keep the rule throughout: Python owns discovery and shape; C owns repeated call
performance.
