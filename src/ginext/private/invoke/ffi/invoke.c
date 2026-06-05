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

/* invoke/ffi/invoke.c - slow FFI fallback for GI method invocation. */
#include "invoke/ffi/invoke.h"
#include "GLib/Error.h"
#include "marshal/enum.h"
#include "marshal/marshal.h"
#include "invoke/arg-cleanup.h"
#include "invoke/bind.h"
#include "invoke/frame.h"
#include "invoke/jit/plan.h"
#include "invoke/plan.h"
#include "invoke/return.h"
#include "runtime/callable.h"
#include "runtime/type-info.h"

#include <stdio.h>
#include <string.h>
#include <girepository/girffi.h>

static gboolean
extract_basic_ffi_return_value (GITypeTag tag,
                                gboolean return_is_pointer,
                                const GIFFIReturnValue *ffi_value,
                                GIArgument *arg)
{
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      if (return_is_pointer)
        return FALSE;
      arg->v_pointer = NULL;
      return TRUE;
    case GI_TYPE_TAG_BOOLEAN:
      arg->v_boolean = (gboolean)ffi_value->v_long;
      return TRUE;
    case GI_TYPE_TAG_INT8:
      arg->v_int8 = (int8_t)ffi_value->v_long;
      return TRUE;
    case GI_TYPE_TAG_UINT8:
      arg->v_uint8 = (uint8_t)ffi_value->v_ulong;
      return TRUE;
    case GI_TYPE_TAG_INT16:
      arg->v_int16 = (int16_t)ffi_value->v_long;
      return TRUE;
    case GI_TYPE_TAG_UINT16:
      arg->v_uint16 = (uint16_t)ffi_value->v_ulong;
      return TRUE;
    case GI_TYPE_TAG_INT32:
      arg->v_int32 = (int32_t)ffi_value->v_long;
      return TRUE;
    case GI_TYPE_TAG_UINT32:
    case GI_TYPE_TAG_UNICHAR:
      arg->v_uint32 = (uint32_t)ffi_value->v_ulong;
      return TRUE;
    case GI_TYPE_TAG_INT64:
      arg->v_int64 = ffi_value->v_int64;
      return TRUE;
    case GI_TYPE_TAG_UINT64:
      arg->v_uint64 = ffi_value->v_uint64;
      return TRUE;
    case GI_TYPE_TAG_FLOAT:
      arg->v_float = ffi_value->v_float;
      return TRUE;
    case GI_TYPE_TAG_DOUBLE:
      arg->v_double = ffi_value->v_double;
      return TRUE;
    case GI_TYPE_TAG_GTYPE:
      /* GType is gsize (pointer-width). On LLP64 (Windows) v_ulong is only
         32 bits, which truncates the high half of a registered type's GType
         (a TypeNode pointer). Read the full pointer-width return value. */
      arg->v_size = (size_t)ffi_value->v_uint64;
      return TRUE;
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      arg->v_string = ffi_value->v_string;
      return TRUE;
    default:
      return FALSE;
    }
}

/* Adapted from glib's gi_callable_info_invoke (gicallableinfo.c). The
 * libgirepository version walks the signature on every call to compute
 * atypes and ffi_prep_cif a fresh `ffi_cif` - both are pure functions of
 * the callable, so we hoist them to descriptor-build time
 * (PyGICompiledCallable->ffi_cif). At call time we just bind the
 * args[] pointers and ffi_call. */
gboolean
pygi_callable_info_invoke (PyGICompiledCallable *compiled,
                           const GIArgument *in_args,
                           size_t n_in_args,
                           GIArgument *out_args,
                           size_t n_out_args,
                           GIArgument *return_value,
                           GError **error)
{
  if (!compiled->ffi_setup_ready)
    {
      g_set_error_literal (error,
                           GI_INVOKE_ERROR,
                           GI_INVOKE_ERROR_ARGUMENT_MISMATCH,
                           "ffi setup not prepared for this callable");
      return FALSE;
    }
  PyGIInvokePlan *plan = &compiled->invoke_plan;
  unsigned int n_args = (unsigned int)plan->n_gi_args;
  unsigned int n_invoke_args = compiled->ffi_n_invoke_args;
  gboolean is_method = compiled->has_self ? TRUE : FALSE;
  gboolean throws = compiled->ffi_throws;
  unsigned int in_pos = 0;
  unsigned int out_pos = 0;
  GError *local_error = NULL;
  void *error_address = &local_error;
  GIFFIReturnValue ffi_return_value;
  void *return_value_p;

  void **args = g_alloca (sizeof (void *) * (n_invoke_args ? n_invoke_args : 1u));

  size_t offset = is_method ? 1u : 0u;
  if (is_method)
    {
      if (n_in_args == 0)
        {
          g_set_error_literal (error,
                               GI_INVOKE_ERROR,
                               GI_INVOKE_ERROR_ARGUMENT_MISMATCH,
                               "Too few \"in\" arguments (handling this)");
          return FALSE;
        }
      args[0] = (void *)&in_args[0];
      in_pos = 1;
    }
  for (unsigned int i = 0; i < n_args; i++)
    {
      GIDirection dir = plan->args[i].direction;
      if (dir == GI_DIRECTION_IN)
        {
          if (in_pos >= n_in_args)
            {
              g_set_error_literal (error,
                                   GI_INVOKE_ERROR,
                                   GI_INVOKE_ERROR_ARGUMENT_MISMATCH,
                                   "Too few \"in\" arguments (handling in)");
              return FALSE;
            }
          if (compiled->ffi_atypes[i + offset] != NULL
              && compiled->ffi_atypes[i + offset]->type == FFI_TYPE_STRUCT)
            args[i + offset] = in_args[in_pos].v_pointer;
          else
            args[i + offset] = (void *)&in_args[in_pos];
          in_pos++;
        }
      else if (dir == GI_DIRECTION_OUT)
        {
          if (out_pos >= n_out_args)
            {
              g_set_error_literal (error,
                                   GI_INVOKE_ERROR,
                                   GI_INVOKE_ERROR_ARGUMENT_MISMATCH,
                                   "Too few \"out\" arguments (handling out)");
              return FALSE;
            }
          args[i + offset] = (void *)&out_args[out_pos++];
        }
      else /* INOUT */
        {
          if (in_pos >= n_in_args || out_pos >= n_out_args)
            {
              g_set_error_literal (error,
                                   GI_INVOKE_ERROR,
                                   GI_INVOKE_ERROR_ARGUMENT_MISMATCH,
                                   "Too few arguments (handling inout)");
              return FALSE;
            }
          args[i + offset] = (void *)&in_args[in_pos++];
          out_pos++;
        }
    }
  if (throws)
    args[n_invoke_args - 1] = &error_address;

  if (in_pos < n_in_args || out_pos < n_out_args)
    {
      g_set_error_literal (error,
                           GI_INVOKE_ERROR,
                           GI_INVOKE_ERROR_ARGUMENT_MISMATCH,
                           "Too many arguments");
      return FALSE;
    }

  /* Pick the libffi-mandated return slot (small returns widen to long). */
  switch (compiled->ffi_rtag)
    {
    case GI_TYPE_TAG_FLOAT:
      return_value_p = &ffi_return_value.v_float;
      break;
    case GI_TYPE_TAG_DOUBLE:
      return_value_p = &ffi_return_value.v_double;
      break;
    case GI_TYPE_TAG_INT64:
    case GI_TYPE_TAG_UINT64:
      return_value_p = &ffi_return_value.v_uint64;
      break;
    default:
      return_value_p = &ffi_return_value.v_long;
    }
  /* Release the GIL for the duration of the C call so that GLib worker
   * threads can acquire it to run Python callbacks (e.g. GObject vfuncs,
   * signal handlers, pad chain functions).  Without this, any blocking C
   * function that waits for GLib events (gst_bus_timed_pop_filtered, etc.)
   * deadlocks: the main thread holds the GIL waiting for a message that
   * can only be produced by GLib threads that are blocked waiting for the GIL.
   *
   * All Python objects have been marshalled to C GIArgument values by
   * pygi_invoke_bind_args before we reach this point, so it is safe to
   * drop the GIL here.  Callbacks re-acquire it via PyGILState_Ensure. */
  Py_BEGIN_ALLOW_THREADS ffi_call (&compiled->ffi_cif,
                                   FFI_FN (compiled->target_fn),
                                   return_value_p,
                                   args);
  Py_END_ALLOW_THREADS

      if (local_error)
  {
    g_propagate_error (error, local_error);
    return FALSE;
  }
  if (!extract_basic_ffi_return_value (compiled->ffi_rtag,
                                       compiled->ffi_return_is_pointer,
                                       &ffi_return_value,
                                       return_value))
    gi_type_info_extract_ffi_return_value (compiled->ffi_rinfo, &ffi_return_value, return_value);
  return TRUE;
}


PyObject *
pygi_method_descriptor_call_ffi_invoke (PyGIMethodDescriptor *d,
                                        PyObject *const *args,
                                        size_t nargs,
                                        PyObject *kwnames)
{
  if (!(kwnames == NULL))
    {
      PyErr_SetString (PyExc_TypeError,
                       "keyword arguments are not implemented for GIR call fallback");
      return NULL;
    }

  GICallableInfo *cb = (GICallableInfo *)d->info;
  if (cb == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "slow ffi fallback missing callable info");
      return NULL;
    }

  /* Fast path: if the descriptor has a cached compiled plan, reuse it
   * and skip the per-call gi_callable_info_get_n_args + pygi_invoke_plan
   * walk. This shaves ~5% off slow-FFI invocations on hot loops. */
  PyGIInvokePlan *cached_plan = (d->compiled != NULL) ? &d->compiled->invoke_plan : NULL;
  size_t n_gi_args
      = cached_plan != NULL ? cached_plan->n_gi_args : gi_callable_info_get_n_args (cb);
  size_t max_in_args = n_gi_args + (d->has_self ? 1u : 0u);
  size_t max_out_args = n_gi_args;

  GIArgument *in_args
      = (GIArgument *)alloca (sizeof (GIArgument) * (max_in_args ? max_in_args : 1u));
  GIArgument *out_args
      = (GIArgument *)alloca (sizeof (GIArgument) * (max_out_args ? max_out_args : 1u));
  GIArgument *out_values
      = (GIArgument *)alloca (sizeof (GIArgument) * (max_out_args ? max_out_args : 1u));
  PyGIArgCleanup *cleanups
      = (PyGIArgCleanup *)alloca (sizeof (PyGIArgCleanup) * (n_gi_args ? n_gi_args : 1u));
  GITypeInfo **out_tis
      = (GITypeInfo **)alloca (sizeof (GITypeInfo *) * (max_out_args ? max_out_args : 1u));
  size_t *in_len_slot = (size_t *)alloca (sizeof (size_t) * (n_gi_args ? n_gi_args : 1u));
  GITypeInfo **in_len_ti
      = (GITypeInfo **)alloca (sizeof (GITypeInfo *) * (n_gi_args ? n_gi_args : 1u));

  memset (in_args, 0, sizeof (GIArgument) * (max_in_args ? max_in_args : 1u));
  memset (out_args, 0, sizeof (GIArgument) * (max_out_args ? max_out_args : 1u));
  memset (out_values, 0, sizeof (GIArgument) * (max_out_args ? max_out_args : 1u));
  memset (cleanups, 0, sizeof (PyGIArgCleanup) * (n_gi_args ? n_gi_args : 1u));
  memset (out_tis, 0, sizeof (GITypeInfo *) * (max_out_args ? max_out_args : 1u));
  for (size_t k = 0; k < n_gi_args; k++)
    {
      in_len_slot[k] = SIZE_MAX;
      in_len_ti[k] = NULL;
    }

  /* Plan: prefer the cached one (no GI re-walk on hot calls). Fall
   * back to building a fresh plan on the stack for callables that
   * never went through pygi_jit_compile_callable (e.g. when JIT was
   * never attempted). */
  PyGIArgPlan *arg_plans = NULL;
  PyGIOutSlotPlan *out_slot_plans = NULL;
  PyGIInvokePlan local_plan;
  PyGIInvokePlan *plan_p;
  if (cached_plan != NULL)
    {
      plan_p = cached_plan;
      /* If the user supplied trailing args manually, expose closure
       * companions only while there are actual Python arguments left to
       * consume. The descriptor plan may already expose user_data, so count
       * from the real cursor rather than from a fixed extra-arg shape. */
      if (G_UNLIKELY (d->compiled->has_closure_companions && nargs > cached_plan->n_py_args))
        {
          arg_plans = (PyGIArgPlan *)alloca (sizeof (PyGIArgPlan) * (n_gi_args ? n_gi_args : 1u));
          memcpy (arg_plans, cached_plan->args, sizeof (PyGIArgPlan) * n_gi_args);
          local_plan = *cached_plan;
          local_plan.args = arg_plans;
          ssize_t cursor = d->has_self ? 1 : 0;
          for (size_t i = 0; i < n_gi_args; i++)
            {
              PyGIArgPlan *ap = &arg_plans[i];
              /* Only un-elide closure (user_data) slots, not destroy
               * slots — destroy is always managed by pygir and never
               * user-supplied. Closure slots have owner_callback_arg
               * >= 0; destroy slots encode it as -2 - callback_idx. */
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
          local_plan.n_py_args = (size_t)cursor;
          plan_p = &local_plan;
        }
    }
  else
    {
      arg_plans = (PyGIArgPlan *)alloca (sizeof (PyGIArgPlan) * (n_gi_args ? n_gi_args : 1u));
      out_slot_plans
          = (PyGIOutSlotPlan *)alloca (sizeof (PyGIOutSlotPlan) * (n_gi_args ? n_gi_args : 1u));
      memset (arg_plans, 0, sizeof (PyGIArgPlan) * (n_gi_args ? n_gi_args : 1u));
      memset (out_slot_plans, 0, sizeof (PyGIOutSlotPlan) * (n_gi_args ? n_gi_args : 1u));
      for (size_t k = 0; k < n_gi_args; k++)
        {
          arg_plans[k].py_arg_index = -1;
          arg_plans[k].in_slot = -1;
          arg_plans[k].out_slot = -1;
          arg_plans[k].length_arg = -1;
          arg_plans[k].owner_array_arg = -1;
          out_slot_plans[k].paired_length_out_slot = -1;
          out_slot_plans[k].paired_length_in_slot = -1;
          out_slot_plans[k].paired_in_length_gi_arg = -1;
        }
      local_plan.args = arg_plans;
      local_plan.out_slots = out_slot_plans;
      pygi_invoke_plan (cb, d->has_self, nargs, &local_plan);
      plan_p = &local_plan;
    }
  PyGIInvokePlan *plan = plan_p;

  PyGIInvokeFrame frame = {
    .in_args = in_args,
    .out_args = out_args,
    .out_values = out_values,
    .out_tis = out_tis,
    .in_len_ti = in_len_ti,
    .in_len_slot = in_len_slot,
    .cleanups = cleanups,
    .n_gi_args = n_gi_args,
    .n_out_args = max_out_args,
  };

  PyObject *previous_namespace = NULL;
  if (pygi_enum_push_namespace_context (d->namespace, &previous_namespace) != 0)
    return pygi_invoke_frame_fail (&frame);
  int bind_result = pygi_invoke_bind_args (d, &frame, cb, plan, args, nargs);
  pygi_enum_pop_namespace_context (previous_namespace);
  if (bind_result != 0)
    return pygi_invoke_frame_fail (&frame);

  GIArgument ret = { 0 };
  g_autoptr (GError) error = NULL;
  if (d->compiled == NULL || !d->compiled->ffi_setup_ready)
    {
      PyErr_SetString (PyExc_RuntimeError, "ffi invoke: ffi_cif not precomputed for this callable");
      return pygi_invoke_frame_fail (&frame);
    }
  gboolean ok = pygi_callable_info_invoke (d->compiled,
                                           in_args,
                                           plan->n_in_args,
                                           out_args,
                                           plan->n_out_args,
                                           &ret,
                                           &error);
  if (!ok)
    {
      /* If the callable can throw and the GError came from the called
       * function itself (not an internal argument-mismatch), surface it
       * as a `GLib.Error` so apps' `except GLib.Error:` clauses catch
       * it - that's the pygobject contract. The internal mismatch
       * errors use the GI_INVOKE_ERROR domain; everything else is a
       * real GError from the C function. */
      if (d->compiled->ffi_throws && error != NULL
          && error->domain != g_quark_from_static_string ("gi-invoke-error-quark"))
        {
          pygi_raise_gerror (g_steal_pointer (&error));
          return pygi_invoke_frame_fail (&frame);
        }
      char shape[256];
      char msg[768];
      pygi_describe_callable_shape (cb, d->has_self, shape, sizeof (shape));
      snprintf (msg,
                sizeof (msg),
                "%s: slow ffi invoke failed for %s: %s",
                d->qualified_name,
                shape,
                error != NULL && error->message != NULL ? error->message : "unknown error");
      PyErr_SetString (PyExc_RuntimeError, msg);
      return pygi_invoke_frame_fail (&frame);
    }

  previous_namespace = NULL;
  if (pygi_enum_push_namespace_context (d->namespace, &previous_namespace) != 0)
    return pygi_invoke_frame_fail (&frame);
  PyObject *out = pygi_invoke_shape_return (cb,
                                            plan,
                                            frame.bound_self,
                                            &ret,
                                            frame.out_tis,
                                            frame.out_values,
                                            plan->n_out_args,
                                            plan->out_slots,
                                            frame.in_len_slot,
                                            frame.in_len_ti,
                                            frame.in_args);
  pygi_enum_pop_namespace_context (previous_namespace);
  /* Clean up AFTER shape_return so that alias-sensitive cases like
   * gvalue_round_trip (where ret aliases an IN arg) remain safe. */
  pygi_invoke_frame_clear (&frame);
  return out;
}
