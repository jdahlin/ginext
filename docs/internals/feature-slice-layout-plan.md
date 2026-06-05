# Feature Slice Layout Plan

This is a planning map for reorganizing `ginext` around vertical feature
slices. The goal is to make one class, function family, or binding concept easy
to inspect across:

- Python overlay
- Python implementation
- CPython implementation
- focused tests
- examples
- docs

Compatibility implementation still belongs under `src/gi/`. A feature slice may
contain compatibility tests or notes, but it should not absorb `gi/` code.

## Proposed Shape

Use feature-owned directories for high-churn runtime behavior:

```text
src/ginext/features/<namespace-or-domain>/<feature>/
  overlay.py
  impl.py
  c/
  tests/
  examples/
  docs/
  README.md
```

Not every slice needs every file. For example, a pure C marshalling slice may
have no `overlay.py`, and a documentation-only backlog slice may have no `c/`.

Keep these as stable facades while migrating:

- `src/ginext/*.py` public implementation modules
- `src/ginext/_overlays/*.py` namespace overlay entry points
- `src/ginext/private/` extension build entry points, until the Meson source
  list can consume feature-owned C files cleanly
- `src/ginext/tests/integration/`, `src/ginext/tests/pygobject/`,
  `src/ginext/tests/typelib/`, and inventory tests for cross-feature coverage

## Slice Metadata

Each slice should eventually have a small `README.md` with:

- public surface
- Python modules
- overlay files
- C files and headers
- focused test command
- examples
- docs
- known compatibility gaps

## Current Feature Inventory

This is intentionally grouped. The current tree has roughly 199 focused test
files, 114 private C files/headers, 37 top-level `ginext` Python files, and 60
example files, so a flat list would be hard to maintain.

### Core Import And Namespace Runtime

Candidate root: `features/runtime/`

- `namespace-loading`: lazy namespace objects, first access, attribute gateway,
  namespace caching, unknown members, public namespace surface
- `namespace-defaults`: default version discovery, app defaults, environment
  overrides, suffixed imports, highest-installed fallback
- `feature-flags`: runtime feature gating and old/new behavior switches
- `abi-modes`: native/compat ABI mode selection and import behavior
- `overlay-registration`: overlay registry, bootstrap, install, state, callback
  metadata, namespace overlay lookup
- `cache-invariants`: layer-wide cache behavior and hot-path cache expectations
- `inventory`: namespace inventory and unsupported argument snapshots

Current evidence:

- Python: `namespace.py`, `defaults.py`, `features.py`, `abi.py`,
  `overlay/*.py`, `_overlays/*.py`
- C: `private/namespace.c`, `private/runtime/*`, `private/ginextmodule.c`
- Tests: `tests/namespace/`, `tests/defaults/`, `tests/features/`,
  `tests/overlay/`, `tests/plan_invariant/`, `tests/inventory/`
- Docs: `docs/internals/abi-modes.md`,
  `docs/internals/native-compat-surface-plan.md`,
  `docs/internals/typelib-versioning.md`

### GIRepository Metadata

Candidate root: `features/girepository/`

- `base-info`: base info wrapping, shared info behavior, unresolved info
- `callable-info`: function, callback, signal, vfunc metadata and argument names
- `registered-type-info`: object, interface, struct, union, enum, flags metadata
- `member-info`: field, property, constant, value, arg, type metadata
- `repository-overlay`: Python-facing GIRepository overlay behavior

Current evidence:

- Python: `GIRepository.py`, `_overlays/GIRepository.py`
- C: `private/GIRepository/*.c`, `private/GIRepository/*.h`
- Tests: `tests/integration/test_girepository_overlay.py`,
  `tests/pygobject/test_repository.py`, `tests/pygobject/test_signature.py`,
  `tests/pygobject/test_docstring.py`
- Docs: `docs/internals/goi-docs-plan.md`,
  `docs/internals/ginext/story/12 binding member kinds.md`

### Invocation Pipeline

Candidate root: `features/invoke/`

- `method-descriptor`: descriptor creation, rejection, static method lookup
- `callable-binding`: callable frame setup, implicit arguments, keyword binding
- `ffi-callout`: libffi call execution
- `return-assembly`: return values, result tuples, out params
- `arg-cleanup`: ownership and cleanup for input arguments
- `jit-plan`: plan creation, plan caching, no-GI-on-hot-path invariants

Current evidence:

- Python: `method.py`
- C: `private/callable_descriptor.c`, `private/runtime/callable.*`,
  `private/invoke/*`, `private/invoke/ffi/invoke.c`
- Tests: `tests/method/`, `tests/invoke/`, `tests/plan_invariant/`,
  `tests/pygobject/test_resulttuple.py`
- Docs: `docs/internals/invoke-plan.md`,
  `docs/internals/invoke-marshaller-analysis.md`,
  `docs/internals/full-jit-plan.md`

### Marshalling

Candidate root: `features/marshal/`

- `scalar-values`: booleans, integers, floats, doubles, unichar, GType, void
- `strings`: UTF-8, filename strings, nullable strings
- `enums-flags`: enum and flags value conversion
- `arrays`: C arrays, strv, flat arrays, GArray, GPtrArray, GByteArray
- `lists`: GList and GSList conversion
- `hash-tables`: GHashTable conversion
- `gvalue`: GValue boxing/unboxing and value round trips
- `container-elements`: nested/container element conversion
- `ownership-transfer`: none/container/full transfer behavior

Current evidence:

- C: `private/marshal/*`, `private/GLib/Array.*`,
  `private/GLib/List.*`, `private/GLib/HashTable.*`
- Tests: `tests/invoke/`, `tests/typelib/test_gi_marshalling_tests.py`,
  `tests/pygobject/test_gi.py`, `tests/pygobject/test_everything.py`,
  `tests/pygobject/test_object_marshaling.py`
- Docs: `docs/internals/invoke-marshaller-analysis.md`,
  `docs/internals/ginext/story/13 primitive and scalar values.md`,
  `docs/internals/ginext/story/14 non scalar values.md`

### GObject Types And Objects

Candidate root: `features/gobject/`

- `object-wrapper`: wrapping/unwrapping, lifecycle, unref, Python instance dict
- `object-construction`: constructor kwargs, abstract type rejection
- `object-registration`: Python type to GType registration and class registry
- `object-class-build`: lazy class creation, caching, parent inheritance
- `object-vfuncs`: vfunc wrappers and overrides
- `object-api`: run_dispose, object helpers, connect_object behavior
- `gtype`: type constants, name helpers, type functions, type marshalling
- `fundamental`: fundamental type support
- `gimeta`: GI metadata attached to Python classes and instances

Current evidence:

- Python: `gobject.py`, `classbuild.py`, `fundamental.py`
- C: `private/GObject/Object-*`, `private/GObject/Type.*`,
  `private/GObject/Fundamental.*`, `private/GObject/GIMeta.*`
- Tests: `tests/gobject/`, `tests/classbuild/`, `tests/constructor/`,
  `tests/pygobject/test_gobject.py`, `tests/pygobject/test_gtype.py`,
  `tests/pygobject/test_typeclass.py`, `tests/pygobject/test_interface.py`
- Docs: `docs/internals/abi2/binding.md`,
  `docs/internals/ginext/story/4 objects methods and properties.md`

### Properties And ParamSpec

Candidate root: `features/gobject/property/`

- `python-properties`: decorator forms, metadata, flags, defaults, bounds
- `instance-io`: property get/set behavior and error paths
- `notify-signals`: property notification behavior
- `paramspec`: ParamSpec creation and introspection
- `property-compat`: PyGObject property compatibility surface

Current evidence:

- Python: `gobject.py`, compatibility facade in `src/gi/_propertyhelper.py`
- C: `private/GObject/ParamSpec*`, `private/GIRepository/PropertyInfo.c`
- Tests: `tests/property/`, `tests/gobject/test_paramspec_introspection_backlog.py`,
  `tests/pygobject/test_properties.py`
- Docs: `docs/internals/abi2/property.md`,
  `docs/internals/gobject-property-optimizations.md`

### Signals And Closures

Candidate root: `features/gobject/signal/`

- `python-defined-signals`: signal definitions and attribute form
- `connect-emit`: connect, emit, notify, once, constructor kwargs
- `arg-adapters`: callback arity and signal arg adaptation
- `owner-policy`: bound method weakening, owner lifetime, one-shot handlers
- `closure-records`: callback retention, closure state, disconnect identity
- `gclosure-arguments`: GClosure argument conversion
- `vfunc-callbacks`: vfunc and callback closure integration

Current evidence:

- Python: `signal.py`, `overlay/callbacks.py`,
  compatibility facade in `src/gi/_signalhelper.py`
- C: `private/GObject/Closure-*`, `private/runtime/signal-api.c`,
  `private/GObject/Object-vfunc*`
- Tests: `tests/signal/`, `tests/closure/`,
  `tests/pygobject/test_signal.py`, `tests/pygobject/test_callback.py`,
  `tests/pygobject/test_async.py`
- Docs: `docs/internals/abi2/signals.md`,
  `docs/internals/abi2/closures/*.md`,
  `docs/internals/closure-jit-plan.md`

### GLib

Candidate root: `features/glib/`

- `variant`: GVariant conversion and compatibility behavior
- `bytes`: GLib.Bytes behavior
- `error`: GLib.Error wrapping and Gio error propagation
- `core`: constants, scalar helpers, unichar helpers
- `main-loop-source`: sources, main loop behavior, timeout/idle callbacks
- `logging`: log writer function callbacks

Current evidence:

- Python: `_overlays/GLib.py`
- C: `private/GLib/Variant.*`, `private/GLib/Error.h`
- Tests: `tests/glib/`, `tests/pygobject/test_glib.py`,
  `tests/pygobject/test_error.py`, `tests/pygobject/test_source.py`,
  `tests/pygobject/test_mainloop.py`, `tests/pygobject/test_events.py`
- Examples: `examples/async/*`

### Gio And Async

Candidate root: `features/gio/`

- `file`: GFile, file interface compatibility, Gio file examples
- `async`: async wrappers, callbacks, user data, Gio.Async, asyncio bridge
- `task`: Gio.Task behavior
- `cancellable`: cancellable support
- `application`: Gio.Application behavior
- `menus-actions`: menu and simple action support
- `list-store`: Gio.ListStore support
- `streams`: input stream support
- `volumes-drives`: volume monitor, drives, enumerators
- `dbus`: DBus and GDBus compatibility
- `app-info`: app info support
- `errors`: Gio error mapping

Current evidence:

- Python: `aio.py`, `_aioloop.py`, `_overlays/Gio.py`,
  `_overlays/GioUnix.py`
- Tests: `tests/gio/`, `tests/pygobject/test_gio.py`,
  `tests/pygobject/test_gdbus.py`, `tests/pygobject/test_subprocess.py`,
  `tests/pygobject/test_iochannel.py`, `tests/pygobject/test_thread.py`
- Examples: `examples/gio/*`, `examples/async/*`
- Docs: `docs/internals/async-runtime.md`,
  `docs/internals/async-cancellation.md`,
  `docs/internals/abi2/async.md`, `docs/internals/abi2/gio-file.md`

### Records, Structs, Unions, Boxed, Cairo

Candidate root: `features/records/`

- `record-base`: record wrapping and shared record behavior
- `structs`: construction, fields, copy, equality, methods
- `unions`: construction, fields, discriminators, methods
- `boxed`: boxed value wrapping, field arrays, ownership, GResource boxed values
- `cairo-foreign`: Cairo foreign type interop
- `fundamental-typelib`: fundamental objects from external typelibs

Current evidence:

- Python: `record.py`
- C: `private/GIRepository/StructInfo.*`, `private/GIRepository/UnionInfo.c`,
  `private/GObject/Boxed.h`, `private/cairo/foreign.h`
- Tests: `tests/record` behavior is split across `tests/struct/`,
  `tests/union/`, `tests/boxed/`, `tests/cairo/`, `tests/typelib/`,
  `tests/pygobject/test_fields.py`, `tests/pygobject/test_cairo.py`
- Docs: `docs/internals/abi2/copy-recursive-design.md`,
  `docs/internals/ginext/story/14 non scalar values.md`

### Enums And Flags

Candidate root: `features/enums/`

- `enum-types`: enum class creation, enum methods, enum value metadata
- `flags-types`: flags class creation and operations
- `python-defined-enums`: Python-defined enum and flag backlog
- `enum-marshalling`: enum/flags argument and return conversion

Current evidence:

- C: `private/GIRepository/EnumInfo.*`,
  `private/GIRepository/FlagsInfo.c`, `private/GIRepository/ValueInfo.c`,
  `private/marshal/enum.*`
- Tests: `tests/enum/`, `tests/invoke/test_enum_flags.py`,
  `tests/pygobject/test_enum.py`

### GTK, GDK, Templates, And UI Toolkits

Candidate root: `features/toolkit/`

- `gtk-template`: template loading, compatibility helpers, template examples
- `gtk-application`: GTK application behavior
- `gtk-widgets`: buttons, boxes, adjustments, scales, widgets, CSS providers
- `gtk-text`: text buffers, text views, text iter
- `gtk-models`: tree paths, list boxes, entry completion
- `gtk-builder`: builder behavior
- `gtk-expression`: expressions, sorters, content providers
- `gdk-events`: GDK atoms, event unions, content providers
- `toolkit-overrides`: Gdk, Gtk, Pango, GdkPixbuf overrides

Current evidence:

- Python: `_gtktemplate.py`, `_overlays/Gtk.py`, `_overlays/Gdk.py`,
  compatibility facade in `src/gi/_gtktemplate.py`
- Tests: `tests/gtk3/`, `tests/gtk4/`,
  `tests/pygobject/test_gtk_template.py`,
  `tests/pygobject/test_overrides_gtk.py`,
  `tests/pygobject/test_overrides_gdk.py`,
  `tests/pygobject/test_overrides_gdkpixbuf.py`,
  `tests/pygobject/test_overrides_pango.py`,
  `tests/pygobject/test_atoms.py`
- Examples: `examples/hello_gtk3.py`, `examples/hello_template.py`,
  `examples/templated/`, `examples/pyedit/`, `examples/terminal/`,
  `examples/web_browser/`, `examples/webcam-effects/`
- Docs: `docs/internals/gtk-expression.md`,
  `docs/internals/gtkcolumnview.md`, `docs/book/building/*.md`,
  `docs/book/gnome/*.md`

### Compatibility Surface

Candidate root: keep implementation in `src/gi/`, add slice docs under
`features/compat/` only if useful.

- `import-machinery`: `gi`, `gi.repository`, import hooks
- `compat-overrides`: GLib, GObject, Gio, Gtk, Gdk, GdkPixbuf, Pango overrides
- `property-helper`: PyGObject-style property helper
- `signal-helper`: PyGObject-style signal helper
- `docstring-signature`: docstrings and signature compatibility
- `pycapi`: Python C API compatibility expectations
- `historical-tests`: broad PyGObject tests that do not map cleanly to one
  native feature

Current evidence:

- Python: `src/gi/*.py`, `src/gi/overrides/*.py`
- Tests: `tests/pygobject/`
- Docs: `docs/internals/testing-compat.md`,
  `docs/internals/pygobject-architectural-issues.md`,
  `docs/internals/pygobject-lifetime-gc-notes.md`

### Applications, Examples, And Documentation

Candidate root: keep runnable applications under `examples/`, but index them
from feature slices.

- `small-examples`: hello world, hello template, Gio examples, async examples
- `template-apps`: templated app, pyedit, terminal, web browser
- `benchmarks`: draw bench, microbench, memory bench, closure bench
- `book`: user-facing guide material under `docs/book/`
- `internals`: architecture, implementation plans, compatibility notes
- `story`: durable ginext narrative docs

Current evidence:

- Examples: `examples/*`
- Docs: `docs/book/`, `docs/internals/`, `docs/internals/ginext/story/`

## Migration Order

Start with vertical slices that are high value and have clear boundaries:

1. `features/glib/variant`
2. `features/gobject/object`
3. `features/gobject/signal`
4. `features/gobject/property`
5. `features/gio/async`
6. `features/gio/file`
7. `features/invoke/callable-binding`
8. `features/marshal/scalar-values`
9. `features/marshal/arrays`
10. `features/girepository/callable-info`

Then migrate lower-risk namespace/toolkit slices after the pattern is proven.

## First Slice Checklist

For the first migrated slice:

1. Move focused tests into the slice, or add a slice-local test index that points
   at their existing locations.
2. Move Python implementation and overlay files only if imports stay stable
   through the old public modules.
3. Move C files only if Meson can keep a readable source list.
4. Add `README.md` with focused test commands.
5. Run the narrowest useful tests.
6. Review imports and Meson diff for unrelated churn.

`GLib.Variant` is the best first candidate because it is meaningful, bounded,
and already has C, Python overlay, focused tests, compatibility tests, and docs.
