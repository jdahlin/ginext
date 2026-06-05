# Invoke Vectorcall Revival Plan

This note scopes the work needed to get `ginext` invoke back toward the old
`goi` microbench numbers for trivial call shapes.

## Current status

The trivial free-function path is now back in the old `goi` range after:

- native vectorcall descriptor surfacing
- tuple-free trivial scalar lanes
- bound `self,bool->void` / `self->int` lanes
- direct top-level descriptor export for free functions instead of the Python
  `Function` wrapper

Current reduced-count microbench numbers across the three relevant layers:

```text
free functions                               ginext native   gi compat    legacy gi
noop_void   (0 args, void)                        36.4 ns       38.0 ns      170.7 ns
noop_int    (0 args, int)                         40.9 ns       41.1 ns      173.3 ns
in_1_int    (1 arg)                              173.2 ns      171.8 ns      327.9 ns
in_2_int    (2 args)                             355.8 ns      234.4 ns      365.3 ns
in_3_int    (3 args)                             404.5 ns      312.2 ns      415.1 ns
in_4_int    (4 args)                             400.2 ns      440.0 ns      478.9 ns
in_5_int    (5 args)                             499.3 ns      571.3 ns      500.6 ns
in_6_int    (6 args)                             507.8 ns      574.4 ns      552.8 ns
in_5_mixed  (i32,i64,f64,i32,u32)               673.6 ns      761.6 ns      530.1 ns
```

```text
methods on GObject (bound)                   ginext native   gi compat    legacy gi
set_flag(self, bool)                            267.2 ns      296.6 ns      323.5 ns
get_index(self) -> int                          194.4 ns      208.7 ns      240.0 ns
lookup(self, str) -> GO                        2919.3 ns     2531.8 ns      455.4 ns
```

Interpretation:

- `noop_void` is effectively solved for the current target.
- the remaining free-function gap is now in the non-trivial arg lanes
- object-return rows like `lookup` are still a separate problem
- legacy `gi` remains much faster on several object/property/signal rows, which
  means the remaining hot spots are no longer the trivial leaf call path

## Why this exists

The current invoke architecture is too generic on the hot path:

- Python `Function.__call__` and `_GICallable.__call__` wrappers
- `types.MethodType` for bound methods
- `private.invoke_callable_descriptor(...)` exposed only as `METH_VARARGS`
- `PyArg_ParseTuple`
- `resolve_call_args`
- tuple rebuilding for bound calls
- dict/kwarg normalization even for the common positional-only case

The profiler showed the native call itself was not the problem. Before the
current short-circuit work on `ginext-optimizations`:

```text
noop public                     351.8 ns
noop direct invoke              262.3 ns

set_flag bound cached           850.6 ns
set_flag attr each             1079.3 ns
set_flag direct invoke          567.0 ns

lookup bound cached            3034.1 ns
lookup direct invoke           2595.2 ns
```

For `noop_void`, `ffi_call` is a rounding error in `perf`. Most time is in
Python call glue and the generic invoke wrapper.

## Historical anchor

Old `goi` already proved that the floor is much lower when the hot path is
specialized.

Commit `16b07745` (`microbench typelib + special-case vectorcalls for noop
int/void shapes`) reported:

```text
noop_void   43 ns
noop_int    44 ns
in_1_int    46 ns
in_3_int    55 ns
in_5_int    65 ns
in_6_int    66 ns
```

That commit used two key ingredients:

1. A native descriptor type with `Py_TPFLAGS_HAVE_VECTORCALL` and
   `Py_TPFLAGS_METHOD_DESCRIPTOR`
2. Fast lanes for trivial scalar signatures that bypassed the generic marshal
   path and called the resolved C function pointer directly

Commit `bd4f1f50` also converted the old method descriptor to a native CPython
vectorcall type.

## Current seam in ginext

The good news is that `ginext` already has a clean place to attach this work:

- `private.build_callable_descriptor(...)` already builds the native compiled
  descriptor and caches plan data
- `PyGICompiledCallable` already knows the invoke plan and resolved target
- `src/ginext/private/callable_descriptor.c` already owns descriptor build and
  generic invoke

The bad news is that Python still wraps the descriptor:

- `src/ginext/method.py`
  - `Function.__call__` calls `private.invoke_callable_descriptor(...)`
  - `_GICallable.__get__` returns `types.MethodType(self, obj)`
  - bound methods call `private.invoke_callable_descriptor(descriptor, (self,
    *args), kwargs)`
- `src/ginext/private/ginextmodule.c`
  - `invoke_callable_descriptor` is still `METH_VARARGS`

That means the current builder has the right native data, but the public call
surface forces us back through Python and varargs parsing.

## Target shape

The target for the common case is:

```text
Python CALL
  -> native descriptor vectorcall
  -> direct args array, no tuple/dict packing
  -> no Python wrapper or MethodType object
  -> specialized trivial-scalar fast lane when shape matches
  -> generic native fallback otherwise
```

More concretely:

- free function lookup returns a native callable object
- instance method lookup returns the same descriptor type, used as a method
  descriptor by CPython
- `obj.method(...)` should go through `LOAD_METHOD`/`CALL` without creating a
  Python `method` object
- generic invoke fallback should itself be vectorcall-based
- kwargs and overlay defaults should fall to a slower path, not burden the
  simple positional fast path

## Implementation slices

### Slice 1: native descriptor/vectorcall surface

Goal: remove the Python wrapper layer without changing generic invoke semantics.

Work:

- Add a native callable/descriptor type in `src/ginext/private/runtime/`
  instead of wrapping descriptors in `method.py`
- Set:
  - `Py_TPFLAGS_HAVE_VECTORCALL`
  - `Py_TPFLAGS_METHOD_DESCRIPTOR`
- Implement:
  - `tp_descr_get`
  - `tp_call` via `PyVectorcall_Call`
  - `__vectorcalloffset__`
- Make `build_callable_descriptor(...)` return this object directly
- Stop using:
  - `_GICallable`
  - `types.MethodType`
  - Python trampoline functions in `method.py`

Success criteria:

- `noop public` drops materially toward the current `noop direct invoke`
- `set_flag bound cached` drops by roughly the current bound-wrapper delta

### Slice 2: vectorcall generic invoke fallback

Goal: keep the generic path, but stop paying `METH_VARARGS` and tuple rebuild.

Work:

- Replace `py_invoke_callable_descriptor(PyObject *args)` with a true vectorcall
  entrypoint taking:
  - `PyObject *const *args`
  - `size_t nargsf`
  - `PyObject *kwnames`
- Remove:
  - `PyArg_ParseTuple`
  - tuple extraction into `call_args`
  - bound-method `(self, *args)` repacking
- Split the generic implementation into:
  - positional fast path
  - kwargs slow path

Success criteria:

- `noop direct invoke` drops materially from the current `~262 ns`
- `set_flag direct invoke` drops materially from the current `~567 ns`

### Slice 3: trivial scalar fast lanes

Goal: restore the old `40-80 ns` class of results for the simple microbench
rows.

Work:

- Reintroduce signature-picked fast vectorcalls for narrow shapes:
  - `void() -> void`
  - `void() -> int`
  - `int -> int`
  - `int, int -> int`
  - up to six int args
- Add equivalent bound-method variants only if the numbers show they matter
- Gate on:
  - no kwargs
  - no self for the first pass
  - no closures, arrays, out args, or special roles
- Call the resolved function pointer directly

Success criteria:

- trivial free-function rows recover to the old order of magnitude
- the generic path remains the fallback for everything else

## Special cases to keep out of the hot path

These should not block slices 1-3:

- overlay arg defaults
- kwargs
- callback/user_data packing
- class-struct wrappers
- object-return methods like `lookup`

All of those should stay on a slow path until the trivial scalar lane is fast
again.

## Separate problem: object returns

`lookup("undo")` is not just wrapper overhead. `perf` shows real return-side
costs:

- `gi_registered_type_info_get_g_type`
- `g_module_symbol`
- wrapper/type resolution
- `g_type_create_instance`

So object-returning methods need their own optimization track after the call
surface is fixed. They should not dilute the trivial-scalar work.

## Benchmark contract for this work

Use the same rows for each slice so deltas stay honest:

- free:
  - `noop_void`
  - `noop_int`
  - `in_1_int`
- bound:
  - `set_flag`
  - `set_flag attr-each`
- heavier control row:
  - `lookup`

For each row, keep measuring:

- public call
- direct/native call surface
- `perf` on at least:
  - `noop_void`
  - `set_flag`

The work is moving in the right direction only if:

- public-call overhead falls sharply in slice 1
- generic-direct overhead falls sharply in slice 2
- trivial free-function rows collapse into double-digit ns in slice 3
