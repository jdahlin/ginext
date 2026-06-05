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

/* invoke/jit/invoke.c - prepare/finish helpers for the full JIT path. */
#include "invoke/jit/invoke.h"
#include "GLib/Error.h"
#include "marshal/marshal.h"

#include "invoke/arg-cleanup.h"
#include "invoke/bind.h"
#include "invoke/return.h"
#include "runtime/callable.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* Arena layout (one contiguous block, lives on the trampoline's stack):
 *
 *   PyGIInvokeFrame            -- header
 *   GIArgument  in_args[max_in]
 *   GIArgument  out_args[max_out]
 *   GIArgument  out_values[max_out]
 *   GITypeInfo *out_tis[max_out]
 *   GITypeInfo *in_len_ti[n_gi_args]
 *   size_t      in_len_slot[n_gi_args]
 *   PyGIArgCleanup cleanups[n_gi_args]
 *   PyGIInvokePlan plan
 *   PyGIArgPlan    plan_args[n_gi_args]
 *   PyGIOutSlotPlan plan_outs[n_gi_args]
 *
 * The plan storage is per-call so concurrent invocations of the same
 * descriptor (free-threaded Python) don't race on closure-detection
 * role assignments. The trampoline reserves compiled->arena_size bytes
 * on its stack; prepare zeroes that buffer and lays the frame out in
 * place. finish never frees - the trampoline's own `leave; ret`
 * deallocates when it returns. */

static size_t
arena_compute_layout (size_t n_gi_args,
                      size_t max_in,
                      size_t max_out,
                      size_t *off_frame_o,
                      size_t *off_in_o,
                      size_t *off_out_o,
                      size_t *off_outv_o,
                      size_t *off_outtis_o,
                      size_t *off_inlent_o,
                      size_t *off_inlens_o,
                      size_t *off_cleanup_o,
                      size_t *off_plan_o,
                      size_t *off_plan_args_o,
                      size_t *off_plan_outs_o)
{
  size_t na = n_gi_args ? n_gi_args : 1u;
  size_t mi = max_in ? max_in : 1u;
  size_t mo = max_out ? max_out : 1u;

  size_t in_bytes = sizeof (GIArgument) * mi;
  size_t out_bytes = sizeof (GIArgument) * mo;
  size_t outv_bytes = sizeof (GIArgument) * mo;
  size_t outtis_bytes = sizeof (GITypeInfo *) * mo;
  size_t inlent_bytes = sizeof (GITypeInfo *) * na;
  size_t inlens_bytes = sizeof (size_t) * na;
  size_t cleanup_bytes = sizeof (PyGIArgCleanup) * na;
  size_t plan_bytes = sizeof (PyGIInvokePlan);
  size_t plan_args_bytes = sizeof (PyGIArgPlan) * na;
  size_t plan_outs_bytes = sizeof (PyGIOutSlotPlan) * na;

  *off_frame_o = 0;
  *off_in_o = sizeof (PyGIInvokeFrame);
  *off_out_o = *off_in_o + in_bytes;
  *off_outv_o = *off_out_o + out_bytes;
  *off_outtis_o = *off_outv_o + outv_bytes;
  *off_inlent_o = *off_outtis_o + outtis_bytes;
  *off_inlens_o = *off_inlent_o + inlent_bytes;
  *off_cleanup_o = *off_inlens_o + inlens_bytes;
  *off_plan_o = *off_cleanup_o + cleanup_bytes;
  *off_plan_args_o = *off_plan_o + plan_bytes;
  *off_plan_outs_o = *off_plan_args_o + plan_args_bytes;
  return *off_plan_outs_o + plan_outs_bytes;
}

size_t
pygi_jit_arena_size_for (size_t n_gi_args, size_t max_in, size_t max_out)
{
  size_t off_frame, off_in, off_out, off_outv, off_outtis;
  size_t off_inlent, off_inlens, off_cleanup, off_plan, off_plan_args, off_plan_outs;
  size_t total = arena_compute_layout (n_gi_args,
                                       max_in,
                                       max_out,
                                       &off_frame,
                                       &off_in,
                                       &off_out,
                                       &off_outv,
                                       &off_outtis,
                                       &off_inlent,
                                       &off_inlens,
                                       &off_cleanup,
                                       &off_plan,
                                       &off_plan_args,
                                       &off_plan_outs);
  /* Round up to 16 - caller will sub rsp by this and the SysV ABI
   * requires 16-byte stack alignment at call boundaries. */
  return (total + 15) & ~(size_t)15;
}

static void
arena_layout_in_place (PyGIInvokeFrame *frame,
                       void *scratch,
                       size_t n_gi_args,
                       size_t max_in,
                       size_t max_out)
{
  uint8_t *block = (uint8_t *)scratch;
  size_t off_frame, off_in, off_out, off_outv, off_outtis;
  size_t off_inlent, off_inlens, off_cleanup, off_plan, off_plan_args, off_plan_outs;
  arena_compute_layout (n_gi_args,
                        max_in,
                        max_out,
                        &off_frame,
                        &off_in,
                        &off_out,
                        &off_outv,
                        &off_outtis,
                        &off_inlent,
                        &off_inlens,
                        &off_cleanup,
                        &off_plan,
                        &off_plan_args,
                        &off_plan_outs);
  (void)frame;
  (void)off_frame;
  PyGIInvokeFrame *f = (PyGIInvokeFrame *)(block + off_frame);
  f->in_args = (GIArgument *)(block + off_in);
  f->out_args = (GIArgument *)(block + off_out);
  f->out_values = (GIArgument *)(block + off_outv);
  f->out_tis = (GITypeInfo **)(block + off_outtis);
  f->in_len_ti = (GITypeInfo **)(block + off_inlent);
  f->in_len_slot = (size_t *)(block + off_inlens);
  f->cleanups = (PyGIArgCleanup *)(block + off_cleanup);
  f->plan = (PyGIInvokePlan *)(block + off_plan);
  f->plan->args = (PyGIArgPlan *)(block + off_plan_args);
  f->plan->out_slots = (PyGIOutSlotPlan *)(block + off_plan_outs);
}

PyGIInvokeFrame *
pygi_jit_prepare_call (PyGICompiledCallable *compiled,
                       PyObject *const *args,
                       size_t nargs,
                       PyObject *kwnames,
                       void *scratch)
{
  if (!(kwnames == NULL))
    {
      PyErr_SetString (PyExc_TypeError,
                       "keyword arguments are not implemented for JIT direct call");
      return NULL;
    }

  GICallableInfo *cb = (GICallableInfo *)compiled->info;
  size_t n_gi_args = compiled->invoke_plan.n_gi_args;
  size_t max_in = compiled->invoke_plan.n_in_args;
  size_t max_out = compiled->invoke_plan.n_out_args;
  size_t out_total = max_out > 0 ? max_out : n_gi_args;

  /* Zero the scratch - the trampoline reserved it via plain `sub rsp`,
   * so its contents are whatever was last on the stack. */
  memset (scratch, 0, compiled->arena_size);

  arena_layout_in_place (NULL, scratch, n_gi_args, max_in, out_total);
  PyGIInvokeFrame *frame = (PyGIInvokeFrame *)scratch;
  frame->n_gi_args = n_gi_args;
  frame->n_out_args = out_total;

  for (size_t k = 0; k < n_gi_args; k++)
    frame->in_len_slot[k] = SIZE_MAX;

  /* Reuse the cached plan - built once at descriptor build, reused on
   * every call. For callables with closure/destroy companions the
   * role assignment depends on the actual call-time nargs (Python may
   * supply user_data explicitly OR let pygir auto-fill NULL); flip
   * the roles in the per-frame plan copy in that case. */
  if (G_UNLIKELY (compiled->has_closure_companions && nargs > compiled->invoke_plan.n_py_args))
    {
      /* Copy the cached plan into the arena's plan slots and expose
       * trailing closure companions only while there are actual Python
       * arguments left to consume. The descriptor plan may already expose
       * user_data, so count from the real cursor rather than from a fixed
       * "one extra/two extra" shape. */
      PyGIInvokePlan *p = frame->plan;
      PyGIArgPlan *arena_args = p->args;
      PyGIOutSlotPlan *arena_outs = p->out_slots;
      *p = compiled->invoke_plan;
      p->args = arena_args;
      p->out_slots = arena_outs;
      memcpy (arena_args, compiled->invoke_plan.args, p->n_gi_args * sizeof (PyGIArgPlan));
      ssize_t cursor = compiled->has_self ? 1 : 0;
      for (size_t i = 0; i < p->n_gi_args; i++)
        {
          PyGIArgPlan *ap = &arena_args[i];
          /* Only un-elide closure (user_data) slots, not destroy slots
           * — destroy is always managed by pygir and never user-supplied.
           * Closure slots have owner_callback_arg >= 0; destroy slots
           * encode it as -2 - callback_idx. */
          if (ap->role == PYGI_ARG_ROLE_CLOSURE_DESTROY && ap->owner_callback_arg >= 0)
            {
              if ((size_t)cursor < nargs)
                ap->role = PYGI_ARG_ROLE_NORMAL;
            }
          if (ap->role == PYGI_ARG_ROLE_NORMAL && ap->direction != GI_DIRECTION_OUT)
            {
              ap->consumes_py_arg = true;
              ap->py_arg_index = cursor++;
            }
        }
      p->n_py_args = (size_t)cursor;
    }
  else
    {
      frame->plan = &compiled->invoke_plan;
    }

  PyGIMethodDescriptor proxy = { 0 };
  proxy.info = (GIFunctionInfo *)compiled->info;
  proxy.has_self = compiled->has_self;
  proxy.qualified_name = compiled->qualified_name;

  if (pygi_invoke_bind_args (&proxy, frame, cb, frame->plan, args, nargs) != 0)
    {
      pygi_invoke_frame_fail (frame);
      return NULL;
    }

  return frame;
}

PyObject *
pygi_jit_finish_call (PyGICompiledCallable *compiled, PyGIInvokeFrame *frame)
{
  /* GError handling: if the callable can throw and gerror is non-NULL,
   * raise a Python exception and do error cleanup. */
  if (compiled->jit_plan.can_throw_gerror && frame->gerror != NULL)
    {
      pygi_raise_gerror (frame->gerror); /* frees gerror, sets GLib.Error */
      frame->gerror = NULL;
      pygi_invoke_frame_fail (frame);
      return NULL;
    }

  GICallableInfo *cb = (GICallableInfo *)compiled->info;
  PyObject *out = pygi_invoke_shape_return (cb,
                                            frame->plan,
                                            frame->bound_self,
                                            &frame->ret,
                                            frame->out_tis,
                                            frame->out_values,
                                            frame->plan->n_out_args,
                                            frame->plan->out_slots,
                                            frame->in_len_slot,
                                            frame->in_len_ti,
                                            frame->in_args);
  pygi_invoke_frame_clear (frame);
  return out;
}
