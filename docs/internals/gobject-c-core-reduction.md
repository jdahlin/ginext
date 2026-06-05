# GObject C-Core Reduction Plan

This note is the GObject-first plan for shrinking the `_gobject` module surface
and reducing Python<->C chatter around wrapper ownership, refcounting,
construction, GC, and destruction.

The direction is simple:

- Python should traffic in wrapper objects.
- Native pointer state and ownership state should live in `GObjectBase`.
- Wrapper cache, wrapper revival, and construction state should stay in C.
- Python should call wrapper methods when unavoidable, not top-level
  `ginext.private.object_*` or `ginext.private.gobject_wrapper_*` helpers.
- `ginextmodule.c` should converge toward bootstrap, invoke, registration, and
  type objects, not an ever-growing bag of lifecycle shims.


## Current GObject-Specific Chatter

The current top-level `_gobject` surface still exports too many GObject
implementation details:

- wrapper registry:
  - `gobject_wrapper_get`
  - `gobject_wrapper_set`
  - `gobject_wrapper_clear`
- wrapper ownership / boundness:
  - `object_is_bound`
  - `gobject_wrapper_owns_ref`
  - `gobject_wrapper_set_owns_ref`
  - `object_unref`
  - `object_ref_count`
  - `object_force_floating`
  - `object_ref_sink`
- construction / wrapping:
  - `construct_gobject`
  - `wrap_gobject_pointer`
  - `wrap_preallocated_gobject_pointer`
  - `set_gobject_wrapper_factory`
  - `set_preallocated_gobject_wrapper_factory`
- property bypass helpers:
  - `object_get_property_by_name`
  - `object_set_property_by_name`

Even where the native state already lives in C, Python still orchestrates the
policy too often. That keeps the control plane noisy and makes
`gobjectclass.py` a lifecycle coordinator instead of a thin API layer.


## End State

The target model for GObject is:

1. `GObjectBase` is the native wrapper base and owns:
   - `GObject *ptr`
   - ownership flags
   - construction state
   - weakref list
   - any wrapper-local GC/lifetime bookkeeping
2. wrapper cache / pointer binding / ownership transitions are internal C
   operations
3. Python-level GObject code uses:
   - wrapper methods
   - invoke
   - registration APIs
4. top-level `_gobject` exports are limited to:
   - invoke core
   - metadata lookup needed to bootstrap invoke
   - registration / type bootstrap
   - special non-introspectable primitives that truly cannot be expressed
     otherwise


## Principles

### 1. Prefer methods on `GObjectBase` over top-level module functions

If the operation is conceptually about a live wrapper instance, it should be a
native wrapper method.

Examples:

- `self.is_bound()`
- `self.owns_ref()`
- `self.release_ref()`
- `self.ref_sink()`
- `self.make_floating()`
- `self.ref_count()`
- `self.bind_from_c(...)`

Not:

- `private.object_is_bound(self)`
- `private.object_unref(self)`
- `private.object_ref_sink(self)`
- `private.object_force_floating(self)`


### 2. Prefer C-internal wrapper/cache operations over Python-callable registry helpers

If an operation exists only to manipulate the wrapper cache or pointer registry,
it should not remain a public Python tool.

Examples:

- `gobject_wrapper_get`
- `gobject_wrapper_set`
- `gobject_wrapper_clear`
- `gobject_wrapper_owns_ref`
- `gobject_wrapper_set_owns_ref`

These should become internal C implementation details, or at most wrapper/class
methods when there is a real Python-level semantic need.


### 3. Construction state should be native wrapper state, not Python glue

The current work already moved significant parts of:

- pointer state
- ownership state
- deferred construction state
- Python construction depth

into C.

That should continue until Python no longer coordinates native object
construction beyond high-level policy like:

- user passed property kwargs
- user passed `on_<signal>=...` constructor handlers


### 4. Destruction and compat dispose should sit on top of native primitives

`__del__` must not remain a place where Python stitches together:

- “is it bound?”
- “do I own the ref?”
- “temporarily rebind before dispose”
- “raw unref at shutdown”

Those are native runtime primitives and should be expressed as such.


## What Stays In `ginextmodule.c`

For GObject, the long-term keepers are:

- type objects:
  - `GObjectBase`
  - `GIMeta`
  - descriptors / wrappers that are true runtime types
- invoke core:
  - `build_callable_descriptor`
  - `invoke_callable_descriptor`
  - `invoke`
- registration/bootstrap:
  - `register_gobject_subclass`
  - `register_signal`
  - `register_property_type_info`
  - wrapper factories only until their bootstrap path is eliminated
- metadata/bootstrap lookup:
  - `object_info_by_gtype`
  - typelib discovery helpers needed before invoke can stand alone

Everything else should be treated as guilty until proven necessary.


## Export Reduction Targets

These are the GObject-focused exports to remove from normal Python use, roughly
in order.

### Tier 1: Wrapper instance lifecycle methods

- `object_is_bound`
- `object_unref`
- `object_ref_count`
- `object_force_floating`
- `object_ref_sink`

Replacement:

- `GObjectBase.is_bound()`
- `GObjectBase.release_ref()`
- `GObjectBase.ref_count()`
- `GObjectBase.make_floating()`
- `GObjectBase.ref_sink()`


### Tier 2: Wrapper ownership/cache shims

- `gobject_wrapper_owns_ref`
- `gobject_wrapper_set_owns_ref`
- `gobject_wrapper_get`
- `gobject_wrapper_set`
- `gobject_wrapper_clear`

Replacement:

- internal C only
- or narrow wrapper/class methods if still needed during transition


### Tier 3: Construction/wrapping helpers

- `construct_gobject`
- `wrap_gobject_pointer`
- `wrap_preallocated_gobject_pointer`
- `set_gobject_wrapper_factory`
- `set_preallocated_gobject_wrapper_factory`

Replacement:

- C-native wrapper/class construction methods
- direct runtime bootstrap in C


### Tier 4: Property bypass helpers

- `object_get_property_by_name`
- `object_set_property_by_name`

Replacement:

- either wrapper/class-native methods temporarily
- or invoke once GValue in/out is expressive enough


## Work Plan

### Slice A: Finish collapsing lifecycle helpers onto `GObjectBase`

Goal:
- stop using top-level `private.object_*` helpers for wrapper-local lifecycle
  decisions

Concrete work:
- move `is_bound`, `owns_ref`, `release_ref`, `ref_sink`,
  `make_floating`, `ref_count` onto `GObjectBase`
- change `gobjectclass.py` to use wrapper methods
- update focused lifecycle and API tests

Validation:
- `make typecheck`
- focused `test_object_lifecycle.py`
- focused `test_object_api.py`
- `make test`
- `make test-debug`
- `make test-asan`

Success means:
- `gobjectclass.py` no longer needs top-level lifecycle helpers for ordinary
  bound wrapper state


### Slice B: Remove Python-visible wrapper registry usage

Goal:
- stop exposing cache/registry manipulation as routine Python operations

Concrete work:
- remove Python uses of:
  - `gobject_wrapper_get`
  - `gobject_wrapper_set`
  - `gobject_wrapper_clear`
  - `gobject_wrapper_owns_ref`
  - `gobject_wrapper_set_owns_ref`
- replace with:
  - internal C calls
  - native wrapper/class methods where transition requires it

Validation:
- focused wrapper identity / cache-hit tests
- `test_object_lifecycle.py`
- `make test`
- `make test-debug`
- `make test-asan`

Success means:
- wrapper cache policy is internal to C, not a Python-callable mini-API


### Slice C: Collapse wrapping/preallocated construction paths

Goal:
- make object wrapping and preallocated construction native wrapper/class
  operations, not a set of free functions

Concrete work:
- replace Python-facing paths that still depend on:
  - `wrap_gobject_pointer`
  - `wrap_preallocated_gobject_pointer`
  - `construct_gobject`
- move preallocated shell allocation and post-bind flow deeper into C
- reduce factory-style bootstrap surface if possible

Validation:
- Python subclass construction tests
- wrapper identity tests
- Gtk template / compat construction regressions
- `make test`
- `make test-debug`
- `make test-asan`

Success means:
- existing object -> wrapper
- preallocated subclass wrapper
- native-created object -> wrapper recovery

are each represented by a small number of native methods, not top-level shims


### Slice D: Simplify destruction/dispose

Goal:
- make `__del__` a thin policy shell or eliminate most of its native work

Concrete work:
- move “safe native release during shutdown” behind a wrapper method
- move “rebind before compat dispose” behind a native helper if still needed
- isolate compat preserve-state behavior from raw lifetime transitions

Validation:
- `test_object_lifecycle.py`
- compat `test_gobject.py`
- Gtk template/dispose regressions
- `make test-debug`
- `make test-asan`

Success means:
- Python no longer stitches together low-level native lifetime operations in
  `__del__`


### Slice E: Remove property bypass helpers

Goal:
- stop using direct module-level property get/set shims for GObject runtime
  behavior

Concrete work:
- route temporary name-based property operations through wrapper/class methods
  if needed
- extend invoke/GValue support so name-based property operations can stop being
  a special bridge

Validation:
- property signal tests
- inherited property tests
- compat property tests
- `make test`

Success means:
- property operations are no longer a separate lifecycle escape hatch


## Immediate Next Step

The right next step is not signals. It is to finish the GObject wrapper-lifetime
cleanup first.

Recommended order:

1. Slice A
2. Slice B
3. Slice C
4. Slice D
5. Slice E

Signal adaptation should come after the object lifetime model is no longer split
between Python glue and top-level `_gobject` shims.


## Success Criteria

This plan is successful when:

- `gobjectclass.py` stops depending on top-level lifecycle helpers
- wrapper cache and ownership manipulation are internal C details
- construction/preallocated wrapping are native class/wrapper methods
- `ginextmodule.c` loses most GObject lifecycle/shim exports
- the remaining `_gobject` public surface is mostly:
  - types
  - invoke
  - registration/bootstrap
  - necessary non-introspectable primitives
