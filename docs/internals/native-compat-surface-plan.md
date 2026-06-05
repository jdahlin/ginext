# Native And Compat Surface Plan

This plan sketches how goi can support two public API surfaces without adding
runtime cost to native-only code:

- `gi.repository`: PyGObject-compatible surface.
- `goi`: Python-native surface.

The motivating conflict is that the same method name cannot be both sync and
async:

```python
# Compat surface
contents, etag = file.load_contents()

# Native surface
result = await file.load_contents()
contents = result.contents
etag = result.etag
```

The two surfaces must therefore have separate descriptors, wrapper classes, and
result shaping, while sharing the same underlying GObject instances and call
planning machinery.

## Import Model

Compatibility mode:

```python
import goi
from gi.repository import Gtk, Gio, GLib
```

Native mode:

```python
from goi import Gtk4, Gio, GLib
```

Compatibility imports should preserve PyGObject behavior and names. Native
imports may choose Python-native behavior: async-first blocking operations,
record results, `PathLike` inputs, typed signal helpers, and other ergonomic
changes.

## Fast-Path Requirement

Native-only code should stay as close as possible to the current cost model.
Current object wrapping stores a single borrowed Python wrapper directly in
GObject qdata:

```text
goi.wrapper -> native Python wrapper
```

Do not replace that with a per-object dictionary or surface table on the hot
path. Instead use direct qdata slots:

```text
goi.native_wrapper -> native Python wrapper
goi.compat_wrapper -> compat Python wrapper
```

If compat is never imported, only the native qdata slot is used. Native wrapping
then remains one qdata lookup and one wrapper check.

Only introduce a generic surface table if goi grows more than two surfaces.

## Surface Concept

Add an internal `GoiSurface` concept:

```c
typedef enum {
  GOI_SURFACE_NATIVE,
  GOI_SURFACE_COMPAT,
} GoiSurfaceKind;
```

Surface should be a construction-time property of descriptors, classes, and
closures. Hot paths should not ask "which surface is this?" dynamically when
they can instead call a surface-specific helper directly.

Preferred hot-path shape:

```c
PyObject *goi_gobject_new_native (PyObject *base_type, GObject *gobject, int transfer_full);
PyObject *goi_gobject_new_compat (PyObject *base_type, GObject *gobject, int transfer_full);
```

Callback closures can store a function pointer instead of branching:

```c
typedef PyObject *(*GoiObjectWrapFunc) (PyObject *base_type, GObject *gobject, int transfer_full);

typedef struct {
  GoiObjectWrapFunc wrap_object;
  /* callback plan, callable, user data, etc. */
} GoiClosure;
```

## Wrapper Identity

Wrapper identity becomes surface-local:

```python
compat_button is native_button  # False
```

Both wrappers point at the same C object:

```text
compat_button -> GtkButton*
native_button -> GtkButton*
```

The invariant:

```text
Values returned by a descriptor are wrapped for that descriptor's surface.
Values passed into a Python callback are wrapped for that callback's surface.
```

Examples:

```python
# Compat signal connection.
button.connect("clicked", callback)
# callback receives gi.repository.Gtk.Button

# Native signal helper.
button.clicked.connect(callback)
# callback receives goi.Gtk4.Button
```

Passing wrappers into C should accept either surface. Pointer extraction remains
surface-agnostic:

```text
PyObject wrapper -> GObject*
```

Returning values from C is surface-specific:

```python
compat_child = compat_box.get_first_child()  # compat wrapper
native_child = native_box.get_first_child()  # native wrapper
```

## Type Registry

The class registry currently has a single reverse lookup:

```text
GType -> PyTypeObject*
```

That must become surface-aware:

```text
(surface, GType) -> PyTypeObject*
```

For the fast path, this can be implemented as two direct registries instead of
one generic map:

```text
native_gtype_to_pytype
compat_gtype_to_pytype
```

Same for no-GType records keyed by `GIBaseInfo` or `"Namespace.Name"`.

Python-defined subclasses should belong to the surface of their base class.
The registered GType should record the owning surface and Python class.

When wrapping a Python-defined subclass through the same surface, return the
exact subclass wrapper. When wrapping it through the other surface, prefer the
nearest introspected base wrapper in the requested surface rather than leaking a
foreign-surface Python subclass into the caller.

## Object Qdata

Current qdata keys:

```text
goi.wrapper
goi.inst_dict
```

Planned qdata keys:

```text
goi.native_wrapper
goi.compat_wrapper
goi.native_inst_dict
goi.compat_inst_dict
```

Instance dictionaries are also surface-local. Native and compat wrappers can
have different Python classes and descriptors, so sharing arbitrary `__dict__`
state across them would be surprising.

The existing single-wrapper functions can be renamed internally to native:

```text
goi_gobject_wrapper_quark()      -> native wrapper quark
goi_gobject_inst_dict_quark()    -> native instance dict quark
goi_gobject_new()                -> native wrapper creation, initially
```

Then add explicit compat entry points once the compat import path exists.

## Native Async Future API

The native surface resolves planned sync/async conflicts in favor of async:

```python
result = await file.load_contents()
contents = result.contents
etag = result.etag
sync_result = file.load_contents_sync()
```

The compat surface keeps PyGObject behavior:

```python
contents, etag = file.load_contents()
file.load_contents_async(cancellable, callback, user_data)
```

Because only TOML is available for hand-written metadata, native future methods
should be data-driven:

```toml
[File.native.methods.load_contents]
kind = "async"
source = "load_contents_async"
finish = "load_contents_finish"
result = "FileLoadContentsResult"

[File.native.methods.load_contents.result_fields]
contents = { from = "contents" }
etag = { from = "etag_out" }
```

Generic runtime machinery should create:

```text
NativeFutureMethodDescriptor
NativeAsyncOperation
Native result record type
```

No per-method Python override should be required for this shape.

## Migration Steps

1. Introduce surface naming in docs and tests without changing behavior.
   Treat current `goi.repository` as the compatibility surface for now.

2. Split wrapper qdata names internally:
   keep current behavior but rename the existing qdata concept to
   `native_wrapper` in code comments/functions, then add tests that native
   wrapping still performs one direct qdata lookup.

3. Add explicit `GoiSurfaceKind` plumbing to descriptors and closure plans.
   Initially every descriptor uses `GOI_SURFACE_NATIVE` or the current single
   surface, so behavior remains unchanged.

4. Split class registry reverse lookups by surface:
   native registry first, compat registry later. Preserve existing lookup APIs
   as native aliases during transition.

5. Add `gi.repository` as a compat surface rather than a direct alias to the
   native namespace. At first it may still use the same classes, but the import
   boundary should exist.

6. Add separate compat qdata wrapper creation:
   `goi_gobject_new_compat()` should use `goi.compat_wrapper` and the compat
   type registry.

7. Add explicit conversion helpers:

   ```python
   native_obj = goi.as_native(compat_obj)
   compat_obj = goi.as_compat(native_obj)
   ```

8. Add the first native-only async method from TOML, preferably
   `Gio.File.load_contents`, returning a record object.

9. Expand TOML-native async coverage to other high-value APIs:
   `Gio.File.query_info`, `Gio.File.read`, `Gio.InputStream.read_bytes`,
   `Gtk.FileDialog.open`, `Adw.AlertDialog.choose`, and VTE spawn operations.

## Tests To Add

- Native-only object wrapping does not create compat qdata.
- Compat-only object wrapping does not create native qdata unless explicitly
  converted.
- Same `GObject*` can have distinct native and compat wrappers.
- Passing native wrapper into compat call extracts the same pointer.
- Passing compat wrapper into native call extracts the same pointer.
- Native signal callback receives native wrappers.
- Compat signal callback receives compat wrappers.
- Native return values are native wrappers.
- Compat return values are compat wrappers.
- Python subclass wrapping stays exact within its owning surface.
- Cross-surface wrapping of a Python subclass returns the nearest requested
  surface base wrapper.
- `await Gio.File.load_contents()` on the native surface returns a record with
  `.contents` and `.etag`.
- `Gio.File.load_contents_sync()` on the native surface performs the blocking
  operation explicitly.
- `Gio.File.load_contents()` on the compat surface remains sync-compatible.

## Open Questions

- Should native imports be `from goi import Gtk4` or `from goi import Gtk` with
  version selection elsewhere?
- Should native result records always be returned, even for one-field results?
  This plan assumes yes for typing and documentation stability.
- Should `goi.repository` remain compat, or should compat live only under
  `gi.repository`?
- How much Python subclass cross-surface behavior should be supported beyond
  nearest-base wrapping?
