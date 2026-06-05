# Python, GObject, and wrapper reference counting

Status: researched 2026-05-15.

This document specifies the lifetime models that matter when a Python object
wraps a `GObject`. It is intentionally more precise than a user guide because
the difficult bugs live at the boundary between two ownership systems.

Primary sources:

- GObject toggle references: <https://docs.gtk.org/gobject/method.Object.add_toggle_ref.html>
- GObject floating references: <https://docs.gtk.org/gobject/floating-refs.html>
- GObject type system concepts: <https://gitlab.gnome.org/GNOME/glib/-/raw/main/docs/reference/gobject/concepts.md?ref_type=heads>
- Python type object slots: <https://docs.python.org/3/c-api/typeobj.html>
- Python reference counting C API: <https://docs.python.org/3/c-api/refcounting.html>
- Python GC support C API: <https://docs.python.org/3/c-api/gcsupport.html>
- Python object lifecycle C API: <https://docs.python.org/3/c-api/lifecycle.html>
- Python `gc` module docs: <https://docs.python.org/3/library/gc.html>
- Python weak references: <https://docs.python.org/3/library/weakref.html>
- CPython `main` GC source: <https://raw.githubusercontent.com/python/cpython/main/Python/gc.c>
- CPython `3.13` GC source: <https://raw.githubusercontent.com/python/cpython/3.13/Python/gc.c>
- CPython refcount macros: <https://raw.githubusercontent.com/python/cpython/main/Include/refcount.h>
- CPython object lifecycle implementation: <https://raw.githubusercontent.com/python/cpython/main/Objects/object.c>
- CPython type-slot implementation: <https://raw.githubusercontent.com/python/cpython/main/Objects/typeobject.c>
- CPython weakref implementation: <https://raw.githubusercontent.com/python/cpython/main/Objects/weakrefobject.c>
- Python 3.14.5 release notes: <https://www.python.org/downloads/release/python-3145/>
- Python 3.14 What's New, GC notes: <https://docs.python.org/3/whatsnew/3.14.html#garbage-collection>
- Python.org discussion of the 3.14/3.15 incremental-GC revert: <https://discuss.python.org/t/reverting-the-incremental-gc-in-python-3-14-and-3-15/107014>
- GLib `GObject` implementation: <https://gitlab.gnome.org/GNOME/glib/-/raw/main/gobject/gobject.c>
- GLib `GObject` public type definitions: <https://gitlab.gnome.org/GNOME/glib/-/raw/main/gobject/gobject.h>
- Local PyGObject source: `pygobject/gi/pygobject-object.c`,
  `pygobject/gi/pygobject-object.h`, `pygobject/gi/pygobject-types.h`,
  `pygobject/gi/pygi-cache-object.c`, `pygobject/gi/pygboxed.c`,
  `pygobject/gi/pygi-boxed.c`, `pygobject/gi/pygpointer.c`,
  `pygobject/gi/pygi-struct.c`, `pygobject/gi/pygi-fundamental.c`,
  `pygobject/gi/pygi-info.c`, `pygobject/gi/pygobject-props.c`,
  `pygobject/gi/pygenum.c`, `pygobject/gi/pygflags.c`, and
  `pygobject/gi/pygi-type.c`.

## One-line model

Python reference counts control the lifetime of Python wrapper objects.
GObject reference counts control the lifetime of native `GObject` instances.
The wrapper boundary is correct only when every cross-runtime edge says exactly
which side owns a strong reference, which side merely observes, and which side
is allowed to break the edge during collection or disposal.

## Python reference counting

Every CPython object has a strong-reference count. `Py_INCREF()` records that
C code is taking a new strong reference. `Py_DECREF()` releases one strong
reference. When the count reaches zero, CPython calls the object's
`tp_dealloc` slot. `Py_XINCREF()` and `Py_XDECREF()` are the nullable variants.
`Py_NewRef()` is the preferred expression form for "INCREF and return the same
object".

Important details:

- A borrowed reference is a non-owning pointer. It must not be stored beyond
  the lifetime guarantee made by the API that returned it unless it is first
  converted to a strong reference.
- A new reference is an owned strong reference. Exactly one matching
  `Py_DECREF()` or ownership transfer is required.
- `Py_DECREF()` can run arbitrary Python code through deallocation,
  `tp_finalize`, weakref callbacks, or user-level finalizers. Data structures
  should be internally consistent before the `DECREF`, not after it.
- `Py_CLEAR(obj)` is the safe "drop a field" primitive: it stores `NULL` in the
  field before releasing the old reference, which protects against re-entrant
  code seeing a stale pointer.
- `Py_REFCNT()` is diagnostic, not a semantic ownership API. Immortal objects
  and free-threaded builds make exact counts unsuitable for logic beyond
  special cases like zero/one checks explicitly supported by CPython.
- Immortal objects, added to CPython's public model in recent releases, may not
  have their refcount mutated by `Py_INCREF()` or `Py_DECREF()`.

For extension types, normal no-cycle destruction is:

1. some owner releases the last strong reference;
2. CPython enters `tp_dealloc`;
3. the type clears owned Python references, releases native resources, and
   calls the correct `tp_free`.

If the type has `tp_finalize`, `tp_dealloc` should use
`PyObject_CallFinalizerFromDealloc()` when the invariant is "finalization must
happen for refcounted destruction too". The Python lifecycle docs are explicit
that Python does not automatically call `tp_finalize` merely because the last
reference was deleted.

## Python cyclic garbage collector

Reference counting alone cannot reclaim cycles such as `a -> b -> a`, because
every object in the cycle still has a non-zero refcount. CPython's cyclic GC is
a supplement to reference counting, not a replacement for it.

Only GC-aware container types participate. A C extension type participates by:

- setting `Py_TPFLAGS_HAVE_GC`;
- allocating with the GC allocator, normally through the type's `tp_alloc`;
- calling `PyObject_GC_Track()` only after all traversable fields are valid;
- calling `PyObject_GC_UnTrack()` before traversable fields become invalid;
- implementing `tp_traverse`;
- implementing `tp_clear` if mutable fields can form cycles;
- freeing with the matching GC free path, normally through `tp_free`.

The core contract is:

- `tp_traverse(self, visit, arg)` reports every Python object that `self`
  strongly owns and that can contribute to a Python cycle.
- `tp_traverse` must not mutate refcounts, allocate objects, or destroy
  objects. It is an observation pass.
- `tp_clear(self)` breaks references that may form cycles while leaving `self`
  valid enough for deallocation to continue.
- If `tp_traverse` exposes an edge, the type must be able to break that edge
  coherently in `tp_clear` or another collection-safe destruction path.

That last point is critical for bindings. A wrapper must not report
native-owned signal closures, qdata, or GObject-owned child references as
Python-owned edges unless wrapper `tp_clear` can actually break the native
ownership that keeps them alive. Otherwise Python GC can decide to clear a
wrapper that is still semantically live from the GObject side.

### CPython collection algorithm

CPython's GC has an important Python 3.14 version boundary:

- Python 3.13 uses the traditional three-generation cyclic GC.
- Python 3.14.0 through 3.14.4 shipped an incremental GC.
- Python 3.14.5, released on 2026-05-10, reverted the incremental GC back to
  the 3.13-style generational collector because of significant memory pressure
  reports in production environments.
- Python 3.15 was also reverted before/around its beta cycle; the core-dev
  discussion says a future reintroduction for 3.16 would need the regular PEP
  process.

For the binding invariants in this document, treat Python 3.13 and Python
3.14.5+ as the practical baseline: GC-capable objects are tracked in
generations, new tracked objects start in generation 0, survivors move toward
older generations, and automatic collection is triggered by
allocation-minus-deallocation counters and thresholds.

The implementation in `Python/gc.c` is refcount-based cycle detection:

1. Choose a generation to collect. Automatic collection chooses the oldest
   generation whose counter exceeds its threshold, with full-collection
   heuristics to avoid repeatedly scanning long-lived objects.
2. Merge younger generations into the generation being collected.
3. For each candidate, copy the real `ob_refcnt` into temporary `gc_refs`.
4. Traverse candidate-to-candidate references and subtract those internal
   references from `gc_refs`.
5. Objects whose adjusted `gc_refs` is still positive are reachable from
   outside the candidate set. They and anything reachable from them are kept.
6. Remaining objects are placed in the unreachable set.
7. Weakrefs are cleared and some callbacks are invoked before objects are
   cleared, so weakref callbacks cannot reveal half-cleared unreachable
   objects.
8. `tp_finalize` is called for unreachable objects that define it.
9. Objects resurrected by finalization are detected and moved back to an older
   generation.
10. Remaining unreachable objects have weakrefs cleared without callbacks and
    then `tp_clear` is called to break cycles.
11. Objects with legacy `tp_del` finalizers, and objects reachable from them,
    may be left uncollectable and reported through `gc.garbage`.

`gc.c` in current `main` and `3.13` are materially similar in this core
algorithm after the 3.14.5/3.15 revert: `update_refs`, `subtract_refs`,
`move_unreachable`, `deduce_unreachable`, weakref handling, finalization,
resurrection handling, and `delete_garbage` are the important steps in both.
Differences observed while researching this document:

- `main` records richer per-collection statistics, including candidates,
  timestamps, duration, and heap size.
- `main` splits weakref handling into clearer phases such as
  `handle_weakref_callbacks()` and `clear_weakrefs()`, while 3.13 uses
  `handle_weakrefs(..., true/false)`.
- The short-lived Python 3.14.0-3.14.4 incremental GC changed collection
  scheduling and threshold meaning enough that tuned `gc.set_threshold()` values
  may not carry across the 3.14.5 revert. Binding correctness must not depend on
  exact generation scheduling.
- `main` still has internal implementation differences from 3.13, including
  richer statistics and comments about dict tracking changes. The binding
  invariants here should not depend on lazy dict untracking or on exact
  per-generation scheduling details.

## Python weak references

A Python weak reference observes a Python object without increasing its Python
refcount. Calling a `weakref.ref` returns the referent while it is still alive,
or `None` after it has been finalized enough for the weakref to be cleared.

Important details:

- Not all Python objects support weakrefs. Extension types opt in with
  `Py_TPFLAGS_MANAGED_WEAKREF` or, older-style, a positive
  `tp_weaklistoffset`.
- Weakref callbacks run when the referent is about to be finalized. The callback
  receives the weakref object, not the referent.
- Weakref callbacks must tolerate that the referent is already unavailable.
- The thread-safe liveness idiom is to call the weakref once and test the
  result, not to test liveness separately and then call later.
- `weakref.finalize` is a higher-level finalizer object that keeps enough state
  to invoke a callback at most once without requiring the user to keep the
  finalizer object alive.

For GObject wrappers, a Python weakref to the wrapper is not the same thing as a
weak reference to the underlying `GObject`. Without toggle refs, the Python
wrapper may die while native code still owns the `GObject`, and a later native
to Python crossing may create a fresh wrapper. Therefore:

- `weakref.ref(wrapper)` tracks wrapper lifetime only.
- `GObject.Object.weak_ref()` tracks underlying GObject disposal/finalization.

This repo intentionally follows that split: `GObject.Object` does not enable
managed Python weakrefs, and `obj.weak_ref()` is backed by
`g_object_weak_ref()`.

## GObject reference counting

`GObject` uses explicit reference counting. `g_object_ref()` increments the
object's reference count and returns the same object as an owned reference.
`g_object_unref()` decrements it. When the count reaches zero, the object is
destroyed.

`g_object_new()` initializes a new object's refcount to one. If the type derives
from `GInitiallyUnowned`, that initial reference is floating; otherwise it is an
ordinary owned reference.

GObject destruction has two phases:

1. `dispose`: release references to other objects. It may run more than once.
   After `dispose`, methods should still fail gracefully rather than accessing
   freed memory.
2. `finalize`: finish destruction and release non-object resources. It runs
   once.

After `finalize`, GObject frees or recycles the instance memory through the type
system. This split exists specifically to cooperate with cycle collectors and
cycle breakers. External code can detect a cycle and call
`g_object_run_dispose()` to force `dispose` and break references even while the
final native refcount is not yet zero.

GObject weak references are disposal notifications. `g_object_weak_ref()` adds a
callback without taking a strong reference. The callback is invoked as the
object is disposed, and the callback receives the user data and the address
where the object was, not a safe live object reference. Plain
`g_object_weak_ref()` is not thread-safe if the final `g_object_unref()` can
happen on another thread; `GWeakRef` is the thread-safe GObject API.

For wrapper code, the native rules imply:

- Every owned `GObject *` field must have exactly one matching
  `g_object_unref()`.
- A wrapper that stores a `GObject *` must know whether it owns a native ref.
  Calling `G_IS_OBJECT()` or `g_object_unref()` on a freed or non-GObject
  pointer is itself unsafe.
- If wrapper deallocation removes qdata from the GObject, it must do so before
  dropping the wrapper's final native ref, because `g_object_unref()` can enter
  disposal/finalization.
- GObject weak-notify callbacks must not assume the object pointer can be
  rewrapped or referenced.

## GObject floating references

Floating refs are a C convenience for newly created objects that are expected to
be immediately adopted by a container. They are not a separate count. They are a
flag on the initial reference of `GInitiallyUnowned` instances.

`g_object_ref_sink()` is the key operation:

- If the object is floating, it clears the floating flag and leaves the refcount
  unchanged. The caller has claimed the existing initial reference.
- If the object is not floating, it behaves like `g_object_ref()` and adds a new
  ordinary strong reference.

GObject's current docs explicitly say floating references should not be exposed
by language bindings. They are not reliably discoverable from annotations, and
some APIs deviate from the expected floating behavior. The recommended binding
policy is to sink immediately after construction when the runtime type is
`GInitiallyUnowned`.

For wrapper code:

- A wrapper should own exactly one native strong reference for as long as the
  wrapper promises that its `GObject *` is live.
- For transfer-none returns, use `g_object_ref_sink()` to acquire/sink a wrapper
  ref.
- For transfer-full returns, the caller already owns a ref. If it is floating,
  sink it; if it is not floating, do not add another ref.
- Do not expose floating state as a user-visible ownership mode.

## GObject toggle references

`g_object_add_toggle_ref()` adds a strong reference and installs a notification
callback for transitions between:

- this toggle ref being the last remaining reference, and
- this toggle ref no longer being the last reference.

The intended use is a proxy object managed by another memory manager, such as a
language binding wrapper. The design has paired references:

- GObject side: a toggle reference keeps the native object alive.
- Proxy side: the native object keeps either a strong or weak reverse reference
  to the proxy.

When other native references exist, the reverse reference to the proxy is
strong, so native activity keeps the proxy alive. When the toggle ref becomes
the last native reference, the reverse reference is downgraded to weak, so the
foreign memory manager can collect the proxy and eventually release the toggle
ref. When another native reference appears, the reverse reference is upgraded to
strong again.

Important constraints from the GObject docs:

- A normal reference must already be held before adding a toggle ref, so the
  initial reverse-link state is strong.
- The toggle ref must be removed with `g_object_remove_toggle_ref()`.
- Multiple toggle refs on the same object interact badly: if there are several,
  none are notified until all but one are removed. Bindings should avoid this
  unless they own unique important proxy state.
- If another thread unrefs the object, the notify callback can race with
  `g_object_remove_toggle_ref()`. The object argument may be dangling after
  removal unless the binding provides its own synchronization.
- The method is documented as not directly available to language bindings.

Toggle refs solve one historical binding problem: preserving wrapper identity
and Python weakref behavior while allowing GObject-only ownership to keep a
Python proxy alive when needed. They also create difficult re-entrancy,
resurrection, multi-toggle, and threading problems.

This repo currently does not use toggle refs. Instead it uses:

- qdata on the GObject to cache the active wrapper pointer;
- one owned GObject ref while the wrapper is live;
- saved instance dict qdata so Python attributes can survive wrapper drop and
  later rewrap;
- explicit `GObject.Object.weak_ref()` for native lifetime notifications;
- no Python weakref support on the wrapper type.

That design means a wrapper may be collected while the GObject is still alive in
C. A later call that returns the same `GObject *` can construct a fresh wrapper.
Code must not promise Python object identity across that gap unless a live
wrapper is still present in qdata.

## Boundary invariants for this repo

The current wrapper implementation is centered in:

- `src/_goi/GObject/Object-wrap.c`
- `src/_goi/GObject/Object-lifecycle.c`
- `src/_goi/GObject/Object-weakref.c`
- `src/_goi/GObject/Object.h`

The intended invariants are:

- A live wrapper with `owns_gobject_ref == true` owns exactly one native
  `GObject` strong reference.
- `goi_gobject_new(..., transfer_full=false)` takes/sinks one native ref for the
  wrapper.
- `goi_gobject_new(..., transfer_full=true)` claims the incoming ref and only
  sinks if the incoming ref is floating.
- qdata key `goi.wrapper` stores the active wrapper as a borrowed pointer. The
  wrapper owns the native ref; qdata does not own a Python ref.
- When the Python wrapper deallocates first, it steals the qdata and unrefs the
  GObject.
- When the GObject is destroyed first, qdata destroy-notify clears the wrapper's
  `gobject` pointer and ownership flag so later wrapper deallocation does not
  touch freed memory.
- Wrapper `tp_finalize` saves Python instance attributes into GObject qdata
  before Python subtype deallocation clears managed dict state.
- A later wrapper for the same still-live GObject restores that saved dict by
  normal Python attribute assignment, not by poking CPython dict internals.
- The wrapper type does not participate in Python cycle GC unless it grows real
  Python-owned fields that need `tp_traverse/tp_clear`.
- The `GObjectWeakRef` helper does participate in Python cycle GC because it
  owns Python callback and user-data references and can clear them.

## Common failure modes

1. Traversing edges the wrapper does not own.
   If `tp_traverse` reports a Python callback owned by a GObject signal closure,
   Python GC may clear the wrapper even though the native closure is still live.

2. Clearing too late.
   If a field is `DECREF`ed before the containing object is internally
   consistent, arbitrary finalizer or weakref callback code can observe broken
   state.

3. Mixing wrapper liveness with GObject liveness.
   A Python weakref to a wrapper cannot answer "is the GObject alive?" in a
   no-toggle-ref design.

4. Treating floating refs as annotations.
   Floating state is runtime object state, not reliable GIR metadata. Bindings
   should normalize it by sinking at the boundary.

5. Using a GObject weak-notify pointer as a live object.
   `GWeakNotify` gets the address where the object was. It is a notification,
   not an ownership opportunity.

6. Removing toggle refs or weak refs without considering other threads.
   GObject's docs explicitly call out races around toggle removal and plain weak
   refs. Free-threaded Python work makes this more important, not less.

7. Rewrapping without identity rules.
   If no wrapper is present in qdata, a new wrapper is allowed. Tests must assert
   pointer identity (`GObject *`) separately from Python object identity.

## Practical checklist for new lifetime-sensitive code

- Decide whether each edge is Python-strong, Python-borrowed, GObject-strong,
  GObject-weak, qdata-borrowed, or transfer-only.
- If C stores a `PyObject *`, `Py_INCREF` it and specify where it is cleared.
- If C stores a `GObject *`, take or claim a native ref and specify where it is
  released.
- Use `Py_CLEAR` for Python fields that can be observed by re-entrant code.
- Remove qdata or weak registrations before releasing the final owned native
  ref.
- Sink floating refs at the binding boundary.
- Do not add `tp_traverse` for native-owned state unless `tp_clear` can break
  the same edge.
- Prefer `GObject.Object.weak_ref()` over Python weakrefs for underlying
  GObject lifetime.
- Add tests for both lifetimes separately: wrapper dies while GObject lives, and
  GObject dies while wrapper still exists.

## Internal hook points and hard limits

This section is the source-code-level model for where CPython and GObject let a
binding participate in lifetime behavior.

### CPython refcount internals

The normal strong-reference fast path is not type-specific:

1. `Py_INCREF(op)` increments the object's refcount unless the object is
   immortal.
2. `Py_DECREF(op)` decrements the object's refcount unless the object is
   immortal.
3. If `Py_DECREF()` reaches zero, it calls `_Py_Dealloc(op)`.
4. `_Py_Dealloc()` reads `Py_TYPE(op)->tp_dealloc` and calls it.

There is no per-type `tp_incref` or `tp_decref` slot. A type can define what
happens when the count reaches zero, but it cannot replace the basic meaning of
`Py_INCREF()` and `Py_DECREF()` for instances of that type.

The current `Include/refcount.h` also matters for future free-threaded work:

- non-limited, GIL builds usually mutate `ob_refcnt` directly;
- free-threaded builds split local and shared refcount state;
- immortal objects are detected before refcount mutation;
- stable ABI and opaque-object builds can route refcount operations through
  function calls instead of direct field access.

Binding code should therefore treat `Py_INCREF`, `Py_DECREF`, `Py_CLEAR`,
`Py_REFCNT`, and `Py_SET_REFCNT` as the API boundary. Direct field access is not
a portable hook.

### CPython deallocation and finalization hooks

The main extension hooks are type slots:

- `tp_new`: allocate or return a new Python object.
- `tp_init`: initialize an already allocated Python object.
- `tp_dealloc`: release native resources and owned Python references when the
  Python refcount reaches zero.
- `tp_finalize`: optional one-shot finalization hook. It is associated with
  Python `__del__` for Python classes.
- `tp_traverse`: expose Python-owned outgoing references to cyclic GC.
- `tp_clear`: break Python-owned outgoing references when cyclic GC collects a
  cycle.
- `tp_weaklistoffset` or `Py_TPFLAGS_MANAGED_WEAKREF`: opt instances into
  Python weakrefs.
- `Py_TPFLAGS_HAVE_GC`: opt instances into cyclic GC.
- `Py_TPFLAGS_MANAGED_DICT`: let CPython manage instance dict storage.

Important implementation details from `Objects/object.c` and
`Objects/typeobject.c`:

- `_Py_Dealloc()` calls `tp_dealloc` directly. In debug builds it verifies that
  the deallocator did not change the current exception.
- `PyObject_CallFinalizerFromDealloc()` temporarily resurrects the object, calls
  `tp_finalize`, then either continues deallocation or reports resurrection by
  returning `-1`.
- Heap Python subclasses use `subtype_dealloc`, not the base type's deallocator
  directly. `subtype_dealloc` handles finalizers, weakrefs, slots, managed
  dicts, and then chains to the nearest base with a different deallocator.
- For GC types, `subtype_dealloc` untracks the object before clearing weakrefs
  and slots, because weakref callbacks or finalizers may trigger GC.
- Weakrefs are cleared before slots and dict storage are cleared. If finalizers
  create new weakrefs during deallocation, CPython clears those later without
  callbacks.
- All heap types created by `type.__new__` get `Py_TPFLAGS_HAVE_GC`,
  `subtype_traverse`, and `subtype_clear` because type objects and instances can
  form cycles through class relationships.
- `Py_TPFLAGS_MANAGED_WEAKREF` is valid only with `Py_TPFLAGS_HAVE_GC`; CPython
  sets `tp_weaklistoffset` to its managed offset.

For wrappers, this means the correct way to hook Python lifetime is:

- put native release logic in `tp_dealloc`;
- call `PyObject_CallFinalizerFromDealloc()` from `tp_dealloc` if the wrapper's
  `tp_finalize` must run on refcounted destruction;
- use `tp_finalize` for state that must be captured before Python subclass
  teardown clears instance dict/slots;
- add `Py_TPFLAGS_HAVE_GC`, `tp_traverse`, and `tp_clear` only for Python-owned
  fields that can form Python cycles;
- add managed weakrefs only if Python wrapper weakref semantics are explicitly
  wanted.

## How current PyGObject/gi does it

This section describes the local `pygobject/gi` source checkout as inspected on
2026-05-15. It is useful as a compatibility reference because `goi` is
intentionally close to PyGObject's public behavior, but not all implementation
choices need to be copied.

### PyGObject's current high-level model

Current PyGObject does not use toggle refs for `GObject` wrappers. The local
`pygobject/gi/pygobject-types.h` still has a `PYGOBJECT_USING_TOGGLE_REF` flag,
but it is marked "No longer used DO_NOT_USE". Current lifetime is built from:

- a Python `PyGObject` wrapper that owns one native `GObject` reference while it
  is live;
- GObject qdata key `PyGObject::wrapper` storing the active Python wrapper
  pointer without owning a Python reference;
- GObject qdata key `PyGObject::instance-data` storing data owned by the native
  GObject instance, not by the wrapper;
- Python GC support on the wrapper type;
- Python weakrefs enabled on the wrapper type;
- a separate `GObjectWeakRef` Python type backed by `g_object_weak_ref()`.

The important semantic split is the same one used in this repo: wrapper
lifetime and GObject lifetime are different things. A Python weakref to the
wrapper tracks the wrapper. `obj.weak_ref()` tracks the underlying GObject.

### PyGObject `PyGObject` layout

`PyGObject` contains:

- `GObject *obj`: the wrapped native object;
- `PyObject *inst_dict`: the Python instance dictionary;
- `PyObject *weakreflist`: Python weakref list storage;
- a stale ABI-preserving union whose old toggle/closure fields are no longer
  used directly.

Per-native-instance state is kept separately in `PyGObjectData`, attached to
the GObject as qdata:

- `PyTypeObject *type`: the Python wrapper type to use when rewrapping;
- `PyObject *inst_dict`: instance dict saved across wrapper replacement;
- `gboolean call_do_dispose`: whether a Python subclass has a custom
  `do_dispose`;
- `GSList *closures`: watched closures connected from this object.

That split matters. `PyGObjectData` belongs to the GObject and is freed by qdata
destroy notify when the native object is finalized. The Python wrapper can come
and go while the instance data remains attached to the native object.

### PyGObject wrapper creation

`pygobject_new(obj)` is `pygobject_new_full(obj, steal=FALSE, g_class=NULL)`.

`pygobject_new_full()` does:

1. Return `None` for `NULL`.
2. Check `PyGObject::wrapper` qdata. If a wrapper already exists, return a new
   Python reference to it. If `steal` is true, also `g_object_unref(obj)` because
   the existing wrapper already owns the native reference it needs.
3. If there is no wrapper, choose the Python type from existing
   `PyGObjectData`, from `g_class`, or from `G_OBJECT_TYPE(obj)`.
4. If the wrapper type is a heap type, `Py_INCREF(tp)`.
5. Allocate with `PyObject_GC_New(PyGObject, tp)`.
6. Initialize `inst_dict`, `weakreflist`, stale flags, and `obj`.
7. If `!steal` or `g_object_is_floating(obj)`, call `g_object_ref_sink(obj)`.
8. Register the wrapper in qdata.
9. Track the wrapper with `PyObject_GC_Track()`.

The net ownership rule is:

- transfer-none: PyGObject adds/sinks one ref for the wrapper;
- transfer-full, non-floating: PyGObject claims the incoming ref;
- transfer-full, floating: PyGObject sinks the floating ref;
- existing wrapper plus transfer-full: PyGObject drops the incoming native ref
  and returns a new Python ref to the existing wrapper.

For Python-side construction, `pygobject_init()` calls
`g_object_new_with_properties()`, sinks if the created object is
`GInitiallyUnowned`, stores the pointer in `self->obj`, and registers the
wrapper. The helper `pyg_object_new()` follows the same broad rule, but if
`pygobject_new()` had to create a wrapper for the newly created object, it drops
the construction ref afterward because the new wrapper took its own ref.

### PyGObject wrapper classes and heap types

PyGObject caches wrapper classes on `GType` qdata. `pygobject_lookup_class()`
first checks `PyGObject::class`, then interface qdata, then tries to import the
type by GType from the typelib, and finally creates a runtime Python type with
`pygobject_new_with_interfaces()`.

Runtime-created GObject wrapper classes are Python heap types. When PyGObject
creates such a type, it:

- builds bases from the GObject parent type plus implemented interfaces;
- sets `tp_dealloc`, `tp_alloc`, `tp_free`, `tp_traverse`, and `tp_clear` to
  the parent wrapper's slots, overriding Python's default heap-type slot choices
  for these lifetime-critical paths;
- selectively inherits custom value slots such as richcompare, hash, iter,
  repr, and str only when exactly one base provides a non-default slot;
- caches the resulting type on the GType qdata with an owned Python reference.

When `pygobject_new_full()` instantiates a heap wrapper type, it `Py_INCREF`s the
type before allocating the instance. That keeps dynamically created wrapper
types alive for the lifetime assumptions PyGObject makes around GType qdata and
instance wrappers.

### PyGObject wrapper registration and qdata

`pygobject_register_wrapper()`:

- asserts the native object has `ref_count >= 1`;
- creates or retrieves `PyGObjectData`;
- saves or restores the instance dictionary through `PyGObjectData::inst_dict`;
- stores the wrapper pointer in `PyGObject::wrapper` qdata with no destroy
  notify.

Because the qdata wrapper pointer is borrowed, the native object does not keep
the Python wrapper alive by itself. The wrapper's native reference keeps the
GObject alive while the wrapper exists, not the other way around.

### PyGObject wrapper deallocation and GC

`PyGObject_Type` is a GC-aware Python type:

- `tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC`;
- `tp_dealloc = pygobject_dealloc`;
- `tp_traverse = pygobject_traverse`;
- `tp_clear = pygobject_clear`;
- `tp_weaklistoffset = offsetof(PyGObject, weakreflist)`;
- `tp_dictoffset = offsetof(PyGObject, inst_dict)` on CPython;
- `tp_finalize = pygobject_finalize` on CPython;
- `tp_alloc = PyType_GenericAlloc`;
- `tp_free = PyObject_GC_Del`.

`pygobject_dealloc()`:

1. `PyObject_GC_UnTrack(self)`;
2. clear Python weakrefs with `PyObject_ClearWeakRefs()` if any exist;
3. call `pygobject_clear(self)`;
4. free with `PyObject_GC_Del(self)`.

`pygobject_clear()`:

1. if `self->obj` is set, retrieve/create `PyGObjectData`;
2. update `PyGObjectData::type` if Python `__class__` changed;
3. clear `PyGObject::wrapper` qdata;
4. release the wrapper's native ref with `g_clear_pointer(&self->obj,
   g_object_unref)` while the GIL is released;
5. `Py_CLEAR(self->inst_dict)`.

`pygobject_finalize()` is used for custom Python `do_dispose`. If the native
object has instance data, the Python class has a custom `do_dispose`, and
`self->obj->ref_count == 1`, PyGObject calls `g_object_run_dispose(self->obj)`
before the wrapper is cleared. This is a deliberate "only when this wrapper has
the last native ref" rule.

### PyGObject traversal policy for closures

`pygobject_traverse()` always visits `self->inst_dict` if present. It only
visits native-instance data and watched closures when `self->obj->ref_count ==
1`.

That condition is not cosmetic. The source comment references Bug 731501 and
states the rule directly: only let Python GC track closures when `tp_clear()`
would free them. With more than one native ref, the GObject is still owned
elsewhere, and PyGObject must not let Python GC pretend it can clear
GObject-owned closure state.

When the condition is true, traversal visits:

- `PyGObjectData::inst_dict`;
- each watched closure's `callback`;
- each watched closure's `extra_args`;
- each watched closure's `swap_data`.

The corresponding clearing path is indirect: `pygobject_clear()` drops the last
wrapper-owned native ref; if that leads to GObject finalization, the qdata
destroy notify frees `PyGObjectData`, invalidates watched closures, and closure
invalidators release their Python callback references.

### PyGObject signal closures

`connect()`, `connect_after()`, `connect_object()`, and
`connect_object_after()` create a `GClosure` through introspection-aware
`pygi_signal_closure_new()` when possible, otherwise `pyg_closure_new()`. The
closure is registered with `pygobject_watch_closure()` before being connected to
the signal.

`pygobject_watch_closure()` stores the closure in `PyGObjectData::closures` and
adds an invalidate notifier. The invalidate notifier removes the closure from
the list while holding the GIL, because Python GC may traverse the list.

This makes closure ownership explicit:

- the signal system owns the connected closure;
- the closure owns its Python callback/user-data references;
- the wrapper watches the closure only so traversal can see it when the wrapper
  is the last native owner and clearing can actually invalidate it.

### PyGObject signal lifetime issue survey

The local GitLab issue snapshot in `docs/pygobject-gitlab-issues` contains a
long-running cluster of bugs around signal connections, callbacks, closure
state, weak targets, and leaks. The common theme is not just "callbacks leak".
It is that a signal connection has several different lifetimes:

- the emitter/source object lifetime;
- the optional target/user-data object lifetime;
- the native `GClosure` lifetime;
- the Python callable lifetime;
- any Python object captured by that callable;
- the Python wrapper lifetime around each participating native object.

The hard invariant is:

> PyGObject may expose a closure's Python references to `tp_traverse()` only if
> the same owner can make `tp_clear()` disconnect or invalidate that closure.

The issue history mostly consists of violations, missing cases, or API gaps
around that invariant.

#### Connection ownership and weak target semantics

- [#1](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/1),
  "Add signal connection reference management": proposes representing a signal
  connection as an object tied to an instance. When that instance has no
  references left, the connection is terminated; the connection also terminates
  when the object is destroyed. This is the same family of idea as an explicit
  owned/scoped signal connection: the binding needs a first-class object that
  knows both the source and the lifetime owner.

- [#36](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/36),
  "`Object.connect_object` holds strong reference to object argument": reports
  that `connect_object()` kept the target alive, preventing the intended
  automatic disconnect when the target was collected. The ownership lesson is
  that a weak-target connection cannot store the target as normal Python
  `swap_data`; doing so changes "disconnect when target dies" into "target dies
  when emitter dies".

- [#557](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/557),
  "A handler connected by the `connect_object(..., gobject)` is not
  disconnected when the gobject is destroyed": the inverse symptom of the same
  contract. A weak-target connection must not only avoid keeping the target
  alive; it must also reliably remove the source handler when the target goes
  away. Both sides are required.

- [#106](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/106),
  "`GObject.disconnect_by_func` only disconnect one instance": shows that
  disconnection identity is also part of the lifecycle model. If a Python API
  promises "disconnect all handlers matching function and data", the closure
  registry needs enough identity information to match all equivalent native
  closures, not only the first Python wrapper object it can find.

These issues argue for an internal connection record with explicit state:
`connected`, `disconnecting`, `disconnected`, `in-flight`, and `invalidated`.
The record needs source object, handler id, closure pointer, optional weak
target/owner, and idempotent cleanup.

#### Callback retention and cross-runtime cycles

- [#42](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/42),
  "`TreeSelection` does not release references if `treeview` is destroyed":
  `treeview.get_selection().connect("changed", mycb)` left `mycb` referenced
  after `treeview.destroy()`. The important shape is that the signal source is
  not always the object the user thinks owns the UI lifetime. The `TreeView`
  lifetime and the `TreeSelection` lifetime differ, so cleanup tied only to the
  visible widget can miss callbacks stored on a helper object.

- [#136](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/136),
  "Problematic use of `Gtk.Builder` in examples and demos": the example stored
  the builder on `self`, then `connect_signals(self)` let `Gtk.Builder` keep a
  reference back to the application object. This is the classic Python-only
  half of the same cycle: `self -> builder -> callbacks/user-data -> self`.

- [#219](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/219),
  "New default SIGINT handling confuses garbage collection": the callback stack
  kept a pointer to `Gio.Application.quit`, preventing collection of the
  application. Bound methods are especially dangerous because a method object
  owns `self`; storing the method as a callback stores the object.

- [#536](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/536),
  "Memory leak when setting widgets as attributes of object": assigning a
  widget as an attribute of an object prevented finalization. This is not
  necessarily signal-specific, but it is the same ownership class as signal
  cycles: Python attributes can preserve widget subgraphs that native GTK also
  owns, producing cycles whose important edges are split between runtimes.

- [#596](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/596),
  "Objects are leaked when using Template Callbacks or connecting signals":
  template callbacks and programmatic signal callbacks kept objects alive until
  application shutdown. This is a direct predecessor to
  [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735): callback
  storage captures `self`, while the object graph reachable from `self` owns
  the callback.

- [#647](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/647),
  "Passing callbacks to `Gtk.Builder` never releases them": even after the
  button and application window are destroyed, something still owns the Python
  callback. This points at builder/scope closure ownership, not ordinary
  `GObject.connect()` alone.

- [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735),
  "`self` reference in some callbacks causes block of `do_dispose`": a callback
  owned through native objects reachable from `self` captures `self`, so
  wrapper finalization and Python `do_dispose()` are never reached. This is the
  clearest current reproducer for cross-runtime callback cycles.

The proposed "owned connection" or "owner-scoped closure" design addresses this
cluster only if the owner that is exposed to Python GC is also able to clear the
native connection. It is not enough to move the callback reference from one list
to another; the owner must have authority to disconnect or invalidate the
closure during `tp_clear()`.

#### Closure registry correctness and threading

- [#158](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/158),
  "Memory corruption around `PyGObjectData->closures` list causes segfault":
  the closure list was accessed concurrently by Python GC and signal-handler
  disconnect code. This is why closure bookkeeping must be GIL-aware and why
  `pygobject_watch_closure()` uses invalidate notifiers to remove closures from
  the watched list. For free-threaded Python, this area needs a stronger lock
  story than "the GIL happens to serialize this".

- [#102](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/102),
  "Handle multiple callbacks having the same destroy": APIs such as
  `g_object_bind_property_full()` can use multiple callbacks with the same
  destroy notifier, and older handling could free closure state too many times.
  A callback/destroy pair is not a unique closure identity. The binding must
  distinguish each native callback slot and make cleanup idempotent.

- [#43](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/43),
  "[meta] Make PyGI marshaling leak free": collects reference leaks and invalid
  object returns, and explicitly links old analysis of object reference counting
  for vfuncs and closures. The useful lesson for signal handling is that signal
  closure marshalling, vfunc reverse marshalling, and ordinary call marshalling
  share machinery but do not share identical ownership rules.

- [#69](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/69),
  "Use callable cache for signal and vfunc closures": argues for a unified
  callable cache that can support reverse marshalling for callbacks and vfuncs.
  This is required for correctness, but it cannot erase lifetime differences:
  signal callbacks are normally owned by a signal connection; vfunc closures are
  owned by class/type machinery; async callbacks are owned by in-flight
  operations.

- [#694](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/694),
  "Python refcounting changed since 3.14.0a7 resulting in test failures":
  CPython can change when temporary references are incremented or borrowed.
  Tests that assert exact incidental Python refcounts are brittle. Lifetime
  tests should assert semantic facts: object collected, handler disconnected,
  weakref cleared, callback released, no use-after-free.

#### Signal and callback argument marshalling

These are not all leaks, but they affect the same closure records and callback
lifetime code paths:

- [#68](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/68),
  "Signal marshalling of string + length": `GtkTextBuffer::insert-text` exposed
  a string/length closure marshalling problem. Signal callbacks need a
  signal-specific invoke plan; ordinary method marshalling is not sufficient.

- [#70](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/70),
  "GtkBuilder user-data objects not passed to signal handlers": builder XML can
  specify an object as signal user data. That object is part of the closure
  state and therefore part of the closure lifetime graph. Missing it breaks
  semantics; owning it strongly can create cycles.

- [#86](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/86),
  "`Gdk.Event` based structs are not usable after signal callbacks are
  finished": event structs passed to signal callbacks may be borrowed native
  memory whose lifetime ends with the callback. If Python stores them, the
  binding must copy or otherwise make ownership explicit.

- [#519](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/519),
  "DBus callbacks leak a reference in Python, because reference counting is not
  automatic": `GDBus` method callbacks hand an invocation object to Python, and
  the reporter expected Pythonic lifetime management. This is a callback
  ownership mismatch: GI transfer annotations and callback conventions must be
  translated into Python-visible ownership.

- [#655](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/655),
  "Pointer arguments in `Gio.Task.new(..., user_data)` segfault": callback
  `user_data` can be an untyped pointer in C but a Python object in bindings.
  The binding must keep Python-owned data alive until the native destroy notify
  runs, without pretending arbitrary pointers are Python objects.

- [#682](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/682),
  "Regression: some callbacks user_data not converted from/to variadics
  anymore": callback `user_data` handling changed around variadic conversion.
  This reinforces that user data is not a trailing afterthought; it is part of
  the callable ABI and part of closure lifetime.

- [#758](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/758),
  "Crash if `user_data` comes before callback in C API": when C places
  `user_data` before the callback, cache generation overwrote an existing arg
  cache and left a Python argument index hole. The immediate symptom is a
  crash, but the lifetime lesson is that callback, user-data, and destroy
  arguments form a group even when the C ABI orders them inconveniently.

#### Binding, model, and template factories

- [#614](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/614),
  "Adding bindings to custom widgets causes them to never get destroyed":
  property bindings can store transform closures and object references. For
  lifetime analysis, bindings are signal-like: they are native connection
  objects with Python callbacks and two endpoint objects.

- [#634](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/634),
  "Memory leak due to `bind_model`": a factory method passed to model binding
  kept a `Gtk.FlowBox` alive after the window closed. Factory callbacks are
  closure state owned by native model/view machinery; they need the same scoped
  cleanup story as signal callbacks.

- [#736](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/736),
  "Regression with finalizing custom widgets defined in templates": template
  finalization changed between releases. Template children and callbacks create
  a hidden object graph; finalization tests must cover both Python wrapper
  collection and native widget disposal.

- [#745](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/745),
  "Allow variadic amount of arguments to template callbacks": a convenience
  request, but it touches callback invocation. Template callbacks need an
  invocation plan that can drop unused signal arguments without changing
  ownership or callback lifetime.

- [#746](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/746),
  "Support `swapped` flag in `GtkBuilder`": swapped signal handlers are
  lifetime-sensitive because the swapped object may be exactly the owner/user
  data that decides when the connection should die.

The survey points toward one design rule: every API that creates callback state
should classify the callback as one of these forms:

- source-owned signal connection;
- weak-target signal connection;
- owner-scoped signal connection;
- builder/template scoped closure;
- async/in-flight callback;
- vfunc/class-owned closure;
- binding/factory closure.

Each form needs an explicit owner, a clearable path, and tests for both
directions of lifetime: source dies first and owner/target dies first.

### PyGObject `GObjectWeakRef`

`obj.weak_ref(callback=None, *user_data)` creates a `PyGObjectWeakRef`.

`PyGObjectWeakRef` is GC-aware:

- it owns Python `callback` and `user_data` references;
- `tp_traverse` visits those references;
- `tp_clear` clears them and unregisters the GObject weak notify;
- `tp_dealloc` untracks, clears, and frees with `PyObject_GC_Del`.

Creation registers `g_object_weak_ref(obj, notify, self)`. If a callback was
provided, PyGObject also `Py_INCREF`s the weakref object itself and stores
`have_floating_ref = TRUE`; this keeps the weakref handle alive even if user
code drops it. The notify callback:

- sets `self->obj = NULL`;
- calls the Python callback with `user_data`;
- clears callback and user data;
- drops the self-reference if one was held.

Calling a live `GObjectWeakRef` returns `pygobject_new(self->obj)`, so it may
return the existing wrapper or create a fresh one. Calling it after native
finalization returns `None`.

This is plain `g_object_weak_ref()`, not `GWeakRef`; it is a disposal
notification API, not a thread-safe weak-to-strong promotion API.

### PyGObject GI marshalling for GObject/fundamental values

For Python-to-C object arguments, `pygi-cache-object.c` uses:

- `PyGIFundamental`: pass the native instance pointer; if transfer is
  `GI_TRANSFER_EVERYTHING`, call the fundamental ref function.
- `PyGObject`: pass `pygobject_get(py_arg)`; if transfer is
  `GI_TRANSFER_EVERYTHING`, call `g_object_ref()` so the callee receives a new
  native reference.

For C-to-Python object returns, `pygi_arg_object_to_py()` uses:

- `NULL` -> `None`;
- real `GObject` -> `pygobject_new_full(pointer, steal=(transfer ==
  GI_TRANSFER_EVERYTHING), NULL)`;
- non-GObject fundamental -> `pygi_fundamental_new(pointer)`, followed by
  `pygi_fundamental_unref()` when transfer was full, because the wrapper took
  its own fundamental ref.

There is also a Python-implemented vfunc/signal return hack:
`pygi_arg_gobject_out_arg_from_py()` may add an extra `g_object_ref()` when both
the Python object refcount and the native GObject refcount look like they are
only held by the return path. The source comments say the check is not reliable
on Python 3.14. This is a compatibility workaround, not a general ownership
rule to copy.

### PyGObject builtin wrapper families and heap-type behavior

The local `gi` C extension has several built-in wrapper families. All are
ordinary CPython objects from Python's point of view: Python references decide
when their `tp_dealloc` runs. Their native ownership models differ:

- `PyGObject` / `gi._gi.GObject`: owns one `GObject` ref; GC-aware; supports
  Python weakrefs; uses qdata for wrapper identity; has `tp_finalize` for
  `do_dispose`.
- `PyGObjectWeakRef` / `gi._gi.GObjectWeakRef`: owns Python callback/user-data
  refs and a registered `g_object_weak_ref`; GC-aware.
- `PyGBoxed` / `gobject.GBoxed`: wraps registered boxed pointers. If
  `free_on_dealloc` is true, dealloc frees with `g_boxed_free(gtype, ptr)`.
  `pygi_gboxed_new(copy_boxed=TRUE)` copies with `g_boxed_copy()` and must own
  the result.
- `PyGIBoxed` / `gi.Boxed`: registered struct/union boxed wrapper. It can own
  either a slice allocation or a boxed allocation. Dealloc uses `g_value_unset`
  plus `g_slice_free1` for slice-allocated `GValue` cases, otherwise
  `g_boxed_free()`.
- `PyGPointer` / `gobject.GPointer`: raw pointer wrapper. It does not own or
  free the pointer. The source explicitly says these types are not recommended
  because there is no copy/free metadata.
- `PyGIStruct` / `gi.Struct`: non-registered struct/union wrapper, subclassing
  `GPointer`. If `free_on_dealloc` is true, dealloc releases foreign structs
  through `pygi_struct_foreign_release()` or frees normal memory with `g_free()`.
- `PyGIFundamental` / `gi.Fundamental`: wraps non-GObject fundamental
  instances. It stores ref/unref function pointers from `GIObjectInfo`; dealloc
  calls the unref function. For `GParamSpec`, construction sinks the floating
  param-spec ref with `g_param_spec_ref_sink()`.
- `PyGIBaseInfo` and subclasses: wrap `GIBaseInfo *`. Construction stores
  `gi_base_info_ref(info)`; dealloc clears Python weakrefs and
  `gi_base_info_unref(info)`. `PyGICallableInfo` additionally frees its callable
  cache before chaining to base dealloc.
- `PyGProps`: GC-aware property proxy. It owns a strong Python ref to the
  containing `PyGObject`; dealloc clears that reference. Traversal reports it.
- `PyGPropsIter`: owns a copied `GParamSpec **` array and frees it with
  `g_free()`.
- `PyGTypeWrapper` / `gobject.GType`: value wrapper around a `GType`. It owns no
  native reference; dealloc just frees the Python object.
- `PyGEnum` and `PyGFlags`: Python classes imported from `gi._enum` and backed
  by `enum.IntEnum` / `enum.IntFlag` behavior. Runtime enum/flags classes are
  normal Python type objects cached on the GType with qdata; enum/flag values
  are Python integer-like objects, not native owned instances.

The recurring pattern is: every wrapper family makes native ownership explicit
with a boolean, transfer flag, ref/unref function pointer, or "raw borrowed
pointer" policy. Only the families that own Python references and can form
cycles opt into Python cyclic GC.

### CPython weakref internals

`PyObject_ClearWeakRefs(object)` is called from deallocation paths when the
object supports weakrefs and the refcount is already zero. It clears the
referent out of each weakref, collects callbacks, and invokes callbacks after
the weakrefs no longer expose the referent.

During cyclic GC, `gc.c` has separate weakref phases. Weakrefs to objects in
unreachable garbage are cleared before `tp_clear`, and callbacks are only called
when the callback itself is not part of the unreachable trash. This is why
weakref callbacks should not be modeled as ordinary strong edges from the
referent.

For a GObject wrapper, Python weakrefs are therefore a hook into wrapper
deallocation only. They do not observe GObject disposal unless the wrapper
design deliberately keeps wrapper lifetime coupled to native lifetime, for
example with toggle refs.

### GObject construction and lifecycle hooks

GObject construction is type-system-driven:

1. `g_type_create_instance()` allocates the instance.
2. `g_object_init()` initializes `ref_count` to `1`, clears qdata, and marks the
   object as in-construction.
3. `GObjectClass.constructor` may be called for custom construction. This hook
   is "seldom overridden" and can return an already existing singleton object.
4. construct properties are set.
5. `GObjectClass.constructed` runs after construction properties are set.
6. remaining properties are set.

The overridable object-class hooks in `GObjectClass` are:

- `constructor`;
- `set_property`;
- `get_property`;
- `dispose`;
- `finalize`;
- `dispatch_properties_changed`;
- `notify`;
- `constructed`.

There is no `ref` or `unref` virtual function in `GObjectClass`. Refcount
operations are centralized in `g_object_ref()`, `g_object_unref()`,
`g_object_ref_sink()`, and related helper paths.

### GObject ref/unref internals

`g_object_ref()` calls an internal `object_ref()` helper:

- if `ref_count > 1`, it atomically increments the count and returns;
- if `ref_count == 1`, it takes the toggle-ref-aware slow path because this may
  transition a sole toggle reference from weak back to strong;
- if a toggle notification is needed, it is returned to `g_object_ref()` and
  invoked after locks are released.

`g_object_unref()` has three materially different cases:

- `old_ref > 2`: atomically decrement and return;
- `old_ref == 2`: this may be a transition to "toggle ref is last ref", so it
  takes the toggle-ref-aware slow path and may notify;
- `old_ref == 1`: clear `GWeakRef` locations, freeze notify, call `dispose`,
  then re-check the refcount because `dispose` may resurrect the object. If it
  is still the final ref, set the count to zero, destroy closures/signals/weak
  notifies, call `finalize`, and free the instance with `g_type_free_instance()`.

Important details:

- `g_object_unref()` deliberately treats resurrection during `dispose` as a
  first-class case.
- plain GObject weak-notify callbacks and closure cleanup are run as part of the
  final unref path.
- GObject qdata is cleared in `g_object_finalize()`, so qdata destroy notifies
  happen during finalization.
- After the atomic decrement in non-final paths, another thread can destroy the
  object; GLib comments explicitly warn that tracing may hold a dangling object
  pointer at that point.

For wrappers, the key limit is that we cannot customize the native refcount
algorithm per wrapped type. We can only choose when to call `g_object_ref()`,
`g_object_ref_sink()`, `g_object_unref()`, `g_object_weak_ref()`,
`g_weak_ref_*()`, `g_object_add_toggle_ref()`, and `g_object_run_dispose()`.

### GObject floating internals

`GInitiallyUnowned` is implemented as a normal `GObject` type whose instance
init calls `g_object_force_floating()`. Floating state is managed by an internal
floating-flag handler, not by a second refcount.

`g_object_ref_sink()` is implemented as:

1. `g_object_ref(object)`;
2. clear/sink the floating flag;
3. if the object had been floating, `g_object_unref(object)`.

The net effect is:

- floating object: refcount ends unchanged, floating flag is cleared;
- non-floating object: refcount increases by one.

`g_object_take_ref()` only clears the floating flag and otherwise does nothing.
It is useful when a callback may return either a floating new object or an
already-owned full reference, and the caller wants exactly one full reference.

For GI bindings, `g_object_ref_sink()` is the normal acquire operation for
transfer-none or maybe-floating returns. `g_object_take_ref()` is more precise
for callback-return adoption when the callback contract already returns a full
reference if the object is not floating.

### GObject weak-reference internals

GLib has two weak-reference families:

- `g_object_weak_ref()`: callback notification during disposal/finalization;
  not a thread-safe way to promote a weak reference to a strong reference.
- `GWeakRef`: a thread-safe weak location that can be atomically promoted with
  `g_weak_ref_get()`.

`GWeakRef` is implemented with per-object `WeakRefData`, a per-weak-ref lock bit
stored in the pointer, and careful lock ordering between the weak ref and the
per-object weak-ref data. `g_weak_ref_get()` does not simply read a pointer and
then call `g_object_ref()`. It locks the weak-ref data and takes the strong ref
while synchronized with the final-unref path that clears weak locations.

This is the exact race plain wrapper code must avoid:

1. thread A reads a weak pointer;
2. thread B drops the final strong ref and begins disposal;
3. thread A calls `g_object_ref()` on an object that is already being cleared.

`GWeakRef` is the GLib primitive for that promotion. `g_object_weak_ref()` is a
notification primitive, not a promotion primitive.

### GObject toggle internals

Toggle refs are stored as qdata under GLib's internal
`GObject-toggle-references` quark. `g_object_add_toggle_ref()` first calls
`g_object_ref()`, then appends a `(notify, data)` tuple to the toggle-ref stack
and marks the object as having toggle refs.

The real toggle work is in the `g_object_ref()` and `g_object_unref()` slow
paths:

- refcount transition `1 -> 2` can notify with `is_last_ref = FALSE`;
- refcount transition `2 -> 1` can notify with `is_last_ref = TRUE`;
- callbacks are captured while holding the necessary locks but invoked only
  after locks are released, because callbacks may run user code.

Multiple toggle refs suppress notification until all but one are removed. This
falls straight out of the source-level model: the slow path can only interpret
"refcount is 1" or "refcount is 2" as a unique proxy-transition signal if there
is at most one toggle reference involved.

For a Python binding, toggle refs are the only built-in GObject mechanism that
lets native refcount transitions ask the wrapper layer to upgrade or downgrade a
reverse reference to a proxy. But because this hooks into the hottest native
ref/unref transitions and can call user code after racing cross-thread unrefs,
it has a much larger correctness surface than qdata plus explicit weak refs.

### What can and cannot be modified

Python:

- Can customize allocation, initialization, deallocation, finalization, weakref
  support, cyclic GC visibility, and attribute storage through type slots and
  flags.
- Cannot customize `Py_INCREF()`/`Py_DECREF()` semantics per type.
- Can make deallocation release a GObject ref, clear qdata, save state, or call
  Python finalization.
- Cannot make a Python weakref observe native GObject lifetime unless wrapper
  lifetime is deliberately coupled to native lifetime.

GObject:

- Can customize construction, property access, `dispose`, `finalize`,
  `constructed`, and notification behavior through `GObjectClass`.
- Cannot customize `g_object_ref()`/`g_object_unref()` as class vfuncs.
- Can attach qdata, weak notifies, `GWeakRef`s, toggle refs, closures, and weak
  pointers.
- Can use `g_object_run_dispose()` to ask an object to drop outgoing object
  references before its refcount reaches zero.
- Cannot safely promote a plain `GWeakNotify` callback pointer back to a live
  object. Use `GWeakRef` when promotion is needed.

Binding design implication:

- Use Python slots to define wrapper lifetime.
- Use GObject ref APIs to define native lifetime.
- Use qdata only for identity/state association, not for ownership unless the
  qdata destroy notify explicitly owns and releases that state.
- Use `GWeakRef` for cross-thread weak-to-strong promotion.
- Use toggle refs only if the design requires native refcount transitions to
  keep or release Python proxy ownership automatically.
