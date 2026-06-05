# Invoke And Marshaller Architecture Analysis

This note maps the current invoke and marshalling implementation so later
cleanup work can preserve conceptual integrity. It focuses on the ginext
runtime under `src/ginext/private`.

## Scope

There is one supported ginext invocation surface: Python namespace lookup
builds a callable descriptor, the descriptor owns a precomputed invoke plan,
and invocation uses libffi.

This descriptor path is the behavior users hit through `from ginext import
GLib`, method calls, constructors, and overlay helpers. The older
`namespace.c` phase-1 invoke API has been retired; `PyGIInvokePlan` now refers
only to the canonical plan type in `src/ginext/private/invoke/plan.h`.

## Primary Call Flow

Normal top-level function call:

1. `Namespace.__getattr__()` in `src/ginext/namespace.py` asks
   `private.namespace_find()` for a GI info capsule.
2. If the info kind is `function`, `Function.__init__()` in
   `src/ginext/method.py` calls
   `private.build_callable_descriptor(info, qualified_name, False)`.
3. `py_build_callable_descriptor()` in
   `src/ginext/private/callable_descriptor.c` creates a
   `PyGIMethodDescriptor` capsule.
4. `compile_callable_for_ffi()` resolves the C symbol, builds the invoke plan,
   validates the supported shape, prepares libffi argument metadata, and caches
   arg names.
5. `Function.__call__()` calls
   `private.invoke_callable_descriptor(self._descriptor, args, kwargs)`.
6. `py_invoke_callable_descriptor()` resolves positional and keyword arguments
   into a flat call argument array.
7. `pygi_method_descriptor_call_ffi_invoke()` in
   `src/ginext/private/invoke/ffi/invoke.c` allocates per-call storage,
   selects the cached plan, binds Python arguments into C arguments, performs
   the libffi call, shapes the return value, and clears per-call resources.

Normal method call is the same after class construction, except
`make_method()` in `src/ginext/method.py` builds the descriptor with
`has_self=True`, and the Python wrapper prepends `self` before calling
`private.invoke_callable_descriptor()`.

Overlay-body fast path:

1. Python overlay code can call `private.invoke(namespace, function, *args)`.
2. `py_invoke_by_name()` in `callable_descriptor.c` resolves and caches a
   descriptor by name.
3. It calls the same `pygi_method_descriptor_call_ffi_invoke()` backend.

## Layer Responsibilities

### Python Lookup Layer

Files:

- `src/ginext/namespace.py`
- `src/ginext/class_.py`
- `src/ginext/method.py`
- `src/ginext/private/__init__.py`

Important names:

- `Namespace.__getattr__`
- `Function`
- `make_method`
- `private.build_callable_descriptor`
- `private.invoke_callable_descriptor`

Responsibilities:

- Convert GI namespace/class/function lookup into Python objects.
- Decide whether a callable is exposed as a top-level `Function` or a bound
  method wrapper.
- Preserve PyGObject-style Python call syntax, including keyword arguments and
  bound `self`.
- Keep the C extension boundary small: build descriptor once, invoke descriptor
  many times.

This layer should not own GI ABI details. It should not know about array length
arguments, closure destroy-notify slots, or libffi.

### Descriptor And Compile Layer

Files:

- `src/ginext/private/callable_descriptor.c`
- `src/ginext/private/runtime/callable.h`

Important names:

- `PyGIMethodDescriptor`
- `PyGICompiledCallable`
- `py_build_callable_descriptor`
- `compile_callable_for_ffi`
- `validate_phase1_plan`
- `descriptor_cache_arg_names`
- `resolve_call_args`
- `py_invoke_callable_descriptor`
- `py_invoke_by_name`

Responsibilities:

- Own the callable descriptor object/capsule used by Python.
- Resolve `GIFunctionInfo` to a C symbol through `dlsym()`.
- Allocate and own the cached `PyGIInvokePlan` storage embedded in the
  compiled callable.
- Validate whether the current runtime supports the callable's argument and
  return shape.
- Precompute libffi `ffi_cif`, argument `ffi_type` pointers, ABI arity, return
  type metadata, and GError shape.
- Cache visible Python argument names and merge kwargs into positional order.
- Handle PyGObject-compatible callback user-data argument packing.

This layer is currently broad. It owns both descriptor construction and the
support matrix. Conceptually, the support matrix is closer to invoke planning
than descriptor mechanics. Moving `validate_phase1_plan()` and related shape
classification into an `invoke/support.c` style layer would make the boundary
cleaner.

### Invoke Plan Layer

Files:

- `src/ginext/private/invoke/plan.h`
- `src/ginext/private/invoke/plan.c`

Important names:

- `PyGIInvokePlan`
- `PyGIArgPlan`
- `PyGIOutSlotPlan`
- `PyGIArgRole`
- `PyGILengthKind`
- `PyGIMarshalKind`
- `pygi_invoke_plan`
- `pygi_invoke_plan_clear`

Responsibilities:

- Perform all GI metadata walking before invocation.
- Cache per-argument direction, transfer, nullability, caller-allocates status,
  type tag, array tag, storage tag, normalized `PyGIType`, and selected fast
  marshal kind.
- Identify hidden companion arguments:
  - callback closure user-data slots,
  - closure destroy-notify slots,
  - C array length arguments.
- Assign visible Python argument indexes.
- Assign C ABI input slots and output storage slots.
- Build the reverse `out_slots[]` map used by return shaping.
- Cache owned `GIArgInfo`, `GITypeInfo`, and array element type-info refs so the
  hot path does not call `gi_*`.

The plan is the central contract between metadata and execution. After plan
construction, bind, libffi/JIT, and return shaping should be able to run without
walking GI metadata.

The plan currently mixes several kinds of facts:

- semantic facts from GI metadata,
- Python call surface facts,
- ABI slot layout,
- fast-path marshal dispatch,
- compatibility rewrites for bad GIR metadata.

That is acceptable for performance, but it makes the plan the highest-risk
type for conceptual drift. If it grows further, splitting it into explicit
"metadata facts", "Python signature", and "ABI layout" sections inside the
same struct would make the design easier to reason about without forcing more
runtime allocation.

### Frame And Cleanup Layer

Files:

- `src/ginext/private/invoke/frame.h`
- `src/ginext/private/invoke/frame.c`
- `src/ginext/private/invoke/arg-cleanup.h`
- `src/ginext/private/invoke/arg-cleanup.c`

Important names:

- `PyGIInvokeFrame`
- `PyGIArgCleanup`
- `pygi_invoke_frame_fail`
- `pygi_invoke_frame_clear`
- `pygi_arg_cleanup_run`
- `pygi_invoke_cleanup_push`

Responsibilities:

- Hold all per-call mutable state:
  - `in_args`,
  - `out_args`,
  - `out_values`,
  - per-output `GITypeInfo` refs,
  - array length type-info refs,
  - cleanup records.
- Provide one cleanup path for bind failures and another for successful calls
  after return shaping.
- Keep temporary C resources alive long enough for the return shaper to wrap or
  copy them.

The success cleanup order matters. Return shaping may temporarily alias
`out_values`, returned pointers, callback closures, GValues, arrays, strings, or
objects. Cleanup happens after Python objects have been created.

### Bind Layer

Files:

- `src/ginext/private/invoke/bind.h`
- `src/ginext/private/invoke/bind.c`

Important names:

- `pygi_invoke_bind_args`
- `bind_out_storage`
- `bind_inout_value`
- `pygi_py_to_c_array_invoke`
- `pygi_marshal_from_py`

Responsibilities:

- Convert the Python call argument array into the C ABI input/output storage
  expected by the plan.
- Unwrap bound `self`, verify GType compatibility, and apply transfer semantics
  for instance arguments.
- Bind callback/user-data/destroy companion slots.
- Bind hidden and visible array length arguments.
- Allocate OUT/INOUT storage, including caller-allocates structs, GValues,
  C arrays, and GArray-like containers.
- Run fast direct conversions for common scalar and object types.
- Fall back to `PyGIMarshalSlot` and `pygi_marshal_from_py()` for generic
  conversions.

The bind layer is where most runtime policy currently concentrates. It knows
about fast scalar conversion, GObject identity, string ownership, GBytes
creation, callback closures, arrays, caller-allocates storage, and length
pairing. Some of this is inevitable because binding must compose all call-site
facts, but the fast path duplicates behavior also present in the marshal layer.

### FFI Invoke Layer

Files:

- `src/ginext/private/invoke/ffi/invoke.h`
- `src/ginext/private/invoke/ffi/invoke.c`

Important names:

- `pygi_method_descriptor_call_ffi_invoke`
- `pygi_callable_info_invoke`
- `extract_basic_ffi_return_value`
- `gi_type_info_extract_ffi_return_value`

Responsibilities:

- Allocate stack-backed per-call storage sized from the compiled plan.
- Choose the cached plan, or build a local plan if no compiled plan exists.
- Copy and adjust the cached plan when closure companion slots need per-call
  user-data exposure.
- Call `pygi_invoke_bind_args()`.
- Build the libffi value array from plan slots.
- Perform the C call.
- Convert a thrown `GError` into Python.
- Pass raw return/output storage to the return shaper.
- Clear the invoke frame.

The custom `pygi_callable_info_invoke()` is intentionally similar to
`gi_callable_info_invoke()`, but uses precomputed metadata and the local plan
layout. It is the ABI executor, not the conversion policy owner.

### Return Shaping Layer

Files:

- `src/ginext/private/invoke/return.h`
- `src/ginext/private/invoke/return.c`

Important names:

- `pygi_invoke_shape_return`
- `out_slot_to_py`
- `build_visible_out_tuple`

Responsibilities:

- Convert raw return and OUT storage into the Python result.
- Hide OUT length slots consumed by arrays.
- Fold return-array length OUT parameters into return conversion.
- Apply PyGObject-compatible result shapes:
  - no OUT values returns the callable return value,
  - void plus one visible OUT returns that one value,
  - void plus multiple visible OUT values returns a tuple,
  - `width`/`height` OUT pairs become a `types.SimpleNamespace`,
  - boolean returns with OUT values include the success boolean.
- Build `PyGIMarshalSlot` values for return and OUT conversion.

This layer owns user-visible result shape policy. That is a real compatibility
surface and should stay explicit. It should not allocate call input storage or
repeat GI metadata walking.

### Marshal Facade Layer

Files:

- `src/ginext/private/marshal/marshal.h`
- `src/ginext/private/marshal/marshal.c`

Important names:

- `PyGIMarshalSlot`
- `PyGIMarshalTargetKind`
- `pygi_marshal_from_py`
- `pygi_marshal_to_py`
- `pygi_argument_from_py`
- `pygi_argument_from_py_for_call`
- `pygi_argument_to_py`
- `pygi_argument_to_py_transfer`

Responsibilities:

- Provide the common conversion API used by bind, return shaping, record-field
  access, GValue helpers, and closure paths.
- Describe conversion target storage:
  - `PYGI_MARSHAL_TARGET_GIARG`,
  - `PYGI_MARSHAL_TARGET_MEMORY`,
  - `PYGI_MARSHAL_TARGET_GVALUE`.
- Carry conversion context:
  - GI type info,
  - normalized `PyGIType`,
  - transfer,
  - array length,
  - caller-allocates status,
  - cleanup output,
  - callable/arg info for diagnostics and callback scope.
- Route direct storage through `PyGIValue`.
- Route arrays, lists, hashes, callbacks, structs, boxed types, objects,
  variants, errors, and foreign/cairo objects through specialized helpers.

`PyGIMarshalSlot` is the intended unifying abstraction, but it is not yet the
only conversion model. `marshal.c` still contains legacy entry points, and the
bind layer has hand-written fast conversions for common types. This gives good
performance but creates semantic duplication.

### Normalized Value Layer

Files:

- `src/ginext/private/marshal/pygi-value.h`
- `src/ginext/private/marshal/pygi-value.c`
- `src/ginext/private/marshal/scalar.c`
- `src/ginext/private/marshal/string.c`
- `src/ginext/private/marshal/enum.c`

Important names:

- `PyGIType`
- `PyGITypeKind`
- `PyGIValue`
- `pygi_type_from_gi`
- `pygi_type_from_gtype`
- `pygi_type_from_gvalue`
- `pygi_type_is_direct_storage`
- `pygi_value_from_py`
- `pygi_value_to_py`
- `pygi_py_to_primitive_storage`
- `pygi_primitive_storage_to_py`

Responsibilities:

- Normalize GI tags, GTypes, and GValue types into a local `PyGIType`.
- Abstract over storage destinations:
  - `GIArgument`,
  - raw memory,
  - `GValue`.
- Convert direct scalar-ish values:
  - booleans,
  - integers,
  - floats,
  - unichar,
  - strings/filenames,
  - GType,
  - enum/flags,
  - direct object/boxed/interface pointer cases where supported.

This layer should be boring and mechanical. It is strongest when it does not
know about callable result shapes, hidden args, or callback closure policies.

### Container And GValue Helpers

Files:

- `src/ginext/private/marshal/c-array.c`
- `src/ginext/private/marshal/container-element.c`
- `src/ginext/private/marshal/gvalue.c`

Important names:

- `pygi_py_to_c_array_invoke`
- `pygi_c_array_to_py`
- `PyGIContainerElement`
- `pygi_container_element_from_type_info`
- `pygi_py_to_gvalue_inplace`
- `pygi_gvalue_from_py`
- `pygi_gvalue_to_py`
- `pygi_gvalue_value_to_py`

Responsibilities:

- Convert Python sequences and buffers to C arrays.
- Convert C arrays back to Python lists or bytes.
- Model element conversion separately from top-level argument conversion.
- Handle GValue as a GType-based conversion axis, not just a GI type tag.
- Support direct elements, strings, variants, GValues, objects/interfaces,
  structs/unions, nested string arrays, and pointer arrays.

These helpers expose an important conceptual split:

- GI callable metadata describes the shape of an argument.
- GType/GValue metadata describes runtime value storage.
- Container element metadata describes repeated values inside arrays/lists/hash
  tables.

Keeping those axes separate is important. Bugs usually appear when one axis is
used to answer a question owned by another.

### Callback And Closure Crossing

Files:

- `src/ginext/private/GObject/Closure.*`
- `src/ginext/private/invoke/bind.c`
- `src/ginext/private/marshal/marshal.c`

Important names:

- `pygi_callback_closure_new`
- `pygi_callback_closure_set_py_user_data`
- `pygi_callback_closure_destroy`
- `PYGI_ARG_ROLE_CLOSURE_DESTROY`
- `owner_callback_arg`
- `has_user_data_slot`

Responsibilities:

- Convert Python callables into C callback closures.
- Attach Python user data to the closure when GI closure annotations identify a
  companion slot.
- Install the correct destroy-notify function for notified-scope callbacks.
- Hide or expose user-data companion slots according to PyGObject-compatible
  call arity rules.

This is one of the most delicate areas because the visible Python signature,
hidden GI slots, C callback lifetime, and cleanup records all interact.

## Data Contracts Between Layers

The important contracts are:

- `PyGIMethodDescriptor` owns the compiled callable and descriptor-level Python
  call metadata.
- `PyGICompiledCallable` owns the cached `PyGIInvokePlan`, libffi metadata, and
  compiled-call flags.
- `PyGIInvokePlan` owns metadata facts and maps GI args to Python args, ABI
  input slots, output slots, and hidden companion roles.
- `PyGIInvokeFrame` owns per-call mutable storage and cleanup records.
- `PyGIMarshalSlot` describes one conversion operation independent of a full
  invocation.
- `PyGIValue` describes direct conversion storage independent of invocation and
  independent of Python result shape.

The intended dependency direction is:

```text
Python lookup
  -> descriptor compile
  -> invoke plan
  -> per-call frame
  -> bind
  -> ABI executor
  -> return shaping
  -> marshal facade
  -> leaf converters
```

In practice, bind and return both call into the marshal facade, and the marshal
facade calls into leaf converters. The ABI executor should only depend on the
plan and frame. Leaf converters should not depend on descriptor or invoke
policy.

## Existing Tests That Guard This Area

The strongest architectural tests are under `src/ginext/tests/plan_invariant`:

- `test_no_gi_on_hot_path.py` asserts descriptor construction may walk GI
  metadata, but repeated invocation does not.
- `test_plan_caching.py` asserts descriptors are cached and may expose plan
  debug state.
- `test_stats_api.py` checks the runtime stats API around invoke metadata
  walks.

The functional invoke tests under `src/ginext/tests/invoke` cover specific
marshalling and call-shape behavior:

- integer and float conversion,
- enum and flags conversion,
- UTF-8 and filename strings,
- nullable arguments,
- keyword argument mapping,
- strv/array handling,
- descriptor-build rejection,
- return type shapes,
- callback/user-data triples,
- CPython PyArg error-message oracle on debug builds.

Related coverage also appears in:

- `src/ginext/tests/typelib/test_gi_marshalling_tests.py`
- `src/ginext/tests/closure`
- `src/ginext/tests/property`
- `src/ginext/tests/pygobject/test_object_marshaling.py`
- `src/ginext/tests/glib/test_variant_compat.py`
- `src/ginext/tests/gtk3/test_template.py`
- `src/ginext/tests/gtk4/test_template.py`

## Conceptual Integrity Assessment

The good parts:

- The system has a clear performance invariant: GI metadata walking belongs in
  descriptor/plan construction, not the hot call path.
- `PyGIInvokePlan` is the right central idea. It makes hidden GI arguments,
  visible Python arguments, ABI slots, OUT slots, and return shaping explicit.
- `PyGIMarshalSlot` is the right direction for unifying conversion APIs across
  call arguments, returns, GValue, record fields, and closure paths.
- The FFI executor is increasingly separated from conversion policy.
- Return shaping is isolated enough that compatibility policy can be audited.

The weak boundaries:

- `callable_descriptor.c` owns descriptor mechanics, support validation, FFI
  preparation, keyword resolution, descriptor caches, and overlay-body invoke.
- `bind.c` owns both orchestration and many direct conversion semantics also
  present in the marshal layer.
- `marshal.c` is both facade and policy bucket for interfaces, boxed types,
  objects, callbacks, arrays, lists, hashes, cairo foreign structs, GBytes, and
  variants.

High-risk details to audit before large refactors:

- Caller-allocates C-array OUT storage in `bind_out_storage()`. The current
  allocation path deserves a targeted review for non-fixed arrays where the
  length is paired but not already known.
- Cleanup after partial bind failures. Some fast paths note that transfer-full
  strings or objects can leak if a later argument fails before the frame reaches
  normal cleanup.
- Transfer defaults in `PyGIMarshalSlot`. Callers should make transfer
  explicit, especially for pointer-like direct conversions.
- Generic nested conversions that still call legacy `pygi_argument_to_py()`
  instead of transfer-explicit forms.
- Closure companion un-eliding rules. The descriptor path should have one
  documented rule for how many extra callback companion values can be supplied
  and which slots stay hidden.
- Local-plan fallback in `pygi_method_descriptor_call_ffi_invoke()`. If the
  cached compiled plan is absent, the temporary plan should have the same clear
  semantics as compiled plans.

## Improvement Tasks

These tasks are ordered to improve conceptual integrity without requiring a
large rewrite.

### Task 1: Retire The Legacy Phase-1 Invoke API

Status: done.

Problem:

`namespace.c` defines a local `PyGIInvokePlan`, `PyGIValuePlan`, and
`PyGIMarshalKind` that are unrelated to the real invoke subsystem in
`src/ginext/private/invoke`. The names imply they are the same abstraction,
but they support only a small simple-IN-args subset.

Work:

- Removed `private.build_invoke_plan()` and `private.invoke_plan()` from the
  C module method table and Python re-export layer.
- Removed the local phase-1 `PyGIInvokePlan`, `PyGIValuePlan`,
  `PyGIMarshalKind`, and simple libffi invoke helpers from `namespace.c`.
- Left invoke stats in `namespace.c` because descriptor construction still uses
  `pygi_ginext_record_plan_gi_metadata_call()`.

Done when:

- There is only one type named like the canonical invoke plan:
  `PyGIInvokePlan` from `invoke/plan.h`.
- Tests and docs no longer have to distinguish "real invoke plan" from
  "`namespace.c` invoke plan".

### Task 2: Split Callable Support Validation Out Of Descriptor Construction

Problem:

`callable_descriptor.c` owns too many reasons to change. It builds descriptors,
resolves symbols, caches argument names, merges kwargs, prepares FFI metadata,
and validates the supported callable shape.

Work:

- Move `validate_phase1_plan()` and related shape checks into a new focused
  module, for example `src/ginext/private/invoke/support.c`.
- Give that module a small API such as:
  `pygi_invoke_validate_supported(const PyGIInvokePlan *plan,
  const char *qualified_name)`.
- Keep support errors identical at first.
- Add a small test that unsupported descriptor-build errors still come from
  descriptor construction.

Done when:

- `callable_descriptor.c` asks the invoke layer whether a plan is supported,
  instead of owning the support matrix itself.
- Future support additions have one obvious file to edit.

### Task 3: Document And Enforce `PyGIInvokePlan` Ownership Boundaries

Problem:

`PyGIInvokePlan` is the central type, but it currently mixes metadata facts,
Python signature facts, ABI layout, fast marshal dispatch, and GIR compatibility
rewrites without clear internal sections.

Work:

- Reorder `PyGIArgPlan` and `PyGIInvokePlan` fields into named sections in
  `invoke/plan.h`:
  - metadata facts,
  - Python signature mapping,
  - ABI slot layout,
  - array/callback companion relationships,
  - precomputed marshal dispatch.
- Add short comments for fields whose owner is not obvious.
- Keep the binary behavior unchanged.
- Add or update plan invariant tests for:
  - visible Python arg count,
  - hidden length args,
  - hidden callback destroy args,
  - no GI metadata calls on repeated invocation.

Done when:

- A reader can tell whether a field is a metadata fact, call-surface fact, or
  ABI-layout fact without reading `plan.c`.
- Bind and return code still consume the same plan, but the conceptual sections
  are explicit.

### Task 4: Make `PyGIMarshalSlot` The Single Generic Conversion Contract

Problem:

The marshal facade is intended to unify conversion, but bind has fast-path
conversions for scalars, strings, GType, GObject, GBytes, enums, and flags.
Those fast paths duplicate semantics that also exist behind
`pygi_marshal_from_py()` and `pygi_marshal_to_py()`.

Work:

- Define the contract of `PyGIMarshalSlot` in `marshal.h`: required fields,
  optional fields, transfer defaults, cleanup ownership, and target-kind
  semantics.
- For each bind fast path, identify the equivalent `PyGIMarshalSlot` shape in
  comments or helper constructors.
- Add test cases that exercise the same conversion through a normal invoke and
  through a marshal-slot caller where one exists, especially for:
  - enum/flags validation,
  - GType from class metadata,
  - nullable object args,
  - filename path-like values,
  - transfer-full strings.
- Only after that, consider replacing low-value fast paths with marshal-slot
  calls.

Done when:

- Fast paths are clearly optimizations of the generic conversion contract, not
  separate semantics.
- Transfer and cleanup behavior is explicit at every marshal-slot call site.

### Task 5: Extract Caller-Allocates OUT Storage Policy From Binding

Problem:

`bind_out_storage()` owns several policies at once: output storage allocation,
caller-allocates structs, GValue storage, C arrays, GArray-like containers, and
length backfilling. This makes array and ownership bugs hard to audit.

Work:

- Introduce focused helpers for caller-allocates cases, for example:
  - `bind_caller_allocates_struct()`,
  - `bind_caller_allocates_gvalue()`,
  - `bind_caller_allocates_c_array()`,
  - `bind_noncaller_out_pointer()`.
- Add explicit tests for caller-allocates C arrays with fixed size, paired
  length, and missing/unknown length.
- Review the current non-fixed C-array allocation path and decide whether it
  should reject unknown size instead of allocating a single element.

Done when:

- `bind_out_storage()` reads as orchestration rather than policy.
- Caller-allocates arrays have an explicit supported/unsupported contract.

### Task 6: Make Cleanup Semantics Explicit For Bind Failures

Problem:

Some fast paths acknowledge that transfer-full resources can leak if a later
argument fails during binding. The frame cleanup model is good, but converted
inputs need consistent registration before the next possible failure.

Work:

- Audit every `GI_TRANSFER_EVERYTHING` conversion in `bind.c` and
  `marshal.c`.
- Register cleanup immediately after allocating or ref-taking any resource
  that is not yet owned by the callee.
- Add tests that force a later argument to fail after an earlier transfer-full
  string/object/bytes conversion.
- Keep success cleanup behavior unchanged unless tests prove it wrong.

Done when:

- Bind failure and successful invocation have documented cleanup paths.
- No conversion relies on "the rest of binding will succeed" to avoid leaks.

### Task 7: Split Marshal Policy By Axis

Problem:

`marshal.c` is both a facade and a policy bucket. It handles direct values,
interfaces, boxed records, objects, callbacks, arrays, lists, hashes, variants,
GBytes, and foreign/cairo structs. That makes it hard to know where new
conversion behavior belongs.

Work:

- Keep `marshal.c` as the facade.
- Move policy clusters into focused files over time:
  - `marshal/interface.c` for interface/object/boxed dispatch,
  - `marshal/callback.c` for callback/GClosure conversion,
  - `marshal/collection.c` for GLib list/hash wrappers,
  - keep `c-array.c`, `gvalue.c`, `scalar.c`, `string.c`, and `enum.c`
    focused on their current axes.
- Avoid behavior changes during moves.

Done when:

- A new conversion can be placed by asking which axis it belongs to:
  GI callable type shape, GType/GValue runtime storage, container element
  conversion, object/boxed/interface wrapping, or callback lifetime.

### Task 8: Move Return-Shape Compatibility Policy Into Named Helpers

Problem:

`return.c` has important PyGObject compatibility policy mixed into the raw
conversion flow. The behavior is legitimate, but the policy should be easy to
find and test.

Work:

- Extract named helpers for result-shape decisions:
  - no visible OUT values,
  - one visible OUT value,
  - multiple visible OUT values,
  - boolean return plus OUT values,
  - return-array plus length OUT,
  - `width`/`height` namespace result.
- Add tests that name those shapes directly.

Done when:

- Return conversion and result-shape policy are separate enough to audit.
- PyGObject-compatible shape decisions are visible in function names, not only
  in branch structure.

The target conceptual model should be:

- descriptors own callable identity and Python call entry,
- plans own metadata-derived call shape,
- frames own per-call storage and cleanup,
- bind owns argument orchestration,
- ABI executors own calling mechanics,
- return shaping owns Python result policy,
- marshallers own conversion mechanics,
- leaf converters own boring storage conversion only.
