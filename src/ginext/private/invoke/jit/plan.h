/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#pragma once

#include "jit/jit.h"
#include "invoke/plan.h"

#include <ffi.h>
#include <girepository/girepository.h>
#include <stdbool.h>

/* ABI kind for a single C-ABI argument or return value. The JIT backend
 * uses this - and only this - to choose how to load/store the value. It
 * does not interpret GI metadata. */
typedef enum
{
  PYGI_ABI_VOID = 0,
  PYGI_ABI_I8,
  PYGI_ABI_U8,
  PYGI_ABI_I16,
  PYGI_ABI_U16,
  PYGI_ABI_I32,
  PYGI_ABI_U32,
  PYGI_ABI_I64,
  PYGI_ABI_U64,
  PYGI_ABI_POINTER,
  PYGI_ABI_FLOAT,
  PYGI_ABI_DOUBLE,
} PyGIAbiKind;

/* Where the value for one ABI arg comes from in the prepared
 * PyGIInvokeFrame. */
typedef enum
{
  PYGI_JIT_ARG_FROM_IN_ARG = 0, /* frame->in_args[source_slot] */
  PYGI_JIT_ARG_FROM_OUT_ARG, /* frame->out_args[source_slot].v_pointer */
  PYGI_JIT_ARG_FROM_ERROR_PTR, /* &frame->gerror */
} PyGIJitArgSource;

typedef struct
{
  PyGIAbiKind kind;
  PyGIJitArgSource source;
  int source_slot; /* index into frame->in_args[]; -1 for ERROR_PTR */
} PyGIJitAbiArg;

#define PYGI_JIT_MAX_ABI_ARGS 32

typedef struct
{
  PyGIAbiKind ret_kind;
  int n_abi_args;
  PyGIJitAbiArg abi_args[PYGI_JIT_MAX_ABI_ARGS];

  /* True if `gerror` is appended to abi_args. */
  bool can_throw_gerror;

  /* True if this callable cannot be lowered to direct ABI. The
   * PyGICompiledCallable falls back to the narrow PyGISignature path
   * (or to FFI if that also rejects). */
  bool unsupported;
  /* Human-readable reason for unsupported, used in error messages. */
  char unsupported_reason[160];
} PyGIJitPlan;

/* Cached per-callable state for JIT direct-call dispatch. Owned by the
 * PyGIMethodDescriptor; lifetime spans the descriptor's. */
typedef struct PyGICompiledCallable
{
  GICallableInfo *info;
  char *qualified_name;
  void *target_fn;

  /* Shared GI-level call plan: per-arg metadata, in/out slot assignment,
   * length pairing. Built once from the GICallableInfo at descriptor build
   * time; reused as read-only metadata by every call. */
  PyGIInvokePlan invoke_plan;
  PyGIArgPlan *invoke_plan_args; /* invoke_plan.args storage */
  PyGIOutSlotPlan *invoke_plan_outs; /* invoke_plan.out_slots storage */

  /* ABI lowering. If `jit_plan.unsupported` is true the descriptor uses
   * the narrow PyGISignature emitter instead. */
  PyGIJitPlan jit_plan;

  /* Narrow JIT signature (legacy direct-call shapes). Filled when
   * jit_plan.unsupported is true and the narrow planner accepts. */
  PyGISignature signature;
  bool has_narrow_signature;

  PyGIJittedTrampoline trampoline;
  bool trampoline_is_full; /* uses prepare/finish path; else narrow */

  int has_self;

  /* Total bytes the per-call arena needs (16-aligned). Computed once at
   * descriptor build time so the trampoline can reserve the right amount
   * on its own stack and pass a pointer to prepare_call. */
  size_t arena_size;

  /* Set when the plan has at least one CLOSURE_DESTROY companion arg.
   * The closure heuristic depends on the actual nargs at call time; if
   * this is true, prepare_call rebuilds the plan into a per-frame slot
   * with the real nargs so role assignments stay correct. */
  bool has_closure_companions;

  /* Precomputed libffi setup for the slow-FFI fallback path. Built once
   * at descriptor-build time so per-call invocations skip the
   * gi_callable_info walk + ffi_prep_cif entirely. */
  bool ffi_setup_ready;
  ffi_cif ffi_cif;
  ffi_type *ffi_rtype;
  ffi_type **ffi_atypes; /* heap-alloc'd, ffi_n_invoke_args entries */
  GITypeInfo *ffi_rinfo; /* owning ref to the return type info */
  GITypeTag ffi_rtag;
  bool ffi_return_is_pointer;
  unsigned int ffi_n_invoke_args;
  bool ffi_throws;
} PyGICompiledCallable;

PyGICompiledCallable *
pygi_jit_compile_callable (GIFunctionInfo *info, int has_self, const char *qualified_name);

void
pygi_jit_compiled_callable_destroy (PyGICompiledCallable *compiled);

/* Lower a built PyGIInvokePlan to a PyGIJitPlan. The result records
 * the ABI arg/return kinds, where each ABI arg's value lives in the
 * frame, and (on rejection) a precise reason. Returns 0 on success, -1
 * if the callable cannot be lowered (jit_plan->unsupported set). */
int
pygi_jit_plan_lower (GICallableInfo *cb,
                     const PyGIInvokePlan *invoke,
                     int has_self,
                     PyGIJitPlan *jit_plan);
