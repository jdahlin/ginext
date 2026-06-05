# PyGObject Lifetime And GC Notes

Status: research notes as of 2026-05-15.

This document is the working model for goi's `GObject` wrapper lifetime,
reference counting, cycle-GC, weakref, and disposal behavior relative to
PyGObject. The immediate driver is PyGObject work item `#735`, but the same
questions show up in older Bugzilla bugs around `tp_traverse`, wrapper cycles,
toggle refs, and closure ownership.

## Current goi surface

goi already exposes the two debug helpers used by upstream-style lifecycle
tests:

- `obj.__grefcount__`: raw underlying `GObject.ref_count`
- `obj.__gpointer__`: capsule around the underlying `GObject *`

Relevant code:

- [src/_goi/GObject/Object.c](../../src/_goi/GObject/Object.c)
- [tests/test_object_lifecycle.py](../../tests/test_object_lifecycle.py)
- [tests/test_regress.py](../../tests/test_regress.py)

goi also already made two notable architecture choices:

1. No Python `weakref.ref()` support for wrappers.
2. A dedicated `obj.weak_ref()` API backed by `g_object_weak_ref()`.

Relevant code:

- [src/_goi/GObject/Object-weakref.c](../../src/_goi/GObject/Object-weakref.c)
- [tests/test_GObject_Object.py](../../tests/test_GObject_Object.py)

Wrapper identity is stored in GObject qdata, and Python instance attributes are
snapshotted into qdata across wrapper GC cycles:

- [src/_goi/GObject/Object-wrap.c](../../src/_goi/GObject/Object-wrap.c)
- [src/_goi/GObject/Object-lifecycle.c](../../src/_goi/GObject/Object-lifecycle.c)

This is already structurally closer to post-toggle-ref PyGObject than to older
PyGObject.

## What current PyGObject documents

Two current upstream statements matter most:

1. PyGObject's weakref docs say wrapper lifetime and GObject lifetime can
   differ, and users should use `GObject.Object.weak_ref()` when they want
   notification about the underlying GObject's finalization.
2. PyGObject 3.55.0 says toggle references were removed, and users relying on
   Python weakrefs should migrate to `GObject.Object.weak_ref()`.

Primary sources:

- PyGObject weakrefs guide:
  https://pygobject.gnome.org/guide/api/weakrefs.html
- PyGObject changelog 3.55.0:
  https://pygobject.gnome.org/changelog.html

This means goi should not chase old toggle-ref-era Python weakref semantics as
the compatibility target. The target is current PyGObject behavior.

## Historical bug pattern

The old bugs are still relevant because they explain the failure modes.

### 1. `tp_traverse()` must only expose Python-owned edges

Bug 92955 is the core design discussion. The problem was that Python cycle GC
would traverse a wrapper and see edges into callback/method objects, then clear
the Python wrapper even though the underlying GObject was still meaningfully
alive elsewhere. That produced half-cleared wrappers and empty `__dict__`
states.

Key idea from the discussion: a wrapper should not claim ownership of edges
that it cannot actually break in `tp_clear()`. If the GObject still owns the
closure or other native state, exposing that edge to Python GC is incorrect.

Primary source:

- Bug 92955: https://bugzilla.gnome.org/show_bug.cgi?id=92955

### 2. Wrapper/GObject cycles were historically solved with toggle refs

Bug 320428 is the long-running design discussion about breaking the
PyGObject<->GObject cycle. It contains the earlier tradeoff discussion between:

- wrapper/GObject back-reference cycles
- Python weakrefs
- dedicated GObject weakrefs
- toggle refs
- hybrid approaches

Primary source:

- Bug 320428: https://bugzilla.gnome.org/show_bug.cgi?id=320428

For current work, the important outcome is not "rebuild toggle refs", but:

- understand why Python weakrefs and wrapper resurrection were hard
- keep the ownership model explicit
- avoid traversing native-owned closure state as though Python owned it

### 3. Closures can keep Python `self` alive in ways that block `do_dispose`

Work item `#735` is the modern version of the same class of problem. The
reported reproducers show a closure stored by a GObject-owned structure
(`Gio.SimpleAction`, `GObject.SignalGroup`) capturing `self`. That is enough to
keep the Python object alive, which in turn blocks expected `do_dispose()`
timing.

Primary source:

- Work item 735:
  https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735

This is not just "a leak". It is a mismatch between:

- Python reachability
- GObject disposal expectations
- where closure ownership actually lives

### 4. `connect_object()` is the canonical "don't traverse what you don't own"
case

Bug 731501 and the later GitLab issue `#387` describe the cycle where closure
data retains the wrapper, Python GC traverses it, and `tp_clear()` breaks the
wrapper even though the actual closure is still owned by the GObject.

Primary sources:

- Bug 731501: https://bugzilla.gnome.org/show_bug.cgi?id=731501
- Work item 387:
  https://gitlab.gnome.org/GNOME/pygobject/-/work_items/387

For goi, this is why `connect_object()` now uses:

- raw `GObject *` for the target
- `g_object_weak_ref()` for auto-disconnect
- temporary `g_object_ref()` around callback invocation

instead of holding a strong Python ref to the wrapper in the trampoline.

## Implications for weakrefs

Current compatibility target:

- Python `weakref.ref(wrapper)` is not the lifetime API.
- `obj.weak_ref()` is the lifetime API for GObject finalization tracking.

That aligns with current upstream docs and avoids depending on resurrectable
wrapper identity.

What still needs verification:

1. `weak_ref()` callback timing relative to `dispose`.
2. `weak_ref().__call__()` behavior during re-entrant disposal/re-ref cases.
3. Thread-safety limits of `g_object_weak_ref()` vs `GWeakRef`.

Note: GObject's own docs explicitly say `g_object_weak_ref()` is not
thread-safe if final unref can happen on another thread. That matters for
future free-threaded Python work.

## Implications for `tp_traverse` / `tp_clear`

goi's `GObject.Object` wrapper currently does not expose a custom
`tp_traverse`/`tp_clear` pair. That is conservative and probably correct for
the current no-toggle-ref design.

The immediate rule should be:

- only traverse Python references that are truly owned by the wrapper and will
  be broken by wrapper teardown
- do not traverse signal closure state, watched closures, or other native-owned
  callback structures just because they indirectly point back to Python

This is exactly the invariant behind the old PyGObject bugs:

- if `tp_traverse()` visits it, `tp_clear()` must be able to invalidate it
  coherently
- otherwise Python GC can produce half-broken live objects

For goi this argues for keeping wrapper GC logic narrow and keeping closure
ownership modeled in native structures instead.

## Implications for toggle refs

Current PyGObject removed them. goi already avoids them.

That is the right default unless a concrete compatibility blocker appears.

But removing toggle refs shifts responsibility onto:

- qdata-based wrapper identity
- explicit weakref API
- correct wrapper re-wrap behavior after wrapper GC
- correct instance-dict preservation across wrapper resurrection
- correct `do_dispose()` dispatch when only native ownership remains

So "no toggle refs" is not the end of the problem. It changes which invariants
have to be made precise.

## Implications for `do_dispose`

There are two separate concerns:

1. Whether goi can call Python `do_dispose()` correctly when GObject enters
   disposal.
2. Whether Python closures keep the Python wrapper alive so that object teardown
   timing differs from what users expect.

Recent PyGObject history shows both are active sources of regressions:

- `#698`: dispose vfunc not called when objects go out of scope
- `#735`: `self` in callbacks blocks `do_dispose`
- `#736`: regression with finalizing custom widgets in templates
- `#751`: floating-object crash around dispose wrapper creation

These are distinct but related. A good test matrix needs to separate them.

## What goi still needs for a full `#735` understanding

### Test coverage gaps

We should add or port tests in these buckets:

1. `__grefcount__` stability tests
   - plain wrapper construction/destruction
   - property get/set of object-valued properties
   - signal connection/disconnection
   - builder/template-created child widgets
   - floating object construction and disposal

2. Wrapper resurrection tests
   - drop Python wrapper while C still owns GObject
   - later C-to-Python crossing recreates wrapper
   - instance `__dict__` survives across that cycle
   - class identity remains correct after re-wrap

3. Closure ownership tests
   - bound methods
   - lambdas capturing `self`
   - `connect_object()`
   - `SignalGroup.connect_closure()`
   - builder/template callbacks

4. `do_dispose` timing tests
   - plain Python subclass
   - widget subclass
   - template child graph
   - floating objects
   - closure captures of `self`

5. Weakref tests
   - `weak_ref(callback)` fires exactly once
   - `weak_ref().unref()` cancels callback
   - `weak_ref().__call__()` returns wrapper while object is alive
   - dead weakrefs return `None`

### Implementation questions

1. Should signal/closure wrappers ever hold Python strong refs to wrappers, or
   should they always prefer raw `GObject *` + transient wrapper materialization
   at call time?
2. Do any current goi closure paths still expose Python-owned cycles that are
   actually native-owned?
3. Is `SignalGroup.connect_closure()` susceptible to the same issue class as
   `connect_object()`?
4. Is wrapper `__dict__` preservation complete for all disposal/re-wrap paths,
   including template-instantiated objects and floating objects?
5. Do we need a dedicated debug API beyond `__grefcount__` and `__gpointer__`,
   or is parity with upstream tests enough?

## Practical guidance for goi

Short version:

- keep `__grefcount__` and `__gpointer__`
- port more PyGObject lifecycle tests before adding new lifetime machinery
- keep Python `weakref.ref()` unsupported for wrappers
- prefer raw `GObject *` plus transient wrapper creation in closure data where
  lifetime-tied behavior matters
- keep `tp_traverse` narrow; never let Python GC believe it owns native closure
  edges that only GObject can actually disconnect

## Immediate next tasks

1. Inventory upstream PyGObject tests that use `__grefcount__`, `weak_ref()`,
   wrapper resurrection, or disposal.
2. Port the cases that still make sense post-toggle-ref-removal.
3. Add focused goi regressions for `SignalGroup.connect_closure()` and
   builder/template callback retention.
4. Compare goi's `do_dispose` behavior against current PyGObject on the
   reproducers from `#698`, `#735`, `#736`, and `#751`.
