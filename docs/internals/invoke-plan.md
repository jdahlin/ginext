# Invoke Refactor Plan

This document is an implementation plan for refactoring `src/runtime/invoke.c`.
The goal is not to split the current tangled control flow into more files. The
goal is to replace the accidental order with explicit invocation phases and
small data contracts.

## Current Problem

`pygir_method_descriptor_call_invoke()` currently owns too much:

- keyword/self validation
- stack allocation of all call state
- callable pre-scan flags
- Python argument index management
- GI in/out slot index management
- hidden closure/destroy argument handling
- IN length placeholders
- OUT and INOUT storage allocation
- caller-allocated OUT buffers
- C-array length pairing in several orders
- GArray/GList/GSList/GHash/GValue/GVariant/callback special cases
- transfer-full string duplication
- `gi_function_info_invoke()`
- return shaping
- cleanup and error cleanup

This makes every new marshaling edge case interact with every other edge case.
The repeated `pygir_in_cleanups_clear()` plus `out_tis` unref blocks are a
symptom: there is no single per-call owner for invocation state.

## Target Shape

The invoke path should be phased like this:

```text
GICallableInfo
  -> descriptor-time callable plan
  -> call-time invoke frame
  -> bind Python args into GIArgument arrays
  -> gi_function_info_invoke()
  -> shape return from planned outputs
  -> cleanup frame
```

The important split is static versus dynamic:

- Static descriptor-time work interprets GI metadata once.
- Dynamic call-time work consumes actual Python arguments and owns temporary
  allocations for one call.

`invoke.c` should become orchestration. It should not rediscover array length
relationships, scan previous OUT slots, or directly dispatch every container
type inline.

## Proposed Files

Keep the public entrypoint in `src/runtime/invoke.c`.

Add or evolve these modules:

- `src/runtime/invoke-plan.c`: descriptor-time callable analysis.
- `src/runtime/invoke-frame.c`: per-call state, allocation, cleanup, error cleanup.
- `src/runtime/invoke-bind.c`: bind Python arguments into a frame using a plan.
- `src/runtime/invoke-return.c`: shape return values using planned output metadata.

Headers:

- `src/runtime/invoke-plan.h`: public plan structures used by descriptor/build and invoke.
- `src/runtime/invoke-frame.h`: frame state helpers.
- `src/runtime/invoke-bind.h`: binder entrypoint.
- `src/runtime/invoke-return.h`: return shaper API.

Do not expose these outside `runtime` unless necessary.

## Phase Ownership

### 1. Callable Plan

The plan owns interpretation of GI metadata. It must not look at Python values
or allocate per-call buffers.

It should answer:

- How many Python positional arguments are visible?
- Does the callable have an implicit `self`?
- Which GI args consume Python values?
- Which GI args are hidden closure/destroy companion slots?
- Which args are IN, OUT, or INOUT?
- Which args are C-array lengths?
- Which array owns each length argument?
- Which length args appear before versus after their array?
- Which OUT slots exist and which GI arg each OUT slot belongs to?
- Which OUT slots are consumed by array-length pairing and should not appear in
  the returned tuple?
- Which shapes are unsupported before call-time binding starts?

Suggested structures:

```c
typedef enum {
  PYGIR_ARG_ROLE_NORMAL,
  PYGIR_ARG_ROLE_SELF,
  PYGIR_ARG_ROLE_CLOSURE_DESTROY,
  PYGIR_ARG_ROLE_ARRAY_LENGTH,
} PygirArgRole;

typedef enum {
  PYGIR_LENGTH_NONE,
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

  PygirArgRole role;
  bool consumes_py_arg;
  bool nullable_or_optional;
  bool caller_allocates;

  ssize_t py_arg_index;      /* -1 for hidden/derived args */
  ssize_t in_slot;           /* -1 if not passed in in_args */
  ssize_t out_slot;          /* -1 if no out_args/out_values slot */

  ssize_t length_arg;        /* array -> length arg, -1 if none */
  ssize_t owner_array_arg;   /* length -> array arg, -1 if none */
  PygirLengthKind length_kind;
} PygirArgPlan;

typedef struct {
  guint gi_arg_index;
  bool visible;
  bool consumed_by_array;
  ssize_t paired_length_out_slot;
  ssize_t paired_length_in_slot;
} PygirOutSlotPlan;

typedef enum {
  PYGIR_RETURN_VALUE_ONLY,
  PYGIR_RETURN_OUT_ONLY,
  PYGIR_RETURN_TUPLE_RETURN_PLUS_OUT,
  PYGIR_RETURN_ARRAY_WITH_OUT_LENGTH,
  PYGIR_RETURN_BOOLEAN_STATUS,
} PygirReturnPolicy;

typedef struct {
  GICallableInfo *callable; /* borrowed from descriptor */
  bool has_self;
  size_t n_gi_args;
  size_t n_py_args;
  size_t n_in_args;
  size_t n_out_args;

  PygirArgPlan *args;
  PygirOutSlotPlan *out_slots;
  PygirReturnPolicy return_policy;
} PygirInvokePlan;
```

The final implementation can keep arrays stack-allocated if that is simpler,
but the logical contract should look like the above.

Important: the current `PygirInvokePlan` flag arrays are not enough. Replace
them or add a second-generation plan type rather than extending ad-hoc flags.

### 2. Invoke Frame

The frame owns all per-call mutable state and all temporary allocations.

Suggested structure:

```c
typedef struct {
  GIArgument *in_args;
  GIArgument *out_args;
  GIArgument *out_values;
  GITypeInfo **out_tis;
  GITypeInfo **in_len_tis;
  PygirCallCleanup *cleanups;

  size_t in_index;
  size_t out_index;
  size_t py_index;
  size_t n_gi_args;
  size_t n_in_args;
  size_t n_out_args;
} PygirInvokeFrame;
```

Rename `PygirInCleanup` to `PygirCallCleanup` if feasible. The current name is
misleading because the cleanup records already own caller-allocated OUT buffers.
If the rename is too noisy for the first patch, add the new abstraction first
and rename later.

Frame API:

```c
int pygir_invoke_frame_init(PygirInvokeFrame *frame, const PygirInvokePlan *plan);
void pygir_invoke_frame_clear(PygirInvokeFrame *frame);
HPy pygir_invoke_frame_fail(HPyContext *ctx, PygirInvokeFrame *frame);
void pygir_invoke_frame_unref_type_infos(PygirInvokeFrame *frame);
```

The exact allocation mechanism can remain `alloca` inside the entrypoint for
now. The key is that all cleanup runs through one function.

Rules:

- All error exits after frame init go through one cleanup path.
- Return conversion happens before call cleanup, preserving current alias safety
  for cases like `gvalue_round_trip`.
- `out_tis` refs are released exactly once.
- `in_len_tis` refs are released exactly once.

### 3. Binder

The binder owns call-time conversion from Python arguments to `GIArgument`
arrays. It walks `PygirArgPlan[]`, not raw GI metadata.

Entry point:

```c
int pygir_invoke_bind_args(HPyContext *ctx,
                           const PygirInvokePlan *plan,
                           PygirInvokeFrame *frame,
                           PygirMethodDescriptor *descriptor,
                           const HPy *args,
                           size_t nargs);
```

Responsibilities:

- validate exact positional arity from the plan
- unwrap and bind `self`
- bind hidden closure/destroy companion slots
- bind derived length placeholders
- allocate OUT storage
- allocate caller-allocated OUT buffers
- bind INOUT initial values
- bind IN values
- fill array length slots from array conversions
- register cleanup records with the frame

The binder should be split internally into small helpers:

```c
static int bind_self(...);
static int bind_hidden_arg(...);
static int bind_out_storage(...);
static int bind_caller_allocated_out(...);
static int bind_inout_arg(...);
static int bind_in_arg(...);
static int bind_array_arg(...);
static int bind_collection_arg(...);
static int duplicate_transfer_full_string(...);
```

Do not preserve the current “walk raw GI args and discover special cases inline”
style. The plan should decide what kind of binding is needed; the binder should
execute that decision.

### 4. Type-Specific Call Marshalling

The current invoke loop directly knows too much about:

- C arrays
- GArray/GPtrArray/GByteArray
- GList/GSList
- GHashTable
- GValue
- GVariant
- callback closures
- scalar fallback conversion

Keep leaf conversion code in existing modules, but add a higher-level call
marshaller that selects the correct leaf helper for IN and INOUT.

Possible API:

```c
int pygir_argument_from_py_for_call(HPyContext *ctx,
                                    HPy value,
                                    GIArgInfo *arg_info,
                                    GITypeInfo *type_info,
                                    GITransfer transfer,
                                    GIArgument *out,
                                    PygirCallCleanup *cleanup);
```

This helper should live outside `invoke.c`; either in `marshal.c` if it stays
small, or a new `call-marshal.c` if it becomes substantial.

It should reuse:

- `pygir_argument_from_py`
- `pygir_hpy_to_c_array_invoke`
- `pygir_garray_from_py`
- `pygir_glist_from_py`
- `pygir_slist_from_py`
- `pygir_ghash_from_py`
- `pygir_gvalue_from_py`
- `pygir_py_item_to_gvariant`
- `pygir_callback_from_py`

`invoke.c` should not contain a long `if (tag == ...)` ladder after this phase.

### 5. Return Shaping

`invoke-return.c` already exists and should remain, but it currently rebuilds
OUT-slot-to-GI-arg mappings by scanning the callable again.

Change it to consume `PygirInvokePlan` and `PygirInvokeFrame`:

```c
HPy pygir_invoke_shape_return(HPyContext *ctx,
                              const PygirInvokePlan *plan,
                              PygirInvokeFrame *frame,
                              GITypeInfo *ret_ti,
                              GIArgument *ret);
```

Responsibilities:

- convert return value
- convert visible OUT values
- fold C-array length OUT slots into their owner array
- fold return-array length OUT slot into the return value
- apply gboolean/GError return policy
- build tuple results

It should not:

- rescan `GICallableInfo` to rebuild out-slot mapping
- decide which OUT slot is visible
- decide which OUT slot is a length consumed by an array

That belongs in the plan.

## Implementation Sequence

### Step 1: Centralize Cleanup Without Behavior Change

Add `PygirInvokeFrame` around the existing arrays and indexes.

Expected result:

- `pygir_method_descriptor_call_invoke()` still contains most binding logic.
- All repeated error cleanup blocks become one `return fail(...)`.
- No behavior changes intended.

Tests:

```sh
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_regress.py -q -n 0
```

If full files are too slow, run targeted groups first:

```sh
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0 -k "array or inout or gvalue or ghash or glist or gslist or closure"
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_regress.py -q -n 0 -k "array or closure or gvalue or ghash"
```

### Step 2: Extract Binder Helpers Without Changing the Plan

Move code from the main loop into helper functions while still using the
current flag-based `PygirInvokePlan`.

Expected result:

- `invoke.c` becomes readable orchestration.
- `invoke-bind.c` owns most of the current loop.
- The current behavior is preserved exactly.

Do not change array pairing semantics in this step.

### Step 3: Introduce Real Arg/Out Slot Plan

Replace the flag-only planner with explicit `PygirArgPlan[]` and
`PygirOutSlotPlan[]`.

Expected result:

- No more `skip[]` mutation in the binder.
- No more repeated scans to map GI arg index to OUT slot.
- No more recomputing visible Python indexes by counting previous GI args.
- The binder gets `py_arg_index`, `in_slot`, `out_slot`, and length ownership
  directly from the plan.

This is the highest-risk step. Keep it isolated.

### Step 4: Move C-Array Pairing Decisions Out of Binder Branches

Use the plan to represent:

- length before array
- length after array
- fixed-size array
- zero-terminated array
- no length metadata
- INOUT length before owner array
- INOUT length after owner array
- OUT array whose length is an IN arg
- OUT array whose length is an OUT arg
- return array whose length is an OUT arg

Expected result:

- `bind_array_arg()` handles a small set of planned length modes.
- `invoke-return.c` folds length slots using `PygirOutSlotPlan`.

### Step 5: Add High-Level Call Marshalling Helper

Add `pygir_argument_from_py_for_call()` or equivalent.

Expected result:

- `invoke-bind.c` stops directly switching over every container type.
- Existing leaf helpers remain in their current files.
- `marshal.c` remains the common scalar/interface conversion layer.

### Step 6: Rename and Tighten Cleanup

Rename `PygirInCleanup` to `PygirCallCleanup` if not done earlier.

Also fix or explicitly document current ownership compromises:

- transfer-full string duplication should have cleanup before successful invoke
  if a later bind step fails
- async/notified callback closure lifetime currently leaks
- nested array ownership comments should move near the relevant leaf marshaller

Do not mix these fixes into the structural refactor unless a failing test forces
it. Keep semantic fixes reviewable.

## Desired End State for `invoke.c`

The final `pygir_method_descriptor_call_invoke()` should look roughly like:

```c
HPy
pygir_method_descriptor_call_invoke(...)
{
  reject_keywords();

  const PygirInvokePlan *plan = descriptor->invoke_plan;
  PygirInvokeFrame frame;
  if (pygir_invoke_frame_init(&frame, plan) != 0)
    return HPy_NULL;

  if (pygir_invoke_bind_args(ctx, plan, &frame, descriptor, args, nargs) != 0)
    return pygir_invoke_frame_fail(ctx, &frame);

  GIArgument ret = { 0 };
  if (!pygir_invoke_c(ctx, descriptor, plan, &frame, &ret))
    return pygir_invoke_frame_fail(ctx, &frame);

  HPy out = pygir_invoke_shape_return(ctx, plan, &frame, ret_ti, &ret);
  pygir_invoke_frame_clear(&frame);
  return out;
}
```

The exact names can differ. The shape should not.

## Guardrails

- Do not change behavior while moving code unless the patch explicitly says so.
- Do not combine structural refactors with ownership/lifetime bug fixes.
- Do not let `invoke-return.c` rediscover mappings already known by the plan.
- Do not let `invoke.c` grow a new type-dispatch ladder.
- Do not make every helper depend on `PygirMethodDescriptor`; pass the narrowest
  data needed.
- Keep leaf marshalling modules reusable by JIT or future call paths.
- Preserve return-before-cleanup ordering for alias-sensitive cases.
- Keep tests running in `ffi` mode; `jit-only` failures are not enough to prove
  the fallback path.

## Useful Test Areas

The risky areas are not generic scalar calls. Focus on:

- C arrays with length before array
- C arrays with length after array
- fixed-size C arrays
- zero-terminated arrays
- INOUT arrays
- OUT arrays with OUT length
- return arrays with OUT length
- caller-allocated OUT structs
- caller-allocated OUT arrays
- GArray/GPtrArray/GByteArray IN/OUT/INOUT
- GList/GSList IN/OUT/INOUT
- GHashTable IN/OUT
- GValue IN/OUT/INOUT/return
- GVariant arrays
- callback closure args
- transfer-full UTF8/FILENAME IN and INOUT

Suggested targeted commands:

```sh
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0 -k "array"
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0 -k "inout"
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0 -k "gvalue"
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0 -k "garray or gptrarray or bytearray"
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gi_marshalling_tests.py -q -n 0 -k "glist or gslist or ghash"
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_regress.py -q -n 0 -k "array or closure or gvalue or ghash"
```

Then run the broader suite:

```sh
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q -n 0
```

## Review Checklist

Before considering the refactor done:

- `invoke.c` is orchestration, not a second marshalling layer.
- Planner output is sufficient for binder and return shaper.
- There is one cleanup path for call-frame resources.
- OUT slot visibility is represented in data, not recomputed.
- Array length ownership is represented in data, not inferred in multiple places.
- Existing leaf converters are reused rather than duplicated.
- FFI tests cover every refactored path.
