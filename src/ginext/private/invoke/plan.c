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

/* invoke/plan.c - descriptor-time callable analysis for GI invocation. */
#include "invoke/plan.h"

#include "runtime/type-info.h" /* gi_base_info_is_named */
#include <girepository/girepository.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <sys/types.h>

/* Resolve a per-arg PyGIMarshalKind from its tag + (for INTERFACE)
 * the resolved interface kind. Anything we can't pin down stays GENERIC
 * and the binder falls through to the slow tag-tree walk. */
static PyGIMarshalKind
resolve_marshal_kind (const PyGIArgPlan *ap, GITransfer transfer)
{
  if (ap->direction != GI_DIRECTION_IN || ap->role != PYGI_ARG_ROLE_NORMAL)
    return PYGI_MARSHAL_GENERIC;
  switch (ap->type.kind)
    {
    case PYGI_TYPE_BOOLEAN:
      return PYGI_MARSHAL_BOOL;
    case PYGI_TYPE_INT8:
      return PYGI_MARSHAL_INT8;
    case PYGI_TYPE_UINT8:
      return PYGI_MARSHAL_UINT8;
    case PYGI_TYPE_INT16:
      return PYGI_MARSHAL_INT16;
    case PYGI_TYPE_UINT16:
      return PYGI_MARSHAL_UINT16;
    case PYGI_TYPE_INT32:
      return PYGI_MARSHAL_INT32;
    case PYGI_TYPE_UINT32:
      return PYGI_MARSHAL_UINT32;
    case PYGI_TYPE_INT64:
      return PYGI_MARSHAL_INT64;
    case PYGI_TYPE_UINT64:
      return PYGI_MARSHAL_UINT64;
    case PYGI_TYPE_FLOAT:
      return PYGI_MARSHAL_FLOAT;
    case PYGI_TYPE_DOUBLE:
      return PYGI_MARSHAL_DOUBLE;
    case PYGI_TYPE_GTYPE:
      return PYGI_MARSHAL_GTYPE;
    case PYGI_TYPE_UTF8:
    case PYGI_TYPE_FILENAME:
      return transfer == GI_TRANSFER_EVERYTHING ? PYGI_MARSHAL_UTF8_OWNED : PYGI_MARSHAL_UTF8;
    case PYGI_TYPE_OBJECT:
    case PYGI_TYPE_INTERFACE:
      if (gi_type_info_is_param_spec (ap->cached_ti))
        return PYGI_MARSHAL_GENERIC;
      return transfer == GI_TRANSFER_EVERYTHING ? PYGI_MARSHAL_GOBJECT_OWNED : PYGI_MARSHAL_GOBJECT;
    case PYGI_TYPE_ENUM:
      return PYGI_MARSHAL_ENUM_INT32;
    case PYGI_TYPE_FLAGS:
      return PYGI_MARSHAL_FLAGS_UINT32;
    case PYGI_TYPE_BOXED:
      {
        GIBaseInfo *iface = gi_type_info_get_interface (ap->cached_ti);
        if (iface == NULL)
          return PYGI_MARSHAL_GENERIC;
        PyGIMarshalKind kind = PYGI_MARSHAL_GENERIC;
        if (gi_base_info_is_named (iface, "GLib", "Bytes"))
          kind = PYGI_MARSHAL_GBYTES;
        gi_base_info_unref (iface);
        return kind;
      }
    default:
      return PYGI_MARSHAL_GENERIC;
    }
}

void
pygi_invoke_plan (GICallableInfo *cb, int has_self, size_t nargs, PyGIInvokePlan *plan)
{
  g_return_if_fail (cb != NULL);
  g_return_if_fail (GI_IS_CALLABLE_INFO (cb));
  g_return_if_fail (plan != NULL);
  g_return_if_fail (plan->args != NULL);
  g_return_if_fail (plan->out_slots != NULL);

  plan->callable = cb;
  plan->has_self = has_self;
  plan->self_gtype = G_TYPE_INVALID;
  plan->instance_transfer = GI_TRANSFER_NOTHING;
  if (has_self && GI_IS_FUNCTION_INFO (cb))
    {
      /* gi_base_info_get_container returns a borrowed reference owned
       * by the parent typelib — don't unref. */
      GIBaseInfo *container = gi_base_info_get_container ((GIBaseInfo *)cb);
      if (container != NULL && GI_IS_REGISTERED_TYPE_INFO (container))
        plan->self_gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)container);
      plan->instance_transfer = gi_callable_info_get_instance_ownership_transfer (cb);
    }
  size_t n = gi_callable_info_get_n_args (cb);
  plan->n_gi_args = n;
  plan->return_array_length_arg = -1;
  plan->return_transfer = gi_callable_info_get_caller_owns (cb);
  plan->return_null_is_error = false;
  plan->can_throw_gerror = gi_callable_info_can_throw_gerror (cb);
  {
    plan->return_ti = gi_callable_info_get_return_type (cb);
    if (plan->return_ti != NULL)
      {
        pygi_type_from_gi (plan->return_ti, &plan->return_type);
        plan->return_type.nullable = gi_callable_info_may_return_null (cb);
        if (GI_IS_FUNCTION_INFO (cb))
          {
            GIFunctionInfoFlags flags = gi_function_info_get_flags ((GIFunctionInfo *)cb);
            plan->return_null_is_error
                = (flags & GI_FUNCTION_IS_CONSTRUCTOR) != 0 && !plan->return_type.nullable;
          }
        plan->return_tag = gi_type_info_get_tag (plan->return_ti);
        plan->return_array_type = plan->return_tag == GI_TYPE_TAG_ARRAY
                                      ? gi_type_info_get_array_type (plan->return_ti)
                                      : GI_ARRAY_TYPE_C;
        if (plan->return_tag == GI_TYPE_TAG_ARRAY && plan->return_array_type == GI_ARRAY_TYPE_C)
          {
            unsigned int len_arg_idx = 0;
            if (gi_type_info_get_array_length_index (plan->return_ti, &len_arg_idx))
              plan->return_array_length_arg = (ssize_t)len_arg_idx;
          }
      }
  }

  /* -- Phase 1: basic per-arg metadata ----------------------------------- */
  /* Cache transfer-full GIArgInfo + GITypeInfo on the plan. Each
   * gi_callable_info_get_arg / gi_arg_info_get_type_info call
   * allocates a fresh GIBaseInfo via gi_base_info_new and refs the
   * parent typelib, and the unref drops back through atomics. Doing
   * this once at descriptor build time lets the binder/return path
   * read straight from the plan, eliminating the entire
   * gi_base_info_unref hot-spot. */
  for (size_t i = 0; i < n; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];
      GIArgInfo *ai = gi_callable_info_get_arg (cb, (guint)i);
      GITypeInfo *ti = gi_arg_info_get_type_info (ai);

      ap->gi_index = (guint)i;
      ap->direction = gi_arg_info_get_direction (ai);
      ap->transfer = gi_arg_info_get_ownership_transfer (ai);
      ap->tag = gi_type_info_get_tag (ti);
      ap->array_type
          = (ap->tag == GI_TYPE_TAG_ARRAY) ? gi_type_info_get_array_type (ti) : GI_ARRAY_TYPE_C;
      ap->storage_tag = gi_type_info_storage_tag (ti);
      ap->nullable_or_optional = gi_arg_info_may_be_null (ai) || gi_arg_info_is_optional (ai);
      ap->caller_allocates = gi_arg_info_is_caller_allocates (ai);
      pygi_type_from_gi (ti, &ap->type);
      ap->type.transfer = ap->transfer;
      ap->type.nullable = ap->nullable_or_optional;
      ap->type.caller_allocates = ap->caller_allocates;
      ap->role = PYGI_ARG_ROLE_NORMAL;
      ap->py_arg_index = -1;
      ap->in_slot = -1;
      ap->out_slot = -1;
      ap->length_arg = -1;
      ap->owner_array_arg = -1;
      ap->owner_callback_arg = -1;
      ap->length_kind = PYGI_LENGTH_NONE;
      /* Owning refs - released by pygi_invoke_plan_clear (plan owns them). */
      ap->cached_ai = ai;
      ap->cached_ti = ti;
      ap->marshal_kind = PYGI_MARSHAL_GENERIC;

      if (ap->tag == GI_TYPE_TAG_ARRAY)
        {
          ap->array_elem_ti = gi_type_info_get_param_type (ti, 0);
          if (ap->array_elem_ti != NULL)
            {
              ap->array_elem_tag = gi_type_info_get_tag (ap->array_elem_ti);
              ap->array_elem_size = gi_type_info_array_element_size (ap->array_elem_ti);
              if (ap->array_elem_size == 0
                  && (ap->array_elem_tag == GI_TYPE_TAG_UTF8
                      || ap->array_elem_tag == GI_TYPE_TAG_FILENAME))
                ap->array_elem_size = sizeof (gchar *);
            }
          ap->array_has_fixed_size = gi_type_info_get_array_fixed_size (ti, &ap->array_fixed_size);
        }

      if (ap->caller_allocates)
        {
          ap->caller_allocates_gvalue = gi_type_info_is_gvalue (ti);
          if (ap->tag == GI_TYPE_TAG_INTERFACE)
            {
              g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
              if (iface && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
                ap->caller_allocates_size = gi_struct_or_union_size (iface);
            }
        }
    }

  /* -- Phase 2: closure / destroy companions ------------------------------
   *
   * PyGObject contract for callback parameters:
   *   - user_data_free_func (destroy, scope="async"): never user-supplied,
   *     pygir manages the lifetime. Always elide from the Python API.
   *   - user_data (closure): optional. If the caller passes it, surface
   *     the slot; if omitted, elide and pass NULL to C.
   *
   * The plan walks the args twice: first to tag the slots and record
   * whether each is "destroy" (always-elided) or "closure" (conditionally
   * elided). Then it checks the caller's arity to decide whether the
   * closure slots get elided too.
   */
  {
    size_t n_destroy = 0; /* always-elided slots */
    size_t n_closure_max = 0; /* elidable slots if arity allows */
    /* Only follow closure/destroy annotations on the *callback*
     * param (which has both `closure=` and optionally `destroy=`).
     * The user_data_free param also carries a back-pointer
     * (`destroy="0"`) in some GIRs (e.g. log_set_writer_func), and
     * following that from the wrong end would elide the callback
     * itself. The forward-pointer source always has a closure_index;
     * the back-pointer source doesn't. Gate on closure_index. */
    for (size_t i = 0; i < n; i++)
      {
        GIArgInfo *ai = plan->args[i].cached_ai;
        unsigned int closure_idx = 0;
        gboolean has_closure = gi_arg_info_get_closure_index (ai, &closure_idx) && closure_idx < n
                               && closure_idx != i;
        unsigned int destroy_idx = 0;
        /* Only follow forward destroy_idx pointers. Some GIRs (e.g.
         * GLib.log_set_writer_func) emit a back-pointer destroy="0" on
         * the destroy_notify arg itself; following it would elide the
         * callback. The forward-source (the callback) always points
         * forward, so the forward check is sufficient. */
        gboolean has_destroy = gi_arg_info_get_destroy_index (ai, &destroy_idx) && destroy_idx < n
                               && destroy_idx > i;
        if (!has_closure && !has_destroy)
          continue;

        if (has_closure)
          {
            if (plan->args[closure_idx].role == PYGI_ARG_ROLE_NORMAL)
              {
                plan->args[closure_idx].role = PYGI_ARG_ROLE_CLOSURE_DESTROY;
                n_closure_max++;
              }
            /* Back-pointer to the callback - bind.c uses it to stash
             * the Python user_data on the closure cookie; FFI / JIT use
             * it to un-elide on user-supplied user_data. */
            plan->args[closure_idx].owner_callback_arg = (ssize_t)i;
          }

        if (has_destroy)
          {
            if (plan->args[destroy_idx].role != PYGI_ARG_ROLE_CLOSURE_DESTROY)
              {
                plan->args[destroy_idx].role = PYGI_ARG_ROLE_CLOSURE_DESTROY;
                plan->args[destroy_idx].owner_callback_arg = -2 - (ssize_t)i;
                n_destroy++;
              }
          }
      }
    /* Validate: with `n_destroy` always-elided slots and up to
     * `n_closure_max` conditionally-elided closure slots, see whether
     * the caller's arity wants the closures elided too.
     *
     *   omitted user_data:  nargs + n_destroy + n_closure_max == visible
     *   supplied user_data: nargs + n_destroy                  == visible
     *
     * If neither matches, abandon the detection and let the generic
     * bind path surface the standard "wrong arity" error.
     */
    if ((n_destroy > 0 || n_closure_max > 0) && nargs != SIZE_MAX)
      {
        size_t n_in_visible = 0;
        for (size_t i = 0; i < n; i++)
          {
            if (plan->args[i].direction == GI_DIRECTION_OUT)
              continue;
            n_in_visible++;
          }
        size_t self_off = has_self ? 1u : 0u;
        size_t want = n_in_visible + self_off;
        if (nargs + n_destroy + n_closure_max == want)
          {
            /* both destroy and closure elided - keep as tagged. */
          }
        else if (nargs + n_destroy == want)
          {
            /* User supplied user_data - un-elide the closure slots. */
            for (size_t i = 0; i < n; i++)
              if (plan->args[i].role == PYGI_ARG_ROLE_CLOSURE_DESTROY
                  && plan->args[i].owner_callback_arg >= 0)
                plan->args[i].role = PYGI_ARG_ROLE_NORMAL;
          }
        else
          {
            /* Neither shape matches - abandon both. */
            for (size_t i = 0; i < n; i++)
              if (plan->args[i].role == PYGI_ARG_ROLE_CLOSURE_DESTROY)
                plan->args[i].role = PYGI_ARG_ROLE_NORMAL;
          }
      }
    /* For cached descriptors (nargs == SIZE_MAX), keep closure companions
     * hidden by default. invoke.c exposes them on a per-call plan copy when
     * the caller supplies extra arguments explicitly. */
  }

  /* -- Phase 3: C-array length relationships ------------------------------ */
  for (size_t k = 0; k < n; k++)
    {
      PyGIArgPlan *ap = &plan->args[k];
      if (ap->tag != GI_TYPE_TAG_ARRAY)
        continue;

      GIArgInfo *ai = ap->cached_ai;
      GITypeInfo *ti = ap->cached_ti;
      (void)ai;

      if (ap->array_type != GI_ARRAY_TYPE_C)
        {
          /* GArray / GPtrArray / GByteArray: no explicit length arg. */
          ap->length_kind = PYGI_LENGTH_NONE;
          continue;
        }

      size_t fixed_size = 0;
      unsigned int li = 0;
      if (gi_type_info_get_array_length_index (ti, &li) && (size_t)li < n)
        {
          /* Mark the length arg. */
          PyGIArgPlan *lap = &plan->args[li];
          if (lap->role == PYGI_ARG_ROLE_NORMAL)
            {
              lap->role = PYGI_ARG_ROLE_ARRAY_LENGTH;
              lap->owner_array_arg = (ssize_t)k;
            }
          ap->length_arg = (ssize_t)li;
          if ((size_t)li == k + 1)
            ap->length_kind = PYGI_LENGTH_AFTER_ARRAY;
          else
            ap->length_kind = PYGI_LENGTH_BEFORE_ARRAY;
          /* Caller-allocates flat C-array + paired length: by C convention
           * the caller passes the length BY VALUE (it's how the caller
           * tells C how big the buffer is). Some GIRs annotate the length
           * as `direction=out` anyway - that's a metadata bug. Without
           * this rewrite gi_function_info_invoke would pass &out_args[i]
           * for the length, and C would dereference an address as a
           * gsize and memset gigabytes (cf. test_array_struct_out_caller_alloc).
           * Force the length to IN-direction here; the bind layer derives
           * the value from the array's allocated element count. */
          if (ap->caller_allocates && ap->direction == GI_DIRECTION_OUT
              && lap->direction == GI_DIRECTION_OUT)
            lap->direction = GI_DIRECTION_IN;
        }
      else if (gi_type_info_get_array_fixed_size (ti, &fixed_size))
        {
          ap->length_kind = PYGI_LENGTH_FIXED;
        }
      else if (gi_type_info_is_zero_terminated (ti))
        {
          ap->length_kind = PYGI_LENGTH_ZERO_TERMINATED;
        }
      else
        {
          ap->length_kind = PYGI_LENGTH_NONE;
        }
    }

  /* -- Phase 4: py_arg_index ---------------------------------------------- */
  /* self occupies Python index 0 when has_self; GI args start at 1. */
  ssize_t py_cursor = has_self ? 1 : 0;
  for (size_t i = 0; i < n; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];

      if (ap->role == PYGI_ARG_ROLE_CLOSURE_DESTROY || ap->role == PYGI_ARG_ROLE_ARRAY_LENGTH)
        {
          ap->consumes_py_arg = false;
          ap->py_arg_index = -1;
          continue;
        }
      if (ap->direction == GI_DIRECTION_OUT)
        {
          ap->consumes_py_arg = false;
          ap->py_arg_index = -1;
          continue;
        }
      /* IN and INOUT NORMAL args consume a Python arg. */
      ap->consumes_py_arg = true;
      ap->py_arg_index = py_cursor++;
    }
  plan->n_py_args = (size_t)py_cursor;

  /* -- Phase 5: in_slot / out_slot simulation ----------------------------- */
  /* Simulate the binding walk to assign every arg its in_args / out_args
   * index.  The walk order mirrors invoke-bind.c exactly so that the plan
   * and the binder always agree. */
  ssize_t in_cursor = has_self ? 1 : 0;
  ssize_t out_cursor = 0;

  for (size_t i = 0; i < n; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];

      /* -- closure/destroy companion: one in_args slot, no out slot -- */
      if (ap->role == PYGI_ARG_ROLE_CLOSURE_DESTROY)
        {
          ap->in_slot = in_cursor++;
          ap->out_slot = -1;
          continue;
        }

      /* -- array length arg -- */
      if (ap->role == PYGI_ARG_ROLE_ARRAY_LENGTH)
        {
          PyGIArgPlan *owner = &plan->args[ap->owner_array_arg];

          if (ap->direction == GI_DIRECTION_IN)
            {
              if (owner->length_kind == PYGI_LENGTH_BEFORE_ARRAY)
                {
                  /* in_len_skip: pre-allocated placeholder filled later. */
                  ap->in_slot = in_cursor++;
                  ap->out_slot = -1;
                }
              else if (owner->direction == GI_DIRECTION_OUT && owner->caller_allocates)
                {
                  /* Caller-allocates OUT array with rewritten-to-IN length:
                   * the owner array doesn't pre-assign in_slot for the length
                   * (its OUT branch handles only its own out_slot), so
                   * allocate one here. The bind layer fills it from the
                   * array's allocated element count. */
                  ap->in_slot = in_cursor++;
                  ap->out_slot = -1;
                }
              else
                {
                  /* AFTER_ARRAY: already assigned when the array was processed. */
                  ap->out_slot = -1;
                }
            }
          else if (ap->direction == GI_DIRECTION_INOUT)
            {
              if (owner->length_kind == PYGI_LENGTH_BEFORE_ARRAY)
                {
                  /* defer_inout_length: storage pointer placed in in_args,
                   * result written to out_args. */
                  ap->in_slot = in_cursor++;
                  ap->out_slot = out_cursor++;
                }
              else
                {
                  /* AFTER_ARRAY: already assigned when the INOUT array was processed. */
                }
            }
          else if (ap->direction == GI_DIRECTION_OUT)
            {
              /* Pure OUT length: gets its own out slot regardless of position.
               * AFTER_ARRAY processing does not pre-assign OUT lengths - each
               * OUT arg in the pair is slotted independently. */
              ap->in_slot = -1;
              ap->out_slot = out_cursor++;
            }
          continue;
        }

      /* -- OUT arg -- */
      if (ap->direction == GI_DIRECTION_OUT)
        {
          /* Pure OUT args have no in_args entry (not even for caller-allocates). */
          ap->in_slot = -1;
          ap->out_slot = out_cursor++;
          continue;
        }

      /* -- INOUT arg -- */
      if (ap->direction == GI_DIRECTION_INOUT)
        {
          if (ap->caller_allocates)
            {
              /* caller-allocates INOUT: buffer in out_args, no in_args entry. */
              ap->in_slot = -1;
              ap->out_slot = out_cursor++;
              continue;
            }
          if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
              && ap->length_kind == PYGI_LENGTH_AFTER_ARRAY)
            {
              /* INOUT C-array with INOUT length immediately following.
               * Both slots are assigned together; length slot is pre-computed so
               * the binder can skip the length arg when it encounters it. */
              ssize_t li = ap->length_arg;
              PyGIArgPlan *lap = &plan->args[li];
              ap->in_slot = in_cursor;
              ap->out_slot = out_cursor;
              lap->in_slot = in_cursor + 1;
              lap->out_slot = out_cursor + 1;
              in_cursor += 2;
              out_cursor += 2;
              continue;
            }
          /* Generic INOUT: storage pointer in in_args, result in out_args. */
          ap->in_slot = in_cursor++;
          ap->out_slot = out_cursor++;
          continue;
        }

      /* -- IN arg -- */
      if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
          && ap->length_kind == PYGI_LENGTH_AFTER_ARRAY)
        {
          /* IN C-array with IN length immediately following.
           * Array at in_cursor, length at in_cursor+1; both set now. */
          ssize_t li = ap->length_arg;
          PyGIArgPlan *lap = &plan->args[li];
          ap->in_slot = in_cursor;
          lap->in_slot = in_cursor + 1;
          in_cursor += 2;
          ap->out_slot = -1;
          continue;
        }
      /* All other IN args (scalar, GArray, GList, callback, BEFORE_ARRAY arrays). */
      ap->in_slot = in_cursor++;
      ap->out_slot = -1;
    }

  plan->n_in_args = (size_t)in_cursor;
  plan->n_out_args = (size_t)out_cursor;

  /* -- Phase 6: out_slots[] - reverse map and visibility ---------------- */
  /* Build out_slots[out_slot_index] from the per-arg out_slot assignments. */
  for (size_t i = 0; i < n; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];
      if (ap->out_slot < 0)
        continue;
      PyGIOutSlotPlan *osp = &plan->out_slots[ap->out_slot];
      osp->gi_arg_index = (guint)i;
      osp->visible = true;
      osp->consumed_by_array = false;
      osp->caller_allocates = ap->caller_allocates;
      osp->paired_length_out_slot = -1;
      osp->paired_length_in_slot = -1;
      osp->paired_in_length_gi_arg = -1;
      osp->tag = ap->tag;
      osp->array_type = ap->array_type;
      osp->arg_name = gi_base_info_get_name ((GIBaseInfo *)ap->cached_ai);
    }

  /* Mark length slots consumed by array slots; set pairing. */
  for (size_t i = 0; i < n; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];
      if (ap->out_slot < 0)
        continue;
      if (ap->tag != GI_TYPE_TAG_ARRAY || ap->array_type != GI_ARRAY_TYPE_C)
        continue;
      ssize_t li = ap->length_arg;
      if (li < 0)
        continue;
      PyGIArgPlan *lap = &plan->args[li];
      if (lap->out_slot >= 0)
        {
          /* Length is also an OUT slot: pair and mark consumed. */
          plan->out_slots[ap->out_slot].paired_length_out_slot = lap->out_slot;
          plan->out_slots[lap->out_slot].consumed_by_array = true;
          plan->out_slots[lap->out_slot].visible = false;
        }
      else if (lap->in_slot >= 0)
        {
          /* Length is only in in_args (IN-side placeholder for an OUT array). */
          plan->out_slots[ap->out_slot].paired_length_in_slot = lap->in_slot;
          plan->out_slots[ap->out_slot].paired_in_length_gi_arg = li;
        }
    }

  /* -- Phase 7: pre-resolve per-arg marshal kind (after roles finalised) -- */
  for (size_t i = 0; i < n; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];
      ap->marshal_kind = resolve_marshal_kind (ap, ap->transfer);
    }
}

void
pygi_invoke_plan_clear (PyGIInvokePlan *plan)
{
  if (plan == NULL || plan->args == NULL)
    return;
  for (size_t i = 0; i < plan->n_gi_args; i++)
    {
      PyGIArgPlan *ap = &plan->args[i];
      if (ap->cached_ti != NULL)
        {
          gi_base_info_unref ((GIBaseInfo *)ap->cached_ti);
          ap->cached_ti = NULL;
        }
      if (ap->array_elem_ti != NULL)
        {
          gi_base_info_unref ((GIBaseInfo *)ap->array_elem_ti);
          ap->array_elem_ti = NULL;
        }
      if (ap->cached_ai != NULL)
        {
          gi_base_info_unref ((GIBaseInfo *)ap->cached_ai);
          ap->cached_ai = NULL;
        }
    }
  if (plan->return_ti != NULL)
    {
      gi_base_info_unref ((GIBaseInfo *)plan->return_ti);
      plan->return_ti = NULL;
    }
}
