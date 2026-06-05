# Full JIT Implementation Plan

This document is a handoff plan for expanding goi's JIT coverage on Linux
x86_64. The goal is to make `jit-only` pass broad GI marshalling tests without
copying all GI marshalling logic into handwritten assembly.

Scope for this plan:

- Target platform: Linux x86_64, System V AMD64 ABI.
- Target mode: `set_call_mode("jit-only")`.
- Preserve the existing FFI path as the correctness baseline.
- Allow refactoring so both FFI and JIT reuse the same non-generic marshalling
  functions.
- Do not design for Windows, macOS, aarch64, or i386 in this pass.

## Current State

The current JIT supports a narrow direct-call signature:

- primitive scalar IN args
- UTF-8 / filename IN args
- object/interface IN args that reduce to `GObject *`
- enum/flags as int32
- primitive scalar returns
- UTF-8 returns
- `GObject *` returns
- float/double register lanes
- one special `self + argv` helper shape

The main restrictions are visible in `src/runtime/callable.c`:

- `gi_signature_from_callable_builder()` rejects GError-throwing callables.
- It rejects all OUT and INOUT args.
- It rejects arrays, lists, hash tables, most interfaces, boxed structs, GValue,
  GVariant, GBytes, callbacks, closures, and GError.
- It lowers GI metadata to only `PygirSignature`, which has `ret`, `args[]`,
  `has_self`, and flags.

The x86_64 backend in `src/jit/arch/x86_64_sysv.c` currently:

- emits an HPy vectorcall-shaped trampoline
- unmarshals each Python arg through helper functions
- loads C args into SysV registers
- calls the target C symbol directly
- marshals the return through helper functions
- checks `PyErr_Occurred()` after helper calls
- does not support C stack arguments beyond six integer/pointer registers
- does not support semantic OUT/INOUT frame handling
- does not understand GI arrays or paired length arguments

The invoke code is organized so shared GI call semantics live under
`src/invoke/`, with engine-specific implementations under `src/invoke/ffi/`
and, later, `src/invoke/jit/`.

## Guiding Architecture

Split the system into three layers:

1. Generic GI call semantics
2. Invocation engines
3. Architecture-specific direct-call stubs

The JIT should not know how to convert a Python list into a `GArray`, shape OUT
params into a Python tuple, free transfer-full strings, build a libffi closure,
or raise a `GError`. Those are GI semantics and should live in shared C helpers.

The x86_64 JIT should know only:

- how to load ABI arguments into registers and stack slots
- how to call a target function pointer
- where to store the raw return value
- how to preserve stack alignment
- how to return to C helper code for finish/cleanup

The desired call pipeline is:

```text
MethodDescriptor.__call__
  -> generated HPy trampoline
    -> shared prepare helper
       - validate kwargs/arity
       - build per-call frame
       - marshal Python args to C storage
       - allocate OUT/INOUT/GError storage
    -> x86_64 direct-call stub
       - load ABI args from prepared frame
       - call target C function
       - store ABI return
    -> shared finish helper
       - check GError
       - shape return + OUT params
       - run cleanup
```

This is still a JIT: it bypasses `gi_function_info_invoke()` and libffi for the
target function call. It deliberately reuses C marshalling helpers around that
call.

## File Layout

Normalize generic code out of `ffi`-specific names.

Shared invoke files:

- `src/invoke/plan.c`
- `src/invoke/plan.h`
- `src/invoke/frame.c`
- `src/invoke/frame.h`
- `src/invoke/bind.c`
- `src/invoke/bind.h`
- `src/invoke/return.c`
- `src/invoke/return.h`
- `src/invoke/arg-cleanup.c`
- `src/invoke/arg-cleanup.h`

FFI-specific files:

- `src/invoke/ffi/invoke.c`
- `src/invoke/ffi/invoke.h`

JIT-specific files:

- `src/invoke/jit/invoke.c`
- `src/invoke/jit/invoke.h`
- `src/invoke/jit/plan.c`
- `src/invoke/jit/plan.h`
- `src/jit/arch/x86_64_sysv.c`

Keep existing generic marshalling modules where they are:

- `src/runtime/marshal.c`
- `src/runtime/c-array.c`
- `src/runtime/array.c`
- `src/runtime/glists.c`
- `src/runtime/ghashtable.c`
- `src/runtime/gvalue.c`
- `src/runtime/variant.c`
- `src/runtime/closure.c`
- `src/runtime/scalar.c`
- `src/runtime/string.c`
- `src/runtime/type-info.c`
- `src/runtime/object-info.c`
- `src/runtime/enum.c`

`src/meson.build` should list shared invoke sources before engine-specific
invoke sources.

## Shared Call Plan

The shared call plan interprets GI metadata once and records semantic facts.
Both FFI and JIT must consume the same plan.

Start from the existing `PygirInvokePlan`, `PygirArgPlan`, and
`PygirOutSlotPlan`, then rename to call-neutral names.

Suggested public structures:

```c
typedef enum {
  PYGIR_ARG_ROLE_NORMAL = 0,
  PYGIR_ARG_ROLE_CLOSURE_DESTROY,
  PYGIR_ARG_ROLE_ARRAY_LENGTH,
  PYGIR_ARG_ROLE_ERROR_POINTER,
} PygirArgRole;

typedef enum {
  PYGIR_LENGTH_NONE = 0,
  PYGIR_LENGTH_BEFORE_ARRAY,
  PYGIR_LENGTH_AFTER_ARRAY,
  PYGIR_LENGTH_FIXED,
  PYGIR_LENGTH_ZERO_TERMINATED,
} PygirLengthKind;

typedef struct {
  guint gi_index;
  GIDirection direction;
  GITransfer transfer;
  GITypeTag tag;
  GIArrayType array_type;

  PygirArgRole role;
  PygirLengthKind length_kind;

  bool consumes_py_arg;
  bool nullable_or_optional;
  bool caller_allocates;
  bool is_return_value;

  ssize_t py_arg_index;
  ssize_t in_slot;
  ssize_t out_slot;
  ssize_t length_arg;
  ssize_t owner_array_arg;
} PygirCallArgPlan;

typedef struct {
  guint gi_arg_index;
  bool visible;
  bool consumed_by_array;
  ssize_t paired_length_out_slot;
  ssize_t paired_length_in_slot;
  ssize_t paired_in_length_gi_arg;
} PygirCallOutSlotPlan;

typedef struct {
  GICallableInfo *callable;
  bool has_self;
  bool can_throw_gerror;

  size_t n_gi_args;
  size_t n_py_args;
  size_t n_in_args;
  size_t n_out_args;

  PygirCallArgPlan *args;
  PygirCallOutSlotPlan *out_slots;
} PygirCallPlan;
```

Plan responsibilities:

- classify each GI arg as IN, OUT, INOUT, array length, closure companion, or
  destroy companion
- record Python-visible arity
- record which args consume Python values
- record C-array length relationships
- record which OUT slots are visible in the Python return
- record which OUT length slots are consumed by array conversion
- record caller-allocated OUT buffers
- record whether the callable throws GError
- preserve enough metadata for both `gi_function_info_invoke()` and direct JIT
  ABI lowering

Plan non-responsibilities:

- do not inspect actual Python values
- do not allocate per-call buffers
- do not perform conversions
- do not decide x86_64 register assignment

## Shared Call Frame

The shared frame owns per-call mutable state and cleanup records. FFI and JIT
should use the same frame for marshalling and return shaping.

Suggested structure:

```c
typedef struct {
  GIArgument *in_args;
  GIArgument *out_args;
  GIArgument *out_values;
  GITypeInfo **out_tis;
  GITypeInfo **in_len_ti;
  size_t *in_len_slot;
  PygirArgCleanup *cleanups;

  GIArgument ret;
  GITypeInfo *ret_ti;

  GError *gerror;
  GError **gerror_ptr;

  size_t n_gi_args;
  size_t n_in_args;
  size_t n_out_args;
  size_t out_tis_count;
} PygirCallFrame;
```

Frame responsibilities:

- own all temporary C storage for one call
- own all `GITypeInfo` references used after the call
- own cleanup records for transfer-none temporaries and caller-allocated OUT
  buffers
- provide a single error cleanup path
- provide a single success cleanup path after return shaping

Frame API:

```c
int pygir_call_frame_init(PygirCallFrame *frame,
                          const PygirCallPlan *plan,
                          void *scratch,
                          size_t scratch_size);

HPy pygir_call_frame_fail(HPyContext *ctx, PygirCallFrame *frame);

void pygir_call_frame_clear(PygirCallFrame *frame);
```

The first implementation can keep `alloca()` in the caller, as the current FFI
path does. The important part is that cleanup ownership is centralized.

## Shared Binder

The binder converts Python arguments into the shared frame using the call plan.
It should be moved out of the FFI namespace and expanded until it covers all
types needed by the failed tests.

Entry point:

```c
int pygir_call_bind_args(HPyContext *ctx,
                         PygirMethodDescriptor *descriptor,
                         PygirCallFrame *frame,
                         const PygirCallPlan *plan,
                         const HPy *args,
                         size_t nargs);
```

Binder responsibilities:

- validate no kwargs, or leave kwargs validation in descriptor call code
- validate positional arity
- unwrap implicit `self`
- bind hidden closure/destroy companion args
- bind derived array length placeholders
- allocate pure OUT storage
- allocate and initialize INOUT storage
- bind caller-allocated OUT buffers
- bind C arrays and write paired lengths
- bind GArray/GPtrArray/GByteArray
- bind GList/GSList/GHashTable
- bind GValue, GVariant, GBytes, GType, ParamSpec
- bind callbacks and closures by reusing `src/runtime/closure.c`
- bind GError pointer storage for throwing callables
- register all cleanup records with the frame

Prefer reusing these existing functions instead of adding JIT-specific
conversion helpers:

- `pygir_argument_from_py_for_call`
- `pygir_argument_from_py`
- `pygir_hpy_to_c_array_invoke`
- `pygir_garray_from_py`
- `pygir_glist_from_py` and `pygir_gslist_from_py` if available, or add them in
  `glists.c`
- `pygir_ghash_from_py` if available, or add it in `ghashtable.c`
- `pygir_variant_from_py`
- `pygir_object_info_from_py`
- `pygir_enum_info_from_py`
- `pygir_flags_info_from_py`
- callback closure helpers from `closure.c`

If a useful helper is currently `static`, make it public through the local
runtime header instead of duplicating code.

## Shared Return Shaper

The return shaper converts the raw return plus OUT slots into Python values. It
should be shared unchanged by FFI and JIT.

Entry point:

```c
HPy pygir_call_shape_return(HPyContext *ctx,
                            const PygirCallPlan *plan,
                            PygirCallFrame *frame);
```

Return shaping responsibilities:

- if there are no OUT args, return the raw return value
- if return is void and one visible OUT arg exists, return that OUT arg
- if return is void and multiple visible OUT args exist, return a tuple
- if return is non-void plus visible OUT args, return `(ret, *outs)`
- fold array length OUT slots into array conversion and hide them from tuple
- use IN-side length placeholders for OUT arrays where required
- for GError-throwing gboolean functions, return meaningful OUT params rather
  than the boolean success marker
- preserve current alias-sensitive cleanup ordering

Return conversion should continue to use:

- `pygir_argument_to_py`
- `pygir_c_array_to_py`
- `pygir_garray_to_py`
- `pygir_glist_to_py`
- `pygir_gslist_to_py`
- `pygir_ghash_to_py`
- `pygir_variant_to_py`
- GValue and boxed wrapper helpers

## FFI Engine After Refactor

The FFI path becomes a thin engine:

```c
HPy
pygir_method_descriptor_call_ffi_invoke(...)
{
  build shared plan;
  init shared frame;
  bind args into frame;

  gboolean ok = gi_function_info_invoke(info,
                                        frame.in_args,
                                        plan.n_in_args,
                                        frame.out_args,
                                        plan.n_out_args,
                                        &frame.ret,
                                        &error);

  if (!ok)
    fail;

  return shape_return_and_clear();
}
```

This preserves the known-correct fallback while giving JIT the same semantic
frame.

## JIT Descriptor Model

Replace the current `PygirSignature`-only descriptor-time decision with two
steps:

1. Build `PygirCallPlan`.
2. Build `PygirJitPlan` from `PygirCallPlan`.

`PygirJitPlan` is the ABI-lowered view of a callable.

Suggested structures:

```c
typedef enum {
  PYGIR_ABI_VOID = 0,
  PYGIR_ABI_I8,
  PYGIR_ABI_U8,
  PYGIR_ABI_I16,
  PYGIR_ABI_U16,
  PYGIR_ABI_I32,
  PYGIR_ABI_U32,
  PYGIR_ABI_I64,
  PYGIR_ABI_U64,
  PYGIR_ABI_POINTER,
  PYGIR_ABI_FLOAT,
  PYGIR_ABI_DOUBLE,
} PygirAbiKind;

typedef enum {
  PYGIR_JIT_ARG_FROM_IN_ARG,
  PYGIR_JIT_ARG_FROM_OUT_ARG,
  PYGIR_JIT_ARG_FROM_ERROR_PTR,
} PygirJitArgSource;

typedef struct {
  PygirAbiKind kind;
  PygirJitArgSource source;
  ssize_t source_slot;
  guint gi_arg_index;
} PygirJitAbiArg;

typedef struct {
  PygirAbiKind ret_kind;
  size_t n_abi_args;
  PygirJitAbiArg abi_args[64];

  bool can_throw_gerror;
  bool has_struct_return;
  bool unsupported;
  char unsupported_reason[160];
} PygirJitPlan;
```

JIT plan responsibilities:

- lower the shared plan to target C ABI argument order
- choose ABI kind for each argument
- record where each argument value lives in the prepared frame
- include hidden `GError **` as the final ABI arg when needed
- reject unsupported direct-call shapes with precise reasons

JIT plan non-responsibilities:

- do not marshal Python values
- do not allocate storage
- do not shape Python returns
- do not assign x86_64 registers directly

## Direct JIT Call Helpers

The generated trampoline should call C helpers before and after the target:

```c
typedef struct {
  PygirCallPlan call_plan;
  PygirJitPlan jit_plan;
  GICallableInfo *callable;
  void *target_fn;
  const char *qualified_name;
} PygirCompiledCallable;

int pygir_jit_prepare_call(HPyContext *ctx,
                           PygirCompiledCallable *compiled,
                           HPy callable,
                           const HPy *args,
                           size_t nargs,
                           HPy kwnames,
                           PygirCallFrame *frame);

HPy pygir_jit_finish_call(HPyContext *ctx,
                          PygirCompiledCallable *compiled,
                          PygirCallFrame *frame);
```

The generated HPy trampoline should store a pointer to `PygirCompiledCallable`
in its table. The flow is:

```text
trampoline(ctx, self, args, nargs, kwnames)
  frame = stack or helper-allocated call frame
  if prepare_call(...) != 0:
    return HPy_NULL
  x86_64_call_target(compiled, frame)
  return finish_call(...)
```

For frame allocation, choose one of:

1. JIT stack frame reserves enough memory and passes it to prepare.
2. `pygir_jit_prepare_call()` heap-allocates a frame arena and finish/fail frees
   it.

Recommendation: start with heap allocation for correctness and simplicity, then
optimize to stack/scratch arena once coverage is good. The target call bypasses
libffi, so this remains a meaningful JIT even with C helper calls.

## x86_64 SysV Backend

The backend should expose a new emitter for full JIT calls:

```c
PygirJittedTrampoline
pygir_jit_emit_full_x86_64(void *target_fn,
                           const PygirCompiledCallable *compiled,
                           const char *name);
```

It can coexist with the current simple emitter during migration.

Backend responsibilities:

- emit vectorcall-compatible HPy trampoline
- call `pygir_jit_prepare_call`
- on prepare failure, return `HPy_NULL`
- load ABI args from `PygirCallFrame`
- call target function pointer
- store return value into `frame->ret`
- call `pygir_jit_finish_call`
- return the HPy result

System V AMD64 rules to implement:

- integer and pointer args use `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`
- float/double args use `xmm0` to `xmm7`
- stack args are placed right-to-left in the overflow area
- stack must be 16-byte aligned at call sites
- integer returns are in `rax`
- float/double returns are in `xmm0`
- pointer returns are in `rax`
- void returns store nothing
- narrow integer returns must be sign- or zero-extended before storing

Initial unsupported ABI shapes:

- by-value structs/unions
- non-trivial SysV aggregate classification
- long double
- varargs
- callbacks that require C to call Python after the outer call has returned,
  unless lifetime is fully handled

These can keep using FFI in `auto` mode and should raise clear
`NotImplementedError` in `jit-only`.

## Loading ABI Arguments From Frame

Each `PygirJitAbiArg` source maps to a `GIArgument` location:

- `FROM_IN_ARG`: `frame->in_args[source_slot]`
- `FROM_OUT_ARG`: `frame->out_args[source_slot]` or the actual pointer stored
  in `frame->out_args[source_slot].v_pointer`
- `FROM_ERROR_PTR`: `frame->gerror_ptr`

The backend should not interpret GI tags. It should interpret only
`PygirAbiKind`.

Recommended storage model:

- scalar IN values live directly in `frame->in_args[slot]`
- pointer IN values live in `frame->in_args[slot].v_pointer`
- OUT/INOUT ABI args are pointer values from `frame->out_args[slot].v_pointer`
- return storage is `frame->ret`

For each ABI kind:

- `I8`, `U8`, `I16`, `U16`, `I32`, `U32`: load 32-bit register value with
  correct extension
- `I64`, `U64`, `POINTER`: load 64-bit GP register value
- `FLOAT`: load single-precision value into next XMM arg register
- `DOUBLE`: load double-precision value into next XMM arg register

## GError Support

For `gi_callable_info_can_throw_gerror(cb)`:

- shared plan records `can_throw_gerror = true`
- frame owns `GError *gerror = NULL`
- frame exposes `GError **gerror_ptr = &frame->gerror`
- JIT plan appends one hidden ABI pointer arg
- direct call receives `GError **` in normal ABI order
- finish helper checks `frame->gerror`
- if non-NULL, raise a Python exception and cleanup
- for gboolean success markers, preserve existing return shaping behavior

This removes the current blanket rejection of throwing callables.

## OUT and INOUT Support

OUT and INOUT should be implemented in shared binder/frame code, not in assembly.

Pure OUT:

- allocate storage according to `GITypeInfo`
- place pointer in ABI args
- convert filled storage after call

INOUT:

- convert Python input into storage
- pass pointer to storage
- convert final storage after call

Caller-allocated OUT:

- allocate a correctly sized buffer
- pass the buffer pointer
- register cleanup
- convert after call

The first milestone should cover scalar OUT/INOUT:

- boolean
- int8/uint8
- int16/uint16
- int32/uint32
- int64/uint64
- float/double
- GType
- UTF-8 / filename pointers

This should clear many `*_out`, `*_inout`, and `*_out_uninitialized` tests.

## Arrays And Containers

Arrays are the largest failure cluster. Reuse existing runtime conversions.

C arrays:

- IN: Python sequence to allocated C buffer
- OUT: allocate pointer storage or caller-allocated fixed buffer
- INOUT: convert to mutable storage and pass pointer
- return: convert pointer plus length metadata
- fixed-size: use fixed length metadata
- zero-terminated: count until NULL or terminator
- length-before and length-after: use plan pairing

GArray/GPtrArray/GByteArray:

- use `pygir_garray_from_py` and `pygir_garray_to_py`
- preserve transfer rules
- support UTF-8 element arrays early
- support primitive element arrays early

GList/GSList:

- implement or expose list conversion helpers in `glists.c`
- start with int, uint32, UTF-8, and boxed pointer cases from tests

GHashTable:

- implement or expose hash conversion helpers in `ghashtable.c`
- start with primitive and UTF-8 keys/values used in tests

GStrv:

- treat as zero-terminated C array of UTF-8 strings
- reuse existing string-vector helpers where possible

## Interfaces And Boxed Values

Use `GITypeInfo` and interface metadata to select runtime conversions:

- enum/flags: scalar int32 ABI
- GObject/interface wrappers: pointer ABI
- GValue: pointer ABI, conversion via `gvalue.c`
- GVariant: pointer ABI, conversion via `variant.c`
- GBytes: pointer ABI
- GType: unsigned integer ABI, probably `gsize`/`guintptr`
- ParamSpec: pointer ABI
- structs/unions by pointer: pointer ABI
- structs/unions by value: initially unsupported in JIT

If the FFI path currently accepts a boxed/interface case via a static helper,
make that helper shared before adding JIT support.

## Callbacks And Closures

Callback args are GI interface callback infos. JIT should not generate callback
closures itself. The binder should reuse `src/runtime/closure.c`.

Binder behavior:

- `None` maps to NULL callback where nullable
- Python callable maps to a libffi closure/trampoline
- closure/destroy companion slots are filled from plan metadata
- cleanup owns closure lifetime correctly

Start with synchronous callback tests. Async callbacks and callbacks retained
after return require stricter lifetime ownership and should be a separate
milestone.

## Descriptor Ownership And Caching

`PygirMethodDescriptor` currently stores:

- `qualified_name`
- `info`
- `has_self`
- `call_kind`
- `trampoline`

Full JIT needs a compiled callable object with metadata and ownership:

```c
typedef struct {
  GICallableInfo *info;
  char *qualified_name;
  void *target_fn;
  PygirCallPlan call_plan;
  PygirJitPlan jit_plan;
  PygirJittedTrampoline trampoline;
} PygirCompiledCallable;
```

Add a pointer to `PygirMethodDescriptor`, or embed it if lifetime is simple:

```c
PygirCompiledCallable *compiled;
```

Descriptor destroy must:

- unref/cancel compiled call plan metadata
- free allocated plan arrays
- free qualified name copies
- leave executable code lifetime policy as-is initially if current JIT leaks code
  pages process-wide

Avoid per-call rebuilding of `PygirCallPlan`.

## Unsupported Shape Reporting

Keep `jit-only` diagnostics precise. Replace the current broad reasons with
lowering-stage reasons:

- metadata unsupported by shared call plan
- marshalling unsupported by shared binder
- direct ABI unsupported by JIT lowering
- x86_64 backend unsupported, for example by-value aggregate or varargs

Examples:

```text
GIMarshallingTests.foo: JIT-only mode - unsupported direct ABI shape:
by-value struct return; shape: interface()
```

```text
Regress.test_torture_signature_2: JIT-only mode - unsupported direct ABI shape:
varargs; shape: ...
```

## Migration Strategy

Do this incrementally. Keep FFI tests passing after each step.

### Phase 0: Normalize The Current Refactor

Tasks:

- decide whether invoke refactor files live under `src/ffi` or `src/runtime`
- update includes and `src/meson.build` accordingly
- make the project build again
- run a small FFI subset

Recommended end state:

- generic plan/frame/bind/return/cleanup files are under `src/invoke/`
- FFI engine is under `src/invoke/ffi/invoke.*`
- JIT engine work lands under `src/invoke/jit/`

Verification:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py::test_int_in -q -n 0
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_regress.py::test_utf8_const_return -q -n 0
```

### Phase 1: Shared Plan And Frame

Tasks:

- rename `PygirInvokePlan` to `PygirCallPlan`
- rename `PygirInvokeFrame` to `PygirCallFrame`
- move generic headers to runtime
- keep FFI invoke using the shared API
- add call-plan initialization/destruction helpers

Verification:

- run representative FFI tests for arrays, OUT, INOUT, GValue, GError

### Phase 2: Full JIT Skeleton

Tasks:

- add `PygirCompiledCallable`
- add descriptor storage for compiled callable
- add `pygir_jit_prepare_call`
- add `pygir_jit_finish_call`
- emit a new trampoline path that calls prepare, target, finish
- support only existing primitive scalar shapes at first

Verification:

- existing passing `jit-only` primitive tests still pass
- perf map names still work
- `auto` mode still chooses JIT where supported

### Phase 3: x86_64 Stack Arguments

Tasks:

- add overflow stack arg support after GP/XMM register exhaustion
- preserve 16-byte stack alignment
- add tests for 7+ arguments

Verification:

- targeted `test_torture_signature_*` progress, except varargs/GError until
  their phases

### Phase 4: Scalar OUT/INOUT

Tasks:

- lower OUT/INOUT pointers in `PygirJitPlan`
- use shared binder to allocate scalar storage
- store return then shape OUT params
- handle uninitialized boolean-return tests

Expected tests:

- `boolean_out_*`
- `int*_out_*`
- `uint*_out_*`
- `float_out_*`
- `double_out_*`
- `*_inout_*`
- `utf8_*_out`

### Phase 5: GError

Tasks:

- append hidden `GError **`
- finish helper raises Python exception
- handle gboolean success marker semantics

Expected tests:

- `test_gerror`
- `test_gerror_out`
- `test_gerror_return`
- `test_function_finish`
- `test_torture_signature_1`

### Phase 6: C Arrays And GStrv

Tasks:

- support C array IN/OUT/INOUT/return through shared binder and return shaper
- support fixed-size arrays
- support zero-terminated arrays
- support length-before and length-after metadata
- support string-vector transfer none/container/full

Expected tests:

- `array_*`
- `fixed_array_*`
- `zero_terminated_array_*`
- `gstrv_*`
- `length_array_*`
- regress `test_array_*`

### Phase 7: GArray/GPtrArray/GByteArray

Tasks:

- expose missing helpers from `array.c`
- support primitive and UTF-8 element arrays
- support transfer none/container/full

Expected tests:

- `garray_*`
- `gptrarray_*`
- `bytearray_*`

### Phase 8: Lists And Hash Tables

Tasks:

- expose or implement GLib list conversion helpers
- expose or implement hash table conversion helpers
- support primitive, UTF-8, enum/flags, boxed pointer cases

Expected tests:

- `glist_*`
- `gslist_*`
- `ghashtable_*`
- regress `test_glist_*`, `test_gslist_*`, `test_ghash_*`

### Phase 9: Interface Pointer Types

Tasks:

- support GValue, GVariant, GBytes, ParamSpec, GType
- support boxed/struct/union by pointer
- keep by-value aggregate unsupported

Expected tests:

- `gvalue_*`
- `gbytes_*`
- `get_variant`
- `test_gvariant_*`
- `param_spec_*`
- `boxed_struct_*` pointer cases

### Phase 10: Callbacks And Closures

Tasks:

- reuse `closure.c` for Python callable to C callback conversion
- wire closure and destroy companion args from plan
- add lifetime cleanup rules
- split sync callbacks from async/retained callbacks

Expected tests:

- `callback_*`
- `test_callback_*`
- `test_closure*`
- `dir_foreach`

## Testing Strategy

Use focused tests at each phase. Do not wait for the full marshalling suite.

Recommended command pattern:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -k 'jit-only and int_out' -q -n 0
```

Then broaden by cluster:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -k 'jit-only and out' -q -n 0
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -k 'jit-only and array' -q -n 0
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_regress.py -k 'jit-only and array' -q -n 0
```

Keep these invariants:

- FFI mode remains the correctness oracle.
- Auto mode must never regress because an unsupported JIT shape should fall
  back to FFI.
- JIT-only mode should raise `NotImplementedError` only for explicitly
  unsupported shapes, not for shapes already supported by the shared binder and
  x86_64 lowering.

## Debugging And Observability

Add temporary or permanent diagnostics:

- `PYGIR_JIT_TRACE=1` prints plan lowering decisions
- `PYGIR_JIT_DUMP=1` dumps ABI arg layout and target symbol
- perf map naming should include qualified callable name
- unsupported reasons should include GI shape and lowering stage

Useful debug output:

```text
JIT lower GIMarshallingTests.int_out_max:
  ret: void
  abi args:
    0 OUT slot 0 pointer -> rdi
  finish: visible OUT slots [0]
```

## Risk Areas

Stack alignment:

- SysV requires 16-byte stack alignment at call boundaries.
- Helper calls and target calls both need correct alignment.

GIL/Python execution:

- Current JIT helpers call Python C API, so they run with the GIL held.
- If target calls are wrapped with `HPy_LeavePythonExecution`, ensure callbacks
  into Python reacquire correctly.
- Start without releasing the GIL for correctness, then consider release in a
  later optimization.

Transfer semantics:

- Transfer-full IN strings and arrays must allocate memory the callee may free.
- Transfer-none temporaries must be cleaned up after return shaping.
- OUT returns may need freeing after conversion depending on GI transfer.

Alias-sensitive cleanup:

- Keep current rule: convert return and OUT values before clearing IN cleanups.
- This matters for cases where return aliases an input value.

By-value structs:

- SysV aggregate classification is complex.
- Keep unsupported until pointer/boxed cases pass.

Callbacks:

- Synchronous callbacks are manageable.
- Async or retained callbacks need explicit lifetime ownership beyond the outer
  call frame.

## Non-Goals For This Pass

- aarch64 backend parity
- i386 backend parity
- Windows ABI support
- by-value aggregate ABI support
- varargs
- optimizing away all helper calls
- replacing libffi closures for Python callbacks
- implementing a general-purpose machine-code marshaller

## Definition Of Done

This plan is complete when:

- generic call planning, binding, frame cleanup, and return shaping are shared
  by FFI and JIT
- JIT directly calls target C functions on Linux x86_64 for supported shapes
- `jit-only` passes scalar OUT/INOUT, GError, array, GArray/GPtrArray/GByteArray,
  list/hash, GValue/GVariant, and synchronous callback test clusters
- unsupported `jit-only` failures are limited to documented non-goals with clear
  diagnostics
- `auto` and `ffi` modes still pass the existing suite
