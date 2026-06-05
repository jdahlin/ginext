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

/* invoke/return.c - shape the return value + OUT params of a finished GI
 * invocation into a single Python value (or tuple). */
#include "invoke/return.h"

#include "GObject/Boxed.h"
#include "GObject/Object-info.h"
#include "marshal/marshal.h"

#include <stddef.h>
#include <string.h>

static PyObject *
build_named_pair_namespace (const char *name0,
                            PyObject *value0,
                            const char *name1,
                            PyObject *value1)
{
  PyObject *types_mod = PyImport_ImportModule ("types");
  PyObject *sns_cls;
  PyObject *args;
  PyObject *kwargs;
  PyObject *result;

  if (types_mod == NULL)
    return NULL;
  sns_cls = PyObject_GetAttrString (types_mod, "SimpleNamespace");
  Py_DECREF (types_mod);
  if (sns_cls == NULL)
    return NULL;

  kwargs = PyDict_New ();
  if (kwargs == NULL)
    {
      Py_DECREF (sns_cls);
      return NULL;
    }
  if (PyDict_SetItemString (kwargs, name0, (PyObject *)(void *)(value0)) < 0
      || PyDict_SetItemString (kwargs, name1, (PyObject *)(void *)(value1)) < 0)
    {
      Py_DECREF (kwargs);
      Py_DECREF (sns_cls);
      return NULL;
    }

  args = PyTuple_New (0);
  if (args == NULL)
    {
      Py_DECREF (kwargs);
      Py_DECREF (sns_cls);
      return NULL;
    }
  result = PyObject_Call (sns_cls, args, kwargs);
  Py_DECREF (args);
  Py_DECREF (kwargs);
  Py_DECREF (sns_cls);
  return result != NULL ? (PyObject *)(result) : NULL;
}

static PyObject *
build_result_tuple_type (PyObject *names)
{
  PyObject *gi_mod = PyImport_ImportModule ("ginext.runtime");
  PyObject *result_tuple_base;
  PyObject *new_type;
  PyObject *result;

  if (gi_mod == NULL)
    return NULL;
  result_tuple_base = PyObject_GetAttrString (gi_mod, "ResultTuple");
  Py_DECREF (gi_mod);
  if (result_tuple_base == NULL)
    return NULL;
  new_type = PyObject_GetAttrString (result_tuple_base, "_new_type");
  Py_DECREF (result_tuple_base);
  if (new_type == NULL)
    return NULL;
  result = PyObject_CallOneArg (new_type, names);
  Py_DECREF (new_type);
  return result;
}

static PyObject *
reuse_bound_boxed_self_if_return_aliases (const PyGIInvokePlan *plan,
                                          PyObject *bound_self,
                                          GITypeInfo *ret_ti,
                                          GIArgument *ret)
{
  if (plan == NULL || !plan->has_self || bound_self == NULL || ret == NULL || ret_ti == NULL)
    return NULL;
  if (!pygi_boxed_check (bound_self) || ret->v_pointer == NULL)
    return NULL;
  if (gi_type_info_get_tag (ret_ti) != GI_TYPE_TAG_INTERFACE)
    return NULL;

  gpointer self_ptr = NULL;
  if (pygi_boxed_get (bound_self, &self_ptr) != 0)
    {
      PyErr_Clear ();
      return NULL;
    }
  if (self_ptr == NULL || self_ptr != ret->v_pointer)
    return NULL;

  return Py_NewRef (bound_self);
}

static PyObject *
fast_return_object_to_py (const PyGIInvokePlan *plan, GIArgument *ret)
{
  if (plan == NULL || ret == NULL)
    return NULL;
  if (plan->return_tag != GI_TYPE_TAG_INTERFACE)
    return NULL;
  if (plan->return_type.kind != PYGI_TYPE_OBJECT && plan->return_type.kind != PYGI_TYPE_INTERFACE)
    return NULL;
  if (ret->v_pointer == NULL && plan->return_null_is_error)
    return NULL;
  if (plan->return_type.gtype == G_TYPE_INVALID || plan->return_type.gtype == G_TYPE_NONE)
    return NULL;
  if (!g_type_is_a (plan->return_type.gtype, G_TYPE_OBJECT)
      && !g_type_is_a (plan->return_type.gtype, G_TYPE_INTERFACE))
    return NULL;

  return pygi_gobject_to_py_as_gtype ((GObject *)ret->v_pointer,
                                      plan->return_type.gtype,
                                      plan->return_transfer);
}

/* Convert one OUT slot to a Python value, pairing C-arrays with their length.
 *
 * Uses out_slots[j] to find the paired length slot directly:
 *   - paired_length_out_slot >= 0: length is another OUT slot
 *   - paired_in_length_gi_arg >= 0: length is an IN-side placeholder
 * Length pairing is captured on the slot; non-array / unpaired slots get
 * the slot with no length fields set, which routes to the scalar path.
 *
 * Pass in_len_ti/in_len_slot/in_args as NULL/NULL/NULL to suppress the
 * IN-length path (used when emitting multiple visible OUT slots in a tuple). */
static PyObject *
out_slot_to_py (GICallableInfo *cb,
                const PyGIInvokePlan *plan,
                size_t j,
                GITypeInfo **out_tis,
                GIArgument *out_values,
                const PyGIOutSlotPlan *out_slots,
                const size_t *in_len_slot,
                GITypeInfo *const *in_len_ti,
                GIArgument *in_args)
{
  const PyGIOutSlotPlan *osp = &out_slots[j];

  PyGIMarshalSlot mslot = {
    .type = out_tis[j],
    .pygi_type = (plan != NULL && osp->gi_arg_index < plan->n_gi_args)
                     ? &plan->args[osp->gi_arg_index].type
                     : NULL,
    .kind = PYGI_MARSHAL_TARGET_GIARG,
    .target.giarg = &out_values[j],
    .callable = cb,
  };
  if (osp->tag == GI_TYPE_TAG_ERROR && plan != NULL && osp->gi_arg_index < plan->n_gi_args)
    {
      mslot.transfer = plan->args[osp->gi_arg_index].transfer;
      mslot.transfer_set = true;
    }
  if ((osp->tag == GI_TYPE_TAG_GLIST || osp->tag == GI_TYPE_TAG_GSLIST) && plan != NULL
      && osp->gi_arg_index < plan->n_gi_args)
    {
      mslot.transfer = plan->args[osp->gi_arg_index].transfer;
      mslot.transfer_set = true;
    }
  if (osp->tag == GI_TYPE_TAG_GHASH && plan != NULL && osp->gi_arg_index < plan->n_gi_args)
    {
      mslot.transfer = plan->args[osp->gi_arg_index].transfer;
      mslot.transfer_set = true;
    }

  if (osp->tag == GI_TYPE_TAG_ARRAY && osp->array_type == GI_ARRAY_TYPE_C)
    {
      if (osp->paired_length_out_slot >= 0)
        {
          size_t k = (size_t)osp->paired_length_out_slot;
          mslot.length_type = out_tis[k];
          mslot.length_arg = &out_values[k];
          if (plan != NULL && osp->gi_arg_index < plan->n_gi_args)
            {
              mslot.transfer = plan->args[osp->gi_arg_index].transfer;
              mslot.transfer_set = true;
            }
        }
      else if (osp->paired_in_length_gi_arg >= 0 && in_len_ti != NULL)
        {
          size_t lgi = (size_t)osp->paired_in_length_gi_arg;
          if (in_len_slot[lgi] != SIZE_MAX && in_len_ti[lgi] != NULL)
            {
              mslot.length_type = in_len_ti[lgi];
              mslot.length_arg = &in_args[in_len_slot[lgi]];
              if (plan != NULL && osp->gi_arg_index < plan->n_gi_args)
                {
                  mslot.transfer = plan->args[osp->gi_arg_index].transfer;
                  mslot.transfer_set = true;
                }
            }
        }
    }
  return pygi_marshal_to_py (&mslot);
}

static PyObject *
build_visible_out_tuple (GICallableInfo *cb,
                         const PyGIInvokePlan *plan,
                         PyObject *prefix_item,
                         size_t n_visible,
                         GITypeInfo **out_tis,
                         GIArgument *out_values,
                         size_t out_index,
                         const PyGIOutSlotPlan *out_slots,
                         const unsigned char *out_consumed,
                         const size_t *in_len_slot,
                         GITypeInfo *const *in_len_ti,
                         GIArgument *in_args)
{
  /* `prefix_item`, when present, is an owned reference stolen into the tuple. */
  Py_ssize_t pos = 0;
  Py_ssize_t prefix_count = prefix_item != NULL ? 1 : 0;
  Py_ssize_t tuple_len = (Py_ssize_t)n_visible + prefix_count;
  PyObject *tup = PyTuple_New (tuple_len);
  PyObject *names = PyList_New (tuple_len);
  if (tup == NULL || names == NULL)
    {
      Py_XDECREF (prefix_item);
      Py_XDECREF (tup);
      Py_XDECREF (names);
      return NULL;
    }

  if (prefix_item != NULL)
    {
      PyTuple_SET_ITEM (tup, pos, prefix_item);
      Py_INCREF (Py_None);
      PyList_SET_ITEM (names, pos, Py_None);
      pos++;
    }

  for (size_t j = 0; j < out_index; j++)
    {
      if (out_consumed[j])
        continue;
      PyObject *item = out_slot_to_py (cb,
                                       plan,
                                       j,
                                       out_tis,
                                       out_values,
                                       out_slots,
                                       in_len_slot,
                                       in_len_ti,
                                       in_args);
      if (item == NULL)
        {
          Py_DECREF (tup);
          Py_DECREF (names);
          return NULL;
        }
      PyTuple_SET_ITEM (tup, pos++, item);
      if (out_slots[j].arg_name != NULL)
        {
          PyObject *name = PyUnicode_FromString (out_slots[j].arg_name);
          if (name == NULL)
            {
              Py_DECREF (tup);
              Py_DECREF (names);
              return NULL;
            }
          PyList_SET_ITEM (names, pos - 1, name);
        }
      else
        {
          Py_INCREF (Py_None);
          PyList_SET_ITEM (names, pos - 1, Py_None);
        }
    }

  PyObject *tuple_type = build_result_tuple_type (names);
  Py_DECREF (names);
  if (tuple_type == NULL)
    {
      Py_DECREF (tup);
      return NULL;
    }

  PyObject *result = PyObject_CallOneArg (tuple_type, tup);
  Py_DECREF (tuple_type);
  Py_DECREF (tup);
  return result;
}

PyObject *
pygi_invoke_shape_return (GICallableInfo *cb,
                          const PyGIInvokePlan *plan,
                          PyObject *bound_self,
                          GIArgument *ret,
                          GITypeInfo **out_tis,
                          GIArgument *out_values,
                          size_t out_index,
                          const PyGIOutSlotPlan *out_slots,
                          const size_t *in_len_slot,
                          GITypeInfo *const *in_len_ti,
                          GIArgument *in_args)
{
  g_return_val_if_fail (cb != NULL, NULL);
  g_return_val_if_fail (GI_IS_CALLABLE_INFO (cb), NULL);
  g_return_val_if_fail (plan != NULL, NULL);
  GITypeInfo *ret_ti = plan->return_ti;
  g_return_val_if_fail (ret_ti != NULL, NULL);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ret_ti), NULL);
  GITypeTag ret_tag = plan->return_tag;
  PyObject *out = NULL;

  /* out_consumed[] starts as a mutable copy of consumed_by_array so the
   * ret_array_len_slot case can additionally mark one slot consumed. */
  unsigned char *out_consumed = (unsigned char *)alloca (out_index ? out_index : 1u);
  size_t n_visible = 0;
  for (size_t j = 0; j < out_index; j++)
    {
      out_consumed[j] = out_slots[j].consumed_by_array ? 1u : 0u;
      if (!out_consumed[j])
        n_visible++;
    }

  if (out_index == 0)
    {
      /* No OUT params: return the return value as-is. */
      out = reuse_bound_boxed_self_if_return_aliases (plan, bound_self, ret_ti, ret);
      if (out != NULL)
        return out;
      out = fast_return_object_to_py (plan, ret);
      if (out != NULL)
        return out;
      out = pygi_marshal_to_py (
          &(PyGIMarshalSlot){ .type = ret_ti,
                              .pygi_type = plan != NULL ? &plan->return_type : NULL,
                              .transfer = plan->return_transfer,
                              .transfer_set = true,
                              .kind = PYGI_MARSHAL_TARGET_GIARG,
                              .target.giarg = ret,
                              .callable = cb });
      if (out != NULL && out == Py_None && plan->return_null_is_error && ret->v_pointer == NULL)
        {
          Py_DECREF (out);
          PyErr_Format (PyExc_RuntimeError,
                        "%s returned NULL for a non-nullable %s result",
                        gi_base_info_get_name ((GIBaseInfo *)cb),
                        gi_type_tag_to_string (ret_tag));
          return NULL;
        }
    }
  else if (ret_tag == GI_TYPE_TAG_VOID)
    {
      /* Void return: return the single visible OUT value or tuple. */
      if (n_visible == 1)
        {
          for (size_t j = 0; j < out_index; j++)
            {
              if (out_consumed[j])
                continue;
              out = out_slot_to_py (cb,
                                    plan,
                                    j,
                                    out_tis,
                                    out_values,
                                    out_slots,
                                    in_len_slot,
                                    in_len_ti,
                                    in_args);
              break;
            }
        }
      else
        {
          /* n_visible >= 2: width/height pair is special-cased to a
           * .width / .height namespace (matches Gtk.Widget-style APIs);
           * everything else gets a plain tuple in declaration order. */
          if (n_visible == 2)
            {
              size_t visible[2];
              size_t pos = 0;
              for (size_t j = 0; j < out_index && pos < 2; j++)
                {
                  if (!out_consumed[j])
                    visible[pos++] = j;
                }
              if (pos == 2 && out_slots[visible[0]].arg_name != NULL
                  && out_slots[visible[1]].arg_name != NULL
                  && strcmp (out_slots[visible[0]].arg_name, "width") == 0
                  && strcmp (out_slots[visible[1]].arg_name, "height") == 0)
                {
                  PyObject *width = out_slot_to_py (cb,
                                                    plan,
                                                    visible[0],
                                                    out_tis,
                                                    out_values,
                                                    out_slots,
                                                    NULL,
                                                    NULL,
                                                    NULL);
                  if (width == NULL)
                    return NULL;
                  PyObject *height = out_slot_to_py (cb,
                                                     plan,
                                                     visible[1],
                                                     out_tis,
                                                     out_values,
                                                     out_slots,
                                                     NULL,
                                                     NULL,
                                                     NULL);
                  if (height == NULL)
                    {
                      Py_XDECREF (width);
                      return NULL;
                    }
                  out = build_named_pair_namespace ("width", width, "height", height);
                  Py_XDECREF (height);
                  Py_XDECREF (width);
                  if (!(out == NULL))
                    return out;
                }
            }
          out = build_visible_out_tuple (cb,
                                         plan,
                                         NULL,
                                         n_visible,
                                         out_tis,
                                         out_values,
                                         out_index,
                                         out_slots,
                                         out_consumed,
                                         NULL,
                                         NULL,
                                         NULL);
        }
    }
  else if (ret_tag == GI_TYPE_TAG_ARRAY && out_index == 1)
    {
      /* C array return whose length is carried by the single OUT param. */
      out = pygi_marshal_to_py (
          &(PyGIMarshalSlot){ .type = ret_ti,
                              .pygi_type = plan != NULL ? &plan->return_type : NULL,
                              .transfer = plan->return_transfer,
                              .transfer_set = true,
                              .kind = PYGI_MARSHAL_TARGET_GIARG,
                              .target.giarg = ret,
                              .length_type = out_tis[0],
                              .length_arg = &out_values[0],
                              .callable = cb });
    }
  else if (ret_tag == GI_TYPE_TAG_BOOLEAN && !plan->can_throw_gerror && n_visible == 0)
    {
      /* Plain success/failure signal - no OUT params, just hand back
       * the bool. */
      out = pygi_marshal_to_py (
          &(PyGIMarshalSlot){ .type = ret_ti,
                              .pygi_type = plan != NULL ? &plan->return_type : NULL,
                              .kind = PYGI_MARSHAL_TARGET_GIARG,
                              .target.giarg = ret,
                              .callable = cb });
    }
  else if (ret_tag == GI_TYPE_TAG_BOOLEAN)
    {
      /* PyGObject-shape: `(success_bool, *out_args)`. Keep IN-side
       * length pairing available here for bool APIs returning C-array OUTs. */
      if (gi_callable_info_skip_return (cb))
        {
          if (n_visible == 1)
            {
              for (size_t j = 0; j < out_index; j++)
                {
                  if (out_consumed[j])
                    continue;
                  out = out_slot_to_py (cb,
                                        plan,
                                        j,
                                        out_tis,
                                        out_values,
                                        out_slots,
                                        in_len_slot,
                                        in_len_ti,
                                        in_args);
                  break;
                }
            }
          else
            {
              out = build_visible_out_tuple (cb,
                                             plan,
                                             NULL,
                                             n_visible,
                                             out_tis,
                                             out_values,
                                             out_index,
                                             out_slots,
                                             out_consumed,
                                             in_len_slot,
                                             in_len_ti,
                                             in_args);
            }
        }
      else
        {
          PyObject *bool_item = pygi_marshal_to_py (
              &(PyGIMarshalSlot){ .type = ret_ti,
                                  .pygi_type = plan != NULL ? &plan->return_type : NULL,
                                  .kind = PYGI_MARSHAL_TARGET_GIARG,
                                  .target.giarg = ret,
                                  .callable = cb });
          if (bool_item == NULL)
            return NULL;
          out = build_visible_out_tuple (cb,
                                         plan,
                                         bool_item,
                                         n_visible,
                                         out_tis,
                                         out_values,
                                         out_index,
                                         out_slots,
                                         out_consumed,
                                         in_len_slot,
                                         in_len_ti,
                                         in_args);
        }
    }
  else
    {
      /* Non-void, non-bool return with OUT params.
       * If the return is a C-array whose length is an OUT slot, fold that
       * OUT slot into the array conversion (mark consumed). */
      size_t ret_array_len_slot = SIZE_MAX;
      if (ret_tag == GI_TYPE_TAG_ARRAY && plan->return_array_type == GI_ARRAY_TYPE_C
          && plan->return_array_length_arg >= 0)
        {
          size_t len_arg_idx = (size_t)plan->return_array_length_arg;
          for (size_t k = 0; k < out_index; k++)
            {
              if (out_slots[k].gi_arg_index == len_arg_idx)
                {
                  ret_array_len_slot = k;
                  if (!out_consumed[k])
                    {
                      out_consumed[k] = 1;
                      n_visible--;
                    }
                  break;
                }
            }
        }
      PyObject *ret_py;
      if (ret_array_len_slot != SIZE_MAX)
        ret_py = pygi_marshal_to_py (
            &(PyGIMarshalSlot){ .type = ret_ti,
                                .pygi_type = plan != NULL ? &plan->return_type : NULL,
                                .transfer = plan->return_transfer,
                                .transfer_set = true,
                                .kind = PYGI_MARSHAL_TARGET_GIARG,
                                .target.giarg = ret,
                                .length_type = out_tis[ret_array_len_slot],
                                .length_arg = &out_values[ret_array_len_slot],
                                .callable = cb });
      else
        {
          ret_py = reuse_bound_boxed_self_if_return_aliases (plan, bound_self, ret_ti, ret);
          if (ret_py == NULL)
            {
              ret_py = fast_return_object_to_py (plan, ret);
              if (ret_py == NULL)
                ret_py = pygi_marshal_to_py (
                    &(PyGIMarshalSlot){ .type = ret_ti,
                                        .pygi_type = plan != NULL ? &plan->return_type : NULL,
                                        .transfer = plan->return_transfer,
                                        .transfer_set = true,
                                        .kind = PYGI_MARSHAL_TARGET_GIARG,
                                        .target.giarg = ret,
                                        .callable = cb });
            }
        }

      if (ret_py != NULL)
        out = build_visible_out_tuple (cb,
                                       plan,
                                       ret_py,
                                       n_visible,
                                       out_tis,
                                       out_values,
                                       out_index,
                                       out_slots,
                                       out_consumed,
                                       NULL,
                                       NULL,
                                       NULL);
    }

  return out;
}
