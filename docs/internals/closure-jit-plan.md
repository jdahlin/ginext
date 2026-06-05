# Closure JIT Plan

## Motivation

The current C-to-Python callback path is already significantly optimized:

- closure metadata is cached in `GoiClosurePlan`
- callback arguments use vectorcall instead of tuple construction
- direct primitive argument conversion bypasses generic marshalling
- scope-call callbacks skip GIL acquire/check overhead
- scalar return and OUT writeback use direct conversion

After these changes, the focused closure benchmark is roughly:

```text
callback no args            41 ns/call
callback int -> int         68 ns/call
callback int -> out int     83 ns/call
callback mixed -> int      176-183 ns/call
callback user-data          78 ns/call
```

The remaining opportunity is a direct specialized callback entry that avoids
libffi closure dispatch and the generic `void **args` frame used by
`goi_closure_invoke()`.

## Measured Headroom

Callgrind instruction counts for `callback mixed -> int`, with a zero-call
baseline subtracted:

```text
current goi mixed -> int       ~2,176 Ir/call
direct vectorcall mixed floor  ~1,308 Ir/call
direct vectorcall prebuilt       ~533 Ir/call
direct vectorcall no-args        ~365 Ir/call
```

Wall-clock comparison:

```text
current goi mixed -> int       ~183 ns/call
direct vectorcall mixed floor   ~96 ns/call
```

That implies a best-case specialized path around:

```text
~40% fewer instructions/call
~48% less time/call
~1.9x throughput
```

This is a floor measurement, not a promise. A first production JIT path should
probably land closer to `100-130 ns/call` for `mixed -> int`, depending on how
much generic safety remains in the emitted path.

## Scope

The first implementation should specialize only common simple callback shapes:

- no-arg callbacks
- scalar IN args:
  - `bool`
  - `int32` / `uint32`
  - `int64` / `uint64`
  - `double`
  - `utf8` / `filename`
  - opaque pointer/user-data
- scalar returns:
  - `void`
  - `bool`
  - `int32` / `uint32`
  - `int64` / `uint64`
  - `double`
- simple scalar OUT writeback, especially `int *`
- user-data slot behavior matching the current closure plan

Everything else should fall back to the existing ffi backend:

- arrays and length-paired arrays
- structs/unions/boxed/interface values
- complex ownership transfer
- callback signatures needing generic marshalling
- unsupported ABI shapes

## Design

No broad marshaller refactor is required. The closure JIT should sit beside
the existing ffi backend and consume the cached `GoiClosurePlan`.

Proposed structure:

```text
src/_goi/GObject/Closure-ffi.c      existing libffi backend
src/_goi/GObject/Closure-jit.c      new specialized native backend
src/_goi/GObject/Closure-plan.c     existing descriptor-time metadata
src/_goi/GObject/Closure.c          shared generic invoke fallback
```

Creation flow:

```text
goi_callback_closure_new()
  try goi_callback_closure_new_jit()
    if signature is supported:
      emit specialized callback entry
      return native code pointer
  fall back to goi_callback_closure_new_ffi()
```

The JIT backend should not replace `goi_closure_invoke()`. It should bypass it
only for supported simple signatures. Unsupported signatures keep using the
shared generic path through libffi.

## Backend Ownership

Before adding `Closure-jit.c`, make closure backend ownership explicit. A small
mechanical change is enough:

```c
typedef enum {
  GOI_CLOSURE_BACKEND_FFI,
  GOI_CLOSURE_BACKEND_JIT,
} GoiClosureBackend;
```

or store a backend destroy callback on the shared base struct. The goal is to
avoid assuming every closure cookie is a `GoiCallbackFfiClosure`.

## Emitted Path

For a supported signature, the emitted callback entry should:

1. Receive C callback args in the platform ABI.
2. Box supported scalar args directly into a stack `PyObject *argv[]`.
3. Substitute captured Python user-data for hidden closure cookie slots.
4. Call the Python callable with `PyObject_Vectorcall`.
5. Convert the Python return directly to the ABI return register/slot.
6. Write supported OUT scalar values back through pointer args.
7. DECREF temporary Python args and result.

For scope-call callbacks, the existing metadata can mark that the caller holds
the GIL. Async/notified/forever callbacks must still acquire/release the GIL.

## Estimated Size

Expected first implementation size:

```text
Closure plan/lowering metadata        150-250 LOC
x86_64 callback trampoline emitter    350-600 LOC
ABI arg unpacking/widening             150-250 LOC
return writeback                       80-150 LOC
backend selection/lifetime glue        100-150 LOC
tests/bench coverage                   150-250 LOC
```

Total estimate:

```text
~900-1,500 LOC
```

Keeping the first supported signature set narrow should keep it closer to
`900-1,100 LOC`.

## Testing

Add focused tests for:

- `callback_no_args_loop`
- `callback_int_loop`
- `callback_out_int_loop`
- `callback_mixed_loop`
- `callback_user_data_loop`
- fallback behavior for unsupported callback shapes

Benchmark before and after with:

```sh
env MESONPY_EDITABLE_SKIP=... PYTHONPATH=... \
  uv run python examples/draw-bench/closure_bench.py --backend=ffi
```

Once the JIT backend exists, the `--backend=jit` run should stop profiling
through `callback_ffi_trampoline` for supported callback shapes.

## Non-Goals

- Do not specialize every callback shape initially.
- Do not refactor generic marshalling before starting this work.
- Do not remove the ffi backend.
- Do not route arrays, structs, boxed values, or interfaces through the first
  specialized path.

## Open Questions

- Should the first emitter target only x86_64 SysV, matching the current
  fastest development path, or share scaffolding with a future aarch64 backend?
- Should no-arg callbacks get a very small hand-written trampoline first as a
  proof of lifecycle/backend ownership?
- Should string args always allocate Python unicode, or can some utf8 callback
  shapes safely reuse/cache immutable Python strings for known constant C
  pointers? This is likely unsafe as a general rule and should not be part of
  the first implementation.
