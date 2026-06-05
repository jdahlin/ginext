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

/* Per-call invocation frame: owns all temporary GITypeInfo references and
 * tracks the mutable state for one GI call. */

#include "invoke/arg-cleanup.h"
#include "invoke/plan.h"
#include <girepository/girepository.h>
#include <Python.h>
#include <stddef.h>

typedef struct
{
  PyObject *bound_self;
  GIArgument *in_args;
  GIArgument *out_args;
  GIArgument *out_values;
  GITypeInfo **out_tis;
  GITypeInfo **in_len_ti;
  size_t *in_len_slot;
  PyGIArgCleanup *cleanups;

  size_t in_index;
  size_t out_index;
  size_t py_index;
  size_t n_gi_args;
  size_t n_out_args;
  /* Number of out_tis[] entries currently owned. Incremented at the same time
   * as the g_steal_pointer into out_tis[], which may happen before out_index
   * is incremented (e.g. during partial INOUT setup). frame_fail uses this
   * to know how many GITypeInfo refs to release. */
  size_t out_tis_count;

  /* Set by the JIT path: target's raw return value lands here, then
   * pygi_jit_finish_call shapes it through pygi_invoke_shape_return.
   * Unused on the FFI path (it manages its own ret local). */
  GIArgument ret;

  /* Used by the JIT path for GError-throwing callables. The trampoline
   * passes `&gerror` to the target as a hidden ABI arg; finish_call
   * raises a Python exception if non-NULL. */
  GError *gerror;

  /* JIT path only: per-call PyGIInvokePlan pointing into the same
   * heap arena as this frame. Each thread gets its own plan storage,
   * so concurrent calls to the same descriptor don't trample each
   * other's closure-detection role assignments. NULL on the FFI path. */
  PyGIInvokePlan *plan;
} PyGIInvokeFrame;

/* Error cleanup: frees out_tis[0..out_tis_count), releases in_len_ti refs,
 * clears all IN cleanups, and returns NULL.
 * Call on every error path after frame initialisation. */
PyObject *
pygi_invoke_frame_fail (PyGIInvokeFrame *frame);

/* Success cleanup: same frees as frame_fail but without returning NULL.
 * Call AFTER the return value has already been converted from GIArgument,
 * so that alias-sensitive cases (e.g. gvalue_round_trip) stay safe. */
void
pygi_invoke_frame_clear (PyGIInvokeFrame *frame);
