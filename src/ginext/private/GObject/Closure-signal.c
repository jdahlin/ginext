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

/* GClosure subclass for Python signal handlers
 * (ported from src/goi/_goi/GObject/Closure-signal.c). The marshal decodes
 * each GValue arg via the regular pygi_argument_to_py /
 * pygi_gvalue_value_to_py paths and calls the Python callable; the return
 * value is written back into the signal's return GValue when applicable. */
#include "Closure.h"

#include "GLib/Array.h"
#include "Closure-record.h"
#include "marshal/gvalue.h"
#include "marshal/marshal.h"
#include "marshal/c-array.h"
#include "runtime/class-registry.h"
#include "GObject/Boxed.h"
#include "GObject/Object-info.h"

typedef struct
{
  GClosure base;
  PyObject *callable; /* New ref. */
  PyGIClosureRecord *record;
  /* GISignalInfo for this signal, or NULL when the closure is used as
   * a callback (marshal/marshal.c::pygi_closure_new path) where no
   * signal context exists. Owned reference: gi_base_info_unref on
   * finalize. When non-NULL the marshal can do GIR-aware element
   * wrapping for container-typed args (GPtrArray<T> etc.) — without
   * it, pygi_gvalue_value_to_py returns the bare boxed wrapper which
   * apps can't iterate. */
  GICallableInfo *signal_info;
  /* When TRUE, the marshal disconnects the handler before invoking the
   * Python callable so re-entrant emissions inside the callback don't
   * see the handler again. */
  gboolean once;
  /* Max number of runtime signal args to pass to Python. -1 means pass
   * everything. This is computed by the Python connect layer because it
   * knows about scoped/user-data adapters; the C marshal only enforces
   * the already-decided prefix. */
  int signal_arg_limit;
} PyGIPyClosure;

static int
py_to_existing_gvalue (PyObject *obj, GValue *value, GICallableInfo *signal_info)
{
  if (value == NULL)
    return 0;

  GType target = G_VALUE_TYPE (value);
  if (target == 0)
    {
      PyErr_SetString (PyExc_SystemError, "signal return GValue is not initialized");
      return -1;
    }

  if (target == G_TYPE_ARRAY && signal_info != NULL)
    {
      g_autoptr (GITypeInfo) return_ti = gi_callable_info_get_return_type (signal_info);
      if (return_ti != NULL && gi_type_info_get_tag (return_ti) == GI_TYPE_TAG_ARRAY)
        {
          GIArgument array_arg;
          PyGIArgCleanup cleanup = { 0 };
          if (pygi_garray_from_py (obj, return_ti, GI_TRANSFER_EVERYTHING, &array_arg, &cleanup)
              != 0)
            return -1;
          g_value_take_boxed (value, array_arg.v_pointer);
          return 0;
        }
    }

  GValue converted = G_VALUE_INIT;
  if (pygi_py_to_gvalue_targeted (target, obj, &converted, "signal return") != 0)
    return -1;

  g_value_copy (&converted, value);
  g_value_unset (&converted);
  return 0;
}

static void
pyclosure_marshal (GClosure *closure,
                   GValue *return_value,
                   guint n_param_values,
                   const GValue *param_values,
                   gpointer invocation_hint,
                   gpointer marshal_data)
{
  (void)invocation_hint;
  (void)marshal_data;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  guint n_call_args = n_param_values;
  if (pc->signal_arg_limit >= 0 && (guint)pc->signal_arg_limit < n_call_args)
    n_call_args = (guint)pc->signal_arg_limit;
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *args = PyTuple_New ((Py_ssize_t)n_call_args);
  if (args == NULL)
    {
      PyErr_Clear ();
      PyGILState_Release (state);
      return;
    }
  /* If we have signal introspection for this closure, the first
   * param_value is the instance and the remaining map 1:1 onto the
   * signal's <parameters>. For container-typed args the GValue alone
   * doesn't carry the element type — pygi_gvalue_value_to_py would
   * hand back the bare boxed wrapper. Walking the GISignalInfo gives
   * us the element GITypeInfo and lets us route those args through
   * pygi_argument_to_py for the same marshalling regular method
   * returns get. */
  guint n_signal_args = 0;
  if (pc->signal_info != NULL)
    n_signal_args = gi_callable_info_get_n_args (pc->signal_info);

  for (guint i = 0; i < n_call_args; i++)
    {
      PyObject *p = NULL;
      /* args index in signal info: skip param_values[0] which is the
       * instance. */
      if (pc->signal_info != NULL && i >= 1 && (i - 1) < n_signal_args)
        {
          GIArgInfo *arg_info = gi_callable_info_get_arg (pc->signal_info, (gint)(i - 1));
          if (arg_info != NULL)
            {
              GITypeInfo *ti = gi_arg_info_get_type_info (arg_info);
              GITypeTag tag = ti != NULL ? gi_type_info_get_tag (ti) : GI_TYPE_TAG_VOID;
              if (tag == GI_TYPE_TAG_ARRAY)
                {
                  GIArgument carg;
                  carg.v_pointer = g_value_peek_pointer (&param_values[i]);
                  GITransfer transfer = gi_arg_info_get_ownership_transfer (arg_info);
                  /* For C arrays with a length parameter, extract the length
                   * value from the neighbouring signal param_value so that
                   * pygi_c_array_to_py can determine how many elements to
                   * convert (e.g. GSettings::change-event's keys/n_keys pair). */
                  if (ti != NULL && gi_type_info_get_array_type (ti) == GI_ARRAY_TYPE_C)
                    {
                      guint len_idx_u = 0;
                      gboolean has_len = gi_type_info_get_array_length_index (ti, &len_idx_u);
                      GITypeInfo *len_ti = NULL;
                      GIArgument len_arg = { 0 };
                      if (has_len && len_idx_u < n_signal_args)
                        {
                          GIArgInfo *len_ai
                              = gi_callable_info_get_arg (pc->signal_info, (gint)len_idx_u);
                          if (len_ai != NULL)
                            {
                              len_ti = gi_arg_info_get_type_info (len_ai);
                              guint len_param_i = len_idx_u + 1;
                              if (len_param_i < n_param_values && len_ti != NULL)
                                {
                                  GITypeTag ltag = gi_type_info_get_tag (len_ti);
                                  const GValue *lv = &param_values[len_param_i];
                                  switch (ltag)
                                    {
                                    case GI_TYPE_TAG_INT32:
                                      len_arg.v_int32 = g_value_get_int (lv);
                                      break;
                                    case GI_TYPE_TAG_UINT32:
                                      len_arg.v_uint32 = g_value_get_uint (lv);
                                      break;
                                    case GI_TYPE_TAG_INT64:
                                      len_arg.v_int64 = g_value_get_int64 (lv);
                                      break;
                                    case GI_TYPE_TAG_UINT64:
                                      len_arg.v_uint64 = g_value_get_uint64 (lv);
                                      break;
                                    default:
                                      break;
                                    }
                                }
                              gi_base_info_unref ((GIBaseInfo *)len_ai);
                            }
                        }
                      p = pygi_c_array_to_py (pc->signal_info,
                                              ti,
                                              &carg,
                                              len_ti,
                                              &len_arg,
                                              transfer);
                      if (len_ti != NULL)
                        gi_base_info_unref ((GIBaseInfo *)len_ti);
                    }
                  else
                    {
                      /* GLib.PtrArray / GLib.Array / C array of <T>: route
                       * through the regular argument marshaller. */
                      p = pygi_argument_to_py_transfer (pc->signal_info, ti, &carg, transfer);
                    }
                  if (p == NULL)
                    PyErr_Clear ();
                }
              else if (tag == GI_TYPE_TAG_INTERFACE)
                {
                  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
                  if (iface != NULL
                      && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)
                          || GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)))
                    {
                      GIArgument carg;
                      carg.v_pointer = g_value_peek_pointer (&param_values[i]);
                      GITransfer transfer = gi_arg_info_get_ownership_transfer (arg_info);
                      /* For pointer-to-boxed struct params with transfer=NOTHING,
                       * wrap as a borrowed alias pointing into the GValue memory.
                       * This allows in-place mutation (e.g. TextIter.assign inside
                       * GtkTextBuffer::insert-text) to be seen by the C caller. */
                      if ((GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
                          && transfer == GI_TRANSFER_NOTHING && carg.v_pointer != NULL)
                        {
                          GType iface_gt
                              = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
                          if (iface_gt != G_TYPE_NONE && iface_gt != 0
                              && G_TYPE_IS_BOXED (iface_gt))
                            {
                              PyObject *cls = pygi_class_registry_get_pytype_for_gtype (iface_gt);
                              if (cls != NULL)
                                p = pygi_boxed_new_alias (cls, carg.v_pointer, iface_gt, NULL);
                            }
                        }
                      if (p == NULL)
                        p = pygi_argument_to_py_transfer (pc->signal_info, ti, &carg, transfer);
                    }
                  if (p == NULL)
                    PyErr_Clear ();
                }
              if (ti != NULL)
                gi_base_info_unref ((GIBaseInfo *)ti);
              gi_base_info_unref ((GIBaseInfo *)arg_info);
            }
        }
      if (p == NULL)
        p = pygi_gvalue_value_to_py ((GValue *)&param_values[i]);
      if (p == NULL)
        {
          /* Wrapping failed — clear any pending Python error so the
           * callback below isn't called with a polluted exception state
           * (which would surface as a SystemError from the user code). */
          PyErr_Clear ();
          p = (Py_INCREF (Py_None), Py_None);
        }
      PyTuple_SET_ITEM (args, (Py_ssize_t)i, p);
    }
  /* once=TRUE: disconnect before calling so a re-entrant emit inside
   * the handler doesn't see this closure. g_closure_ref pins the
   * closure across the disconnect (which would otherwise unref the
   * last reference and finalize us mid-marshal). */
  if (pc->once)
    {
      gulong handler_id = pygi_closure_record_handler_id (pc->record);
      if (handler_id != 0 && param_values != NULL && n_param_values >= 1)
        {
          GObject *source = g_value_get_object (&param_values[0]);
          if (source != NULL && g_signal_handler_is_connected (source, handler_id))
            {
              g_closure_ref (closure);
              pygi_closure_record_set_signal_metadata (pc->record, source, 0, NULL);
              g_signal_handler_disconnect (source, handler_id);
              g_closure_unref (closure);
            }
        }
    }
  pygi_closure_record_invoke_begin (pc->record);
  PyObject *result = NULL;
  PyObject *call_with_owner = NULL;
  if (PyObject_GetOptionalAttrString (pc->callable,
                                      "__pygi_call_with_owner__",
                                      &call_with_owner)
      < 0)
    result = NULL;
  else if (call_with_owner == NULL)
    {
      result = PyObject_CallObject (pc->callable, args);
    }
  else
    {
      GObject *owner = pygi_closure_record_owner (pc->record);
      if (owner == NULL || !G_IS_OBJECT (owner))
        result = PyObject_CallObject (pc->callable, args);
      else
        {
          PyObject *owner_obj = pygi_gobject_to_py (owner, GI_TRANSFER_NOTHING);
          if (owner_obj != NULL)
            {
              Py_ssize_t n = PyTuple_GET_SIZE (args);
              PyObject *owner_args = PyTuple_New (n + 1);
              if (owner_args != NULL)
                {
                  PyTuple_SET_ITEM (owner_args, 0, owner_obj);
                  for (Py_ssize_t i = 0; i < n; i++)
                    {
                      PyObject *item = PyTuple_GET_ITEM (args, i);
                      Py_INCREF (item);
                      PyTuple_SET_ITEM (owner_args, i + 1, item);
                    }
                  result = PyObject_CallObject (call_with_owner, owner_args);
                  Py_DECREF (owner_args);
                }
              else
                Py_DECREF (owner_obj);
            }
        }
      Py_DECREF (call_with_owner);
    }
  pygi_closure_record_invoke_end (pc->record);
  /* Copy-on-retain: transfer-none boxed args were wrapped as aliases into the
   * GValue memory (freed when this emission returns). If the handler kept one
   * past its own scope (refcount above the single reference the args tuple
   * holds), promote it to an owned copy now, while the source is still valid, so
   * it does not dangle. Non-retained aliases stay borrowed and free with the
   * tuple. */
  Py_ssize_t arg_count = PyTuple_GET_SIZE (args);
  for (Py_ssize_t i = 0; i < arg_count; i++)
    {
      PyObject *arg = PyTuple_GET_ITEM (args, i);
      if (arg != NULL && Py_REFCNT (arg) > 1)
        pygi_boxed_promote_borrowed_alias (arg);
    }
  Py_DECREF (args);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return;
    }
  if (return_value != NULL && py_to_existing_gvalue (result, return_value, pc->signal_info) != 0)
    PyErr_Print ();
  Py_DECREF (result);
  PyGILState_Release (state);
}

static void
pyclosure_finalize (gpointer data, GClosure *closure)
{
  (void)data;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  PyGILState_STATE state = PyGILState_Ensure ();
  pygi_closure_record_set_state (pc->record, PYGI_CLOSURE_STATE_FINALIZED);
  pygi_closure_record_free (pc->record);
  pc->record = NULL;
  Py_CLEAR (pc->callable);
  if (pc->signal_info != NULL)
    {
      gi_base_info_unref ((GIBaseInfo *)pc->signal_info);
      pc->signal_info = NULL;
    }
  PyGILState_Release (state);
}

static GClosure *
pygi_closure_new_full_with_kind (PyObject *callable,
                                 PyObject *user_callable,
                                 GICallableInfo *signal_info,
                                 GObject *weak_target,
                                 PyGIClosureRecordKind kind)
{
  GClosure *closure = g_closure_new_simple (sizeof (PyGIPyClosure), NULL);
  if (closure == NULL)
    return NULL;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  Py_INCREF (callable);
  pc->callable = callable;
  PyObject *effective_user_callable = user_callable;
  PyObject *declared_user_callable = PyObject_GetAttrString (callable, "__pygi_user_callable__");
  if (declared_user_callable != NULL)
    effective_user_callable = declared_user_callable;
  else
    PyErr_Clear ();
  pc->record = pygi_closure_record_new (kind, callable, effective_user_callable);
  Py_XDECREF (declared_user_callable);
  pygi_closure_record_set_signal_metadata (pc->record, NULL, 0, weak_target);
  pc->signal_info
      = signal_info != NULL ? (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)signal_info) : NULL;
  pc->signal_arg_limit = -1;
  g_closure_set_marshal (closure, pyclosure_marshal);
  g_closure_add_finalize_notifier (closure, NULL, pyclosure_finalize);
  return closure;
}

GClosure *
pygi_closure_new_for_signal_full (PyObject *callable,
                                  PyObject *user_callable,
                                  GICallableInfo *signal_info,
                                  GObject *weak_target)
{
  return pygi_closure_new_full_with_kind (callable,
                                          user_callable,
                                          signal_info,
                                          weak_target,
                                          PYGI_CLOSURE_RECORD_SIGNAL);
}

GClosure *
pygi_closure_new_for_signal (PyObject *callable, GICallableInfo *signal_info)
{
  return pygi_closure_new_for_signal_full (callable, callable, signal_info, NULL);
}

GClosure *
pygi_closure_new (PyObject *callable)
{
  return pygi_closure_new_for_signal (callable, NULL);
}

GClosure *
pygi_closure_new_with_kind (PyObject *callable, PyGIClosureRecordKind kind)
{
  return pygi_closure_new_full_with_kind (callable, callable, NULL, NULL, kind);
}

void
pygi_closure_set_once (GClosure *closure, gboolean once)
{
  if (closure == NULL)
    return;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  pc->once = once ? TRUE : FALSE;
}

void
pygi_closure_set_signal_arg_limit (GClosure *closure, int signal_arg_limit)
{
  if (closure == NULL)
    return;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  pc->signal_arg_limit = signal_arg_limit >= 0 ? signal_arg_limit : -1;
}

void
pygi_closure_set_signal_metadata (GClosure *closure,
                                  GObject *source,
                                  gulong handler_id,
                                  GObject *weak_target)
{
  if (closure == NULL)
    return;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  pygi_closure_record_set_signal_metadata (pc->record, source, handler_id, weak_target);
}

void *
pygi_closure_get_record (GClosure *closure)
{
  if (closure == NULL)
    return NULL;
  PyGIPyClosure *pc = (PyGIPyClosure *)closure;
  return pc->record;
}

guint
pygi_closure_disconnect_by_callable (GObject *instance, PyObject *callable)
{
  return pygi_closure_records_disconnect_by_user_callable (instance, callable);
}
